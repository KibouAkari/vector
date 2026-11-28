#!/usr/bin/env python3
"""Build a pinned web revision and replace only the existing Compose app.

No database backup, model request, scan, message, game or worker restart.
Private evidence stays on the operator host. Run through the existing runner.
"""
import argparse
import copy
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import time
import uuid
from urllib.parse import urlsplit


def require(value, code):
    if not value:
        raise RuntimeError(code)


def safe(value):
    path = Path(value)
    require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)), 'UNSAFE_PATH')
    return path


def digest(value):
    return hashlib.sha256(value).hexdigest()


def compose_bytes(profile):
    # Compose interpolates strings even when its input is JSON.
    return (json.dumps(profile, indent=2).replace('$', '$$') + '\n').encode()


def candidate_profile(original, service, image):
    profile = copy.deepcopy(original)
    app = profile['services'][service]
    app.pop('build', None)
    app['image'] = image
    app.setdefault('environment', {})['HOSTNAME'] = '0.0.0.0'
    return profile


def extract_source(archive, target):
    with tarfile.open(fileobj=io.BytesIO(archive)) as handle:
        members = handle.getmembers()
        require(sum(member.size for member in members) < 300_000_000, 'ARCHIVE_LIMIT')
        for member in members:
            name = PurePosixPath(member.name)
            require(not name.is_absolute() and '..' not in name.parts and
                    not member.issym() and not member.islnk() and
                    (member.isfile() or member.isdir()), 'UNSAFE_ARCHIVE')
            path = safe(target.joinpath(*name.parts))
            if member.isdir():
                path.mkdir(mode=0o700, parents=True, exist_ok=True)
            else:
                require(member.size <= 30_000_000, 'ARCHIVE_FILE_LIMIT')
                path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as output:
                    output.write(handle.extractfile(member).read())


def atomic(path, data, mode, uid, gid):
    temporary = safe(path.with_name('.vector-write-' + uuid.uuid4().hex))
    try:
        with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode), 'wb') as output:
            os.fchmod(output.fileno(), mode)
            os.fchown(output.fileno(), uid, gid)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


