#!/usr/bin/env python3
"""Build and qualify an isolated web candidate. Never apply it to production.

Requires an operator-owned JSON baseline (the read-only readiness output), exact
revision, repository, Compose/source paths and existing container names. Native
and PostgreSQL images are reused by immutable ID; no live mounts or environment
are copied. Docker's legacy builder must support enforced CPU/memory limits.
"""
import argparse
import contextlib
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import signal
import stat
import subprocess
import tarfile
import time
import uuid


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical_container(row):
    return {'id': row['Id'], 'image_id': row['Image'],
            'running': row['State']['Running'], 'started_at': row['State']['StartedAt'],
            'state_flags': {key: row['State'].get(key) for key in ('Paused', 'Restarting', 'Dead', 'OOMKilled', 'ExitCode')},
            'mounts': sorted(row.get('Mounts', []), key=lambda item: json.dumps(item, sort_keys=True)),
            'mount_fingerprints': sorted(sha(json.dumps(item, sort_keys=True).encode()) for item in row.get('Mounts', [])),
            'networks': {name: {key: sorted(network.get(key) or []) if key in ('Aliases', 'DNSNames') else network.get(key) for key in
                              ('NetworkID', 'EndpointID', 'IPAddress', 'GlobalIPv6Address', 'Aliases', 'DNSNames')}
                         for name, network in sorted(row['NetworkSettings']['Networks'].items())}}


def source_fingerprint(root):
    entries = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            entries.append([str(path.relative_to(root)), 'link', os.readlink(path)])
        elif path.is_file():
            entries.append([str(path.relative_to(root)), sha(path.read_bytes())])
    return sha(json.dumps(entries, separators=(',', ':')).encode())


def unpack_source(data, target):
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            parts = Path(member.name).parts
            if member.name.startswith('/') or '..' in parts or not (member.isfile() or member.isdir()):
                raise RuntimeError('UNSUPPORTED_SOURCE_ARCHIVE_ENTRY')
        archive.extractall(target, filter='data')


def validate_baseline(baseline, observed, app, worker, compose_hash):
    if baseline.get('production_unchanged') is not True or baseline.get('read_only') is not True:
        raise RuntimeError('INVALID_READ_ONLY_BASELINE')
    for key, name in (('app', app), ('worker', worker)):
        expected = baseline.get(key) or {}
        current = observed.get(name) or {}
        for field in ('id', 'image_id', 'started_at', 'running'):
            if field not in expected or expected[field] != current.get(field):
                raise RuntimeError('BASELINE_CONTAINER_CHANGED')
        if expected.get('mount_fingerprints') != current.get('mount_fingerprints'):
            raise RuntimeError('BASELINE_MOUNTS_CHANGED')
        if any(current.get('state_flags', {}).get(key) for key in ('Paused', 'Restarting', 'Dead')):
            raise RuntimeError('BASELINE_CONTAINER_NOT_READY')
        if not current['running']:
            raise RuntimeError('BASELINE_CONTAINER_NOT_RUNNING')
    if baseline.get('compose_sha256') != compose_hash:
        raise RuntimeError('BASELINE_COMPOSE_CHANGED')


def native_watchdog(deadline, server='/work/server.py'):
    return ("import os,signal,time,math,runpy; "
            "signal.signal(signal.SIGALRM,lambda *_: os._exit(124)); "
            "remaining=math.floor(" + str(float(deadline)) + "-time.monotonic()); "
            "remaining>0 or os._exit(124); signal.alarm(remaining); "
            "runpy.run_path(" + repr(server) + ",run_name='__main__')")


def limits(name, network, user, memory='512m', cpus='1'):
    return ['--name', name, '--pull', 'never', '--network', network, '--user', user,
            '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--cpus', cpus, '--memory', memory, '--memory-swap', memory,
            '--pids-limit', '128', '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m,mode=1777']


# Connection details stay inside the existing application container. This only
# owns the same cooperative session-level CPU lock as production local work.
SLOT_CODE = r"""
const {Client}=require('pg');
const c=new Client({connectionString:process.env.DATABASE_URL,connectionTimeoutMillis:5000});
(async()=>{try{
 await c.connect();
 const r=await c.query('SELECT pg_try_advisory_lock($1::bigint) AS locked',['6194261933202610']);
 if(r.rows[0]?.locked!==true)throw Error('BUSY');
 console.log('LOCKED');
 let lease;
 await new Promise(resolve=>{lease=setTimeout(()=>process.exit(1),900000);process.stdin.once('data',resolve);process.stdin.once('end',resolve);process.stdin.resume();});
 await c.query('SELECT pg_advisory_unlock($1::bigint)',['6194261933202610']);
 await c.end();
 clearTimeout(lease);
}catch{console.log('UNAVAILABLE');await c.end().catch(()=>{});process.exitCode=1;}})();
"""


