"""Pure guards for a code-only assistant rollout. No Docker or production actions."""
import importlib.util
import json
import subprocess
import sys
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

    def test_command_failure_reports_phase_but_keeps_stderr_private(self):
        from types import SimpleNamespace
        evidence=self.root/'evidence';evidence.mkdir(mode=0o700)
        with patch.object(updater,'COMMAND_EVIDENCE',evidence), patch.object(updater,'COMMAND_INDEX',0), \
             patch.object(updater.subprocess,'run',return_value=SimpleNamespace(returncode=1,stderr=b'synthetic_private_value')):
            with self.assertRaisesRegex(RuntimeError,'isolated-qualification') as raised:
                updater.run(['docker','run','synthetic'])
            self.assertNotIn('synthetic_private_value',str(raised.exception))
        self.assertEqual((evidence/'1-isolated-qualification.stderr').read_bytes(),b'synthetic_private_value')
        self.assertEqual((evidence/'1-isolated-qualification.stderr').stat().st_mode & 0o777,0o600)

    def test_missing_release_lock_does_not_create_a_parallel_lock(self):
        lock = self.root / 'mistyped.lock'
        result = subprocess.run([sys.executable, spec.origin, '--release-root', str(self.root),
            '--lock-file', str(lock)], capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(lock.exists())

    def test_private_joke_is_preserved_without_reformatting_other_source(self):
        old = "def old():\n    return 'Example captain natürlich. Völlig unvoreingenommene Vector-Meinung.'\n"
        new = "# generic\ndef new():\n    return 'Du natürlich. Völlig unvoreingenommene Vector-Meinung.'\n\nANSWER = 42\n"
        expected = new.replace('Du natürlich.', 'Example captain natürlich.')
        self.assertEqual(updater.preserve_joke(old, new).decode(), expected)
        for invalid in ('def f(): return 1', old + old.replace('old()', 'other()')):
            with self.assertRaisesRegex(RuntimeError, 'UNIQUE_PRIVATE_JOKE_REQUIRED'):
                updater.preserve_joke(invalid, new)

    def test_three_operator_alias_guards_are_preserved_without_other_literal_changes(self):
        generic = (ROOT / 'services/minecraft-assistant/runtime.py').read_text()
        patterns = (
            r'(?:server|minecraft)(?:\b|$)',
            r'\b(?:ich|von mir|für mich|fuer mich|mein(?:e[rmns]?)?|my)\b(?!\s+(?:server|minecraft))',
            r'\bserver\b|minecraft|\binsgesamt\b|\bschon\b|\bbisher\b',
        )
        installed = generic
        expected = generic
        for pattern in patterns:
            self.assertEqual(generic.count(pattern), 1)
            installed = installed.replace(pattern, pattern.replace('minecraft', 'ExampleRealm'))
            # The candidate is unchanged outside these literal source ranges.
            expected = expected.replace("r'" + pattern + "'", repr(pattern.replace('minecraft', 'ExampleRealm')))
        self.assertEqual(updater.preserve_server_literals(installed, generic), expected)
        self.assertIn("model='vector-qwen3:1.7b-q8'", expected)
        for incomplete in (installed.replace(patterns[0].replace('minecraft', 'ExampleRealm'), 'no alias'),
                           installed + "\ndef unknown_player_target(): pass\n"):
            with self.assertRaisesRegex(RuntimeError, 'UNIQUE_OPERATOR_ROUTING'):
                updater.preserve_server_literals(incomplete, generic)

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
        config = dict(expected_project_name='synthetic', container='assistant', service='assistant', compose=str(compose), project_directory=str(self.root),
            expected_image='sha256:' + 'a' * 64, expected_runtime_sha256=updater.digest(b'pass'),
            expected_profile_sha256=updater.digest(updater.canonical(profile)))
        row = dict(Image=config['expected_image'], State=dict(Running=True, Health=dict(Status='healthy')),
            Config=dict(Labels={'com.docker.compose.service': 'assistant', 'com.docker.compose.project.config_files': str(compose),
                               'com.docker.compose.config-hash': 'b' * 64, 'com.docker.compose.project': 'synthetic',
                               'com.docker.compose.project.working_dir': str(self.root)}),
            Mounts=[dict(Destination='/code', Source=str(code), RW=False)])
        with patch.object(updater, 'run', return_value=('assistant ' + 'b' * 64).encode()) as command:
            foreign = json.loads(json.dumps(row))
            foreign['Config']['Labels']['com.docker.compose.project'] = 'foreign'
            with self.assertRaisesRegex(RuntimeError, 'COMPOSE_PROJECT_IDENTITY_MISMATCH'):
                updater.validate_live(config, {'assistant': foreign}, profile)
            self.assertEqual(updater.validate_live(config, {'assistant': row}, profile), code)
            self.assertEqual(command.call_args.args[0][:4], ['docker', 'compose', '--project-name', 'synthetic'])
            row['Mounts'][0]['RW'] = True
            with self.assertRaisesRegex(RuntimeError, 'LIVE_CODE_BIND_MISMATCH'):
                updater.validate_live(config, {'assistant': row}, profile)
            row['Mounts'][0]['RW'] = False
        with patch.object(updater, 'run', return_value=('assistant ' + 'c' * 64).encode()):
            with self.assertRaisesRegex(RuntimeError, 'RUNNING_SERVICE_PROFILE_DRIFT'):
                updater.validate_live(config, {'assistant': row}, profile)

    def rollback_fixture(self):
        original_code = self.root / 'original-code'
        candidate_code = self.root / 'candidate-code'
        original_code.mkdir()
        candidate_code.mkdir()
        (original_code / 'runtime.py').write_text('original')
        (candidate_code / 'runtime.py').write_text('candidate')
        active = self.root / 'active.yml'
        active.write_bytes(b'candidate')
        release = self.root / 'release'
        release.mkdir()
        (release / 'compose.original').write_bytes(b'original')
        profile = {'name': 'synthetic', 'services': {'assistant': {'image': 'synthetic-image'}}}
        config = dict(expected_project_name='synthetic', schema=1, container='assistant', service='assistant', compose=str(active), project_directory=str(self.root),
            expected_image='sha256:' + 'a' * 64, expected_runtime_sha256=updater.digest(b'original'),
            expected_compose_sha256=updater.digest(b'original'), expected_profile_sha256=updater.digest(updater.canonical(profile)))
        updater.write_private(release / 'operator.json', updater.canonical(config))
        def row(generation, source):
            return dict(Id=generation, Image=config['expected_image'], State=dict(StartedAt=generation),
                        Mounts=[dict(Destination='/code', Source=str(source), RW=False)])
        original = row('original', original_code)
        candidate = row('candidate', candidate_code)
        restored = row('restored', original_code)
        record = dict(candidate_compose_sha256=updater.digest(b'candidate'), original_code=str(original_code), candidate_code=str(candidate_code),
            original_files=updater.tree_files(original_code), candidate_files=updater.tree_files(candidate_code), other_containers={},
            original_identity=updater.identity(original), deployed_identity=updater.identity(candidate))
        updater.write_private(release / 'record.json', updater.canonical(record))
        return release, active, profile, candidate, restored

    def test_rollback_resolved_profile_or_image_drift_cannot_consume_precondition(self):
        release, active, profile, candidate, restored = self.rollback_fixture()
        with patch.object(updater, 'compose', return_value=dict(profile, changed='environment')):
            with self.assertRaisesRegex(RuntimeError, 'ORIGINAL_RESOLVED_PROFILE_DRIFT'):
                updater.rollback(release)
        self.assertEqual(active.read_bytes(), b'candidate')
        self.assertFalse((release / 'rollback.progress.json').exists())
        with patch.object(updater, 'compose', return_value=profile), patch.object(updater, 'verify_image', side_effect=RuntimeError('IMAGE_TAG_DRIFT')):
            with self.assertRaisesRegex(RuntimeError, 'IMAGE_TAG_DRIFT'):
                updater.rollback(release)
        self.assertEqual(active.read_bytes(), b'candidate')
        self.assertFalse((release / 'rollback.progress.json').exists())

    def test_failed_recreate_has_owned_resume_and_rejects_foreign_generation(self):
        release, active, profile, candidate, restored = self.rollback_fixture()
        with patch.object(updater, 'compose', return_value=profile), patch.object(updater, 'verify_image'), patch.object(updater, 'inventory', return_value={'assistant': candidate}), patch.object(updater, 'recreate', side_effect=RuntimeError('synthetic failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
                updater.rollback(release)
        self.assertEqual(active.read_bytes(), b'original')
        marker = json.loads((release / 'rollback.progress.json').read_bytes())
        self.assertEqual(marker['phase'], 'failed')
        self.assertEqual(marker['generation'], list(updater.identity(candidate)))
        with patch.object(updater, 'compose', return_value=profile), patch.object(updater, 'verify_image'), patch.object(updater, 'inventory', return_value={'assistant': restored}), patch.object(updater, 'recreate') as recreate:
            with self.assertRaisesRegex(RuntimeError, 'RESUME_GENERATION_OR_COMPOSE_DRIFT'):
                updater.rollback(release)
            recreate.assert_not_called()
        with patch.object(updater, 'compose', return_value=profile), patch.object(updater, 'verify_image'), patch.object(updater, 'inventory', side_effect=[{'assistant': candidate}, {'assistant': restored}]), patch.object(updater, 'recreate'), patch.object(updater, 'await_health'):
            updater.rollback(release)
        self.assertEqual(json.loads((release / 'rollback.progress.json').read_bytes())['phase'], 'verified')

    def test_failed_health_records_new_owned_generation_for_resume(self):
        release, active, profile, candidate, restored = self.rollback_fixture()
        with patch.object(updater, 'compose', return_value=profile), patch.object(updater, 'verify_image'), patch.object(updater, 'inventory', side_effect=[{'assistant': candidate}, {'assistant': restored}]), patch.object(updater, 'recreate'), patch.object(updater, 'await_health', side_effect=RuntimeError('synthetic health failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic health failure'):
                updater.rollback(release)
        marker = json.loads((release / 'rollback.progress.json').read_bytes())
        self.assertEqual(marker['phase'], 'failed')
        self.assertEqual(marker['generation'], list(updater.identity(restored)))
        with patch.object(updater, 'compose', return_value=profile), patch.object(updater, 'verify_image'), patch.object(updater, 'inventory', return_value={'assistant': restored}), patch.object(updater, 'recreate'), patch.object(updater, 'await_health'):
            updater.rollback(release)
        self.assertEqual(json.loads((release / 'rollback.progress.json').read_bytes())['phase'], 'verified')

    def test_explicit_project_is_used_for_render_recreate_and_rollback_render(self):
        config = dict(expected_project_name='synthetic', project_directory='/operator', compose='/operator/current.yml', service='assistant')
        with patch.object(updater, 'run', return_value=b'{}') as command:
            updater.compose(config, '/release/compose.original')
            self.assertEqual(command.call_args.args[0], ['docker', 'compose', '--project-name', 'synthetic',
                '--project-directory', '/operator', '-f', '/release/compose.original', 'config', '--format', 'json'])
        with patch.object(updater, 'compose', return_value={}), patch.object(updater, 'verify_image'), patch.object(updater, 'run') as command:
            updater.recreate(config)
            self.assertEqual(command.call_args.args[0][:4], ['docker', 'compose', '--project-name', 'synthetic'])
            self.assertIn('--no-deps', command.call_args.args[0])

    def test_private_config_requires_complete_pins_and_owner_only_permissions(self):
        compose = self.root / 'compose.json'
        compose.write_text('{}')
        value = dict(expected_project_name='synthetic', schema=1, container='assistant', service='assistant', compose=str(compose),
            project_directory=str(self.root), expected_image='sha256:' + 'a' * 64,
            expected_runtime_sha256='b' * 64, expected_compose_sha256='c' * 64, expected_profile_sha256='d' * 64)
        config = self.root / 'operator.json'
        config.write_text(json.dumps(value))
        config.chmod(0o600)
        self.assertEqual(updater.read_config(config), value)
        portrait=dict(value, expected_portraits_sha256='e' * 64)
        config.write_text(json.dumps(portrait))
        self.assertEqual(updater.read_config(config), portrait)
        config.write_text(json.dumps(dict(portrait, expected_portraits_sha256='bad')))
        with self.assertRaisesRegex(RuntimeError, 'INVALID_OPERATOR_PIN'):
            updater.read_config(config)
        for project in ('', 'Foreign', '-foreign', 'bad/project', 'bad project', 'a' * 64):
            config.write_text(json.dumps(dict(value, expected_project_name=project)))
            with self.assertRaisesRegex(RuntimeError, 'INVALID_COMPOSE_PROJECT_NAME'):
                updater.read_config(config)
        config.write_text(json.dumps(value))
        config.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, 'PRIVATE_CONFIG_REQUIRED'):
            updater.read_config(config)
        config.chmod(0o600)
        config.write_text(json.dumps(dict(value, extra='not permitted')))
        with self.assertRaisesRegex(RuntimeError, 'UNSUPPORTED_OPERATOR_CONFIG'):
            updater.read_config(config)


if __name__ == '__main__':
    unittest.main()