class Update:
    def __init__(self, args):
        self.args = args
        self.root = safe(args.workspace)
        self.repo = safe(self.root / 'github/vector')
        require(all(path.is_dir() for path in (self.root, self.repo, self.root / 'releases')), 'WORKSPACE_MISSING')
        require(re.fullmatch(r'[a-f0-9]{40}', args.revision), 'INVALID_REVISION')
        self.release = self.root / 'releases' / ('vector-operations-' + uuid.uuid4().hex)
        self.release.mkdir(mode=0o700)
        self.log = self.release / 'commands.log'
        self.lock = open(self.root / '.operations-update.lock', 'a')
        fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def run(self, command, timeout=30):
        result = subprocess.run(command, capture_output=True, timeout=timeout)
        if result.returncode:
            with self.log.open('ab') as output:
                output.write(result.stdout[-20000:] + result.stderr[-20000:])
            raise RuntimeError('COMMAND_FAILED_' + command[0])
        return result.stdout

    def inspect(self, name):
        return json.loads(self.run(['docker', 'inspect', name]))[0]

    def inventory(self):
        ids = self.run(['docker', 'ps', '-aq']).decode().split()
        rows = json.loads(self.run(['docker', 'inspect', *ids])) if ids else []
        return {row['Name'].lstrip('/'): (row['Id'], row['Image'], row['State']['StartedAt'], row['State']['Running']) for row in rows}

    def compose(self, path, *args):
        return ['docker', 'compose', '--project-directory', str(self.directory), '-p', self.project, '-f', str(path), *args]

    def profile(self, path):
        return json.loads(self.run(self.compose(path, 'config', '--format', 'json')))

    def others_unchanged(self):
        current = self.inventory()
        return {k: v for k, v in current.items() if k != self.args.app} == {k: v for k, v in self.before.items() if k != self.args.app}

    def verify_http(self, full=True):
        probe = r"""const http=require('node:http');const routes=process.argv[1]==='full'?['/api/health','/api/brain','/api/connections','/api/traffic','/api/teams']:['/api/health'];
(async()=>{const output={};for(const route of routes){const r=await new Promise((resolve,reject)=>{const q=http.get({host:'127.0.0.1',port:3000,path:route,timeout:4000},r=>{let body='';r.on('data',p=>body+=p);r.on('end',()=>resolve({status:r.statusCode,body}));});q.on('error',reject);q.on('timeout',()=>q.destroy(Error('timeout')));});if(route==='/api/health'){const health=JSON.parse(r.body);if(r.status!==200||health.database!=='ok'||health.redis!=='ok')throw Error('health');output.database=health.database;output.redis=health.redis;}else if(![401,403].includes(r.status))throw Error('anonymous access');}output.anonymous_access_blocked=true;console.log(JSON.stringify(output));})().catch(()=>process.exitCode=1);"""
        return json.loads(self.run(['docker', 'exec', self.args.app, 'node', '-e', probe, 'full' if full else 'health'], timeout=30))

    def apply(self):
        app = self.inspect(self.args.app)
        require(app['State']['Running'] and app['Config'].get('WorkingDir') == '/app', 'APP_NOT_READY')
        require(not any(m['Destination'] == '/app' or m['Destination'].startswith('/app/') for m in app.get('Mounts', [])), 'APP_SOURCE_MOUNTED')
        labels = app['Config'].get('Labels') or {}
        files = labels.get('com.docker.compose.project.config_files', '').split(',')
        require(len(files) == 1 and files[0], 'SINGLE_COMPOSE_FILE_REQUIRED')
        self.path = safe(files[0])
        self.directory = safe(labels['com.docker.compose.project.working_dir'])
        self.project = labels['com.docker.compose.project']
        self.service = labels['com.docker.compose.service']
        original = self.path.read_bytes()
        meta = self.path.stat()
        profile = self.profile(self.path)
        require(self.service in profile['services'], 'APP_SERVICE_MISSING')
        self.before = self.inventory()
        old_image = app['Image']
        self.run(['git', '-C', str(self.repo), 'cat-file', '-e', self.args.revision + '^{commit}'])
        source = self.release / 'source'
        source.mkdir(mode=0o700)
        extract_source(self.run(['git', '-C', str(self.repo), 'archive', self.args.revision], timeout=60), source)
        require((source / 'Dockerfile').is_file(), 'DOCKERFILE_MISSING')
        tag = 'vector-app:operations-' + self.args.revision[:12] + '-' + uuid.uuid4().hex[:8]
        command = ['docker', 'build', '--force-rm', '--pull=false', '--memory', '4g', '--memory-swap', '4g',
                   '--cpu-period', '100000', '--cpu-quota', '200000', '--label', 'org.opencontainers.image.revision=' + self.args.revision, '-t', tag, str(source)]
        print('Building pinned Vector ' + self.args.revision[:12] + '. No model calls or data backup.', flush=True)
        with self.log.open('ab') as output:
            build = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, env=dict(os.environ, DOCKER_BUILDKIT='0'))
            started = time.monotonic()
            while True:
                try:
                    code = build.wait(timeout=20)
                    break
                except subprocess.TimeoutExpired:
                    print('Image build running ... ' + str(int(time.monotonic()-started)) + ' s', flush=True)
                    if time.monotonic()-started > 1800:
                        build.terminate()
                        build.wait(timeout=15)
                        raise RuntimeError('BUILD_DEADLINE')
        require(code == 0, 'BUILD_FAILED_SEE_PRIVATE_LOG')
        image = self.inspect(tag)['Id']
        check = "const fs=require('node:fs'),a=require('node:assert');const m=JSON.parse(fs.readFileSync('.next/server/app-paths-manifest.json'));for(const p of ['/brain/page','/teams/page','/connections/page','/traffic/page','/api/brain/route','/api/traffic/route'])a.ok(m[p],p);a.ok(fs.existsSync('public/vector-assets/brand/vector-mark.svg'));console.log('Packaged routes and branding verified');"
        self.run(['docker', 'run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '128', '--memory', '512m', '--cpus', '1', '--entrypoint', 'node', image, '-e', check])
        candidate = candidate_profile(profile, self.service, image)
        if getattr(self.args,'traffic_key_file',None):
            key=safe(self.args.traffic_key_file).read_text().strip()
            require(len(key)>=32 and not any(ch.isspace() for ch in key),'INVALID_COLLECTOR_KEY')
            candidate['services'][self.service].setdefault('environment',{})['VECTOR_TRAFFIC_INGEST_TOKEN']=key
        temporary = self.release / 'compose.check.json'
        temporary.write_bytes(compose_bytes(candidate))
        require(self.profile(temporary) == candidate, 'COMPOSE_ROUNDTRIP_FAILED')
        self.verify_http(False)
        require(self.others_unchanged() and self.inventory().get(self.args.app) == self.before[self.args.app], 'CONTAINERS_CHANGED_DURING_BUILD')
        require(digest(self.path.read_bytes()) == digest(original), 'COMPOSE_CHANGED_DURING_BUILD')
        # Do not interrupt an observed running model job or target scan.
        idle_probe = r"""const {Pool}=require('pg');const p=new Pool({connectionString:process.env.DATABASE_URL});(async()=>{let n=0;for(const table of ['agent_jobs','security_scan_runs']){if((await p.query('SELECT to_regclass($1) AS t',[table])).rows[0].t)n+=Number((await p.query('SELECT COUNT(*) AS n FROM '+table+" WHERE status='running'")).rows[0].n);}console.log(n);})().catch(()=>process.exitCode=1).finally(()=>p.end());"""
        idle_deadline = time.monotonic()+60
        while int(self.run(['docker','exec',self.args.app,'node','-e',idle_probe]).decode().strip()):
            require(time.monotonic()<idle_deadline,'RUNNING_TASKS_RETRY_AFTER_COMPLETION')
            print('Waiting for running tasks to finish ...',flush=True)
            time.sleep(5)
        require(digest(self.path.read_bytes())==digest(original) and self.others_unchanged(), 'DEPLOYMENT_BASELINE_CHANGED')
        changed = False
        try:
            print('Replacing only the web app. Minecraft, inference and worker stay online.', flush=True)
            atomic(self.path, temporary.read_bytes(), 0o600 if getattr(self.args,'traffic_key_file',None) else meta.st_mode & 0o777, meta.st_uid, meta.st_gid)
            changed = True
            self.run(self.compose(self.path, 'up', '-d', '--no-deps', '--no-build', '--pull', 'never', self.service), timeout=120)
            deadline = time.monotonic()+100
            while True:
                try:
                    require(self.inspect(self.args.app)['Image'] == image, 'WRONG_IMAGE')
                    checks = self.verify_http()
                    break
                except Exception:
                    if time.monotonic() > deadline:
                        raise RuntimeError('NEW_APP_NOT_HEALTHY')
                    time.sleep(2)
            require(self.others_unchanged(), 'OTHER_CONTAINERS_CHANGED')
            require(self.profile(self.path) == candidate, 'DEPLOYED_CONFIG_CHANGED')
            if self.args.public_url:
                self.run(['curl', '--silent', '--show-error', '--fail', '--max-time', '15', '--output', '/dev/null', self.args.public_url.rstrip('/')+'/api/health'], timeout=20)
                checks['public_https_ok'] = True
            report = dict(deployed=True, revision=self.args.revision, image_id=image, only_app_recreated=True,
                          other_containers_unchanged=True, live_http_checks=checks, model_calls=0, cloud_calls=0,
                          messages_sent=0, external_scans_started=0, backup_created=False, release=str(self.release))
            (self.release/'deployment.json').write_text(json.dumps(report, indent=2)+'\n')
            print(json.dumps(report, indent=2))
        except Exception:
            if changed and digest(self.path.read_bytes()) == digest(temporary.read_bytes()):
                print('Update did not pass health checks; restoring the previous app configuration.', flush=True)
                atomic(self.path, original, meta.st_mode & 0o777, meta.st_uid, meta.st_gid)
                configured = self.profile(self.path)['services'][self.service].get('image')
                require(configured and self.inspect(configured)['Id'] == old_image, 'ROLLBACK_IMAGE_DRIFT')
                self.run(self.compose(self.path, 'up', '-d', '--no-deps', '--no-build', '--pull', 'never', self.service), timeout=120)
            raise


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--app', default='vector-app')
    parser.add_argument('--revision', required=True)
    parser.add_argument('--public-url')
    parser.add_argument('--traffic-key-file')
    args = parser.parse_args()
    if args.public_url:
        url = urlsplit(args.public_url)
        require(url.scheme == 'https' and url.hostname and not url.username and not url.password and
                not url.query and not url.fragment and url.path in ('', '/'), 'INVALID_PUBLIC_URL')
    update = Update(args)
    print('Private build and deployment evidence: ' + str(update.release), flush=True)
    update.apply()


if __name__ == '__main__':
    main()
