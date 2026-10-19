#!/usr/bin/env python3
"""Apply an operator-pinned, already qualified web image; never build or pull.

Private JSON provides all host identities. Evidence contains private canonical
Compose configuration and must remain on the operator's host.
"""
import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import time
import uuid


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe(path, regular=False):
    path = Path(path)
    require(path.is_absolute(), 'ABSOLUTE_PATH_REQUIRED')
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'SYMLINK_PATH')
    if regular:
        require(path.is_file(), 'REGULAR_FILE_REQUIRED')
    return path


def read_json(path):
    return json.loads(safe(path, True).read_text())


def atomic(path, data, mode=0o600):
    path = safe(path)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temp.unlink(missing_ok=True)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def candidate_profile(original, service, image):
    result = json.loads(json.dumps(original))
    app = result['services'][service]
    app['image'] = image
    app.setdefault('environment', {})['HOSTNAME'] = '0.0.0.0'
    return result


def compose_bytes(profile):
    # Compose interpolates even JSON strings. Literal dollars must survive a
    # serialize/reparse round trip without expanding host environment secrets.
    return (json.dumps(profile, indent=2).replace('$', '$$') + '\n').encode()


def validate_stage(report, before, after, config):
    require(report.get('passed') is True and report.get('cleanup_verified') is True
            and report.get('production_unchanged') is True, 'STAGE_NOT_QUALIFIED')
    require(report.get('production_activated') is False, 'STAGE_ALREADY_ACTIVATED')
    require(report.get('revision') == config['revision'] and report.get('image_id') == config['image_id'], 'STAGE_IDENTITY_MISMATCH')
    require(before == after, 'STAGE_BASELINE_CHANGED')
    for phase in ('normal', 'outage'):
        value = report.get('qualification', {}).get(phase, {})
        require(value.get('passed') is True and value.get('executed_jobs') == 0
                and value.get('cloud_calls') == 0, 'STAGE_MATRIX_INCOMPLETE')
    require(before.get('compose') == config['expected_compose_sha256'], 'COMPOSE_BASELINE_MISMATCH')
    expected = config['expected_app']
    observed = before.get('containers', {}).get(config['app'], {})
    require(all(observed.get(k) == expected[k] for k in ('id', 'image_id', 'started_at')), 'APP_BASELINE_MISMATCH')
    require(config['worker'] in before.get('containers', {}), 'WORKER_BASELINE_MISSING')


def others_unchanged(before, after, app):
    return {k: v for k, v in before.items() if k != app} == {k: v for k, v in after.items() if k != app}


def validate_config(config):
    require(config.get('schema') == 1, 'CONFIG_SCHEMA')
    for key in ('repo', 'stage', 'compose', 'project_directory', 'source', 'output', 'lock_file'):
        safe(config[key])
    require(re.fullmatch('[a-f0-9]{40}', config['revision']), 'REVISION_REQUIRED')
    require(re.fullmatch('sha256:[a-f0-9]{64}', config['image_id']), 'IMAGE_ID_REQUIRED')
    for key in ('project', 'service', 'app', 'worker'):
        require(re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.-]*', config[key]), 'INVALID_COMPOSE_IDENTITY')
    from urllib.parse import urlsplit
    url = urlsplit(config['public_url'])
    require(url.scheme == 'https' and url.hostname and not url.username and not url.password
            and url.port in (None, 443) and not url.query and not url.fragment, 'HTTPS_URL_REQUIRED')
    require(isinstance(config['host_port'], int) and 1 <= config['host_port'] <= 65535, 'HOST_PORT_REQUIRED')
    require(Path(config['source']).parent.stat().st_dev == Path(config['output']).stat().st_dev, 'SOURCE_BACKUP_FILESYSTEM_MISMATCH')


JOBS = r"""const {Client}=require('pg');
(async()=>{const c=new Client({connectionString:process.env.DATABASE_URL,connectionTimeoutMillis:5000});
try{await c.connect();await c.query('BEGIN READ ONLY');
const r=await c.query("SELECT count(*)::int AS n FROM agent_jobs WHERE status IN ('queued','running')");
console.log(JSON.stringify({idle:r.rows[0].n===0}));await c.query('ROLLBACK');}
catch{process.exitCode=1;}finally{await c.end();}})();"""


