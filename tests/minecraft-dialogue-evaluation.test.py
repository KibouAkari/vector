"""Own-child cancellation and release-lock boundaries; no Docker or model calls."""
import importlib.util
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dialogue_evaluation', ROOT/'scripts/deploy/evaluate-minecraft-dialogue.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Evaluation(unittest.TestCase):
    def test_existing_private_slot_binding_is_retained_without_reading_secret(self):
        installed = (ROOT/'services/minecraft-assistant/server.py').read_text().replace(
            '/run/secrets/vector_minecraft_slot_dsn', '/run/secrets/operator_slot').replace(
            "value.username != 'vector_minecraft_slot'", "value.username != 'operator_slot'")
        candidate = (ROOT/'services/minecraft-assistant/server.py').read_text()
        result = module.preserve_slot_binding(installed, candidate, [
            {'Destination': '/run/secrets/operator_slot', 'RW': False}])
        self.assertEqual(result, candidate.replace(
            '/run/secrets/vector_minecraft_slot_dsn', '/run/secrets/operator_slot').replace(
            "value.username != 'vector_minecraft_slot'", "value.username != 'operator_slot'"))
        ast.parse(result)
        self.assertIn("stat.S_IMODE(meta.st_mode) != 0o400", result)
        self.assertIn("meta.st_uid != os.getuid()", result)

    def test_missing_writable_or_ambiguous_slot_mount_is_rejected(self):
        source = (ROOT/'services/minecraft-assistant/server.py').read_text()
        mount = {'Destination': '/run/secrets/vector_minecraft_slot_dsn', 'RW': False}
        for mounts in ([], [dict(mount, RW=True)], [mount, mount]):
            with self.subTest(mounts=mounts), self.assertRaisesRegex(RuntimeError, 'READ_ONLY_EXISTING_SLOT_MOUNT_REQUIRED'):
                module.preserve_slot_binding(source, source, mounts)

    def test_changed_factory_or_unsafe_binding_is_rejected(self):
        source = (ROOT/'services/minecraft-assistant/server.py').read_text()
        mounts = [{'Destination': '/run/secrets/vector_minecraft_slot_dsn', 'RW': False}]
        for invalid in (source.replace('def knowledge_for(', 'def renamed('),
                        source.replace('/run/secrets/vector_minecraft_slot_dsn', '/tmp/slot'),
                        source.replace("value.username != 'vector_minecraft_slot'", "value.username == 'vector_minecraft_slot'")):
            with self.subTest(), self.assertRaises(RuntimeError):
                module.preserve_slot_binding(invalid, source, mounts)

    def test_watchdog_reaps_only_its_own_child(self):
        foreign = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        try:
            identity = '1'*32
            code = module.WATCHDOG.replace('timeout=110', 'timeout=.05')
            result = subprocess.run([sys.executable, '-c', code], input=json.dumps({
                'program': 'import time; time.sleep(30)', 'evaluation_id': identity}).encode(),
                capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 137, result.stderr)
            self.assertIn(('VECTOR_DIALOGUE_TERMINATED='+identity).encode(), result.stdout)
            self.assertIsNone(foreign.poll())
        finally:
            foreign.terminate(); foreign.wait(timeout=5)

    def test_targeted_cancellation_leaves_unrelated_process_alive(self):
        identity = '2'*32
        foreign = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        target = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)',
                                   '--vector-dialogue-evaluation', identity], start_new_session=True)
        try:
            result = subprocess.run([sys.executable, '-c', module.CANCEL, identity],
                                    capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['terminated'])
            target.wait(timeout=5)
            self.assertIsNone(foreign.poll())
        finally:
            if target.poll() is None:target.kill(); target.wait(timeout=5)
            foreign.terminate(); foreign.wait(timeout=5)

    def test_missing_release_lock_is_never_created(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = root/'missing.lock'
            args = ['evaluation', '--guard-helper', str(ROOT/'scripts/deploy/update-minecraft-ranking-runtime.py'),
                    '--baseline', str(root), '--source-root', str(root),
                    '--workspace-root', str(root), '--lock-file', str(lock)]
            with patch.object(sys, 'argv', args), self.assertRaises(FileNotFoundError):
                module.main()
            self.assertFalse(lock.exists())


if __name__ == '__main__':
    unittest.main()
