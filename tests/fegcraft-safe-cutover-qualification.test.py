from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('safe_qualification', ROOT / 'scripts/deploy/qualify-fegcraft-safe-cutover.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class Qualification(unittest.TestCase):
    def test_persistence_gates_native_qualification_without_activation(self):
        for case in ('success', 'unpersisted', 'changed', 'missing-welcome-proof'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); (root / 'releases').mkdir()
                calls = []
                report = {'persistence_checks_passed': True, 'same_host_data_bind': True,
                    'same_world_directory': True, 'persistent_version': '26.2', 'extra_writable_layer_paths': 0,
                    'fabric_loader_pinned_to_0_19_5': False, 'production_unchanged': True,
                    'game_container': 'same-container', 'game_image': 'same-image', 'compose_sha256': 'same-profile',
                    'data_directory_identity': [1, 2], 'world_directory_identity': [1, 3]}
                audits = [0]
                def audit():
                    audits[0] += 1
                    value = dict(report)
                    if case == 'unpersisted':
                        value['persistence_checks_passed'] = False; value['extra_writable_layer_paths'] = 1
                        return value, [{'path': '/unpersisted/synthetic'}]
                    if case == 'changed' and audits[0] == 2: value['compose_sha256'] = 'changed'
                    return value, []
                def qualify():
                    calls.append('qualify')
                    capture = root / 'releases/capture'; capture.mkdir()
                    (capture / 'result.json').write_text(json.dumps({'owner_welcome_tests_passed': case != 'missing-welcome-proof', 'addon_sha256': 'qualified-hash'}))
                    identity = root / 'releases/vector-fegcraft-identity-qualification-synthetic'; identity.mkdir()
                    (identity / 'result.json').write_text(json.dumps({'passed': True, 'revision': 'a' * 40, 'capture': str(capture)}))
                def export(revision, source, directory, name):
                    return SimpleNamespace(audit=audit) if name == 'persistence_audit' else SimpleNamespace(main=qualify)
                with patch.object(m, 'ROOT', root), patch.object(m, 'export', side_effect=export), \
                        patch.object(m.os, 'geteuid', return_value=0), patch.dict(m.os.environ, {'VECTOR_FEGCRAFT_REV': 'a' * 40}), redirect_stdout(io.StringIO()):
                    if case == 'success': m.main()
                    else:
                        with self.assertRaises(RuntimeError): m.main()
                results = list((root / 'releases').glob('vector-fegcraft-safe-cutover-*/result.json'))
                self.assertEqual(len(results), 1 if case == 'success' else 0)
                self.assertEqual(calls, [] if case == 'unpersisted' else ['qualify'])
                self.assertFalse(list(root.rglob('owner-welcome-v2.ready')))
                if results:
                    saved = json.loads(results[0].read_text())
                    self.assertFalse(saved['production_activated']); self.assertFalse(saved['backup_verified'])
                    self.assertFalse(saved['data_loss_guarantee']); self.assertTrue(saved['fabric_loader_pin_requires_review'])


if __name__ == '__main__': unittest.main()