class Release:
    def __init__(self, config, directory):
        self.c = config
        self.directory = Path(directory)
        self.state_path = self.directory / 'state.json'
        self.state = {}
        self.sequence = 0
        spec = importlib.util.spec_from_file_location('qualified_stage', Path(__file__).with_name('stage-web-recovery.py'))
        self.shared = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.shared)

    def run(self, *args, timeout=40, data=None):
        self.sequence += 1
        result = subprocess.run(list(map(str, args)), input=data, capture_output=True, timeout=timeout)
        if result.returncode:
            atomic(self.directory / ('command-' + str(self.sequence) + '.stderr'), result.stderr)
            raise RuntimeError('COMMAND_FAILED_' + str(self.sequence))
        return result.stdout

    def inspect(self, name):
        return json.loads(self.run('docker', 'inspect', name))[0]

    def snapshot(self):
        ids = self.run('docker', 'ps', '-aq').decode().split()
        rows = json.loads(self.run('docker', 'inspect', *ids)) if ids else []
        return {r['Name'].lstrip('/'): self.shared.canonical_container(r) for r in rows}

    def compose(self, path, *args, timeout=40):
        return self.run('docker', 'compose', '--project-name', self.c['project'],
                        '--project-directory', self.c['project_directory'], '-f', path, *args, timeout=timeout)

    def profile(self, path):
        return json.loads(self.compose(path, 'config', '--format', 'json'))

    def config_hash(self, path):
        output = self.compose(path, 'config', '--hash', self.c['service']).decode().split()
        require(output and re.fullmatch('[a-f0-9]{64}', output[-1]), 'CONFIG_HASH_UNAVAILABLE')
        return output[-1]

    def labels(self, row, config_hash):
        labels = row['Config'].get('Labels') or {}
        expected = {'com.docker.compose.project': self.c['project'],
                    'com.docker.compose.service': self.c['service'],
                    'com.docker.compose.project.working_dir': self.c['project_directory'],
                    'com.docker.compose.config-hash': config_hash}
        require(all(labels.get(k) == value for k, value in expected.items()), 'CONTAINER_COMPOSE_IDENTITY_MISMATCH')
        files = labels.get('com.docker.compose.project.config_files', '').split(',')
        require(files == [self.c['compose']], 'MULTIPLE_OR_FOREIGN_COMPOSE_FILES')

    def save(self, **values):
        self.state.update(values)
        atomic(self.state_path, (json.dumps(self.state, indent=2) + '\n').encode())
        if values.get('status'):
            print('Release step: ' + values['status'], flush=True)

    def idle(self):
        result = json.loads(self.run('docker', 'exec', self.c['app'], 'node', '-e', JOBS, timeout=15))
        require(result == {'idle': True}, 'ACTIVE_AGENT_JOBS_NO_RELEASE')

    def healthy(self, image, config_hash):
        row = self.inspect(self.c['app'])
        require(row['Image'] == image and row['State']['Running'] and not row['State'].get('OOMKilled'), 'APP_NOT_HEALTHY')
        self.labels(row, config_hash)
        from urllib.parse import urlsplit
        host = urlsplit(self.c['public_url']).hostname
        # Next must listen on every attached interface, including loopback.
        hosts = ['127.0.0.1'] + [v['IPAddress'] for v in row['NetworkSettings']['Networks'].values() if v.get('IPAddress')]
        probe = r"""const http=require('node:http');let left=JSON.parse(process.argv[1]);
(async()=>{for(const host of left)await new Promise((resolve,reject)=>{
const r=http.get({host,port:3000,path:'/api/health',timeout:4000},s=>{s.resume();s.statusCode===200?resolve():reject(Error('HTTP'));});
r.on('timeout',()=>r.destroy(Error('TIMEOUT')));r.on('error',reject);});})().catch(()=>process.exitCode=1);"""
        self.run('docker', 'exec', self.c['app'], 'node', '-e', probe, json.dumps(hosts), timeout=25)
        for args in (['http://127.0.0.1:' + str(self.c['host_port']) + '/api/health'],
                     ['--resolve', host + ':443:127.0.0.1', self.c['public_url'].rstrip('/') + '/api/health'],
                     [self.c['public_url'].rstrip('/') + '/api/health']):
            status = self.run('curl', '--silent', '--show-error', '--fail', '--max-time', '12',
                              '--output', '/dev/null', '--write-out', '%{http_code}', *args, timeout=15)
            require(status == b'200', 'HTTP_HEALTH_FAILED')
        # Existing database/cache health must remain as observed; no probes with
        # credentials or SQL writes are introduced here.
        return row

    def wait_healthy(self, image, config_hash):
        deadline = time.monotonic() + 100
        while True:
            try:
                return self.healthy(image, config_hash)
            except Exception:
                if time.monotonic() >= deadline:
                    raise RuntimeError('APP_READINESS_DEADLINE')
                time.sleep(2)

    def export(self, destination):
        destination.mkdir(mode=0o700)
        archive = self.run('git', '-C', self.c['repo'], 'archive', '--format=tar', self.c['revision'], timeout=60)
        self.shared.unpack_source(archive, destination)

    def apply(self):
        print('Release step: validate_qualification_and_current_baseline', flush=True)
        c = self.c
        stage = Path(c['stage'])
        before = read_json(stage / 'before.json')
        validate_stage(read_json(stage / 'result.json'), before, read_json(stage / 'after.json'), c)
        observed = self.snapshot()
        require(all(observed.get(name) == before['containers'].get(name) for name in (c['app'], c['worker'])), 'APP_OR_WORKER_CHANGED_SINCE_STAGE')
        qualification_before = before
        before = dict(before, containers=observed)
        atomic(self.directory / 'qualification-baseline.json', (json.dumps(qualification_before, indent=2) + '\n').encode())
        require(sha(Path(c['compose']).read_bytes()) == before['compose'], 'COMPOSE_CHANGED_SINCE_STAGE')
        require(self.shared.source_fingerprint(Path(c['source'])) == before['source'], 'SOURCE_CHANGED_SINCE_STAGE')
        self.run('docker', 'image', 'inspect', c['image_id'])
        original = self.profile(c['compose'])
        original_hash = self.config_hash(c['compose'])
        self.labels(self.inspect(c['app']), original_hash)
        original_image = original['services'][c['service']]['image']
        require(json.loads(self.run('docker', 'image', 'inspect', original_image))[0]['Id'] == c['expected_app']['image_id'], 'ORIGINAL_IMAGE_PIN_CHANGED')
        require(not any(m.get('Destination') == c['source'] or m.get('Source') == c['source'] for m in self.inspect(c['app']).get('Mounts', [])), 'BOUND_SOURCE_NOT_SUPPORTED')
        self.idle()
        compose = Path(c['compose'])
        shutil.copy2(compose, self.directory / 'compose.original')
        candidate = candidate_profile(original, c['service'], c['image_id'])
        candidate_path = self.directory / 'compose.candidate.json'
        atomic(candidate_path, compose_bytes(candidate))
        require(self.profile(candidate_path) == candidate, 'CANDIDATE_COMPOSE_ROUNDTRIP_FAILED')
        new_hash = self.config_hash(candidate_path)
        source_new = self.directory / 'source.qualified'
        self.export(source_new)
        # Verify exported bytes independently against the qualified stage export.
        qualified = self.shared.source_fingerprint(source_new)
        exported_stage = stage / 'source'
        # Stage adds Dockerfile.stage locally; compare all Git-exported entries.
        require(all((exported_stage / p.relative_to(source_new)).is_file()
                    and (exported_stage / p.relative_to(source_new)).read_bytes() == p.read_bytes()
                    for p in source_new.rglob('*') if p.is_file()), 'QUALIFIED_SOURCE_MISMATCH')
        atomic(self.directory / 'config.json', (json.dumps(c, indent=2) + '\n').encode())
        atomic(self.directory / 'before.json', (json.dumps(before, indent=2) + '\n').encode())
        self.save(status='prepared', original_profile=original, candidate_profile=candidate,
                  original_hash=original_hash, candidate_hash=new_hash,
                  original_source=before['source'], qualified_source=qualified,
                  original_app=c['expected_app'], new_app=None,
                  source_mode=stat.S_IMODE(Path(c['source']).stat().st_mode),
                  source_uid=Path(c['source']).stat().st_uid, source_gid=Path(c['source']).stat().st_gid,
                  compose_mode=stat.S_IMODE(compose.stat().st_mode), compose_uid=compose.stat().st_uid,
                  compose_gid=compose.stat().st_gid, started_ns=time.time_ns())
        require(self.snapshot() == before['containers'], 'PRODUCTION_CHANGED_DURING_PREPARATION')
        require(sha(compose.read_bytes()) == c['expected_compose_sha256'] and self.shared.source_fingerprint(Path(c['source'])) == before['source'], 'FILES_CHANGED_DURING_PREPARATION')
        self.idle()
        self.save(status='source_move_pending')
        os.rename(c['source'], self.directory / 'source.original')
        self.save(status='source_saved')
        os.rename(source_new, c['source'])
        os.chown(c['source'], self.state['source_uid'], self.state['source_gid'])
        os.chmod(c['source'], self.state['source_mode'])
        self.save(status='source_updated')
        self.save(status='compose_update_pending')
        atomic(compose, candidate_path.read_bytes(), self.state['compose_mode'])
        os.chown(compose, self.state['compose_uid'], self.state['compose_gid'])
        self.save(status='recreation_started')
        self.compose(compose, 'up', '-d', '--no-deps', '--no-build', '--pull', 'never', c['service'], timeout=120)
        row = self.inspect(c['app'])
        require(row['Image'] == c['image_id'], 'RECREATED_IMAGE_MISMATCH')
        self.labels(row, new_hash)
        self.save(new_app={'id': row['Id'], 'image_id': row['Image'], 'started_at': row['State']['StartedAt'], 'config_hash': new_hash})
        print('Release step: verify_app_interfaces_and_https', flush=True)
        self.wait_healthy(c['image_id'], new_hash)
        require(others_unchanged(before['containers'], self.snapshot(), c['app']), 'OTHER_PRODUCTION_CONTAINER_CHANGED')
        require(self.profile(compose) == candidate and self.shared.source_fingerprint(Path(c['source'])) == qualified, 'DEPLOYED_FILES_CHANGED')
        self.save(status='deployed', verified=True)

    def rollback(self):
        c, s = self.c, self.state
        require(s.get('status') in ('source_move_pending', 'source_saved', 'source_updated', 'compose_update_pending', 'recreation_started', 'deployed', 'rollback_started'), 'RELEASE_NOT_ROLLBACKABLE')
        before = read_json(self.directory / 'before.json')
        require(others_unchanged(before['containers'], self.snapshot(), c['app']), 'ROLLBACK_OTHER_CONTAINERS_CHANGED')
        row = self.inspect(c['app'])
        generation = s.get('new_app') or s['original_app']
        require(row['Id'] == generation['id'], 'ROLLBACK_UNRECORDED_OR_FOREIGN_CONTAINER')
        require(row['Image'] == generation['image_id'], 'ROLLBACK_FOREIGN_IMAGE')
        expected_hash = generation.get('config_hash', s['candidate_hash'] if s.get('new_app') else s['original_hash'])
        self.labels(row, expected_hash)
        compose = Path(c['compose'])
        current_profile = self.profile(compose)
        expected_profile = s['original_profile'] if s['status'] in ('source_move_pending', 'source_saved', 'source_updated') else s['candidate_profile']
        if s['status'] == 'rollback_started':
            expected_profile = s['original_profile'] if s.get('rollback_files_restored') else s['candidate_profile']
        if s['status'] in ('compose_update_pending', 'rollback_started'):
            require(current_profile in (s['original_profile'], s['candidate_profile']), 'ROLLBACK_FOREIGN_COMPOSE')
        else:
            require(current_profile == expected_profile, 'ROLLBACK_FOREIGN_COMPOSE')
        require(json.loads(self.run('docker', 'image', 'inspect', s['original_profile']['services'][c['service']]['image']))[0]['Id'] == s['original_app']['image_id'], 'ROLLBACK_ORIGINAL_IMAGE_PIN_CHANGED')
        source = Path(c['source'])
        saved = self.directory / 'source.original'
        # Recover an atomic source restore that completed just before its journal
        # write. Both exact owned source trees must establish the transition.
        failed = self.directory / 'source.failed'
        restored_before_journal = (s['status'] == 'rollback_started' and not saved.exists()
            and source.is_dir() and failed.is_dir()
            and self.shared.source_fingerprint(source) == s['original_source']
            and self.shared.source_fingerprint(failed) == s['qualified_source'])
        if restored_before_journal:
            self.save(rollback_source_restored=True)
        require(saved.is_dir() or s['status'] == 'source_move_pending' or s.get('rollback_source_restored'), 'ORIGINAL_SOURCE_BACKUP_MISSING')
        if saved.exists():
            require(self.shared.source_fingerprint(saved) == s['original_source'], 'ORIGINAL_SOURCE_BACKUP_CHANGED')
        if source.exists():
            fingerprint = self.shared.source_fingerprint(source)
            allowed = s['original_source'] if s['status'] == 'source_move_pending' else s['qualified_source']
            if s.get('rollback_source_restored'):
                allowed = s['original_source']
            require(fingerprint == allowed, 'ROLLBACK_FOREIGN_SOURCE')
        original = self.directory / 'compose.original'
        require(self.profile(original) == s['original_profile'], 'ORIGINAL_COMPOSE_BACKUP_CHANGED')
        # The failed new app may be unavailable; its generation and the entire
        # other-container baseline are checked above. Never require it for recovery.
        self.save(status='rollback_started')
        if saved.exists():
            if source.exists():
                os.rename(source, self.directory / 'source.failed')
            os.rename(saved, source)
        self.save(rollback_source_restored=True)
        atomic(compose, original.read_bytes(), s['compose_mode'])
        os.chown(compose, s['compose_uid'], s['compose_gid'])
        self.save(rollback_files_restored=True)
        self.compose(compose, 'up', '-d', '--no-deps', '--no-build', '--pull', 'never', c['service'], timeout=120)
        restored = self.inspect(c['app'])
        require(restored['Image'] == s['original_app']['image_id'], 'ROLLBACK_RECREATED_IMAGE_MISMATCH')
        self.labels(restored, s['original_hash'])
        self.save(new_app={'id': restored['Id'], 'image_id': restored['Image'], 'started_at': restored['State']['StartedAt'], 'config_hash': s['original_hash']})
        print('Release step: verify_restored_app', flush=True)
        self.wait_healthy(s['original_app']['image_id'], s['original_hash'])
        require(others_unchanged(before['containers'], self.snapshot(), c['app']), 'ROLLBACK_OTHER_CONTAINERS_CHANGED')
        self.save(status='rolled_back', rollback_verified=True)


