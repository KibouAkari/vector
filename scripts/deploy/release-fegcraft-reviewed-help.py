#!/usr/bin/env python3
"""Qualify the actual mode3 service, then replace only the owned assistant."""
import ast
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
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
from types import SimpleNamespace

ROOT=Path('/root/vector-workspace')
REPO=ROOT/'github/vector'
HELPER='8d80f1d3c4ecdd818be33519298333423b152e59'
ROLE_REV='579e3e107c8a72b578a0b88762a065300fe1b4fa'
ROLE_REPORT=ROOT/'releases/vector-fegcraft-slot-role-20261018T091321Z-5b8e9f/result.json'
INSTALL=ROOT/'releases/vector-fegcraft-install-20261017T125904Z-4fdeaf'
SERVICE='vector-fegcraft-assistant'
IMAGE='sha256:db331e915c9cce6f6440b629c6e3c4009b4ffd955046b484f0433090771f78c2'
SECRET=ROOT/'local-inference/fegcraft-slot-role/slot-dsn'
SLOT_TARGET='/run/secrets/vector_fegcraft_slot_dsn'
LABEL='com.vector.reviewed-help-stage'
FILES=('runtime.py','server.py','stats.py','policy.py','recipes.py','knowledge.py','documentation.py','public-knowledge.json')


