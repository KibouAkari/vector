import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('evaluation', ROOT / 'scripts/deploy/evaluate-fegcraft-bridge.py')
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


class EvaluationTests(unittest.TestCase):
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
