#!/usr/bin/env python3
"""Qualify synthetic HTTP, then update ONLY the owned standalone assistant."""
import ast
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import stat
import subprocess
import sys
import time

ROOT = Path('/root/vector-workspace')
REPO = ROOT / 'github/vector'
INSTALL = ROOT / 'releases/vector-fegcraft-install-20261017T125904Z-4fdeaf'
OLD = '98bad3fba4b0f8ed9d90a845d66b4d4c3f896059'
FILES = ('runtime.py', 'server.py', 'stats.py', 'policy.py', 'recipes.py')
SERVICE = 'vector-fegcraft-assistant'
IMAGE = 'sha256:eca0b83a886fcc9952ef13755853ef63134e5c76733d40564460398776c92dd7'
OTHERS = ('fegcraft-updated', 'vector-app', 'vector-worker', 'vector-runner', 'vector-postgres',
          'vector-redis', 'vector-local-inference', 'vector-privacy-ner')


def run(*args, timeout=30):
    result = subprocess.run(args, capture_output=True, timeout=timeout)
    if result.returncode: raise RuntimeError('MOD_HELP_COMMAND_FAILED:' + args[0])
    return result.stdout


def safe(path):
    if any(p.is_symlink() for p in (path, *path.parents)): raise RuntimeError('MOD_HELP_SYMLINK')


def read(path):
    safe(path); meta = path.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_size > 2_000_000: raise RuntimeError('MOD_HELP_FILE_INVALID')
    return path.read_bytes()


def sha(raw): return hashlib.sha256(raw).hexdigest()


def atomic(path, raw, mode=0o600):
    safe(path); temporary = path.parent / ('.mod-help-' + secrets.token_hex(8))
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        with os.fdopen(fd, 'wb') as handle: handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally: temporary.unlink(missing_ok=True)


def helper(directory):
    spec = importlib.util.spec_from_file_location('owned_fegcraft_install', directory / 'installer.py')
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def snapshots(h):
    result = {}
    for name in OTHERS:
        value = h.inspect(name); state = value['State']
        if not state['Running'] or state.get('Restarting') or state.get('OOMKilled'):
            raise RuntimeError('MOD_HELP_OTHER_SERVICE_NOT_RUNNING')
        if name == 'fegcraft-updated' and state.get('Health', {}).get('Status') != 'healthy':
            raise RuntimeError('MOD_HELP_GAME_NOT_HEALTHY')
        result[name] = [value['Id'], value['Image'], state['StartedAt']]
    result['game_compose'] = sha(read(Path('/opt/fegcraft-updated/docker-compose.yml')))
    result['app_compose'] = sha(read(Path('/opt/vector/docker-compose.yml')))
    return result


def check_owner(h, manifest):
    value = h.inspect(SERVICE)
    if (value['Image'] != IMAGE or value['Config'].get('Labels', {}).get('com.vector.installation') != manifest['owner']
            or value['Config']['Labels'].get('com.docker.compose.project') != SERVICE
            or value['Config']['Labels'].get('com.docker.compose.service') != 'assistant'):
        raise RuntimeError('MOD_HELP_SERVICE_OWNERSHIP_CHANGED')
    return value


