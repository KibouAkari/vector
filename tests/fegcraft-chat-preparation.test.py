"""Preparation must not mistake old/incomplete evidence for deployment readiness."""
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import json

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('preparation', ROOT / 'scripts/deploy/prepare-fegcraft-chat-cutover.py')
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)


class Evidence(unittest.TestCase):
    def test_restic_adapter_cannot_start_backup_or_maintenance(self):
        namespace = {}
        exec('def restic(*args): return ["restic", "--repo", "private", *args]\ndef read_config(): return restic("cat", "config")', namespace)
        engine = prep.readonly_backup_engine(SimpleNamespace(**namespace))
        self.assertEqual(engine.read_config(), ['restic', '--no-cache', '--no-lock', '--repo', 'private', 'cat', 'config'])
        for command in ('backup', 'prune', 'forget', 'unlock', 'init'):
            with self.assertRaises(RuntimeError):
                engine.restic(command)

    def test_backup_requires_recent_successful_consistent_restore_probe(self):
        now = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
        result = {'consistent_staging_completed': True, 'world_restore_probe_passed': True,
                  'container_recreated': False}
        snapshot = {'time': (now - timedelta(hours=10)).isoformat()}
        accepted = prep.backup_summary(result, snapshot, now)
        self.assertTrue(accepted['verified'])
        self.assertFalse(accepted['entire_restore_tested'])
        self.assertFalse(accepted['writable_container_layer_included'])
        for key in result:
            self.assertFalse(prep.backup_summary({k: v for k, v in result.items() if k != key}, snapshot, now)['verified'])
        for hours in (37, -1):
            self.assertFalse(prep.backup_summary(result, {'time': (now - timedelta(hours=hours)).isoformat()}, now)['verified'])

    def test_private_exceptions_do_not_escape(self):
        for error in (ValueError('private-value'), RuntimeError('private-value'),
                      RuntimeError('FAILED: secret'), OSError('/private/value')):
            self.assertNotIn('private', prep.error_code(error))
            self.assertNotIn('secret', prep.error_code(error))
        self.assertEqual(prep.error_code(RuntimeError('CURRENT_RELEASE_CHANGED')), 'CURRENT_RELEASE_CHANGED')

    def test_capture_requires_discord_welcome_and_no_external_activity(self):
        value = {'revision': 'a' * 40, 'passed': True, 'cleanup_verified': True,
                 'production_compose_unchanged': True, 'production_container_identities_unchanged': True,
                 'installed_integration_unchanged': True, 'discord_channel_bot_replay_and_block_registry_passed': True,
                 'statistics_dialogue_tests_passed': True, 'owner_welcome_tests_passed': True,
                 'production_activated': False, 'model_calls': 0, 'cloud_calls': 0, 'external_messages_sent': 0}
        prep.capture_report(value, 'a' * 40)
        for key in value:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                prep.capture_report({k: v for k, v in value.items() if k != key}, 'a' * 40)
        with self.assertRaises(RuntimeError):
            prep.capture_report(dict(value, external_messages_sent=1), 'a' * 40)

    def test_mode0_or_changed_release_is_rejected_before_runtime_probe(self):
        profile = b'{}'
        manifest = {'backend_revision': prep.DEPLOYED, 'backend_release': str(prep.RELEASE),
                    'compose_sha256': prep.sha(profile)}
        raw = json.dumps(manifest).encode()
        record = {'status': 'deployed', 'revision': prep.DEPLOYED, 'new_profile_sha': prep.sha(profile),
                  'new_manifest_sha': prep.sha(raw)}
        files = {prep.INSTALL / 'compose.json': profile, prep.INSTALL / 'manifest.json': raw,
                 prep.RELEASE / 'deployment.json': json.dumps(record).encode(),
                 prep.RELEASE / 'compose.candidate.json': b'changed'}
        with patch.object(prep, 'read', side_effect=files.__getitem__):
            with self.assertRaisesRegex(RuntimeError, 'CURRENT_RELEASE_CHANGED'):
                prep.current_assistant(None, SimpleNamespace())


if __name__ == '__main__':
    unittest.main()
