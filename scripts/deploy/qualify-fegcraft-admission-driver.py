#!/usr/bin/env python3
"""Prepare the pinned binary driver and test admission in a disposable PG only."""
import ast
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path('/root/vector-workspace')
REPO = ROOT/'github/vector'
HELPER = '8d80f1d3c4ecdd818be33519298333423b152e59'
READINESS = ROOT/'releases/vector-fegcraft-admission-readiness-20261018T075331Z-8a1744/result.json'
PYTHON = 'sha256:eca0b83a886fcc9952ef13755853ef63134e5c76733d40564460398776c92dd7'
MANIFEST = 'services/fegcraft-assistant/driver-wheels.json'
REQUIREMENTS = 'services/fegcraft-assistant/driver-requirements.txt'
HARNESS = 'tests/fegcraft-admission-driver.integration.py'
LABEL = 'com.vector.admission-driver'


def run(*args, timeout=30):
    value = subprocess.run(args, capture_output=True, timeout=timeout)
    if value.returncode:
        raise RuntimeError('DRIVER_COMMAND_FAILED:' + args[0])
    return value.stdout


def source(revision, path):
    return run('git','-C',str(REPO),'show',revision+':'+path)


def validate_manifest(value):
    if value.get('python') != '3.12' or value.get('architecture') != 'x86_64' or len(value.get('files',[])) != 3:
        raise RuntimeError('DRIVER_MANIFEST_SCOPE')
    names = set()
    for item in value['files']:
        parsed = urllib.parse.urlsplit(item['url'])
        if (not re.fullmatch(r'[A-Za-z0-9_.-]+\.whl',item['name']) or item['name'] in names
            or parsed.scheme != 'https' or parsed.netloc != 'files.pythonhosted.org'
            or not parsed.path.startswith('/packages/') or '..' in parsed.path or '%' in parsed.path
            or parsed.path.rsplit('/',1)[-1] != item['name'] or parsed.query or parsed.fragment
            or not re.fullmatch('[a-f0-9]{64}',item['sha256'])
            or type(item['size']) is not int or not 0 < item['size'] < 8*1024*1024):
            raise RuntimeError('DRIVER_MANIFEST_ENTRY')
        names.add(item['name'])
    return value['files']