def baseline(h):
    raw_manifest, raw_compose = read(INSTALL / 'manifest.json'), read(INSTALL / 'compose.json')
    manifest, profile = json.loads(raw_manifest), json.loads(raw_compose)
    if (manifest.get('status') != 'installed_pending_real_channel' or manifest.get('compose_sha256') != sha(raw_compose)
            or manifest.get('backend_revision')):
        raise RuntimeError('MOD_HELP_BASELINE_CHANGED')
    if len(h.owned_files(manifest)) != 3: raise RuntimeError('MOD_HELP_OWNED_FILES_CHANGED')
    for name in FILES:
        if read(INSTALL / 'code' / name) != run('git','-C',str(REPO),'show',OLD + ':services/fegcraft-assistant/' + name):
            raise RuntimeError('MOD_HELP_EXISTING_CODE_CHANGED')
    for name, expected in [('health.py', h.HEALTH), ('read-probe.py', h.READ_PROBE)]:
        if read(INSTALL / 'code' / name) != expected.encode(): raise RuntimeError('MOD_HELP_PROBE_CHANGED')
    if 'carryon' not in json.loads(read(INSTALL/'mods.json')): raise RuntimeError('MOD_HELP_CARRYON_NOT_IN_INVENTORY')
    value = check_owner(h, manifest); service = profile['services']['assistant']
    uid, gid = map(int, service['user'].split(':'))
    if not uid or not gid: raise RuntimeError('MOD_HELP_ROOT_SERVICE_REFUSED')
    expected = h.profile(INSTALL, uid, gid, h.DATA / 'DiscordIntegration-Data/vector/token')
    expected['services']['assistant']['labels'] = {'com.vector.installation': manifest['owner']}
    if profile != expected: raise RuntimeError('MOD_HELP_UNEXPECTED_PROFILE')
    if (value['Config'].get('Entrypoint') != service['entrypoint'] or value['Config'].get('User') != service['user']
            or value.get('HostConfig', {}).get('ReadonlyRootfs') is not True
            or set(value['NetworkSettings']['Networks']) != {'mc-net'}
            or value['NetworkSettings'].get('Ports')):
        raise RuntimeError('MOD_HELP_RUNTIME_PROFILE_CHANGED')
    declared = {(v['target'], v['source'], v.get('read_only', False)) for v in service['volumes']}
    actual = {(v['Destination'], v.get('Source'), not v.get('RW', False)) for v in value['Mounts'] if v['Type'] == 'bind'}
    if declared != actual or any(v['Type'] not in ('bind', 'tmpfs') for v in value['Mounts']):
        raise RuntimeError('MOD_HELP_RUNTIME_MOUNTS_CHANGED')
    env = dict(item.split('=',1) for item in value['Config']['Env'] if '=' in item)
    if any(env.get(key) != val for key,val in service['environment'].items()): raise RuntimeError('MOD_HELP_RUNTIME_ENV_CHANGED')
    return manifest, profile, raw_manifest, raw_compose


def candidate(profile, code):
    value = copy.deepcopy(profile)
    matches = [v for v in value['services']['assistant']['volumes'] if v['target'] == '/code']
    if len(matches) != 1 or not matches[0].get('read_only'): raise RuntimeError('MOD_HELP_CODE_BIND_INVALID')
    matches[0]['source'] = str(code)
    return value


def healthy(h, manifest):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        value = check_owner(h, manifest); state = value['State']
        if not state['Running'] or state.get('Restarting') or state.get('OOMKilled'): raise RuntimeError('MOD_HELP_SERVICE_NOT_RUNNING')
        if state.get('Health', {}).get('Status') == 'healthy':
            run('docker','exec',value['Id'],'python3','/code/health.py')
            coverage = json.loads(run('docker','exec',value['Id'],'python3','/code/read-probe.py'))
            if coverage.get('complete_statistics') is not True or coverage.get('recipes') != 975 or coverage.get('mod_ids',0) < 1:
                raise RuntimeError('MOD_HELP_READ_COVERAGE_FAILED')
            return coverage
        time.sleep(1)
    raise RuntimeError('MOD_HELP_HEALTH_TIMEOUT')


