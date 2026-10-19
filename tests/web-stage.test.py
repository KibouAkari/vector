"""Synthetic stage-only boundaries. No Docker, network, model or live files."""
import importlib.util
import io
import fcntl
import subprocess
import sys
import os
import time
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('web_stage', Path(__file__).resolve().parents[1] / 'scripts/deploy/stage-web-recovery.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class Boundaries(unittest.TestCase):
    def row(self):
        return {'Id': 'synthetic-id', 'Image': 'synthetic-image',
                'State': {'Running': True, 'StartedAt': 'synthetic-time'},
                'Mounts': [{'Destination': '/one', 'Source': '/synthetic/a'}, {'Destination': '/two', 'Source': '/synthetic/b'}],
                'NetworkSettings': {'Networks': {'private': {'NetworkID': 'network', 'IPAddress': '192.0.2.1'}}}}

    def test_mount_order_does_not_fake_production_change(self):
        a = self.row()
        b = json.loads(json.dumps(a))
        b['Mounts'].reverse()
        a['NetworkSettings']['Networks']['private']['Aliases'] = ['b', 'a']
        b['NetworkSettings']['Networks']['private']['Aliases'] = ['a', 'b']
        self.assertEqual(stage.canonical_container(a), stage.canonical_container(b))
        b['NetworkSettings']['Networks']['private']['IPAddress'] = '192.0.2.2'
        self.assertNotEqual(stage.canonical_container(a), stage.canonical_container(b))

    def test_exact_app_worker_compose_baseline(self):
        current = stage.canonical_container(self.row())
        baseline = {'read_only': True, 'production_unchanged': True, 'app': dict(current), 'worker': dict(current), 'compose_sha256': 'hash'}
        observed = {'app': current, 'worker': current}
        stage.validate_baseline(baseline, observed, 'app', 'worker', 'hash')
        for field in ('id', 'image_id', 'started_at', 'running'):
            changed = json.loads(json.dumps(baseline))
            changed['worker'][field] = 'different'
            with self.assertRaisesRegex(RuntimeError, 'BASELINE_CONTAINER_CHANGED'):
                stage.validate_baseline(changed, observed, 'app', 'worker', 'hash')
        with self.assertRaisesRegex(RuntimeError, 'BASELINE_COMPOSE_CHANGED'):
            stage.validate_baseline(baseline, observed, 'app', 'worker', 'other')

    def test_archive_never_escapes_or_follows_links(self):
        for name, kind in (('../outside', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE), ('link', tarfile.SYMTYPE)):
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode='w') as archive:
                info = tarfile.TarInfo(name)
                info.type = kind
                info.linkname = '/outside'
                archive.addfile(info)
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(RuntimeError, 'UNSUPPORTED_SOURCE_ARCHIVE_ENTRY'):
                    stage.unpack_source(buffer.getvalue(), Path(directory))
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_source_fingerprint_detects_content_and_symlink_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / 'input'
            file.write_text('a')
            first = stage.source_fingerprint(root)
            file.write_text('b')
            self.assertNotEqual(first, stage.source_fingerprint(root))
            file.unlink()
            file.symlink_to('elsewhere')
            self.assertNotEqual(first, stage.source_fingerprint(root))

    def test_private_container_limits_and_no_public_ports(self):
        args = stage.limits('test', 'internal', '1001:1001')
        for flag in ('--read-only', '--cap-drop', '--security-opt', '--memory', '--memory-swap', '--pids-limit', '--cpus'):
            self.assertIn(flag, args)
        self.assertNotIn('--publish', args)
        self.assertNotIn('--privileged', args)
        self.assertNotIn('--env-file', args)

    def test_cleanup_owns_only_temporary_objects_and_deletes_synthetic_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            release = Path(directory)
            (release / 'input').mkdir()
            for name in ('app.env', 'postgres.env', 'input/service-token'):
                (release / name).write_text('synthetic-secret')
            instance = stage.Stage(SimpleNamespace(), release)
            instance.owned = ['temporary-test-app', 'temporary-test-native']
            instance.network = 'temporary-test-network'
            calls = []
            def fake_run(command, **kwargs):
                calls.append(command)
                return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
            with patch.object(stage.subprocess, 'run', side_effect=fake_run):
                self.assertEqual(instance.cleanup(), [])
            removals = [cmd for cmd in calls if cmd[:2] == ['docker', 'rm']]
            self.assertEqual({cmd[-1] for cmd in removals}, {'temporary-test-app', 'temporary-test-native'})
            self.assertTrue(all(not (release / name).exists() for name in ('app.env', 'postgres.env', 'input/service-token')))
            self.assertIsNone(instance.network)

    def test_lost_cpu_slot_rejects_operation_before_child_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = stage.Stage(SimpleNamespace(), Path(directory))
            instance.slot = SimpleNamespace(poll=lambda: 1)
            process = SimpleNamespace(poll=lambda: None, kill=lambda: None, communicate=lambda: (b'', b''))
            with patch.object(stage.subprocess, 'Popen', return_value=process), patch.object(process, 'kill') as kill:
                with self.assertRaisesRegex(RuntimeError, 'SHARED_CPU_SLOT_LOST'):
                    instance.run('synthetic-command')
                kill.assert_not_called()

    def test_log_timeout_never_skips_removal_and_failed_removal_is_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            release = Path(directory)
            (release / 'input').mkdir()
            (release / 'input/service-token').write_text('synthetic-secret')
            instance = stage.Stage(SimpleNamespace(), release)
            instance.owned = ['temporary-app', 'temporary-ner']
            instance.network = 'temporary-network'
            calls = []
            def first_run(command, **kwargs):
                calls.append(command)
                if command[1] == 'logs':
                    raise stage.subprocess.TimeoutExpired(command, 3)
                return SimpleNamespace(returncode=1 if command[-1] == 'temporary-app' else 0, stdout=b'', stderr=b'')
            with patch.object(stage.subprocess, 'run', side_effect=first_run):
                self.assertEqual(instance.cleanup(), ['CONTAINER_REMOVAL_FAILED'])
            self.assertEqual(instance.owned, ['temporary-app'])
            self.assertEqual([cmd[-1] for cmd in calls if cmd[1] == 'rm'], ['temporary-ner', 'temporary-app'])
            self.assertFalse((release / 'input/service-token').exists())
            self.assertTrue(any(cmd[1:3] == ['network', 'rm'] for cmd in calls))
            with patch.object(stage.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=b'', stderr=b'')):
                self.assertEqual(instance.cleanup(), [])
            self.assertEqual(instance.owned, [])

    def test_baseline_mount_change_is_rejected(self):
        current = stage.canonical_container(self.row())
        baseline = {'read_only': True, 'production_unchanged': True, 'app': dict(current), 'worker': dict(current), 'compose_sha256': 'hash'}
        baseline['worker']['mount_fingerprints'] = ['changed']
        with self.assertRaisesRegex(RuntimeError, 'BASELINE_MOUNTS_CHANGED'):
            stage.validate_baseline(baseline, {'app': current, 'worker': current}, 'app', 'worker', 'hash')

    def test_long_operation_emits_secret_free_heartbeat(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = stage.Stage(SimpleNamespace(), Path(directory))
            clock = [0]
            calls = [0]
            def communicate(**kwargs):
                calls[0] += 1
                if calls[0] == 1:
                    clock[0] = 25
                    raise subprocess.TimeoutExpired('synthetic', 5)
                return b'ok', b''
            process = SimpleNamespace(returncode=0, poll=lambda: 0, communicate=communicate)
            with patch.object(stage.subprocess, 'Popen', return_value=process), patch.object(stage.time, 'monotonic', side_effect=lambda: clock[0]), patch('builtins.print') as output:
                self.assertEqual(instance.run('secret-command-never-printed', timeout=60), b'ok')
            self.assertEqual(output.call_count, 1)
            self.assertIn('still running', output.call_args.args[0])
            self.assertNotIn('secret-command', output.call_args.args[0])

    def test_operator_lock_contention_aborts_before_stage_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_path = root / 'operator.lock'
            with lock_path.open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                command = [sys.executable, spec.origin]
                for name in ('repo', 'source', 'compose', 'baseline', 'output'):
                    command += ['--' + name, str(root / name)]
                command += ['--lock-file', str(lock_path), '--revision', 'a' * 40,
                            '--app', 'synthetic-app', '--worker', 'synthetic-worker',
                            '--native', 'synthetic-native', '--postgres', 'synthetic-db',
                            '--native-image', 'sha256:' + 'a' * 64]
                result = subprocess.run(command, capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('operator lock', result.stderr)
            self.assertFalse((root / 'output').exists())

    def test_paused_and_other_runtime_state_flags_are_observed(self):
        original = self.row()
        changed = json.loads(json.dumps(original))
        changed['State']['Paused'] = True
        current = stage.canonical_container(changed)
        self.assertNotEqual(stage.canonical_container(original), current)
        baseline = {'read_only': True, 'production_unchanged': True, 'app': current, 'worker': current, 'compose_sha256': 'hash'}
        with self.assertRaisesRegex(RuntimeError, 'BASELINE_CONTAINER_NOT_READY'):
            stage.validate_baseline(baseline, {'app': current, 'worker': current}, 'app', 'worker', 'hash')
        for flag in ('Restarting', 'Dead', 'OOMKilled', 'ExitCode'):
            changed = self.row()
            changed['State'][flag] = 1
            self.assertNotEqual(stage.canonical_container(original), stage.canonical_container(changed))

    def test_typo_lock_path_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = [sys.executable, spec.origin]
            for name in ('repo', 'source', 'compose', 'baseline', 'output', 'lock-file'):
                command += ['--' + name, str(root / name)]
            command += ['--revision', 'a' * 40, '--app', 'synthetic', '--worker', 'synthetic',
                        '--native', 'synthetic', '--postgres', 'synthetic', '--native-image', 'sha256:' + 'a' * 64]
            result = subprocess.run(command, capture_output=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / 'lock-file').exists())
            self.assertFalse((root / 'output').exists())

    def test_native_watchdog_terminates_pid1_independently_of_docker(self):
        with tempfile.TemporaryDirectory() as directory:
            server = Path(directory) / 'synthetic-server.py'
            server.write_text('import time; time.sleep(30)')
            before = time.monotonic()
            result = subprocess.run([sys.executable, '-c', stage.native_watchdog(time.monotonic() + 2, str(server))], capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 124)
            self.assertLess(time.monotonic() - before, 4)
            result = subprocess.run([sys.executable, '-c', stage.native_watchdog(time.monotonic() - 1, str(server))], capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 124)

    def test_daemon_failure_waits_for_watchdog_before_native_shutdown_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = stage.Stage(SimpleNamespace(), Path(directory))
            instance.native_name = 'synthetic-native'
            instance.owned = ['synthetic-native']
            instance.native_deadline_monotonic = 10
            clock = [0]
            def sleep(seconds):
                clock[0] += seconds
            with patch.object(stage.subprocess, 'run', side_effect=OSError('synthetic daemon unavailable')), patch.object(stage.time, 'monotonic', side_effect=lambda: clock[0]), patch.object(stage.time, 'sleep', side_effect=sleep), patch('builtins.print'):
                with self.assertRaisesRegex(RuntimeError, 'NATIVE_SHUTDOWN_UNVERIFIED_AFTER_WATCHDOG'):
                    instance.ensure_native_stopped()
            self.assertGreater(clock[0], 15)
            self.assertEqual(instance.owned, ['synthetic-native'])

    def test_native_kill_is_verified_before_cleanup_can_release_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = stage.Stage(SimpleNamespace(), Path(directory))
            instance.native_name = 'synthetic-native'
            calls = []
            def command(args, **kwargs):
                calls.append(args)
                if args[1] == 'inspect':
                    return SimpleNamespace(returncode=0, stdout=b'[{"State":{"Running":false}}]', stderr=b'')
                return SimpleNamespace(returncode=1 if args[1] == 'rm' else 0, stdout=b'', stderr=b'')
            with patch.object(stage.subprocess, 'run', side_effect=command):
                instance.ensure_native_stopped()
            self.assertTrue(any(item[1] == 'kill' for item in calls))
            self.assertEqual(calls[-1][1], 'inspect')

    def test_before_after_evidence_is_retained_on_failed_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / 'baseline.json'
            baseline.write_text('{}')
            baseline.chmod(0o600)
            args = SimpleNamespace(revision='a' * 40, native_image='sha256:' + 'b' * 64,
                                   repo=root, source=root, compose=root / 'compose', baseline=baseline,
                                   output=root / 'evidence', app='synthetic', worker='synthetic')
            fingerprint = {'containers': {}, 'compose': 'hash', 'source': 'hash'}
            with patch.object(stage.Stage, 'fingerprint', return_value=fingerprint), patch.object(stage.Stage, 'cleanup', return_value=[]), patch('builtins.print'):
                with self.assertRaises(SystemExit):
                    stage.stage_main(args)
            release = next(args.output.iterdir())
            for name in ('before.json', 'after.json'):
                self.assertEqual(json.loads((release / name).read_text()), fingerprint)
            self.assertFalse(json.loads((release / 'result.json').read_text())['passed'])

    def test_sigterm_raises_controlled_failure_and_unwinds(self):
        code = """import importlib.util,os,signal
spec=importlib.util.spec_from_file_location('stage', %r)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
try:
 with m.termination_handler():
  try: os.kill(os.getpid(),signal.SIGTERM)
  finally: print('UNWOUND',flush=True)
except RuntimeError as exc:
 print(str(exc),flush=True)
""" % spec.origin
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), ['UNWOUND', 'STAGE_TERMINATED'])

    def test_build_removes_intermediate_containers_on_failure(self):
        source = Path(spec.origin).read_text()
        self.assertIn("stage.run('docker', 'build', '--force-rm'", source)

    def test_native_shutdown_window_cannot_be_interrupted_by_ctrl_c(self):
        import os
        import signal
        before = signal.getsignal(signal.SIGINT)
        with stage.uninterrupted_cleanup():
            os.kill(os.getpid(), signal.SIGINT)
            self.assertEqual(signal.getsignal(signal.SIGINT), signal.SIG_IGN)
        self.assertEqual(signal.getsignal(signal.SIGINT), before)

    def test_terminal_group_interrupt_cannot_release_admission_client(self):
        code = r'''import importlib.util,os,signal,subprocess,sys,time
spec=importlib.util.spec_from_file_location('stage', %r)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
real_popen=subprocess.Popen
child="import signal,sys; signal.signal(signal.SIGINT,signal.SIG_DFL); print('LOCKED',flush=True); sys.stdin.buffer.read()"
def synthetic_client(command,**kwargs):
 return real_popen([sys.executable,'-c',child],**kwargs)
m.subprocess.Popen=synthetic_client
signal.signal(signal.SIGINT,signal.SIG_IGN)
with m.cpu_slot('synthetic') as client:
 os.killpg(os.getpgrp(),signal.SIGINT)
 time.sleep(.1)
 assert client.poll() is None, 'admission received terminal interrupt'
print('HELD_UNTIL_EXPLICIT_RELEASE')
''' % spec.origin
        result = subprocess.run([sys.executable, '-c', code], capture_output=True,
                                text=True, timeout=5, start_new_session=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'HELD_UNTIL_EXPLICIT_RELEASE')


if __name__ == '__main__':
    unittest.main()

