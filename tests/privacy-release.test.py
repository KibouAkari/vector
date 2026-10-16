import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('privacy_activation', ROOT / 'scripts/deploy/activate-privacy-review.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

RAW = b'''name: vector
services:
  app:
    image: qualified-tag
    environment:
      VECTOR_LOCAL_WORKERS: "1"
      SECRET: ${SYNTHETIC_ENV_REFERENCE}
    networks:
    - vector-internal
    - vector-local-inference
    volumes:
    - /opt/vector-data/files:/app/files
  worker:
    image: untouched
networks:
  vector-internal:
    internal: true
  vector-local-inference:
    external: true
    name: vector-local-inference
'''


def base_and_profile():
    base = dict(name='vector', services={'app': dict(image=a.TAG,
                environment={'VECTOR_LOCAL_WORKERS': '1'},
                networks={'vector-internal': None, 'vector-local-inference': None},
                volumes=[dict(type='bind', source='/files', target='/app/files')]),
                'worker': dict(image='untouched')},
                networks={'vector-internal': dict(internal=True), 'vector-local-inference': dict(external=True)})
    profile = dict(services={a.SERVICE: a.native_service('/code', '/token', 'stamp'),
                            'token-check': dict(volumes=[a.bind('/token', a.TOKEN_TARGET)])},
                   networks={a.NETWORK: dict(name=a.NETWORK, external=True, ipam={})})
    return base, profile


class CandidateTests(unittest.TestCase):
    def test_preserve_raw_configuration_and_indentless_sequences(self):
        service = a.native_service('/code', '/token', 'stamp')
        candidate = a.candidate_bytes(RAW, service, '/token').decode()
        self.assertIn('SECRET: ${SYNTHETIC_ENV_REFERENCE}', candidate)
        self.assertIn('  worker:\n    image: untouched', candidate)
        self.assertIn('      VECTOR_LOCAL_WORKERS: "1"', candidate)
        self.assertIn('      VECTOR_PRIVACY_REVIEW: "1"', candidate)
        line = next(x for x in candidate.splitlines() if x.startswith('  privacy-ner: '))
        self.assertEqual(json.loads(line.split(': ', 1)[1]), service)
        token_line = next(x for x in candidate.splitlines() if x.startswith('    - {'))
        self.assertEqual(json.loads(token_line[6:]), a.bind('/token', a.TOKEN_TARGET))
        self.assertIn('    - "vector-privacy-ner"\n    - vector-internal', candidate)
        self.assertEqual(candidate.count('VECTOR_PRIVACY_REVIEW:'), 1)

    def test_reject_ambiguous_layout_and_repeat_activation(self):
        for raw in [RAW.replace(b'environment:', b'environment: {}'),
                    RAW.replace(b'VECTOR_LOCAL_WORKERS: "1"', b'VECTOR_PRIVACY_REVIEW: "0"'),
                    RAW.replace(b'\n', b'\r\n'), RAW.rstrip(b'\n')]:
            with self.subTest(raw=raw), self.assertRaises(RuntimeError):
                a.candidate_bytes(raw, {}, '/token')

    def test_expected_canonical_changes_are_narrow(self):
        base, profile = base_and_profile()
        before = copy.deepcopy(base)
        expected = a.expected_config(base, profile)
        self.assertEqual(base, before)
        self.assertEqual(expected['services']['worker'], before['services']['worker'])
        self.assertEqual(expected['networks']['vector-internal'], before['networks']['vector-internal'])
        self.assertEqual(expected['services']['app']['environment'], {'VECTOR_LOCAL_WORKERS': '1', 'VECTOR_PRIVACY_REVIEW': '1'})
        self.assertEqual(len(expected['services']['app']['volumes']), 2)
        self.assertNotIn('ipam', expected['networks'][a.NETWORK])
        for alteration in ['image', 'networks', 'environment']:
            broken = copy.deepcopy(base)
            broken['services']['app'][alteration] = {} if alteration != 'image' else 'wrong'
            with self.subTest(alteration=alteration), self.assertRaises(RuntimeError):
                a.expected_config(broken, profile)

    def test_normalize_only_empty_ipam_on_our_external_network(self):
        value = {'networks': {a.NETWORK: {'name': a.NETWORK, 'external': True, 'ipam': {}},
                              'other': {'ipam': {}}}}
        normalized = a.normalized(value)
        self.assertEqual(normalized['networks']['other'], {'ipam': {}})
        self.assertNotIn('ipam', normalized['networks'][a.NETWORK])
        for ipam in [{'driver': 'default'}, {'config': []}]:
            value['networks'][a.NETWORK]['ipam'] = ipam
            self.assertEqual(a.normalized(value), value)

    def test_native_profile_no_network_escape_or_privilege(self):
        service = a.native_service('/code', '/token', 'stamp')
        self.assertEqual(service['image'], a.NATIVE_IMAGE)
        self.assertNotIn('ports', service)
        self.assertEqual(service['networks'], [a.NETWORK])
        self.assertEqual(service['user'], '65534:65534')
        self.assertTrue(service['read_only'])
        self.assertTrue(all(v['read_only'] and not v['bind']['create_host_path'] for v in service['volumes']))
        self.assertEqual(service['environment']['VECTOR_PRIVACY_NER_IDLE_SECONDS'], '300')
        self.assertEqual(service['mem_limit'], service['memswap_limit'])


class RollbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.compose = self.folder / 'compose.yml'
        self.compose.write_bytes(b'candidate')
        (self.folder / 'compose.original.yml').write_bytes(b'original')
        (self.folder / 'compose.candidate.yml').write_bytes(b'candidate')
        self.record_path = self.folder / 'activation.json'
        self.record = dict(commit=a.MERGED, image_id=a.IMAGE, stamp='stamp',
                           original_sha256=a.digest(b'original'), candidate_sha256=a.digest(b'candidate'),
                           source_hash='source', mode=0o600, uid=0, gid=0,
                           other_containers={'worker': 'same'}, network_created=True)
        self.record_path.write_text(json.dumps(self.record))
        self.calls = []
        def run(*args, **kwargs):
            self.calls.append(args)
            if args[:3] == ('docker', 'container', 'ls'):
                return 'native-id'
            if args[:3] == ('docker', 'network', 'inspect'):
                return json.dumps([dict(Id='network-id', Labels={a.OWNER_LABEL: 'stamp'}, Containers={})])
            return ''
        def obj(name):
            if name == a.NETWORK:
                return dict(Image=a.NATIVE_IMAGE, Id='native-id', Config={'Labels': {a.OWNER_LABEL: 'stamp'}})
            return dict(NetworkSettings={'Networks': {'vector-internal': {}, 'vector-local-inference': {}}}, Config={'Env': ['VECTOR_LOCAL_WORKERS=1']})
        self.h = dict(run=run, obj=obj, app_image_or_missing=lambda: a.IMAGE, LIVE=self.folder,
                      tree_hash=lambda p: 'source', idle=lambda: self.calls.append(('idle',)),
                      atomic=lambda p, data, *args: p.write_bytes(data), compose_up=lambda: self.calls.append(('compose_up',)),
                      healthy=lambda image: True, verify_others=lambda others: self.calls.append(('others', others)),
                      save_record=lambda p, value: p.write_text(json.dumps(value)))
        self.patch = patch.object(a, 'COMPOSE', self.compose)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_rollback_app_first_then_owned_native_only(self):
        a.rollback(self.h, self.record_path, manual=True)
        self.assertEqual(self.compose.read_bytes(), b'original')
        self.assertLess(self.calls.index(('compose_up',)), self.calls.index(('docker', 'rm', '--force', 'native-id')))
        self.assertIn(('docker', 'network', 'rm', 'network-id'), self.calls)
        self.assertEqual(json.loads(self.record_path.read_text())['status'], 'rolled-back')

    def test_refuse_later_compose_image_or_source_changes_before_any_write(self):
        for target in ['compose', 'image', 'source']:
            self.compose.write_bytes(b'later' if target == 'compose' else b'candidate')
            h = dict(self.h)
            if target == 'image': h['app_image_or_missing'] = lambda: 'another-image'
            if target == 'source': h['tree_hash'] = lambda p: 'another-source'
            with self.subTest(target=target), self.assertRaises(RuntimeError):
                a.rollback(h, self.record_path)
            self.assertEqual(self.compose.read_bytes(), b'later' if target == 'compose' else b'candidate')
            self.assertEqual(self.calls, [])

    def test_refuse_unowned_native_before_changing_app(self):
        h = dict(self.h)
        h['obj'] = lambda name: dict(Image=a.NATIVE_IMAGE, Config={'Labels': {a.OWNER_LABEL: 'other'}})
        with self.assertRaisesRegex(RuntimeError, 'different native service'):
            a.rollback(h, self.record_path)
        self.assertEqual(self.compose.read_bytes(), b'candidate')
        self.assertNotIn(('compose_up',), self.calls)

    def test_failed_health_does_not_remove_native_or_network(self):
        h = dict(self.h, healthy=lambda image: False)
        with self.assertRaisesRegex(RuntimeError, 'health'):
            a.rollback(h, self.record_path)
        self.assertFalse(any(call[:2] == ('docker', 'rm') or call[:3] == ('docker', 'network', 'rm') for call in self.calls))


class ReleaseGuardTests(unittest.TestCase):
    def test_checkout_guard_extension_keeps_live_source_revision_and_rejects_unknown_heads(self):
        shell = (ROOT / 'scripts/deploy/release-privacy-review.sh').read_text()
        embedded = shell.split("<<'PRIVACY_RELEASE_PYTHON'\n")[1].split('\nPRIVACY_RELEASE_PYTHON\n')[0]
        namespace = {'__name__': 'test_release'}
        exec(compile(embedded, 'release-privacy-review.sh', 'exec'), namespace)
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'control.sh'
            for head in [a.MERGED, '37130b59a6dad080076e1dea7ded563f996b1672',
                         '6a4e31b97e86f20fa6f4daa3504d45697ee89ede', 'unknown']:
                inner = f'''\ndef main():
    if {head!r} not in (OLD_REV, REV):
        raise RuntimeError('CHECKOUT')
    if OLD_REV != '37130b59a6dad080076e1dea7ded563f996b1672':
        raise RuntimeError('LIVE SOURCE REVISION CHANGED')
    raise RuntimeError('CALLED')
'''
                outer = "import ast\nTESTED='1f742366856a17ff7ab3ab01542d1eb7aca0a4a7'\nMERGED='d73f6f982db62532a80696d230dd77b01246c057'\n"
                outer += f"def prepare():\n    n={{'OLD_REV':CURRENT,'REV':MERGED,'OTHERS':('worker',)}}\n    exec(compile(ast.parse({inner!r}),'inner','exec'),n)\n    return n\ndef main():\n    prepare()['main']()\n"
                archive.write_text("<<'CONTROL_RELEASE_PYTHON'\n" + outer + '\nCONTROL_RELEASE_PYTHON\n')
                with patch.dict(namespace, SCRIPT=archive), patch.object(a.sys, 'argv', ['release', '--rollback', 'record']):
                    with self.subTest(head=head), self.assertRaisesRegex(RuntimeError, '^CHECKOUT$' if head == 'unknown' else '^CALLED$'):
                        namespace['main']()


if __name__ == '__main__':
    unittest.main()
