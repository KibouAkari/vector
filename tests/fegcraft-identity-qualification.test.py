import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import io
from contextlib import redirect_stdout
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('identity_qualification', ROOT / 'scripts/deploy/qualify-fegcraft-identity.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Qualification(unittest.TestCase):
    def test_orchestration_rejects_changed_production_and_unqualified_capture(self):
        for case in ('success', 'container', 'compose', 'marker', 'manifest', 'directory', 'failed', 'revision', 'discord', 'dialogue'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                data = root / 'game/data'
                (root / 'releases').mkdir()
                (data / 'config').mkdir(parents=True)
                (data / 'DiscordIntegration-Data/vector').mkdir(parents=True)
                (data / 'config/Discord-Integration.toml').write_text('[webhook]\nenable=true\n')
                marker = data / 'DiscordIntegration-Data/vector/introduction-v1.attempted'
                marker.write_text('synthetic marker')
                compose = data.parent / 'docker-compose.yml'
                compose.write_text('synthetic game profile')
                activated = [False]
                calls = []
                def run(*args, **kwargs):
                    calls.append(args)
                    if args[0] == 'nginx':
                        return b'# configuration file /etc/nginx/sites-enabled/vector:\nserver_name vector.kibouakari.com;\n'
                    return json.dumps([{'State': {'Health': {'Status': 'healthy'}}}]).encode()
                def installation(value):
                    return (root / ('foreign' if activated[0] and case == 'directory' else 'installed'),
                            {'files': {'owned': 'changed' if activated[0] and case == 'manifest' else 'original'}})
                def evaluate():
                    capture = root / 'releases/vector-fegcraft-bridge-evaluation-synthetic'
                    capture.mkdir()
                    (capture / 'result.json').write_text(json.dumps({'passed': case != 'failed', 'revision': 'b' * 40 if case == 'revision' else 'a' * 40,
                        'statistics_dialogue_tests_passed': case != 'dialogue',
                        'discord_channel_bot_replay_and_block_registry_passed': case != 'discord'}))
                    activated[0] = True
                    if case == 'compose':
                        compose.write_text('changed')
                    if case == 'marker':
                        marker.write_text('changed')
                def load(path, name):
                    if name == 'identity_installation':
                        return SimpleNamespace(installation=installation)
                    if name == 'identity_bridge_evaluation':
                        return SimpleNamespace(main=evaluate)
                    return SimpleNamespace(write=lambda output: {'resource_format': [88, 0]})
                original_digest = module.digest
                def digest(path):
                    return 'synthetic-app-profile' if str(path) == '/opt/vector/docker-compose.yml' else original_digest(path)
                with patch.multiple(module, ROOT=root, REPO=root / 'repo', DATA=data), \
                        patch.dict(module.os.environ, {'VECTOR_FEGCRAFT_REV': 'a' * 40}), \
                        patch.object(module.os, 'geteuid', return_value=0), \
                        patch.object(module, 'run', side_effect=run), \
                        patch.object(module, 'export'), patch.object(module, 'module', side_effect=load), \
                        patch.object(module, 'resource_version', return_value=[88, 0]), \
                        patch.object(module, 'identities', side_effect=lambda: {'id': 'changed' if activated[0] and case == 'container' else 'original'}), \
                        patch.object(module, 'digest', side_effect=digest), redirect_stdout(io.StringIO()):
                    if case == 'success':
                        module.main()
                    else:
                        with self.assertRaises(RuntimeError):
                            module.main()
                reports = list((root / 'releases').glob('vector-fegcraft-identity-qualification-*/result.json'))
                self.assertEqual(len(reports), 1 if case == 'success' else 0)
                self.assertFalse(any('restart' in args or 'mc-send-to-console' in args for args in calls))

    def test_site_hint_exact_domain_and_no_configuration_values(self):
        dump = '''# configuration file /etc/nginx/nginx.conf:
http { include /etc/nginx/sites-enabled/*; }
# configuration file /etc/nginx/sites-enabled/vector:
server {
    server_name vector.kibouakari.com;
    ssl_certificate_key /private/synthetic.key;
}
# configuration file /etc/nginx/sites-enabled/other:
server {
    server_name vector.kibouakari.com.example.invalid;
}
'''
        self.assertEqual(module.site_candidates(dump), ['/etc/nginx/sites-enabled/vector'])
        with self.assertRaisesRegex(RuntimeError, 'SITE_PATH'):
            module.site_candidates(dump.replace('/etc/nginx/sites-enabled/vector:', '/tmp/foreign.conf:'))

    def test_exact_installed_version_and_immutable_game_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'server.jar'
            def write(version):
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr('version.json', json.dumps(version))
                return hashlib.sha256(path.read_bytes()).hexdigest()
            sha = write({'id': '26.2', 'pack_version': {'resource_major': 88, 'resource_minor': 0}})
            with patch.object(module, 'GAME_SHA', sha):
                self.assertEqual(module.resource_version(path), [88, 0])
                path.write_bytes(path.read_bytes() + b'changed')
                with self.assertRaisesRegex(RuntimeError, 'GAME_JAR_CHANGED'):
                    module.resource_version(path)
            sha = write({'id': '26.3', 'pack_version': {'resource_major': 88, 'resource_minor': 0}})
            with patch.object(module, 'GAME_SHA', sha):
                with self.assertRaisesRegex(RuntimeError, 'RESOURCE_FORMAT'):
                    module.resource_version(path)

    def test_duplicate_version_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'version.json'
            path.write_bytes(b'{}')
            link = Path(temp) / 'link'
            link.symlink_to(path)
            with self.assertRaisesRegex(RuntimeError, 'SYMLINK'):
                module.read(link)
            with self.assertRaisesRegex(RuntimeError, 'INPUT_FILE'):
                module.read(path, limit=1)


if __name__ == '__main__':
    unittest.main()
