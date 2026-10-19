"""Qualified release policy tests. Synthetic only; no Docker or live files."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('release', Path(__file__).resolve().parents[1] / 'scripts/deploy/release-qualified-web.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class Boundaries(unittest.TestCase):
    def fixture(self):
        config = {'revision': 'a' * 40, 'image_id': 'sha256:' + 'b' * 64,
                  'app': 'app', 'worker': 'worker', 'expected_compose_sha256': 'c',
                  'expected_app': {'id': 'id', 'image_id': 'old', 'started_at': 'time'}}
        before = {'compose': 'c', 'containers': {'app': dict(config['expected_app']), 'worker': {'id': 'worker'}}}
        phase = {'passed': True, 'executed_jobs': 0, 'cloud_calls': 0}
        report = {'passed': True, 'cleanup_verified': True, 'production_unchanged': True,
                  'production_activated': False, 'revision': config['revision'], 'image_id': config['image_id'],
                  'qualification': {'normal': dict(phase), 'outage': dict(phase)}}
        return config, before, report

    def test_exact_successful_matrix_and_identity_required(self):
        config, before, report = self.fixture()
        release.validate_stage(report, before, copy.deepcopy(before), config)
        for key in ('passed', 'cleanup_verified', 'production_unchanged'):
            changed = copy.deepcopy(report)
            changed[key] = False
            with self.assertRaisesRegex(RuntimeError, 'STAGE_NOT_QUALIFIED'):
                release.validate_stage(changed, before, before, config)
        for phase in ('normal', 'outage'):
            for key, value in (('executed_jobs', 1), ('cloud_calls', 1), ('passed', False)):
                changed = copy.deepcopy(report)
                changed['qualification'][phase][key] = value
                with self.assertRaisesRegex(RuntimeError, 'STAGE_MATRIX_INCOMPLETE'):
                    release.validate_stage(changed, before, before, config)
        changed = copy.deepcopy(before)
        changed['source'] = 'changed'
        with self.assertRaisesRegex(RuntimeError, 'STAGE_BASELINE_CHANGED'):
            release.validate_stage(report, before, changed, config)
        config['expected_app']['id'] = 'other'
        with self.assertRaisesRegex(RuntimeError, 'APP_BASELINE_MISMATCH'):
            release.validate_stage(report, before, before, config)

    def test_only_app_image_and_hostname_change(self):
        original = {'name': 'synthetic', 'services': {'app': {'image': 'old',
                    'environment': {'SECRET': 'literal${PASSWORD}', 'HOSTNAME': 'bad'},
                    'volumes': ['/private:/private:ro']}, 'worker': {'image': 'worker'}},
                    'networks': {'internal': {'internal': True}}}
        candidate = release.candidate_profile(original, 'app', 'sha256:new')
        expected = copy.deepcopy(original)
        expected['services']['app']['image'] = 'sha256:new'
        expected['services']['app']['environment']['HOSTNAME'] = '0.0.0.0'
        self.assertEqual(candidate, expected)
        self.assertEqual(original['services']['app']['image'], 'old')
        serialized = release.compose_bytes(candidate)
        self.assertIn(b'literal$${PASSWORD}', serialized)
        self.assertEqual(json.loads(serialized.replace(b'$$', b'$')), candidate)

    def test_other_generations_and_inventory_are_guarded(self):
        baseline = {'app': {'id': 'old'}, 'worker': {'id': 'worker'}, 'game': {'id': 'game'}}
        after = copy.deepcopy(baseline)
        after['app']['id'] = 'new'
        self.assertTrue(release.others_unchanged(baseline, after, 'app'))
        after['game']['id'] = 'restarted'
        self.assertFalse(release.others_unchanged(baseline, after, 'app'))
        after = dict(baseline, unexpected={'id': 'added'})
        self.assertFalse(release.others_unchanged(baseline, after, 'app'))

    def test_atomic_private_files_and_symlink_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'state.json'
            release.atomic(target, b'first')
            release.atomic(target, b'second')
            self.assertEqual(target.read_bytes(), b'second')
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            link = Path(temporary) / 'link'
            link.symlink_to(target)
            with self.assertRaisesRegex(RuntimeError, 'SYMLINK_PATH'):
                release.atomic(link, b'forbidden')
            self.assertEqual(target.read_bytes(), b'second')
            self.assertEqual(len(list(Path(temporary).iterdir())), 2)

    def rollback_fixture(self, temporary):
        root = Path(temporary)
        source = root / 'source'
        source.mkdir()
        (source / 'app').write_text('qualified')
        saved = root / 'source.original'
        saved.mkdir()
        (saved / 'app').write_text('original')
        original = {'services': {'app': {'image': 'old'}}}
        candidate = {'services': {'app': {'image': 'new'}}}
        (root / 'before.json').write_text(json.dumps({'containers': {'app': {'id': 'old'}, 'worker': {'id': 'worker'}}}))
        engine = release.Release.__new__(release.Release)
        engine.directory = root
        engine.c = {'source': str(source), 'compose': str(root / 'compose'), 'app': 'app', 'service': 'app'}
        engine.state = {'status': 'deployed', 'new_app': {'id': 'owned', 'image_id': 'new'},
                        'original_app': {'id': 'old', 'image_id': 'old'},
                        'candidate_profile': candidate, 'original_profile': original,
                        'candidate_hash': 'candidate', 'original_hash': 'original',
                        'original_source': 'original', 'qualified_source': 'qualified'}
        engine.shared = SimpleNamespace(source_fingerprint=lambda p: (p / 'app').read_text())
        engine.snapshot = Mock(return_value={'app': {'id': 'owned'}, 'worker': {'id': 'worker'}})
        engine.inspect = Mock(return_value={'Id': 'owned', 'Image': 'new'})
        engine.labels = Mock()
        engine.profile = Mock(side_effect=lambda p: original if Path(p).name == 'compose.original' else candidate)
        engine.run = Mock(return_value=json.dumps([{'Id': 'old'}]).encode())
        engine.save = Mock()
        return engine

    def test_rollback_rejects_foreign_generation_before_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine = self.rollback_fixture(temporary)
            engine.inspect.return_value = {'Id': 'foreign', 'Image': 'new'}
            with self.assertRaisesRegex(RuntimeError, 'ROLLBACK_UNRECORDED_OR_FOREIGN_CONTAINER'):
                engine.rollback()
            engine.save.assert_not_called()
            self.assertTrue((Path(temporary) / 'source.original').exists())

    def test_rollback_validates_resolved_original_image_before_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine = self.rollback_fixture(temporary)
            engine.run.return_value = json.dumps([{'Id': 'retagged'}]).encode()
            with self.assertRaisesRegex(RuntimeError, 'ROLLBACK_ORIGINAL_IMAGE_PIN_CHANGED'):
                engine.rollback()
            engine.save.assert_not_called()
            self.assertTrue((Path(temporary) / 'source.original').exists())

    def test_rollback_checks_original_tree_and_profile_before_writes(self):
        for boundary in ('source', 'profile'):
            with tempfile.TemporaryDirectory() as temporary:
                engine = self.rollback_fixture(temporary)
                if boundary == 'source':
                    (Path(temporary) / 'source.original/app').write_text('foreign')
                    error = 'ORIGINAL_SOURCE_BACKUP_CHANGED'
                else:
                    engine.profile.side_effect = lambda p: {'foreign': True} if Path(p).name == 'compose.original' else engine.state['candidate_profile']
                    error = 'ORIGINAL_COMPOSE_BACKUP_CHANGED'
                with self.assertRaisesRegex(RuntimeError, error):
                    engine.rollback()
                engine.save.assert_not_called()
                self.assertEqual((Path(temporary) / 'source/app').read_text(), 'qualified')

    def working_rollback(self, temporary):
        engine = self.rollback_fixture(temporary)
        root = Path(temporary)
        engine.state.update(compose_mode=0o640, compose_uid=root.stat().st_uid,
                            compose_gid=root.stat().st_gid)
        (root / 'compose.original').write_text(json.dumps(engine.state['original_profile']))
        (root / 'compose').write_text(json.dumps(engine.state['candidate_profile']))
        engine.profile.side_effect = lambda p: json.loads(Path(p).read_text())
        engine.save.side_effect = lambda **values: engine.state.update(values)
        engine.compose = Mock()
        engine.wait_healthy = Mock()
        original_inspect = engine.inspect.return_value
        engine.inspect.side_effect = [original_inspect, {'Id': 'restored', 'Image': 'old',
                                                       'State': {'StartedAt': 'restored-time'}}]
        return engine

    def assert_restored(self, engine, temporary):
        root = Path(temporary)
        self.assertEqual((root / 'source/app').read_text(), 'original')
        self.assertFalse((root / 'source.original').exists())
        self.assertEqual(json.loads((root / 'compose').read_text()), engine.state['original_profile'])
        self.assertEqual((root / 'compose').stat().st_mode & 0o777, 0o640)
        self.assertEqual(engine.state['status'], 'rolled_back')
        self.assertTrue(engine.state['rollback_verified'])
        self.assertEqual(engine.state['new_app']['config_hash'], 'original')
        engine.compose.assert_called_once_with(root / 'compose', 'up', '-d', '--no-deps',
                                               '--no-build', '--pull', 'never', 'app', timeout=120)
        engine.wait_healthy.assert_called_once_with('old', 'original')

    def test_successful_rollback_from_saved_source_before_new_tree_move(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine = self.working_rollback(temporary)
            root = Path(temporary)
            (root / 'source/app').unlink()
            (root / 'source').rmdir()
            engine.state.update(status='source_saved', new_app=None)
            (root / 'compose').write_text(json.dumps(engine.state['original_profile']))
            engine.inspect.side_effect = [{'Id': 'old', 'Image': 'old'},
                {'Id': 'restored', 'Image': 'old', 'State': {'StartedAt': 'restored-time'}}]
            engine.rollback()
            self.assert_restored(engine, temporary)

    def test_successful_resume_between_rollback_source_renames(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine = self.working_rollback(temporary)
            root = Path(temporary)
            (root / 'source').rename(root / 'source.failed')
            engine.state['status'] = 'rollback_started'
            engine.rollback()
            self.assert_restored(engine, temporary)
            self.assertEqual((root / 'source.failed/app').read_text(), 'qualified')

    def test_successful_resume_after_source_restore_before_journal(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine = self.working_rollback(temporary)
            root = Path(temporary)
            (root / 'source').rename(root / 'source.failed')
            (root / 'source.original').rename(root / 'source')
            engine.state['status'] = 'rollback_started'
            engine.rollback()
            self.assert_restored(engine, temporary)

    def test_successful_resume_after_compose_restore_before_journal(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine = self.working_rollback(temporary)
            root = Path(temporary)
            (root / 'source').rename(root / 'source.failed')
            (root / 'source.original').rename(root / 'source')
            (root / 'compose').write_text(json.dumps(engine.state['original_profile']))
            engine.state.update(status='rollback_started', rollback_source_restored=True)
            engine.rollback()
            self.assert_restored(engine, temporary)

    def test_same_image_listener_change_uses_generation_config_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine = self.working_rollback(temporary)
            engine.state['new_app']['image_id'] = 'old'
            engine.state['new_app']['config_hash'] = 'candidate'
            engine.inspect.side_effect = [{'Id': 'owned', 'Image': 'old'},
                {'Id': 'restored', 'Image': 'old', 'State': {'StartedAt': 'restored-time'}}]
            engine.rollback()
            self.assertEqual(engine.labels.call_args_list[0].args[1], 'candidate')
            self.assert_restored(engine, temporary)


if __name__ == '__main__':
    unittest.main()