def rollback(directory):
    safe(directory)
    if directory.parent != ROOT / 'releases' or not directory.name.startswith('vector-fegcraft-mod-help-'):
        raise RuntimeError('MOD_HELP_ROLLBACK_PATH_INVALID')
    record = json.loads(read(directory / 'deployment.json'))
    if sha(read(directory / 'installer.py')) != record['helper_sha256']: raise RuntimeError('MOD_HELP_HELPER_CHANGED')
    h = helper(directory)
    old_manifest = read(directory / 'manifest.before.json'); old_profile = read(directory / 'compose.before.json')
    if sha(old_manifest) != record['old_manifest_sha256'] or sha(old_profile) != record['old_compose_sha256']:
        raise RuntimeError('MOD_HELP_ROLLBACK_EVIDENCE_CHANGED')
    if sha(read(INSTALL / 'compose.json')) not in (record['candidate_sha256'], record['old_compose_sha256']):
        raise RuntimeError('MOD_HELP_LATER_PROFILE_EDIT_PRESERVED')
    if sha(read(INSTALL / 'manifest.json')) not in (record['new_manifest_sha256'], record['old_manifest_sha256']):
        raise RuntimeError('MOD_HELP_LATER_MANIFEST_EDIT_PRESERVED')
    if h.existing_service(): check_owner(h, json.loads(old_manifest))
    if snapshots(h) != record['others']: raise RuntimeError('MOD_HELP_OTHER_PRODUCTION_CHANGED')
    atomic(INSTALL / 'compose.json', old_profile); atomic(INSTALL / 'manifest.json', old_manifest)
    h.compose(INSTALL,'up','-d','--no-deps','--no-build','--pull','never','assistant')
    healthy(h,json.loads(old_manifest))
    if snapshots(h) != record['others']: raise RuntimeError('MOD_HELP_OTHER_PRODUCTION_CHANGED')
    record['status'] = 'rolled_back'; atomic(directory / 'deployment.json',(json.dumps(record,indent=2)+'\n').encode())
    print('Nur Vector-Dienst zurückgesetzt. Minecraft und andere Dienste unverändert.')


def deploy(directory, h, revision, code):
    manifest, profile, old_manifest, old_profile = baseline(h)
    before = snapshots(h)
    for name, source in [('health.py',h.HEALTH),('read-probe.py',h.READ_PROBE)]: atomic(code/name,source.encode(),0o644)
    value = candidate(profile, code); raw = (json.dumps(value,indent=2)+'\n').encode()
    next_manifest = copy.deepcopy(manifest)
    next_manifest.update(compose_sha256=sha(raw), backend_revision=revision, backend_release=str(directory))
    new_manifest = (json.dumps(next_manifest,indent=2)+'\n').encode()
    record = {'status':'prepared','revision':revision,'helper_sha256':sha(read(directory/'installer.py')),
              'old_manifest_sha256':sha(old_manifest),'old_compose_sha256':sha(old_profile),
              'candidate_sha256':sha(raw),'new_manifest_sha256':sha(new_manifest),'others':before}
    atomic(directory/'manifest.before.json',old_manifest); atomic(directory/'compose.before.json',old_profile)
    atomic(directory/'compose.candidate.json',raw); atomic(directory/'deployment.json',(json.dumps(record,indent=2)+'\n').encode())
    atomic(directory/'update.py',Path(__file__).read_bytes(),0o700)
    atomic(directory/'rollback.sh',('#!/bin/bash\nset -Eeuo pipefail\nexec python3 '+shlex.quote(str(directory/'update.py'))+' --rollback '+shlex.quote(str(directory))+'\n').encode(),0o700)
    # Validate the canonical candidate without changing the active profile.
    run('docker','compose','-p',SERVICE,'-f',str(directory/'compose.candidate.json'),'config','--quiet')
    if snapshots(h) != before or read(INSTALL/'manifest.json') != old_manifest or read(INSTALL/'compose.json') != old_profile:
        raise RuntimeError('MOD_HELP_BASELINE_CHANGED_DURING_PREPARATION')
    check_owner(h,manifest)
    try:
        atomic(INSTALL/'compose.json',raw); atomic(INSTALL/'manifest.json',new_manifest)
        h.compose(INSTALL,'up','-d','--no-deps','--no-build','--pull','never','assistant')
        coverage = healthy(h,next_manifest)
        if snapshots(h) != before: raise RuntimeError('MOD_HELP_OTHER_PRODUCTION_CHANGED')
        record['status']='deployed'; atomic(directory/'deployment.json',(json.dumps(record,indent=2)+'\n').encode())
    except Exception:
        rollback(directory)
        raise
    print(json.dumps({'deployed':True,'only_assistant_recreated':True,'minecraft_unchanged':True,
                     'other_services_unchanged':True,'coverage':coverage,'model_calls':0,'cloud_calls':0,
                     'messages_sent':0,'welcome_sent':False,'rollback':str(directory/'rollback.sh')},indent=2))


