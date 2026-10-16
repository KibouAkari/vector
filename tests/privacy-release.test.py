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
    def test_install_preserves_archived_byte_output_and_exact_source(self):
        data = '# Unicode source: Zoë\nvalue = 1\n\n'.encode('utf8')
        with tempfile.TemporaryDirectory() as directory:
            code = Path(directory)
            calls = []
            def atomic(path, content, mode, uid, gid):
                calls.append((mode, uid, gid))
                path.write_bytes(content)
            h = {'run': lambda *args: data, 'atomic': atomic}
            hashes = a.install_code(h, code)
            self.assertEqual((code / 'server.py').read_bytes(), data)
            self.assertEqual((code / 'privacy-ner-core.py').read_bytes(), data)
            self.assertEqual(set(hashes.values()), {a.digest(data)})
            self.assertEqual(calls, [(0o644, 0, 0)] * 2)
            with self.assertRaisesRegex(RuntimeError, 'byte-output'):
                a.install_code(dict(h, run=lambda *args: data.decode()), code)

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

    def test_app_mount_order_is_ignored_without_changing_definitions(self):
        base, profile = base_and_profile()
        expected = a.expected_config(base, profile)
        actual = copy.deepcopy(expected)
        actual['services']['app']['volumes'].reverse()
        self.assertEqual(a.normalized(actual), expected)
        self.assertNotEqual(actual, expected)
        self.assertEqual(a.normalized(actual)['services']['worker'], expected['services']['worker'])

    def test_mount_sources_permissions_and_options_still_require_exact_equality(self):
        base, profile = base_and_profile()
        expected = a.expected_config(base, profile)
        for field, value in [('source', '/other'), ('read_only', False),
                             ('bind', {'create_host_path': True})]:
            actual = copy.deepcopy(expected)
            token = next(m for m in actual['services']['app']['volumes'] if m['target'] == a.TOKEN_TARGET)
            token[field] = value
            with self.subTest(field=field):
                self.assertNotEqual(a.normalized(actual), expected)
        actual = copy.deepcopy(expected)
        actual['services']['app']['volumes'].append(copy.deepcopy(actual['services']['app']['volumes'][0]))
        with self.assertRaisesRegex(RuntimeError, 'Duplicate'):
            a.normalized(actual)
        with self.assertRaisesRegex(RuntimeError, 'canonical'):
            a.normalized({'services': {'app': {'volumes': ['unparsed-short-volume']}}})

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


class PreparedFilesTests(unittest.TestCase):
    def fixture(self, root):
        directory = root / 'private'
        directory.mkdir(mode=0o700)
        directory.chmod(0o700)
        code = directory / ('code-' + a.TESTED)
        code.mkdir(mode=0o755)
        code.chmod(0o755)
        data = b'value = 1\n'
        for name in ['server.py', 'privacy-ner-core.py']:
            path = code / name
            path.write_bytes(data)
            path.chmod(0o644)
        token = directory / 'token'
        # Synthetic, deliberately not a production credential.
        token.write_bytes(b'0' * 64 + b'\n')
        token.chmod(0o444)
        h = {'run': lambda *args: data,
             'atomic': lambda *args: self.fail('Resume must not overwrite any file')}
        return directory, code, token, data, h

    def test_resume_verified_files_without_writing_or_rotating_token(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory, code, token, data, h = self.fixture(Path(temporary))
            paths = [directory, code, token, code / 'server.py', code / 'privacy-ner-core.py']
            before = [(p.lstat().st_ino, p.lstat().st_mtime_ns) for p in paths]
            result = a.prepare_private_files(h, directory, owner=os.getuid())
            self.assertEqual(result[:2], (code, token))
            self.assertEqual(set(result[2].values()), {a.digest(data)})
            self.assertEqual(before, [(p.lstat().st_ino, p.lstat().st_mtime_ns) for p in paths])
            self.assertEqual(token.read_bytes(), b'0' * 64 + b'\n')

    def test_resume_rejects_modified_code_token_modes_links_and_extra_files(self):
        for change in ['code', 'token', 'mode', 'symlink', 'hardlink', 'extra', 'code-extra', 'dir-mode']:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                directory, code, token, data, h = self.fixture(Path(temporary))
                if change == 'code': (code / 'server.py').write_bytes(b'changed = 1\n')
                if change == 'token':
                    token.chmod(0o600)
                    token.write_bytes(b'invalid\n')
                    token.chmod(0o444)
                if change == 'mode': token.chmod(0o644)
                if change == 'symlink':
                    (code / 'server.py').unlink()
                    (code / 'server.py').symlink_to(code / 'privacy-ner-core.py')
                if change == 'hardlink': os.link(token, Path(temporary) / 'alias')
                if change == 'extra': (directory / 'unknown').touch()
                if change == 'code-extra': (code / 'unknown').touch()
                if change == 'dir-mode': directory.chmod(0o755)
                with self.assertRaises(RuntimeError):
                    a.prepare_private_files(h, directory, owner=os.getuid())

    def test_prepared_owner_and_symlink_directory_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory, code, token, data, h = self.fixture(Path(temporary))
            with self.assertRaisesRegex(RuntimeError, 'ownership'):
                a.prepare_private_files(h, directory, owner=os.getuid() + 1)
            link = Path(temporary) / 'alias'
            link.symlink_to(directory, target_is_directory=True)
            with self.assertRaises(RuntimeError):
                a.prepare_private_files(h, link, owner=os.getuid())


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