@contextlib.contextmanager
def protected_cleanup():
    previous = {sig: signal.signal(sig, signal.SIG_IGN) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--rollback', type=Path)
    args = parser.parse_args()
    require(bool(args.config) != bool(args.rollback), 'CHOOSE_CONFIG_OR_ROLLBACK')
    os.umask(0o077)
    config_path = safe(args.config if args.config else args.rollback / 'config.json', True)
    require(config_path.stat().st_uid == os.geteuid() and not config_path.stat().st_mode & 0o077, 'PRIVATE_OWNED_CONFIG_REQUIRED')
    config = read_json(config_path)
    validate_config(config)
    lock_path = safe(config['lock_file'], True)
    require(lock_path.stat().st_uid == os.geteuid(), 'OWNED_RELEASE_LOCK_REQUIRED')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.rollback:
            directory = safe(args.rollback)
        else:
            directory = Path(config['output']) / ('web-release-' + uuid.uuid4().hex)
            directory.mkdir(mode=0o700)
        if not args.rollback:
            for name in ('release-qualified-web.py', 'stage-web-recovery.py'):
                shutil.copy2(Path(__file__).with_name(name), directory / name)
            rollback = '#!/usr/bin/env bash\nset -Eeuo pipefail\nexec python3 ' + __import__('shlex').quote(str(directory / 'release-qualified-web.py')) + ' --rollback ' + __import__('shlex').quote(str(directory)) + '\n'
            atomic(directory / 'rollback.sh', rollback.encode(), 0o700)
        release = Release(config, directory)
        print('Private release evidence: ' + str(directory), flush=True)
        if args.rollback:
            release.state = read_json(directory / 'state.json')
            with protected_cleanup():
                release.rollback()
        else:
            def terminate(*_):
                raise RuntimeError('RELEASE_TERMINATED')
            signal.signal(signal.SIGTERM, terminate)
            try:
                release.apply()
            except BaseException:
                if release.state.get('status') not in (None, 'prepared'):
                    with protected_cleanup():
                        try:
                            release.rollback()
                        except Exception as error:
                            release.save(rollback_error=str(error) if type(error) is RuntimeError else type(error).__name__)
                            print('Automatic rollback could not be verified. Keep the private evidence.', flush=True)
                raise
        print(json.dumps({'status': release.state['status'], 'app_only': True,
                          'model_calls': 0, 'cloud_calls': 0, 'messages_sent': 0,
                          'release': str(directory)}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(str(error) if type(error) is RuntimeError else type(error).__name__)
