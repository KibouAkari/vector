import copy
import os
import tempfile
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('evaluation', Path(__file__).parents[1] / 'scripts/deploy/evaluate-local-workers.py')
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


class FingerprintTests(unittest.TestCase):
    def info(self):
        return dict(Id='fixture-id', Image='sha256:fixture', Config=dict(Image='fixture-tag'),
            State=dict(StartedAt='fixture-time', Running=True),
            Mounts=[dict(Type='bind', Source='/fixture/a', Destination='/a', RW=False),
                    dict(Type='bind', Source='/fixture/b', Destination='/b', RW=True)],
            NetworkSettings=dict(Networks=dict(private=dict(NetworkID='network', EndpointID='endpoint',
                IPAddress='172.20.0.2', Aliases=['alias-b', 'alias-a']))))

    def test_mount_alias_and_dictionary_order_do_not_change_fingerprint(self):
        first = self.info()
        reordered = copy.deepcopy(first)
        reordered['Mounts'].reverse()
        reordered['NetworkSettings']['Networks']['private']['Aliases'].reverse()
        self.assertEqual(evaluation.production_fingerprint(first), evaluation.production_fingerprint(reordered))

    def test_actual_identity_restart_mount_and_network_changes_are_detected(self):
        original = self.info()
        for path, value in [(('Id',), 'replacement'), (('Image',), 'new-image'),
                (('State', 'StartedAt'), 'restart'), (('State', 'Running'), False),
                (('Mounts', 0, 'RW'), True),
                (('NetworkSettings', 'Networks', 'private', 'IPAddress'), '172.20.0.3')]:
            changed = copy.deepcopy(original)
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            self.assertNotEqual(evaluation.production_fingerprint(original), evaluation.production_fingerprint(changed))

    def test_evaluator_code_remains_readable_with_restrictive_umask_but_snapshots_are_private(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'evaluation'
            previous = os.umask(0o077)
            try:
                evaluation.create_evaluation_directory(root)
                self.assertEqual(root.stat().st_mode & 0o777, 0o755)
                self.assertEqual((root / 'lib').stat().st_mode & 0o777, 0o755)
                snapshot = root / 'before.json'
                evaluation.private_json(snapshot, {'fixture': True})
                self.assertEqual(snapshot.stat().st_mode & 0o777, 0o600)
                with self.assertRaises(FileExistsError):
                    evaluation.private_json(snapshot, {'overwritten': True})
            finally:
                os.umask(previous)


if __name__ == '__main__':
    unittest.main()
