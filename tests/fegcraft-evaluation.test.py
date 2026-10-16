import importlib.util
import json
import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('evaluation', ROOT / 'scripts/deploy/evaluate-fegcraft-bridge.py')
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


class EvaluationTests(unittest.TestCase):
    def test_interrupted_or_incomplete_capture_cannot_pass(self):
        checks = {'production_unchanged': True}
        result = {**checks, **dict.fromkeys(evaluation.COMPLETION_FLAGS, True)}
        self.assertTrue(evaluation.qualified(result, None, [], checks))
        for flag in evaluation.COMPLETION_FLAGS:
            partial = dict(result); partial.pop(flag)
            self.assertFalse(evaluation.qualified(partial, None, [], checks))
        self.assertFalse(evaluation.qualified(result, 'EVALUATION_INTERRUPTED', [], checks))
        self.assertFalse(evaluation.qualified(result, None, ['CLEANUP_FAILED'], checks))

    def test_timeout_retains_bounded_partial_log(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / 'compile.log'
            def child(args, **kwargs):
                kwargs['stdout'].write(b'x' * (evaluation.LOG_LIMIT + 20) + b'failure tail')
                raise subprocess.TimeoutExpired(args, 1)
            with patch.object(evaluation.subprocess, 'run', side_effect=child):
                with self.assertRaisesRegex(RuntimeError, 'TIMEOUT:compile.log'):
                    evaluation.run(['synthetic'], log=log)
            self.assertEqual(log.stat().st_size, evaluation.LOG_LIMIT)
            self.assertTrue(log.read_bytes().endswith(b'failure tail'))
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)

    def test_completed_log_is_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / 'client.log'
            def child(args, **kwargs):
                kwargs['stdout'].write(b'x' * (evaluation.LOG_LIMIT + 1))
                return subprocess.CompletedProcess(args, 1)
            with patch.object(evaluation.subprocess, 'run', side_effect=child):
                with self.assertRaisesRegex(RuntimeError, 'FAILED:client.log'):
                    evaluation.run(['synthetic'], log=log)
            self.assertEqual(log.stat().st_size, evaluation.LOG_LIMIT)

    def test_inspection_distinguishes_absence_from_daemon_failure(self):
        for kind in ('container', 'network', 'image'):
            missing = subprocess.CompletedProcess([], 1, b'[]\n', b'Error: No such object: synthetic\n')
            with patch.object(evaluation, 'run', return_value=missing):
                self.assertIsNone(evaluation.inspect(kind, 'synthetic'))
            for message in (b'Cannot connect to the Docker daemon', b'permission denied', b''):
                failed = subprocess.CompletedProcess([], 1, b'', message)
                with patch.object(evaluation, 'run', return_value=failed):
                    with self.assertRaisesRegex(RuntimeError, 'INSPECTION_FAILED'):
                        evaluation.remove_owned(kind, 'synthetic', 'owner')

    def test_unprivileged_container_has_bounded_private_execution(self):
        args = evaluation.container_args('synthetic', 'owner', 'none')
        for flag in ('--read-only', '--cap-drop', '--security-opt', '--pids-limit', '--cpus', '--memory', '--memory-swap'):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index('--user') + 1], '65534:65534')
        self.assertEqual(args[args.index('--network') + 1], 'none')
        self.assertNotIn('--privileged', args)
        self.assertNotIn('/var/run/docker.sock', ' '.join(args))

    def test_cleanup_refuses_foreign_resource(self):
        with patch.object(evaluation, 'inspect', return_value={'Config': {'Labels': {evaluation.LABEL: 'someone-else'}}}), patch.object(evaluation, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'OWNERSHIP'):
                evaluation.remove_owned('container', 'synthetic', 'expected')
            run.assert_not_called()

    def test_cleanup_only_removes_owned_resource(self):
        with patch.object(evaluation, 'inspect', return_value={'Config': {'Labels': {evaluation.LABEL: 'expected'}}}), patch.object(evaluation, 'run') as run:
            evaluation.remove_owned('container', 'synthetic', 'expected')
            run.assert_called_once_with(['docker', 'container', 'rm', '-f', 'synthetic'])

    def test_export_traversable_under_restrictive_runner_umask(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            original_mode = parent.stat().st_mode & 0o777
            class Result:
                def __init__(self, value): self.stdout = value
            def run(args, **kwargs):
                if 'ls-tree' in args:
                    return Result(b'100644 blob abc\tservices/fegcraft-assistant/server.py\0' * 8)
                return Result(b'print("synthetic")\n')
            old = os.umask(0o077)
            try:
                with patch.object(evaluation, 'run', side_effect=run):
                    evaluation.export_sources('a' * 40, parent / 'code')
            finally:
                os.umask(old)
            for path in ((parent / 'code'), (parent / 'code/services'), (parent / 'code/services/fegcraft-assistant')):
                self.assertEqual(path.stat().st_mode & 0o777, 0o755)
            self.assertEqual((parent / 'code/services/fegcraft-assistant/server.py').stat().st_mode & 0o777, 0o644)
            self.assertEqual(parent.stat().st_mode & 0o777, original_mode)

    def test_source_export_rejects_links_and_parent_escape(self):
        for row in (b'120000 blob abc\tservices/link\0', b'100644 blob abc\t../outside\0'):
            with self.subTest(row=row), tempfile.TemporaryDirectory() as temporary:
                class Result: stdout = row
                with patch.object(evaluation, 'run', return_value=Result()), self.assertRaises(RuntimeError):
                    evaluation.export_sources('a' * 40, Path(temporary) / 'code')


if __name__ == '__main__':
    unittest.main()
