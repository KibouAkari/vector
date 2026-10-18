"""Real loopback TLS/curl and guarded publication retry regressions."""
from contextlib import redirect_stdout
import hashlib
import http.server
import importlib.util
import io
import json
import os
from pathlib import Path
import ssl
import stat
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publication_installer', ROOT / 'scripts/deploy/install-fegcraft-chat-identity.py')
installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)


def fixture_old():
    return SimpleNamespace(ASSETS={'avatar.png': 'fixture-hash', 'pack.zip': 'fixture-hash'},
                           atomic=lambda path, raw, uid, gid, mode: path.write_bytes(raw))


class Clock:
    def __init__(self): self.now = 0
    def read(self): return self.now
    def sleep(self, seconds): self.now += seconds


class Publication(unittest.TestCase):
    def verify(self, failures, *, timeout=3):
        clock = Clock(); calls = []
        def probe(old, directory, name, origin, expected, remaining):
            row = failures.pop(0) if failures else {'curl_exit': 0, 'http_status': 200, 'digest_matches': True, 'ready': True}
            calls.append((name, origin))
            return dict(row, asset=name, route='origin' if origin else 'public')
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(io.StringIO()):
            installer.verify_assets_ready(fixture_old(), Path(temporary), timeout=timeout,
                                          clock=clock.read, sleep=clock.sleep, probe=probe)
        return calls, clock.now

    def test_stale_reload_responses_must_become_verified_on_both_routes(self):
        failures = [{'curl_exit': 0, 'http_status': code, 'digest_matches': False, 'ready': False} for code in (404, 502)]
        calls, elapsed = self.verify(failures)
        self.assertEqual(elapsed, 2)
        self.assertEqual(calls[-5:], [('avatar.png', True), ('avatar.png', False),
                                      ('pack.zip', True), ('pack.zip', False), ('health', True)])

    def test_tls_and_redirect_failures_are_not_bypassed(self):
        for code, status in ((60, 0), (0, 302), (0, 403)):
            with self.subTest(code=code, status=status), self.assertRaisesRegex(RuntimeError, 'CHECK_REJECTED'):
                self.verify([{'curl_exit': code, 'http_status': status, 'digest_matches': False, 'ready': False}])

    def test_wrong_200_body_never_satisfies_readiness_and_wait_is_bounded(self):
        failures = [{'curl_exit': 0, 'http_status': 200, 'digest_matches': False, 'ready': False} for _ in range(10)]
        with self.assertRaisesRegex(RuntimeError, 'READINESS_TIMEOUT'):
            self.verify(failures, timeout=2)
        self.assertEqual(len(failures), 8)

    def test_error_codes_are_specific_but_private_values_remain_private(self):
        self.assertEqual(installer.safe_error(RuntimeError('RELEASE_COMMAND_FAILED:curl')), 'RELEASE_COMMAND_FAILED:curl')
        self.assertEqual(installer.safe_error(RuntimeError('private fixture value')), 'RuntimeError')
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); out = io.StringIO()
            old = fixture_old(); old.save = lambda directory, plan: None
            try:
                raise RuntimeError('private fixture value')
            except RuntimeError as exc:
                with redirect_stdout(out): installer.record_failure(old, directory, {'phase': 'https_assets'}, exc)
            self.assertNotIn('private fixture value', out.getvalue())
            self.assertNotIn('private fixture value', (directory / 'failure-primary.json').read_text())
            self.assertIn('private fixture value', (directory / 'failure-primary-private.txt').read_text())

    def test_only_root_owned_empty_directory_from_recorded_time_window_qualifies(self):
        meta = dict(st_mode=stat.S_IFDIR | 0o755, st_uid=0, st_gid=33, st_ctime_ns=15, st_mtime_ns=16)
        self.assertTrue(installer.owned_empty_directory(SimpleNamespace(**meta), 10, 20))
        for key, value in (('st_uid', 1000), ('st_mode', stat.S_IFDIR | 0o777), ('st_ctime_ns', 21), ('st_mtime_ns', 9)):
            self.assertFalse(installer.owned_empty_directory(SimpleNamespace(**dict(meta, **{key: value})), 10, 20))
        with tempfile.TemporaryDirectory() as temporary:
            public = Path(temporary); keep = public / 'keep'; keep.write_text('synthetic')
            p = SimpleNamespace(safe=lambda path: None)
            with self.assertRaisesRegex(RuntimeError, 'DIRECTORY_NOT_EMPTY'):
                installer.retire_failed_public_directory(p, None, SimpleNamespace(PUBLIC=public), {})
            self.assertEqual(keep.read_text(), 'synthetic')

    def test_failed_release_adoption_requires_exact_restored_files_and_keeps_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); failed = root / 'failed'; failed.mkdir()
            control = root / 'control'; control.mkdir(); data = root / 'data'; (data / 'config').mkdir(parents=True)
            public = root / 'public'; site, addon, bridge = root / 'site', root / 'addon', control / 'bridge'
            for path in (site, addon, bridge, control / 'token', control / 'introduction-v1.attempted', data / 'config/Discord-Integration.toml'):
                path.write_bytes(b'synthetic')
            (failed / 'installer.py').write_bytes(b'synthetic installer')
            public.mkdir(mode=0o755); public.chmod(0o755)
            digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            old = fixture_old(); old.PUBLIC = public; old.nginx_site = lambda: site; old.digest = digest
            rows = [{'path': str(path), 'backup': 'before-' + str(i), 'before': digest(path) if path.is_file() else None}
                    for i, path in enumerate((site, addon, bridge, public / 'avatar.png', public / 'pack.zip'))]
            protected = (control / 'token', control / 'introduction-v1.attempted', data / 'config/Discord-Integration.toml')
            plan = {'revision': installer.FAILED_REVISION, 'status': 'rolled_back', 'recreation_started': False,
                    'original_container': 'fixture-container', 'original_image': 'fixture-image', 'files': rows,
                    'protected': {'owned': 'fixture'}, 'protected_files': {str(path): digest(path) for path in protected}}
            (failed / 'plan.json').write_text(json.dumps(plan))
            p = SimpleNamespace(safe=lambda path: None, read=lambda path: path.read_bytes(),
                                source=lambda revision, path: b'synthetic installer')
            game = {'Id': 'fixture-container', 'Image': 'fixture-image'}
            # CI's host UID is not root; normalize only this fixture UID. Real time/mode checks still run.
            predicate = installer.owned_empty_directory
            def fixture_owner(meta, earliest, latest):
                return predicate(SimpleNamespace(st_mode=meta.st_mode, st_uid=0, st_gid=meta.st_gid,
                                 st_ctime_ns=meta.st_ctime_ns, st_mtime_ns=meta.st_mtime_ns), earliest, latest)
            with patch.object(installer, 'FAILED_RELEASE', failed), patch.object(installer, 'CONTROL', control), \
                 patch.object(installer, 'DATA', data), patch.object(installer, 'BRIDGE', bridge), \
                 patch.object(installer, 'protected_live', return_value=plan['protected']), \
                 patch.object(installer, 'owned_empty_directory', side_effect=fixture_owner), redirect_stdout(io.StringIO()):
                bridge.write_bytes(b'changed by another owner action')
                with self.assertRaisesRegex(RuntimeError, 'FILES_NOT_RESTORED'):
                    installer.retire_failed_public_directory(p, SimpleNamespace(ADDON=addon), old, game)
                self.assertTrue(public.is_dir())
                bridge.write_bytes(b'synthetic')
                installer.retire_failed_public_directory(p, SimpleNamespace(ADDON=addon), old, game)
            self.assertFalse(public.exists())
            self.assertTrue((failed / 'plan.json').is_file())
            self.assertEqual(bridge.read_bytes(), b'synthetic')