@contextlib.contextmanager
def cpu_slot(app):
    process = subprocess.Popen(['docker', 'exec', '-i', app, 'node', '-e', SLOT_CODE],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               start_new_session=True)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            if not selector.select(10) or process.stdout.readline().strip() != b'LOCKED':
                raise RuntimeError('SHARED_CPU_SLOT_UNAVAILABLE')
        process.lease_deadline = time.monotonic() + 840
        process.native_deadline_monotonic = time.monotonic() + 780
        yield process
        if process.poll() is not None:
            raise RuntimeError('SHARED_CPU_SLOT_LOST')
    finally:
        if process.stdin:
            with contextlib.suppress(BrokenPipeError):
                process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


class Stage:
    def __init__(self, args, release):
        self.args, self.release = args, release
        self.owned, self.network = [], None
        self.sequence = 0
        self.slot = None
        self.native_name = None
        self.native_deadline_monotonic = None

    def check_slot(self):
        if self.slot is not None:
            if self.slot.poll() is not None:
                raise RuntimeError('SHARED_CPU_SLOT_LOST')
            if time.monotonic() >= getattr(self.slot, 'lease_deadline', 0):
                raise RuntimeError('SHARED_CPU_SLOT_DEADLINE')

    def run(self, *command, data=None, timeout=30, environment=None):
        self.check_slot()
        self.sequence += 1
        process = subprocess.Popen(command, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
        deadline = time.monotonic() + timeout
        first = True
        heartbeat = time.monotonic() + 20
        try:
            while True:
                self.check_slot()
                if time.monotonic() >= heartbeat:
                    print('Stage step ' + str(self.sequence) + ' is still running; production remains unchanged.', flush=True)
                    heartbeat = time.monotonic() + 20
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError('STAGE_COMMAND_TIMEOUT_' + str(self.sequence))
                try:
                    stdout, stderr = process.communicate(input=data if first else None, timeout=min(5, remaining))
                    break
                except subprocess.TimeoutExpired:
                    first = False
            if process.returncode:
                (self.release / f'command-{self.sequence}-stderr.log').write_bytes(stderr)
                raise RuntimeError('STAGE_COMMAND_FAILED_' + str(self.sequence))
            return stdout
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def inspect(self, name):
        return json.loads(self.run('docker', 'inspect', name))[0]

    def snapshot(self):
        names = self.run('docker', 'ps', '-aq').decode().split()
        rows = json.loads(self.run('docker', 'inspect', *names)) if names else []
        return {row['Name'].lstrip('/'): canonical_container(row) for row in rows
                if row['Name'].lstrip('/') not in self.owned}

    def fingerprint(self):
        return {'containers': self.snapshot(), 'compose': sha(self.args.compose.read_bytes()),
                'source': source_fingerprint(self.args.source)}

    def start(self, name, *arguments):
        self.owned.append(name)
        return self.run('docker', 'run', *arguments)

    def ensure_native_stopped(self):
        """Do not release cooperative admission while an isolated model can run.

        An absolute monotonic-deadline PID1 watchdog is armed independently of the Docker
        daemon. If daemon operations cannot verify shutdown, hold the lease past
        that deadline and fail qualification rather than claiming cleanup.
        """
        name = self.native_name
        if not name:
            return
        with contextlib.suppress(Exception):
            logs = subprocess.run(['docker', 'logs', name], capture_output=True, timeout=3)
            (self.release / (name + '.log')).write_bytes(logs.stdout + logs.stderr)
        for attempt in range(2):
            try:
                removed = subprocess.run(['docker', 'rm', '-fv', name], capture_output=True, timeout=8)
                if removed.returncode == 0:
                    self.owned = [item for item in self.owned if item != name]
                    self.native_name = None
                    return
            except Exception:
                pass
            try:
                subprocess.run(['docker', 'kill', '--signal', 'KILL', name], capture_output=True, timeout=5)
                observed = subprocess.run(['docker', 'inspect', name], capture_output=True, timeout=5)
                if observed.returncode == 0 and json.loads(observed.stdout)[0]['State']['Running'] is False:
                    return
                if observed.returncode and (b'No such object' in observed.stderr or b'No such container' in observed.stderr):
                    self.owned = [item for item in self.owned if item != name]
                    self.native_name = None
                    return
            except Exception:
                pass
        # The native PID1 watchdog deadline is fixed when the slot is acquired,
        # not when Docker eventually starts the container. Delayed creation
        # therefore cannot extend its runtime past the lease's safety reserve.
        if self.native_deadline_monotonic is None:
            raise RuntimeError('NATIVE_WATCHDOG_NOT_ARMED')
        while time.monotonic() <= self.native_deadline_monotonic + 5:
            print('Waiting for the isolated model shutdown watchdog; the CPU slot remains held.', flush=True)
            time.sleep(min(20, max(.1, self.native_deadline_monotonic + 5 - time.monotonic())))
        raise RuntimeError('NATIVE_SHUTDOWN_UNVERIFIED_AFTER_WATCHDOG')

    def cleanup(self):
        errors, remaining = [], []
        # Remove the model first while the CPU slot is still held. Failure to
        # collect diagnostics must never prevent any removal or token cleanup.
        order = sorted(reversed(self.owned), key=lambda name: not name.endswith('-ner'))
        for name in order:
            try:
                logs = subprocess.run(['docker', 'logs', name], capture_output=True, timeout=3)
                (self.release / (name + '.log')).write_bytes(logs.stdout + logs.stderr)
            except Exception:
                pass
            try:
                result = subprocess.run(['docker', 'rm', '-fv', name], capture_output=True, timeout=30)
                if result.returncode:
                    raise RuntimeError('REMOVE_FAILED')
            except Exception:
                errors.append('CONTAINER_REMOVAL_FAILED')
                remaining.append(name)
        self.owned = remaining
        if self.network:
            try:
                result = subprocess.run(['docker', 'network', 'rm', self.network], capture_output=True, timeout=20)
                if result.returncode:
                    raise RuntimeError('REMOVE_FAILED')
                self.network = None
            except Exception:
                errors.append('NETWORK_REMOVAL_FAILED')
        for name in ('app.env', 'postgres.env', 'input/service-token'):
            try:
                (self.release / name).unlink(missing_ok=True)
            except Exception:
                errors.append('SECRET_REMOVAL_FAILED')
        return errors

    def qualify(self, image, native_image, postgres_image):
        work = self.release / 'input'
        work.mkdir(mode=0o755)
        work.chmod(0o755)
        for source, name in [('services/privacy-ner/server.py', 'server.py'),
                             ('lib/privacy-ner-core.py', 'privacy-ner-core.py'),
                             ('tests/privacy-api.integration.mjs', 'api-test.mjs')]:
            path = work / name
            path.write_bytes(self.run('git', '-C', str(self.args.repo), 'show', self.args.revision + ':' + source))
            path.chmod(0o644)
        token = work / 'service-token'
        token.write_text(secrets.token_hex(32))
        token.chmod(0o444)
        password = secrets.token_hex(24)
        env = self.release / 'app.env'
        env.write_text('\n'.join(['DATABASE_URL=postgres://vector_privacy_test:' + password + '@privacy-test-db:5432/vector_privacy_api_test',
                                 'VECTOR_SECRET=' + secrets.token_hex(32), 'FILE_ENCRYPTION_KEY=' + secrets.token_hex(32),
                                 'VECTOR_PRIVACY_TEST_PASSWORD=' + secrets.token_hex(24),
                                 'VECTOR_PRIVACY_API_EVALUATION=1', 'VECTOR_PRIVACY_REVIEW=1', 'VECTOR_LOCAL_WORKERS=1',
                                 'FILE_STORAGE_PATH=/tmp/vector-privacy-api-files', 'COOKIE_SECURE=false',
                                 'HOSTNAME=0.0.0.0', 'PORT=3000', 'NEXT_TELEMETRY_DISABLED=1']) + '\n')
        pg_env = self.release / 'postgres.env'
        pg_env.write_text('POSTGRES_USER=vector_privacy_test\nPOSTGRES_PASSWORD=' + password + '\nPOSTGRES_DB=vector_privacy_api_test\nPGDATA=/var/lib/postgresql/data/pgdata\n')
        suffix = uuid.uuid4().hex[:12]
        network = 'vector-web-stage-' + suffix
        self.run('docker', 'network', 'create', '--internal', network)
        self.network = network
        pg_name, ner_name, app_name = [network + '-' + item for item in ('db', 'ner', 'app')]
        self.start(pg_name, '--detach', *limits(pg_name, network, 'postgres'), '--network-alias', 'privacy-test-db',
                   '--env-file', str(pg_env), '--tmpfs', '/var/lib/postgresql/data:rw,nosuid,nodev,size=512m,mode=1777',
                   '--tmpfs', '/var/run/postgresql:rw,nosuid,nodev,size=16m,mode=1777', postgres_image,
                   'postgres', '-c', 'shared_buffers=32MB', '-c', 'max_connections=30')
        for attempt in range(80):
            self.check_slot()
            result = subprocess.run(['docker', 'exec', pg_name, 'pg_isready', '-U', 'vector_privacy_test'], capture_output=True, timeout=5)
            if result.returncode == 0:
                break
            time.sleep(.25)
        else:
            raise RuntimeError('DISPOSABLE_DATABASE_NOT_READY')
        self.check_slot()
        self.native_name = ner_name
        self.native_deadline_monotonic = self.slot.native_deadline_monotonic
        watchdog = native_watchdog(self.slot.native_deadline_monotonic)
        self.start(ner_name, '--detach', *limits(ner_name, network, '65534:65534', '4g', '2'),
                   '--network-alias', 'vector-privacy-ner', '--mount', f'type=bind,src={work},dst=/work,readonly',
                   '--mount', f'type=bind,src={token},dst=/run/secrets/vector_privacy_ner_token,readonly',
                   '--env', 'HF_HOME=/tmp/hf', '--env', 'HF_HUB_OFFLINE=1', '--env', 'TRANSFORMERS_OFFLINE=1',
                   '--env', 'TOKENIZERS_PARALLELISM=false', '--env', 'VECTOR_PRIVACY_NER_IDLE_SECONDS=3',
                   '--entrypoint', 'python', native_image, '-c', watchdog)
        self.start(app_name, '--detach', *limits(app_name, network, '1001:1001', '1g'),
                   '--network-alias', 'privacy-test-app', '--env-file', str(env),
                   '--mount', f'type=bind,src={token},dst=/run/secrets/vector_privacy_ner_token,readonly',
                   '--workdir', '/app', '--entrypoint', 'node', image, 'server.js')
        results = {}
        for phase in ('normal', 'outage'):
            if phase == 'outage':
                self.run('docker', 'stop', '--time', '10', ner_name)
            name = network + '-client-' + phase
            # API qualification can take several native scans; retain one bounded matrix.
            self.owned.append(name)
            output = self.run('docker', 'run', *limits(name, network, '1001:1001'), '--env-file', str(env),
                              '--env', 'VECTOR_PRIVACY_API_PHASE=' + phase,
                              '--mount', f'type=bind,src={work},dst=/work,readonly', '--workdir', '/app',
                              '--entrypoint', 'node', image, '/work/api-test.mjs', timeout=600 if phase == 'normal' else 150)
            results[phase] = json.loads(output)
            if results[phase].get('passed') is not True or results[phase].get('executed_jobs') != 0 or results[phase].get('cloud_calls') != 0:
                raise RuntimeError('ISOLATED_PRIVACY_API_FAILED')
        for name in self.owned:
            if self.inspect(name)['HostConfig'].get('PortBindings'):
                raise RuntimeError('UNEXPECTED_PUBLISHED_PORT')
        if not json.loads(self.run('docker', 'network', 'inspect', network))[0]['Internal']:
            raise RuntimeError('NETWORK_NOT_INTERNAL')
        return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'source', 'compose', 'baseline', 'output', 'lock-file'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('revision', 'app', 'worker', 'postgres', 'native', 'native-image'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    if any(part.is_symlink() for part in (args.lock_file, *args.lock_file.parents)):
        raise SystemExit('Symlink lock paths are not supported.')
    descriptor = os.open(args.lock_file, os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid():
        os.close(descriptor)
        raise SystemExit('Existing operator lock must be a regular file owned by the executing user.')
    with os.fdopen(descriptor, 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another release operation holds the operator lock.')
        with termination_handler():
            stage_main(args)



@contextlib.contextmanager
def uninterrupted_cleanup():
    previous = {sig: signal.signal(sig, signal.SIG_IGN) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


@contextlib.contextmanager
def termination_handler():
    previous = signal.getsignal(signal.SIGTERM)
    def terminate(signum, frame):
        # A repeated termination request must not interrupt cleanup midway.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        raise RuntimeError('STAGE_TERMINATED')
    signal.signal(signal.SIGTERM, terminate)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)

def stage_main(args):
    if not re.fullmatch('[a-f0-9]{40}', args.revision) or not re.fullmatch('sha256:[a-f0-9]{64}', args.native_image):
        raise SystemExit('Exact revision and native image ID required.')
    for path in (args.repo, args.source, args.compose, args.baseline, args.output):
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise SystemExit('Symlink paths are not supported.')
    if args.baseline.stat().st_mode & 0o077:
        raise SystemExit('Baseline must be private (mode 0600).')
    os.umask(0o077)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    release = args.output / ('web-stage-' + uuid.uuid4().hex)
    release.mkdir(mode=0o700)
    stage = Stage(args, release)
    report = {'passed': False, 'production_activated': False, 'messages_sent': 0, 'cloud_calls': 0, 'revision': args.revision}
    before = None
    print('Private stage evidence: ' + str(release), flush=True)
    try:
        before = stage.fingerprint()
        (release / 'before.json').write_text(json.dumps(before, indent=2) + '\n')
        baseline = json.loads(args.baseline.read_text())
        validate_baseline(baseline, before['containers'], args.app, args.worker, before['compose'])
        for relative, expected in baseline.get('host_source_hashes', {}).items():
            if relative.startswith('/') or '..' in Path(relative).parts:
                raise RuntimeError('INVALID_BASELINE_SOURCE_PATH')
            path = args.source / relative
            actual = sha(path.read_bytes()) if path.is_file() and not path.is_symlink() else None
            if actual != expected:
                raise RuntimeError('BASELINE_SOURCE_CHANGED')
        native = stage.inspect(args.native)
        if native['Image'] != args.native_image or not native['State']['Running']:
            raise RuntimeError('NATIVE_BASELINE_CHANGED')
        postgres_image = stage.inspect(args.postgres)['Image']
        stage.run('git', '-C', str(args.repo), 'cat-file', '-e', args.revision + '^{commit}')
        context = release / 'source'
        context.mkdir()
        unpack_source(stage.run('git', '-C', str(args.repo), 'archive', '--format=tar', args.revision), context)
        dockerfile = (context / 'Dockerfile').read_text()
        if any(line.startswith('FROM ') and line.split()[1] != 'node:24-alpine' for line in dockerfile.splitlines()):
            raise RuntimeError('UNEXPECTED_BUILD_BASE')
        base = json.loads(stage.run('docker', 'image', 'inspect', 'node:24-alpine'))[0]['Id']
        (context / 'Dockerfile.stage').write_text(dockerfile.replace('FROM node:24-alpine', 'FROM ' + base))
        image_tag = 'vector-web-stage:' + release.name
        environment = dict(os.environ, DOCKER_BUILDKIT='0')
        print('Build with two CPUs and 4 GiB maximum; unsupported limits fail closed.', flush=True)
        stage.run('docker', 'build', '--force-rm', '--pull=false', '--memory', '4g', '--memory-swap', '4g',
                  '--cpu-period', '100000', '--cpu-quota', '200000', '-f', str(context / 'Dockerfile.stage'),
                  '-t', image_tag, str(context), timeout=1200, environment=environment)
        image = json.loads(stage.run('docker', 'image', 'inspect', image_tag))[0]['Id']
        report.update(image_id=image, image_tag=image_tag, base_image_id=base)
        print('Run one isolated native privacy matrix under the shared CPU slot.', flush=True)
        with cpu_slot(args.app) as slot:
            stage.slot = slot
            try:
                report['qualification'] = stage.qualify(image, args.native_image, postgres_image)
            finally:
                # Destroy the model-bearing test container before releasing the
                # shared CPU slot, including on assertions or interrupted scans.
                with uninterrupted_cleanup():
                    shutdown_error = None
                    try:
                        stage.ensure_native_stopped()
                    except Exception as exc:
                        shutdown_error = exc
                    report['cleanup_errors'] = stage.cleanup()
                    if shutdown_error is not None:
                        raise shutdown_error
                    if report['cleanup_errors']:
                        raise RuntimeError('ISOLATED_CLEANUP_FAILED')
        stage.slot = None
        report['passed'] = True
    except Exception as exc:
        report['error'] = str(exc) if type(exc) is RuntimeError else type(exc).__name__
    finally:
        stage.slot = None
        try:
            report['cleanup_errors'] = report.get('cleanup_errors', []) + stage.cleanup()
            report['cleanup_verified'] = not report['cleanup_errors']
        except Exception:
            report['cleanup_verified'] = False
        try:
            after = stage.fingerprint()
            report['production_unchanged'] = before is not None and after == before
        except Exception as exc:
            after = {'snapshot_error': type(exc).__name__}
            report['production_unchanged'] = False
        (release / 'after.json').write_text(json.dumps(after, indent=2) + '\n')
        report['passed'] = report['passed'] and report['cleanup_verified'] and report['production_unchanged']
        (release / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if not report['passed']:
        raise SystemExit('Stage failed; no live apply was attempted.')
    print('Candidate retained; no production container or configuration was changed.')


if __name__ == '__main__':
    main()