def run(*args,input=None,timeout=30):
    result=subprocess.run(args,input=input,capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError('REVIEWED_HELP_COMMAND_FAILED:'+args[0])
    return result.stdout


def source(rev,path):return run('git','-C',str(REPO),'show',rev+':'+path)
def sha(raw):return hashlib.sha256(raw).hexdigest()


def safe(path):
    if any(p.is_symlink() for p in (path,*path.parents)):raise RuntimeError('REVIEWED_HELP_SYMLINK')


def read(path):
    safe(path);info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size>2_000_000:raise RuntimeError('REVIEWED_HELP_FILE_LIMIT')
    return path.read_bytes()


def atomic(path,raw,mode=0o600):
    safe(path);temporary=path.parent/('.reviewed-help-'+secrets.token_hex(8))
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
        with os.fdopen(fd,'wb') as f:
            os.fchmod(f.fileno(),mode);f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:temporary.unlink(missing_ok=True)


def load(revision,path):
    raw=source(revision,path);ast.parse(raw)
    ns={'__name__':'reviewed_help_support','__file__':str(REPO/path)}
    exec(compile(raw,ns['__file__'],'exec'),ns)
    return SimpleNamespace(**ns)


def role_evidence(value):
    if (value.get('revision')!=ROLE_REV or value.get('driver_image')!=IMAGE
        or any(value.get(k) is not True for k in ('passed','dedicated_db_role_qualified','role_owned',
          'database_destination_verified','cleanup_verified','production_containers_and_profiles_unchanged'))
        or any(value.get(k) is not False for k in ('production_activated','eligible_for_activation'))
        or any(value.get(k)!=0 for k in ('model_calls','cloud_calls','messages_sent'))
        or value.get('role_secret_path')!=str(SECRET)):
        raise RuntimeError('REVIEWED_HELP_ROLE_EVIDENCE_CHANGED')
    p=value.get('privileges',{});s=value.get('shared_slot',{})
    if (p.get('checked_databases')!=3 or p.get('global_public_acl_changed') is not False
        or any(p.get(k) is not True for k in ('no_application_object_privileges','no_permanent_create_privileges',
          'no_security_definer_or_foreign_access','inherited_public_temp','system_catalog_access_retained'))
        or any(s.get(k) is not True for k in ('role_login_verified','same_database_shared_slot_verified',
          'both_contention_directions_verified','release_verified'))):raise RuntimeError('REVIEWED_HELP_ROLE_SCOPE_CHANGED')


def protected(snapshot):
    # Full configs may contain secrets. Persist hashes only, never their values.
    omitted={'/'+SERVICE,str(INSTALL/'compose.json'),str(INSTALL/'manifest.json')}
    return {k:sha(json.dumps(v,sort_keys=True).encode()) for k,v in snapshot.items() if k not in omitted}


def protected_live(h):
    # Rollback must remain possible even when the candidate assistant is down.
    names=tuple(n for n in h.NAMES if n!=SERVICE)
    values=json.loads(run('docker','inspect',*names))
    if {v['Name'].lstrip('/') for v in values}!=set(names):raise RuntimeError('REVIEWED_HELP_PROTECTED_SET_CHANGED')
    snapshot={}
    for v in values:
        state=v['State']
        if not state['Running'] or state.get('OOMKilled') or state.get('Restarting'):
            raise RuntimeError('REVIEWED_HELP_PROTECTED_SERVICE_DOWN')
        if v['Name']=='/fegcraft-updated' and state.get('Health',{}).get('Status')!='healthy':
            raise RuntimeError('REVIEWED_HELP_GAME_NOT_HEALTHY')
        row={k:v[k] for k in ('Id','Image','Config','HostConfig','Mounts')}
        row['Mounts']=h.canonical_mounts(row['Mounts']);row['StartedAt']=state['StartedAt']
        row['networks']=sorted(v['NetworkSettings']['Networks']);snapshot[v['Name']]=row
    for path in (Path('/opt/vector/docker-compose.yml'),Path('/opt/fegcraft-updated/docker-compose.yml'),h.ADDON):
        snapshot[str(path)]=sha(read(path))
    return protected(snapshot)


def candidate(profile,code,catalog):
    value=copy.deepcopy(profile);s=value['services']['assistant']
    mounts={m['target']:m for m in s['volumes']}
    if (len(mounts)!=len(s['volumes']) or '/code' not in mounts or not mounts['/code'].get('read_only')
        or SLOT_TARGET in mounts or '/inputs/documentation.json' in mounts
        or s['environment'].get('VECTOR_FEGCRAFT_KNOWLEDGE')!='0' or s['networks']!=['mc-net']):
        raise RuntimeError('REVIEWED_HELP_CANDIDATE_BASELINE_CHANGED')
    s['image']=IMAGE;s['environment']['VECTOR_FEGCRAFT_KNOWLEDGE']='3'
    mounts['/code']['source']=str(code)
    for src,dst in ((SECRET,SLOT_TARGET),(catalog,'/inputs/documentation.json')):
        s['volumes'].append({'type':'bind','source':str(src),'target':dst,'read_only':True,'bind':{'create_host_path':False}})
    for network in ('vector-internal','vector-local-inference'):
        expected={'external':True,'name':network}
        if network in value['networks'] and value['networks'][network]!=expected:raise RuntimeError('REVIEWED_HELP_NETWORK_CHANGED')
        value['networks'][network]=expected;s['networks'].append(network)
    return value


def check_runtime(name,profile,owner):
    v=json.loads(run('docker','inspect',name))[0];s=profile
    labels=v['Config'].get('Labels') or {};hc=v['HostConfig']
    if name==SERVICE and (labels.get('com.docker.compose.project')!=SERVICE
                          or labels.get('com.docker.compose.service')!='assistant'):
        raise RuntimeError('REVIEWED_HELP_COMPOSE_OWNER_CHANGED')
    actual=[(m['Destination'],m.get('Source'),not m.get('RW',False)) for m in v['Mounts'] if m['Type']=='bind']
    declared=[(m['target'],m['source'],m.get('read_only',False)) for m in s['volumes']]
    env=dict(x.split('=',1) for x in v['Config']['Env'] if '=' in x)
    if (labels.get('com.vector.installation')!=owner or v['Image']!=s['image']
        or v['Config'].get('User')!=s['user'] or v['Config'].get('Entrypoint')!=s['entrypoint']
        or hc.get('ReadonlyRootfs') is not True or hc.get('Privileged') or hc.get('CapAdd')
        or set(hc.get('CapDrop') or [])!={'ALL'} or 'no-new-privileges:true' not in (hc.get('SecurityOpt') or [])
        or hc.get('PortBindings') or hc.get('Devices') or hc.get('Memory')!=256*1024**2
        or hc.get('NanoCpus')!=1_000_000_000 or hc.get('PidsLimit')!=64
        or sorted(actual)!=sorted(declared) or any(m['Type'] not in ('bind','tmpfs') for m in v['Mounts'])
        or set(v['NetworkSettings']['Networks'])!=set(s['networks'])
        or any(env.get(k)!=val for k,val in s['environment'].items())):
        raise RuntimeError('REVIEWED_HELP_RUNTIME_SCOPE_CHANGED')
    return v


def healthy(name,service,owner,require_docker=True):
    deadline=time.monotonic()+65
    while time.monotonic()<deadline:
        v=check_runtime(name,service,owner);state=v['State']
        if not state['Running'] or state.get('OOMKilled') or state.get('Restarting'):
            raise RuntimeError('REVIEWED_HELP_SERVICE_STOPPED')
        if not require_docker or state.get('Health',{}).get('Status')=='healthy':
            try:run('docker','exec',name,'python3','/code/health.py',timeout=6)
            except RuntimeError:
                time.sleep(1);continue
            coverage=json.loads(run('docker','exec',name,'python3','/code/read-probe.py',timeout=10))
            if coverage.get('complete_statistics') is not True or coverage.get('recipes')!=975 or coverage.get('mod_ids')!=63:
                raise RuntimeError('REVIEWED_HELP_INPUT_COVERAGE_CHANGED')
            return coverage
        time.sleep(1)
    raise RuntimeError('REVIEWED_HELP_HEALTH_TIMEOUT')


def cleanup_stage(name,owner):
    ids=run('docker','ps','-aq','--filter','name=^/'+name+'$').decode().split()
    for identity in ids:
        v=json.loads(run('docker','inspect',identity))[0]
        if (v['Config'].get('Labels') or {}).get(LABEL)!=owner:raise RuntimeError('REVIEWED_HELP_STAGE_FOREIGN')
        run('docker','rm','-f',identity)


def stage(directory,profile,owner):
    suffix=secrets.token_hex(8);name='vector-reviewed-stage-'+suffix
    value=copy.deepcopy(profile);s=value['services'].pop('assistant');value['services'][name]=s
    state=directory/'stage-state';state.mkdir(mode=0o700)
    uid,gid=map(int,s['user'].split(':'));os.chown(state,uid,gid)
    for m in s['volumes']:
        if m['target']=='/state':m['source']=str(state)
    s['container_name']=name;s['restart']='no';s['labels'][LABEL]=suffix
    path=directory/'stage.json';atomic(path,(json.dumps(value,indent=2)+'\n').encode())
    try:
        run('docker','compose','-p',name,'-f',str(path),'config','--quiet')
        run('docker','compose','-p',name,'-f',str(path),'up','-d','--no-deps','--no-build','--pull','never',name,timeout=45)
        healthy(name,s,owner,require_docker=False)
        probe=subprocess.run(['docker','exec',name,'python3','/code/rollout-probe.py'],capture_output=True,timeout=100)
        atomic(directory/'stage-probe.log',(probe.stdout+probe.stderr)[:32768])
        if probe.returncode:raise RuntimeError('REVIEWED_HELP_STAGE_FAILED_SEE_PRIVATE_STAGE_PROBE_LOG')
        result=json.loads(probe.stdout)
        if result.get('passed') is not True or result.get('model_calls')!=2:raise RuntimeError('REVIEWED_HELP_STAGE_FAILED')
        return result
    finally:cleanup_stage(name,suffix)


def compose():
    run('docker','compose','-p',SERVICE,'-f',str(INSTALL/'compose.json'),
      'up','-d','--no-deps','--no-build','--pull','never','assistant',timeout=90)


def rollback(directory,h):
    safe(directory)
    if directory.parent!=ROOT/'releases' or not directory.name.startswith('vector-fegcraft-reviewed-help-'):
        raise RuntimeError('REVIEWED_HELP_ROLLBACK_PATH')
    record=json.loads(read(directory/'deployment.json'))
    old_profile=read(directory/'compose.before.json');old_manifest=read(directory/'manifest.before.json')
    if sha(old_profile)!=record['old_profile_sha'] or sha(old_manifest)!=record['old_manifest_sha']:
        raise RuntimeError('REVIEWED_HELP_ROLLBACK_BACKUP_CHANGED')
    if (sha(read(INSTALL/'compose.json')) not in (record['old_profile_sha'],record['new_profile_sha'])
        or sha(read(INSTALL/'manifest.json')) not in (record['old_manifest_sha'],record['new_manifest_sha'])):
        raise RuntimeError('REVIEWED_HELP_LATER_EDIT_PRESERVED')
    if protected_live(h)!=record['protected']:raise RuntimeError('REVIEWED_HELP_OTHER_SERVICE_CHANGED')
    candidate_raw=read(directory/'compose.candidate.json')
    if sha(candidate_raw)!=record['new_profile_sha']:raise RuntimeError('REVIEWED_HELP_CANDIDATE_BACKUP_CHANGED')
    ids=run('docker','ps','-aq','--filter','name=^/'+SERVICE+'$').decode().split()
    if ids:
        owner=json.loads(old_manifest)['owner']
        try:check_runtime(SERVICE,json.loads(old_profile)['services']['assistant'],owner)
        except RuntimeError:check_runtime(SERVICE,json.loads(candidate_raw)['services']['assistant'],owner)
    atomic(INSTALL/'compose.json',old_profile);atomic(INSTALL/'manifest.json',old_manifest);compose()
    healthy(SERVICE,json.loads(old_profile)['services']['assistant'],json.loads(old_manifest)['owner'])
    if protected_live(h)!=record['protected']:raise RuntimeError('REVIEWED_HELP_ROLLBACK_OTHER_CHANGED')
    record['status']='rolled_back';atomic(directory/'deployment.json',(json.dumps(record,indent=2)+'\n').encode())
    print('Assistent auf bisherigen Modus zurückgesetzt. Minecraft unverändert; Spielzustand und Rollenkennung bleiben erhalten.')


def main():
    os.umask(0o077);sys.dont_write_bytecode=True
    revision=os.environ.get('VECTOR_FEGCRAFT_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision):raise RuntimeError('REVIEWED_HELP_ROOT_AND_PIN_REQUIRED')
    h=load(HELPER,'scripts/diagnostics/fegcraft-admission-readiness.py');safe(ROOT/'.chat-release.lock')
    with (ROOT/'.chat-release.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        run('git','-C',str(REPO),'merge-base','--is-ancestor',revision,'origin/main')
        if len(sys.argv)==3 and sys.argv[1]=='--rollback':return rollback(Path(sys.argv[2]),h)
        if sys.argv[1:]:raise RuntimeError('REVIEWED_HELP_ARGUMENTS_INVALID')
        before=h.snapshot();h.baseline(before);h.addon();h.evidence(json.loads(read(h.EVIDENCE)))
        for name in FILES:
            if name!='server.py':run('git','-C',str(REPO),'diff','--exit-code',h.TESTED,revision,'--','services/fegcraft-assistant/'+name)
        role_evidence(json.loads(read(ROLE_REPORT)))
        role=load(revision,'scripts/deploy/prepare-fegcraft-slot-role.py')
        role.driver_evidence(json.loads(read(role.DRIVER)))
        verified=role.actor(source(revision,'scripts/lib/fegcraft-slot-role.mjs'),'verify',role.read_intent(h))
        profile_raw=read(INSTALL/'compose.json');manifest_raw=read(INSTALL/'manifest.json')
        profile=json.loads(profile_raw);manifest=json.loads(manifest_raw);service=profile['services']['assistant']
        check_runtime(SERVICE,service,manifest['owner'])
        uid,gid=map(int,service['user'].split(':'));info=SECRET.stat()
        if (read(SECRET)!=verified['dsn'].encode() or info.st_uid!=uid or info.st_gid!=gid or stat.S_IMODE(info.st_mode)!=0o400):
            raise RuntimeError('REVIEWED_HELP_ROLE_SECRET_CHANGED')
        del verified
        if json.loads(run('docker','image','inspect',IMAGE))[0]['Id']!=IMAGE:raise RuntimeError('REVIEWED_HELP_IMAGE_CHANGED')
        directory=ROOT/'releases'/('vector-fegcraft-reviewed-help-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3))
        safe(directory);directory.mkdir(mode=0o700)
        print('Dienstprüfung und Rückrollbelege:',directory,flush=True)
        code=directory/'code';code.mkdir(mode=0o755);code.chmod(0o755)
        for name in FILES:
            raw=source(revision,'services/fegcraft-assistant/'+name)
            if name.endswith('.py'):ast.parse(raw)
            atomic(code/name,raw,0o644)
        if sha(read(code/'public-knowledge.json'))!=h.CATALOG:raise RuntimeError('REVIEWED_HELP_CATALOG_CHANGED')
        old_code=next(Path(m['source']) for m in service['volumes'] if m['target']=='/code')
        for name in ('health.py','read-probe.py'):atomic(code/name,read(old_code/name),0o644)
        probe=source(revision,'tests/fegcraft-service-smoke.py');ast.parse(probe);atomic(code/'rollout-probe.py',probe,0o644)
        value=candidate(profile,code,code/'public-knowledge.json')
        result=stage(directory,value,manifest['owner']);atomic(directory/'stage-result.json',(json.dumps(result,indent=2)+'\n').encode())
        if h.snapshot()!=before or read(INSTALL/'compose.json')!=profile_raw or read(INSTALL/'manifest.json')!=manifest_raw:
            raise RuntimeError('REVIEWED_HELP_BASELINE_CHANGED_DURING_STAGE')
        new_profile=(json.dumps(value,indent=2)+'\n').encode();next_manifest=copy.deepcopy(manifest)
        next_manifest.update(compose_sha256=sha(new_profile),backend_revision=revision,backend_release=str(directory))
        new_manifest=(json.dumps(next_manifest,indent=2)+'\n').encode()
        record=dict(status='prepared',revision=revision,protected=protected(before),old_profile_sha=sha(profile_raw),
          old_manifest_sha=sha(manifest_raw),new_profile_sha=sha(new_profile),new_manifest_sha=sha(new_manifest))
        atomic(directory/'compose.before.json',profile_raw);atomic(directory/'manifest.before.json',manifest_raw)
        atomic(directory/'compose.candidate.json',new_profile);atomic(directory/'deployment.json',(json.dumps(record,indent=2)+'\n').encode())
        atomic(directory/'release.py',Path(__file__).read_bytes(),0o700)
        atomic(directory/'rollback.sh',('#!/bin/bash\nset -Eeuo pipefail\nexport VECTOR_FEGCRAFT_REV='+revision+'\nexec python3 '+shlex.quote(str(directory/'release.py'))+' --rollback '+shlex.quote(str(directory))+'\n').encode(),0o700)
        run('docker','compose','-p',SERVICE,'-f',str(directory/'compose.candidate.json'),'config','--quiet')
        try:
            atomic(INSTALL/'compose.json',new_profile);atomic(INSTALL/'manifest.json',new_manifest);compose()
            coverage=healthy(SERVICE,value['services']['assistant'],manifest['owner'])
            if protected_live(h)!=record['protected']:raise RuntimeError('REVIEWED_HELP_PROTECTED_PRODUCTION_CHANGED')
            record['status']='deployed';atomic(directory/'deployment.json',(json.dumps(record,indent=2)+'\n').encode())
        except BaseException:
            rollback(directory,h);raise
        summary=dict(deployed=True,only_assistant_recreated=True,minecraft_unchanged=True,other_services_unchanged=True,
          coverage=coverage,knowledge_mode='reviewed-local-selection',reviewed_passages=14,universal_mod_accuracy_claimed=False,
          qualification=result,role_secret_only=True,production_state_retained=True,real_chat_verified=False,
          messages_sent=0,welcome_sent=False,rollback=str(directory/'rollback.sh'))
        atomic(directory/'result.json',(json.dumps(summary,indent=2)+'\n').encode());print(json.dumps(summary,indent=2))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if type(exc) is RuntimeError else type(exc).__name__)
        raise SystemExit(1)