class CurlTLS(unittest.TestCase):
    def test_real_curl_waits_for_files_and_rejects_untrusted_tls(self):
        assets = {'avatar.png': b'synthetic avatar', 'pack.zip': b'synthetic pack'}
        attempts = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                attempts.append(self.path)
                if len(attempts) == 1:
                    status, body = 404, b'not ready'
                elif self.path == '/api/health':
                    status, body = 200, b'{"ok":true}'
                else:
                    status, body = 200, assets.get(self.path.removeprefix('/assets/'), b'unknown')
                self.send_response(status); self.send_header('Content-Length', str(len(body)))
                self.end_headers(); self.wfile.write(body)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); cert, key = directory / 'cert.pem', directory / 'key.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(key),
                            '-out', str(cert), '-days', '1', '-subj', '/CN=VectorFixture',
                            '-addext', 'subjectAltName=IP:127.0.0.1'], capture_output=True, check=True, timeout=15)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(cert, key)
            server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
            server.socket = context.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            old = fixture_old(); old.DOMAIN = '127.0.0.1'
            old.URL = 'https://127.0.0.1:' + str(server.server_port) + '/assets/'
            old.sha = lambda raw: hashlib.sha256(raw).hexdigest()
            old.ASSETS = {name: old.sha(raw) for name, raw in assets.items()}
            try:
                with patch.dict(os.environ, {'CURL_CA_BUNDLE': str(cert)}), redirect_stdout(io.StringIO()):
                    installer.verify_assets_ready(old, directory, timeout=5, sleep=lambda seconds: None)
                results = json.loads((directory / 'https-checks.json').read_text())
                self.assertEqual(results[0]['http_status'], 404)
                self.assertTrue(all(row['ready'] for row in results[-5:]))
                self.assertEqual(results[-1]['asset'], 'health')
                with patch.dict(os.environ), redirect_stdout(io.StringIO()):
                    for name in ('CURL_CA_BUNDLE', 'SSL_CERT_FILE', 'SSL_CERT_DIR'): os.environ.pop(name, None)
                    with self.assertRaisesRegex(RuntimeError, 'CHECK_REJECTED'):
                        installer.verify_assets_ready(old, directory, timeout=5)
                failed = json.loads((directory / 'https-checks.json').read_text())[-1]
                self.assertEqual(failed['curl_exit'], 60)
                self.assertFalse(failed['ready'])
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=2)


if __name__ == '__main__': unittest.main()