def wants_deploy(args, environment):
    flag = environment.get('VECTOR_FEGCRAFT_MOD_HELP_DEPLOY', '0')
    if flag not in ('0','1') or args not in ([],['--deploy']):
        raise RuntimeError('MOD_HELP_ARGUMENTS_INVALID')
    return args == ['--deploy'] or flag == '1'


def main():
    os.umask(0o077); sys.dont_write_bytecode = True
    if os.geteuid() != 0: raise RuntimeError('ROOT_OWNER_REQUIRED')
    safe(ROOT / '.chat-release.lock')
    with (ROOT / '.chat-release.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        if len(sys.argv) == 3 and sys.argv[1] == '--rollback': return rollback(Path(sys.argv[2]))
        activate = wants_deploy(sys.argv[1:], os.environ)
        revision = os.environ.get('VECTOR_FEGCRAFT_REV','')
        if not re.fullmatch('[a-f0-9]{40}',revision): raise RuntimeError('MOD_HELP_PIN_REQUIRED')
        directory = ROOT/'releases'/('vector-fegcraft-mod-help-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3))
        safe(directory); directory.mkdir(mode=0o700)
        print('Qualifikation und Dienstbelege: '+str(directory),flush=True)
        public = directory/'synthetic'; public.mkdir(mode=0o755)
        code = public/'services/fegcraft-assistant'; code.mkdir(parents=True,mode=0o755); code.parent.chmod(0o755)
        tests = public/'tests'; tests.mkdir(mode=0o755)
        for source, target in [('services/fegcraft-assistant/'+name,code/name) for name in FILES] + [('tests/fegcraft-mod-help.test.py',tests/'fegcraft-mod-help.test.py'),('scripts/deploy/install-fegcraft-assistant.py',directory/'installer.py')]:
            content = run('git','-C',str(REPO),'show',revision+':'+source); ast.parse(content)
            atomic(target,content,0o644 if target.is_relative_to(public) else 0o600)
        run('docker','image','inspect',IMAGE)
        # Only public source and synthetic fixtures, loopback HTTP, no real input mounts.
        evaluation_name = 'vector-mod-help-eval-' + secrets.token_hex(8)
        evaluation_owner = secrets.token_hex(16)
        try:
            result = subprocess.run(['docker','run','--rm','--name',evaluation_name,
             '--label','com.vector.mod-help-evaluation='+evaluation_owner,'--network','none','--read-only','--user','65534:65534',
             '--cap-drop','ALL','--security-opt','no-new-privileges:true','--pids-limit','64','--memory','256m','--cpus','1',
             '--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=32m,mode=1777',
             '--env','PYTHONDONTWRITEBYTECODE=1','--mount','type=bind,src='+str(public)+',dst=/work,readonly',
             '--entrypoint','python3',IMAGE,'/work/tests/fegcraft-mod-help.test.py'],capture_output=True,timeout=60)
        finally:
            leftover = run('docker','ps','-aq','--filter','name=^/'+evaluation_name+'$').strip().decode()
            if leftover:
                item = json.loads(run('docker','inspect',leftover))[0]
                if item['Config'].get('Labels',{}).get('com.vector.mod-help-evaluation') != evaluation_owner:
                    raise RuntimeError('MOD_HELP_EVALUATION_CLEANUP_OWNERSHIP_CHANGED')
                run('docker','rm','-f',item['Id'])
        atomic(directory/'qualification.log',result.stdout+result.stderr)
        if result.returncode: raise RuntimeError('MOD_HELP_ISOLATED_HTTP_FAILED')
        atomic(directory/'result.json',(json.dumps({'passed':True,'revision':revision,'tests':11,'synthetic_only':True,
             'model_calls':0,'cloud_calls':0,'messages_sent':0,'production_activated':False},indent=2)+'\n').encode())
        print('Isolierte signierte HTTP-Prüfungen bestanden. Keine Spielnachricht oder Modellanfrage.',flush=True)
        if activate: deploy(directory,helper(directory),revision,code)
        else: print('Nur geprüft. Keine Produktionsänderung.')


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('ERROR: '+(str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)+'. Kein Minecraft-Neustart oder Backup durch dieses Skript.',file=sys.stderr)
        raise SystemExit(1)
