import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/deploy/activate-local-workers.py'
spec = importlib.util.spec_from_file_location('activation', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def compose(indent=6):
    # Deliberately retain substitutions and a synthetic secret-like placeholder.
    return ('services:\n  app:\n    image: ' + m.TAG + '\n'
            '    environment:\n      DATABASE_URL: ${DATABASE_URL}\n'
            '      NOTE: synthetic-placeholder\n    networks:\n'
            + ' ' * indent + '- vector-internal\n'
            '    restart: unless-stopped\n  worker:\n    image: vector-worker\n'
            'networks:\n  vector-internal:\n    name: vector-internal\n'
            '  vector-tools:\n    name: vector_vector-tools\n'
            'volumes:\n  state: {}\n').encode()


class ActivationTests(unittest.TestCase):
    def test_preserves_other_configuration_and_env_substitutions(self):
        for indent in (4, 6):
            with self.subTest(indent=indent):
                original = compose(indent)
                result = m.candidate_bytes(original)
                undo = result.replace(b'      VECTOR_LOCAL_WORKERS: "1"\n', b'', 1)
                undo = undo.replace((' ' * indent + '- vector-local-inference\n').encode(), b'', 1)
                undo = undo.replace(b'  vector-local-inference:\n    external: true\n    name: vector-local-inference\n', b'', 1)
                self.assertEqual(undo, original)
                self.assertIn(b'${DATABASE_URL}', result)

    def test_rejects_preconfigured_or_ambiguous_layout(self):
        for value in (
            compose().replace(b'    environment:\n', b'    environment: {}\n'),
            compose().replace(b'      NOTE:', b'      VECTOR_LOCAL_WORKERS:'),
            compose().replace(b'      - vector-internal', b'      - another-network'),
            compose().replace(b'  app:', b'  app2:'),
            compose().replace(b'\n', b'\r\n'),
        ):
            with self.subTest(value=value):
                with self.assertRaises(RuntimeError):
                    m.candidate_bytes(value)

    def test_canonical_delta_is_limited_to_flag_and_external_network(self):
        base = {'services': {'app': {'image': m.TAG, 'environment': {'PRIVATE': 'untouched'},
                                    'networks': {'vector-internal': None}},
                             'worker': {'image': 'vector-worker'}},
                'networks': {'vector-internal': {'name': 'vector-internal'}}, 'volumes': {'keep': {}}}
        unchanged = json.loads(json.dumps(base))
        actual = m.expected_config(base)
        self.assertEqual(base, unchanged)
        self.assertEqual(actual['services']['worker'], base['services']['worker'])
        self.assertEqual(actual['services']['app']['environment']['PRIVATE'], 'untouched')
        self.assertEqual(actual['networks'][m.NETWORK], {'name': m.NETWORK, 'external': True})
        del actual['services']['app']['environment']['VECTOR_LOCAL_WORKERS']
        del actual['services']['app']['networks'][m.NETWORK]
        del actual['networks'][m.NETWORK]
        self.assertEqual(actual, base)

    def test_rollback_refuses_future_compose_or_image_and_restores_disabled_state(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original, candidate = compose(), m.candidate_bytes(compose())
            (root / 'compose.original.yml').write_bytes(original)
            (root / 'compose.candidate.yml').write_bytes(candidate)
            live = root / 'live.yml'
            record_path = root / 'activation.json'
            record = dict(commit=m.MERGED, image_id=m.IMAGE, mode=0o640, uid=0, gid=0,
                          original_sha256=hashlib.sha256(original).hexdigest(),
                          candidate_sha256=hashlib.sha256(candidate).hexdigest(), other_containers={})
            record_path.write_text(json.dumps(record))
            writes, ups, idles = [], [], []
            app = {'Image': m.IMAGE, 'NetworkSettings': {'Networks': {'vector-internal': {}}}}
            def atomic(path, data, mode, uid, gid):
                writes.append((mode, uid, gid))
                path.write_bytes(data)
            h = {'obj': lambda name: app, 'atomic': atomic, 'compose_up': lambda: ups.append(1),
                 'healthy': lambda image: True, 'verify_others': lambda value: None,
                 'idle': lambda: idles.append(1),
                 'save_record': lambda path, value: path.write_text(json.dumps(value))}
            with patch.object(m, 'COMPOSE', live):
                live.write_bytes(b'new owner change')
                with self.assertRaises(RuntimeError): m.rollback(h, record_path, manual=True)
                self.assertEqual(writes, [])
                live.write_bytes(candidate)
                app['Image'] = 'different-release'
                with self.assertRaises(RuntimeError): m.rollback(h, record_path, manual=True)
                self.assertEqual(writes, [])
                app['Image'] = m.IMAGE
                m.rollback(h, record_path, manual=True)
                self.assertEqual(live.read_bytes(), original)
                self.assertEqual(writes, [(0o640, 0, 0)])
                self.assertEqual(ups, [1])
                self.assertEqual(idles, [1])
                self.assertEqual(json.loads(record_path.read_text())['status'], 'rolled-back')


if __name__ == '__main__':
    unittest.main()
