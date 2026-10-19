"""Pure guards for a code-only assistant rollout. No Docker or production actions."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('updater', ROOT / 'scripts/deploy/update-minecraft-ranking-runtime.py')
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class Guards(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_private_joke_is_preserved_without_reformatting_other_source(self):
        old = "def old():\n    return 'Example captain natürlich. Völlig unvoreingenommene Vector-Meinung.'\n"
        new = "# generic\ndef new():\n    return 'Du natürlich. Völlig unvoreingenommene Vector-Meinung.'\n\nANSWER = 42\n"
        expected = new.replace('Du natürlich.', 'Example captain natürlich.')
        self.assertEqual(updater.preserve_joke(old, new).decode(), expected)
        for invalid in ('def f(): return 1', old + old.replace('old()', 'other()')):
            with self.assertRaisesRegex(RuntimeError, 'UNIQUE_PRIVATE_JOKE_REQUIRED'):
                updater.preserve_joke(invalid, new)

    def test_only_readonly_code_bind_source_changes(self):
        old = self.root / 'old'
        old.mkdir()
        profile = {'name': 'synthetic', 'services': {'assistant': {'environment': {'MODE': '5'},
            'image': 'sha256:' + 'a' * 64, 'volumes': [
                {'type': 'bind', 'source': str(old), 'target': '/code', 'read_only': True},
                {'type': 'bind', 'source': '/operator/state', 'target': '/state'}]}}, 'networks': {'private': {}}}
        candidate = updater.changed_profile(profile, 'assistant', self.root / 'new')
        self.assertEqual(profile['services']['assistant']['volumes'][0]['source'], str(old))
        candidate['services']['assistant']['volumes'][0]['source'] = str(old)
        self.assertEqual(candidate, profile)
        for altered in (dict(profile, services=dict(profile['services'], other={})),
                        dict(profile, services={'assistant': {'volumes': []}})):
            with self.assertRaises(RuntimeError):
                updater.code_source(altered, 'assistant')

    def test_atomic_compose_replacement_preserves_owner_and_permissions(self):
        path = self.root / 'compose.yml'
        path.write_bytes(b'original')
        path.chmod(0o640)
        before = path.stat()
        updater.replace_atomic(path, b'candidate')
        after = path.stat()
        self.assertEqual(path.read_bytes(), b'candidate')
        self.assertEqual((before.st_uid, before.st_gid, before.st_mode), (after.st_uid, after.st_gid, after.st_mode))

    def test_snapshot_ignores_counters_but_detects_restart_and_image_changes(self):
        row = {'Id': 'same', 'Image': 'image', 'State': {'StartedAt': 'one', 'Health': {'Status': 'healthy'}}}
        changed = dict(row, State=dict(row['State'], Health={'Status': 'starting'}))
        self.assertEqual(updater.identity(row), updater.identity(changed))
        changed['State']['StartedAt'] = 'two'
        self.assertNotEqual(updater.identity(row), updater.identity(changed))

    def test_code_tree_refuses_links_and_keeps_all_non_runtime_files(self):
        (self.root / 'runtime.py').write_text('pass')
        (self.root / 'state.py').write_text('ANSWER = 1')
        before = updater.tree_files(self.root)
        self.assertEqual(set(before), {'runtime.py', 'state.py'})
        (self.root / 'secret-link').symlink_to('/outside')
        with self.assertRaisesRegex(RuntimeError, 'UNSUPPORTED_CODE_TREE'):
            updater.tree_files(self.root)

    def test_live_profile_must_match_container_compose_hash_and_readonly_bind(self):
        code = self.root / 'code'
        code.mkdir()
        (code / 'runtime.py').write_text('pass')
        compose = self.root / 'compose.json'
        compose.write_text('{}')
        profile = {'name': 'synthetic', 'services': {'assistant': {'volumes': [dict(type='bind', source=str(code), target='/code', read_only=True)]}}}
        config = dict(container='assistant', service='assistant', compose=str(compose), project_directory=str(self.root),
            expected_image='sha256:' + 'a' * 64, expected_runtime_sha256=updater.digest(b'pass'),
            expected_profile_sha256=updater.digest(updater.canonical(profile)))
        row = dict(Image=config['expected_image'], State=dict(Running=True, Health=dict(Status='healthy')),
            Config=dict(Labels={'com.docker.compose.service': 'assistant', 'com.docker.compose.project.config_files': str(compose),
                               'com.docker.compose.config-hash': 'b' * 64, 'com.docker.compose.project': 'synthetic',
                               'com.docker.compose.project.working_dir': str(self.root)}),
            Mounts=[dict(Destination='/code', Source=str(code), RW=False)])
        with patch.object(updater, 'run', return_value=('assistant ' + 'b' * 64).encode()):
            self.assertEqual(updater.validate_live(config, {'assistant': row}, profile), code)
            row['Mounts'][0]['RW'] = True
            with self.assertRaisesRegex(RuntimeError, 'LIVE_CODE_BIND_MISMATCH'):
                updater.validate_live(config, {'assistant': row}, profile)
            row['Mounts'][0]['RW'] = False
        with patch.object(updater, 'run', return_value=('assistant ' + 'c' * 64).encode()):
            with self.assertRaisesRegex(RuntimeError, 'RUNNING_SERVICE_PROFILE_DRIFT'):
                updater.validate_live(config, {'assistant': row}, profile)

    def test_private_config_requires_complete_pins_and_owner_only_permissions(self):
        compose = self.root / 'compose.json'
        compose.write_text('{}')
        value = dict(schema=1, container='assistant', service='assistant', compose=str(compose),
            project_directory=str(self.root), expected_image='sha256:' + 'a' * 64,
            expected_runtime_sha256='b' * 64, expected_compose_sha256='c' * 64, expected_profile_sha256='d' * 64)
        config = self.root / 'operator.json'
        config.write_text(json.dumps(value))
        config.chmod(0o600)
        self.assertEqual(updater.read_config(config), value)
        config.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, 'PRIVATE_CONFIG_REQUIRED'):
            updater.read_config(config)
        config.chmod(0o600)
        config.write_text(json.dumps(dict(value, extra='not permitted')))
        with self.assertRaisesRegex(RuntimeError, 'UNSUPPORTED_OPERATOR_CONFIG'):
            updater.read_config(config)


if __name__ == '__main__':
    unittest.main()