def fetch_wheels(manifest, directory):
    entries = validate_manifest(manifest)
    if any(p.is_symlink() for p in (directory,*directory.parents)):
        raise RuntimeError('DRIVER_WHEEL_SYMLINK')
    directory.mkdir(mode=0o755,exist_ok=True)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args): return None
    # These fixed public package URLs contain no owner data. Honour the host's
    # HTTPS proxy for downloads; exact size/hash and no redirects remain required.
    opener = urllib.request.build_opener(NoRedirect())
    for item in entries:
        target = directory/item['name']
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_file() or target.stat().st_size != item['size']:
                raise RuntimeError('DRIVER_EXISTING_WHEEL_MISMATCH')
            raw = target.read_bytes()
        else:
            with opener.open(item['url'],timeout=20) as response:
                raw = response.read(item['size']+1)
            if len(raw) != item['size'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
                raise RuntimeError('DRIVER_DOWNLOADED_WHEEL_MISMATCH')
            fd = os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
            with os.fdopen(fd,'wb') as handle: handle.write(raw)
        if hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise RuntimeError('DRIVER_EXISTING_WHEEL_MISMATCH')


def check_readiness(value):
    if (value.get('revision') != HELPER or any(value.get(k) is not True for k in ('audit_completed','production_unchanged','cleanup_verified'))
        or value.get('production_activated') is not False or value.get('eligible_for_activation') is not False
        or value.get('production_differences') != {'containers':[],'changed_file_count':0}
        or value.get('baseline') != {'owned_mode_zero_baseline':True,'read_only_input_mounts_retained':True}
        or value.get('installed_addon',{}).get('http_wall_deadline_seconds') != 27
        or value.get('database_catalog',{}).get('proposed_role_exists') is not False):
        raise RuntimeError('DRIVER_READINESS_EVIDENCE_MISMATCH')


def cleanup(names, network, owner):
    for name in reversed(names):
        ids = run('docker','ps','-aq','--filter','name=^/'+name+'$').decode().split()
        for identity in ids:
            value = json.loads(run('docker','inspect',identity))[0]
            if (value['Config'].get('Labels') or {}).get(LABEL) != owner:
                raise RuntimeError('DRIVER_CLEANUP_OWNERSHIP_MISMATCH')
            run('docker','rm','-f',identity)
    ids = run('docker','network','ls','-q','--filter','name=^'+network+'$').decode().split()
    for identity in ids:
        value = json.loads(run('docker','network','inspect',identity))[0]
        if (value.get('Labels') or {}).get(LABEL) != owner or value.get('Containers'):
            raise RuntimeError('DRIVER_NETWORK_CLEANUP_REFUSED')
        run('docker','network','rm',identity)
    if any(run('docker','ps','-aq','--filter','name=^/'+name+'$').strip() for name in names):
        raise RuntimeError('DRIVER_CLEANUP_INCOMPLETE')


def main():
    os.umask(0o077)
    if len(sys.argv)==3 and sys.argv[1]=='--fetch-ci-wheels':
        if os.environ.get('CI') != 'true': raise RuntimeError('DISPOSABLE_CI_REQUIRED')
        fetch_wheels(json.loads(Path(MANIFEST).read_text()),Path(sys.argv[2]))
        return
    if sys.argv[1:]: raise RuntimeError('DRIVER_ARGUMENTS_INVALID')
    revision = os.environ.get('VECTOR_FEGCRAFT_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision): raise RuntimeError('ROOT_AND_PIN_REQUIRED')
    namespace={'__name__':'readiness_support','__file__':str(REPO/'scripts/diagnostics/fegcraft-admission-readiness.py')}
    raw=source(HELPER,'scripts/diagnostics/fegcraft-admission-readiness.py'); ast.parse(raw)
    exec(compile(raw,namespace['__file__'],'exec'),namespace)
    from types import SimpleNamespace
    h=SimpleNamespace(**namespace)
    h.read(ROOT/'.chat-release.lock')
    with (ROOT/'.chat-release.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        run('git','-C',str(REPO),'merge-base','--is-ancestor',revision,'origin/main')
        check_readiness(json.loads(h.read(READINESS)))
        h.evidence(json.loads(h.read(h.EVIDENCE)))
        for name in h.SOURCE_FILES:
            run('git','-C',str(REPO),'diff','--exit-code',h.TESTED,revision,'--','services/fegcraft-assistant/'+name)
        before=h.snapshot(); h.baseline(before); h.addon()
        pg_image=before['/vector-postgres']['Image']
        owner=secrets.token_hex(12)
        directory=ROOT/'releases'/('vector-fegcraft-admission-driver-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+owner[:6])
        if any(p.is_symlink() for p in (directory,*directory.parents)): raise RuntimeError('DRIVER_REPORT_SYMLINK')
        directory.mkdir(mode=0o700)
        print('Belege:',directory,flush=True)
        context=directory/'build';context.mkdir(mode=0o755);context.chmod(0o755)
        wheels=context/'wheels';wheels.mkdir(mode=0o755);wheels.chmod(0o755)
        print('Bereite gepinnten Treiber vor; Rollen-/CPU-Sperrtest nur in isolierter temporärer PostgreSQL-Datenbank. Minecraft bleibt online.',flush=True)
        manifest=json.loads(source(revision,MANIFEST));fetch_wheels(manifest,wheels)
        (wheels/'requirements.txt').write_bytes(source(revision,REQUIREMENTS));(wheels/'requirements.txt').chmod(0o644)
        base_tag='vector-fegcraft-driver-base:'+owner
        image_tag='vector-fegcraft-driver:'+owner
        run('docker','image','tag',PYTHON,base_tag)
        dockerfile=('FROM '+base_tag+'\nCOPY wheels /wheels\n'
          'RUN python3 -m pip install --disable-pip-version-check --no-cache-dir --no-index --no-deps --require-hashes --find-links=/wheels -r /wheels/requirements.txt\n'
          'ENV PSYCOPG_IMPL=binary PYTHONDONTWRITEBYTECODE=1\n'
          'LABEL com.vector.admission-driver="'+owner+'"\n')
        (context/'Dockerfile').write_text(dockerfile);(context/'Dockerfile').chmod(0o644)
        try:
            build=subprocess.run(['docker','build','--pull=false','--network=none','--tag',image_tag,str(context)],capture_output=True,timeout=180)
            (directory/'build.log').write_bytes(build.stdout+build.stderr)
            if build.returncode: raise RuntimeError('DRIVER_OFFLINE_IMAGE_BUILD_FAILED')
            image=json.loads(run('docker','image','inspect',image_tag))[0]
            if image['Config'].get('Labels',{}).get(LABEL)!=owner: raise RuntimeError('DRIVER_IMAGE_OWNER_MISMATCH')
            image_id=image['Id']
        finally:
            # Remove only this unique alias, never a shared running image.
            run('docker','image','rm',base_tag)
        work=directory/'input';work.mkdir(mode=0o755);work.chmod(0o755)
        for path in (HARNESS, *('services/fegcraft-assistant/'+name for name in ('runtime.py','stats.py','policy.py'))):
            target=work/path;target.parent.mkdir(parents=True,exist_ok=True)
            for p in (target.parent,target.parent.parent):p.chmod(0o755)
            raw=source(revision,path);ast.parse(raw);target.write_bytes(raw);target.chmod(0o644)
        client='vector-driver-client-'+owner; database='vector-driver-pg-'+owner; probe='vector-driver-uid-'+owner
        network='vector-driver-test-'+owner; names=[probe,database,client]
        password=secrets.token_hex(32)
        secret=directory/'fixture.json'
        secret.write_text(json.dumps({'disposable':True,'dsn':'postgresql://vector_fixture:'+password+'@'+database+':5432/vector_admission_fixture'}))
        os.chown(secret,65534,65534);secret.chmod(0o400)
        result=None
        try:
            uid=int(run('docker','run','--rm','--name',probe,'--label',LABEL+'='+owner,'--pull','never','--network','none',
              '--user','65534:65534','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true',
              '--entrypoint','id',pg_image,'-u','postgres').strip())
            if not 1 <= uid <= 65534: raise RuntimeError('DRIVER_POSTGRES_UID_INVALID')
            run('docker','network','create','--internal','--label',LABEL+'='+owner,network)
            run('docker','run','-d','--name',database,'--label',LABEL+'='+owner,'--pull','never','--network',network,
              '--read-only','--user',str(uid)+':'+str(uid),'--cap-drop','ALL','--security-opt','no-new-privileges:true',
              '--cpus','1','--memory','256m','--pids-limit','128',
              '--tmpfs','/var/lib/postgresql/data:rw,nosuid,nodev,size=192m,mode=700,uid='+str(uid)+',gid='+str(uid),
              '--tmpfs','/var/run/postgresql:rw,nosuid,nodev,size=8m,mode=775,uid='+str(uid)+',gid='+str(uid),
              '--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=8m,mode=1777',
              '--env','PGDATA=/var/lib/postgresql/data/pgdata','--env','POSTGRES_USER=vector_fixture',
              '--env','POSTGRES_PASSWORD='+password,'--env','POSTGRES_DB=vector_admission_fixture',pg_image)
            for _ in range(30):
                ready=subprocess.run(['docker','exec',database,'pg_isready','-h','127.0.0.1','-U','vector_fixture','-d','vector_admission_fixture'],capture_output=True,timeout=3)
                if ready.returncode==0: break
                time.sleep(1)
            else: raise RuntimeError('DRIVER_FIXTURE_DATABASE_TIMEOUT')
            attempt=subprocess.run(['docker','run','--rm','--name',client,'--label',LABEL+'='+owner,'--pull','never','--network',network,
              '--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges:true',
              '--cpus','1','--memory','192m','--pids-limit','64','--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777',
              '--mount','type=bind,src='+str(work)+',dst=/code,readonly',
              '--mount','type=bind,src='+str(secret)+',dst=/run/secrets/fixture.json,readonly',
              '--entrypoint','python3',image_id,'/code/'+HARNESS,'/run/secrets/fixture.json'],capture_output=True,timeout=60)
            (directory/'qualification-stderr.log').write_bytes(attempt.stderr)
            result=json.loads(attempt.stdout)
            if attempt.returncode or result.get('passed') is not True: raise RuntimeError('DRIVER_ISOLATED_ADMISSION_FAILED')
            if result.get('server_version_num')!=170011: raise RuntimeError('DRIVER_POSTGRES_VERSION_CHANGED')
        finally:
            cleaned=False
            try:
                cleanup(names,network,owner)
                cleaned=True
            finally:
                secret.unlink(missing_ok=True)
                try: unchanged=h.snapshot()==before
                except Exception: unchanged=None
                (directory/'isolation-progress.json').write_text(json.dumps({
                  'isolated_admission':result,'driver_image':image_id,'production_role_created':False,
                  'cleanup_verified':cleaned,'production_unchanged':unchanged,
                  'eligible_for_activation':False,'production_activated':False},indent=2)+'\n')
        unchanged=h.snapshot()==before
        record={'passed':True,'revision':revision,'driver_image':image_id,'driver_tag':image_tag,
          'wheel_manifest_sha256':hashlib.sha256(source(revision,MANIFEST)).hexdigest(),
          'isolated_admission':result,'cleanup_verified':True,'production_unchanged':unchanged,
          'production_role_created':False,'dedicated_db_role_qualified':False,'eligible_for_activation':False,
          'production_activated':False,'model_calls':0,'cloud_calls':0,'messages_sent':0}
        record['passed']=unchanged
        (directory/'result.json').write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps(record,indent=2));print('Report:',directory/'result.json')
        if not unchanged: raise RuntimeError('DRIVER_PRODUCTION_CHANGED')
        print('Treiber-Image und isolierte Rollenprüfung bestanden. Kein produktiver Rollout, keine produktive Rolle oder Spielnachricht.')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if type(exc) is RuntimeError else type(exc).__name__)
        raise SystemExit(1)
