"""Scoped compose edits, private preservation and recovery of a stopped game."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


installer = load('scripts/deploy/install-fegcraft-chat-identity.py', 'identity_installer')
layer = load('scripts/lib/fegcraft-root-preservation.py', 'private_root_layer')
old = load('scripts/deploy/release-fegcraft-dialogue.py', 'identity_pure_helpers')


class Guards(unittest.TestCase):
    def test_unhealthy_or_absent_game_does_not_prevent_other_service_protection(self):
        records = [{'Name': '/vector-app', 'Id': 'app', 'Image': 'fixture-image', 'Config': {'Env': ['SYNTHETIC=one']},
                    'HostConfig': {}, 'Mounts': [], 'NetworkSettings': {'Networks': {'private': {}}},
                    'State': {'Running': True, 'StartedAt': 'fixture-time'}}]
        p = SimpleNamespace(run=Mock(side_effect=lambda *args: json.dumps(records).encode()),
                            INSTALL=Path('/synthetic-install'), read=lambda path: b'synthetic config',
                            sha=lambda value: hashlib.sha256(value).hexdigest())
        h = SimpleNamespace(NAMES=('fegcraft-updated', 'vector-app'), sha=p.sha, ADDON=Path('/synthetic-addon.jar'),
                            canonical_mounts=lambda value: sorted(value, key=lambda row: json.dumps(row, sort_keys=True)))
        baseline = installer.protected_live(p, h, {})
        p.run.assert_called_once_with('docker', 'inspect', 'vector-app')
        self.assertIn('/vector-app', baseline)
        self.assertNotIn('/fegcraft-updated', baseline)
        records[0]['Config']['Env'] = ['SYNTHETIC=changed']
        self.assertNotEqual(baseline, installer.protected_live(p, h, {}))

    def test_compose_patch_retains_game_settings_and_pins_both_versions(self):
        for env in ('      VERSION: "26.2"\n      TYPE: FABRIC\n', '      - VERSION=26.2\n      - TYPE=FABRIC\n'):
            raw = ('services:\n  mc:\n    image: current\n    environment:\n' + env
                   + '    volumes:\n      - ./data:/data\n  unrelated:\n    image: untouched\n').encode()
            updated = installer.patch_loader(old.patch_compose(raw, 'mc', 'sha256:' + 'a' * 64), 'mc')
            text = updated.decode()
            for value in ('FABRIC_LOADER_VERSION', '0.19.5', 'FABRIC_LAUNCHER_VERSION', '1.1.2', './data:/data', 'image: untouched'):
                self.assertIn(value, text)
            rollback = installer.patch_loader(installer.image_only(raw, 'mc', 'sha256:' + 'a' * 64), 'mc')
            self.assertNotIn('RESOURCE_PACK', rollback.decode())
        before = {'services': {'mc': {'image': 'old', 'environment': {'VERSION': '26.2'}, 'volumes': ['same']}}}
        after = copy.deepcopy(before)
        after['services']['mc'].update(image='new')
        after['services']['mc']['environment'].update(old.PACK_ENV, FABRIC_LOADER_VERSION='0.19.5', FABRIC_LAUNCHER_VERSION='1.1.2')
        installer.validate_profile(before, after, 'mc', 'new', True, old)
        after['services']['mc']['volumes'] = ['other']
        with self.assertRaises(RuntimeError): installer.validate_profile(before, after, 'mc', 'new', True, old)

    def test_bridge_enables_only_known_hook_logo_and_once_welcome(self):
        raw = b'enabled=true\nintroductionEnabled=false\ntokenFile=/data/DiscordIntegration-Data/vector/token\navatarUrl=\n'
        value = old.properties(installer.bridge_settings(old, raw))
        self.assertEqual(value['discordInputEnabled'], 'true')
        self.assertEqual(value['introductionEnabled'], 'false')
        self.assertEqual(value['ownerWelcomeEnabled'], 'true')
        self.assertEqual(value['tokenFile'], '/data/DiscordIntegration-Data/vector/token')
        with self.assertRaises(RuntimeError): installer.bridge_settings(old, raw + b'unknown=value\n')

    def test_failed_file_restoration_still_recovers_same_original_game(self):
        helper = SimpleNamespace(write_records=Mock(side_effect=RuntimeError('CHANGED')), save=Mock())
        engine = SimpleNamespace(restart=Mock(), ready=Mock())
        game = {'Id': 'original'}
        with self.assertRaises(RuntimeError):
            installer.recover_original(SimpleNamespace(), helper, engine, game, Path('/private'), {}, True)
        engine.restart.assert_called_once_with(game, wait_for_stop=True)
        engine.ready.assert_called_once_with(game)

    def test_running_or_unclean_game_is_never_committed(self):
        for state in ({'Running': True}, {'Running': False, 'ExitCode': 137},
                      {'Running': False, 'ExitCode': 0, 'OOMKilled': True}):
            with self.assertRaises(RuntimeError): layer.stopped({'State': state})
        layer.stopped({'State': {'Running': False, 'ExitCode': 0}})
        for path in ('/data', '/data/world', '/', '../private', '/tmp/../data', None):
            with self.assertRaises(RuntimeError): layer.allowed_path(path)

    def test_archive_comparison_detects_content_and_permission_loss_without_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def write(name, body=b'synthetic', mode=0o600, member_name='private-fixture'):
                path = root / name
                with tarfile.open(path, 'w') as archive:
                    info = tarfile.TarInfo(member_name); info.size = len(body); info.mode = mode
                    archive.addfile(info, io.BytesIO(body))
                return path
            baseline = layer.archive_fingerprint(write('before.tar'))
            self.assertEqual(baseline, layer.archive_fingerprint(write('same.tar')))
            self.assertNotEqual(baseline, layer.archive_fingerprint(write('content.tar', b'other')))
            self.assertNotEqual(baseline, layer.archive_fingerprint(write('mode.tar', mode=0o644)))
            with self.assertRaises(RuntimeError): layer.archive_fingerprint(write('unsafe.tar', member_name='../escape'))

    def test_image_keeps_configuration_and_parent_layers(self):
        config = {'Env': ['SYNTHETIC=fixture'], 'Entrypoint': ['/not-executed'], 'Labels': {'fixture': 'owned'}, 'Volumes': {'/data': {}}}
        game = {'Config': config}
        parent = {'Os': 'linux', 'Architecture': 'amd64', 'RootFS': {'Layers': ['parent']}, 'Size': 50}
        image = copy.deepcopy(parent)
        image.update(Config=copy.deepcopy(config), RootFS={'Layers': ['parent', 'private']}, Size=100)
        image['Config']['Labels'][layer.LABEL] = 'owner'
        layer.validate_image(game, parent, image, 'owner')
        image['Config']['Env'] = ['DIFFERENT=fixture']
        with self.assertRaises(RuntimeError): layer.validate_image(game, parent, image, 'owner')
        image['Config']['Env'] = config['Env']; image['RootFS']['Layers'] = ['other-parent', 'private']
        with self.assertRaises(RuntimeError): layer.validate_image(game, parent, image, 'owner')


@unittest.skipUnless(os.environ.get('VECTOR_ROOT_PRESERVATION_DOCKER') == '1', 'Actual Docker proof runs in CI')
class DockerProof(unittest.TestCase):
    def test_private_changed_root_file_survives_and_mounted_world_is_excluded(self):
        owner = secrets.token_hex(6)
        tag = 'vector-root-synthetic:' + owner
        created = None
        preserved = None
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); context = root / 'build'; context.mkdir()
            (context / 'baseline').write_text('baseline')
            (context / 'Dockerfile').write_text('FROM scratch\nCOPY baseline /private-fixture\nVOLUME /data\nENV SYNTHETIC=fixture\nENTRYPOINT ["/never-executed"]\n')
            world = root / 'world'; world.mkdir(); (world / 'synthetic-world').write_text('not in image')
            (root / 'changed').write_text('changed private synthetic fixture')
            try:
                layer.run('docker', 'build', '--network=none', '--label', layer.LABEL + '=' + owner,
                          '-t', tag, str(context), timeout=90)
                created = layer.run('docker', 'create', '--network', 'none', '--label', layer.LABEL + '=' + owner,
                                    '--mount', 'type=bind,src=' + str(world) + ',dst=/data', tag).decode().strip()
                layer.run('docker', 'cp', str(root / 'changed'), created + ':/private-fixture')
                proof = root / 'proof'; proof.mkdir()
                preserved = layer.preserve(created, [{'change': 'C', 'path': '/private-fixture'}], proof, owner)
                self.assertTrue(preserved['archived_metadata_and_content_verified'])
                self.assertFalse(preserved['mounted_world_included'])
                self.assertEqual((world / 'synthetic-world').read_text(), 'not in image')
                # Never start either fixture. Verify exclusion through a fresh stopped image container.
                probe = layer.run('docker', 'create', '--network', 'none', '--mount', 'type=tmpfs,destination=/data',
                                  '--entrypoint', '/never-executed', preserved['image']).decode().strip()
                try:
                    copied = subprocess.run(['docker', 'cp', probe + ':/data/synthetic-world', '-'], capture_output=True)
                    self.assertNotEqual(copied.returncode, 0)
                finally:
                    layer.run('docker', 'rm', probe)
            finally:
                if created:
                    value = layer.inspect('container', created)
                    self.assertFalse(value['State']['Running'])
                    self.assertEqual(value['Config']['Labels'][layer.LABEL], owner)
                    layer.run('docker', 'rm', created)
                for image in ([preserved['image']] if preserved else []) + [tag]:
                    value = layer.inspect('image', image)
                    self.assertEqual(value['Config']['Labels'][layer.LABEL], owner)
                    layer.run('docker', 'image', 'rm', image)


if __name__ == '__main__':
    unittest.main()
