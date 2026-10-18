#!/usr/bin/env python3
"""Provision/qualify only the owned no-app-data CPU role; no service deployment."""
import ast
import base64
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import select
import shlex
import stat
import subprocess
import sys

ROOT=Path('/root/vector-workspace')
REPO=ROOT/'github/vector'
STATE=ROOT/'local-inference/fegcraft-slot-role'
HELPER='8d80f1d3c4ecdd818be33519298333423b152e59'
DRIVER_REV='395796b051a1f957a9ae24d6678d228ecf60b0ca'
DRIVER=ROOT/'releases/vector-fegcraft-admission-driver-20261018T083328Z-6e49a8/result.json'
IMAGE='sha256:db331e915c9cce6f6440b629c6e3c4009b4ffd955046b484f0433090771f78c2'
WHEEL_SHA='046c5afb8d315a61e7635f50c9c0a0506b13cba2a0eb5b48feb8ecd1e1d29168'
LABEL='com.vector.slot-role-probe'
SLOT='6194261933202610'


def run(*args,input=None,timeout=30):
    value=subprocess.run(args,input=input,capture_output=True,timeout=timeout)
    if value.returncode:raise RuntimeError('SLOT_ROLE_COMMAND_FAILED:'+args[0])
    return value.stdout


def source(revision,path):return run('git','-C',str(REPO),'show',revision+':'+path)


def write_new(path,raw,mode=0o600,uid=0,gid=0):
    if any(p.is_symlink() for p in (path,*path.parents)):raise RuntimeError('SLOT_ROLE_SYMLINK')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    with os.fdopen(fd,'wb') as f:
        f.write(raw);f.flush();os.fsync(f.fileno());os.fchown(f.fileno(),uid,gid);os.fchmod(f.fileno(),mode)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def driver_evidence(value):
    if (value.get('revision')!=DRIVER_REV or value.get('driver_image')!=IMAGE or value.get('wheel_manifest_sha256')!=WHEEL_SHA
        or any(value.get(k) is not True for k in ('passed','cleanup_verified','production_unchanged'))
        or any(value.get(k) is not False for k in ('production_activated','eligible_for_activation','production_role_created'))
        or any(value.get(k)!=0 for k in ('model_calls','cloud_calls','messages_sent'))):
        raise RuntimeError('SLOT_ROLE_DRIVER_EVIDENCE_MISMATCH')
    result=value.get('isolated_admission',{})
    if (result.get('server_version_num')!=170011 or result.get('driver_version')!='3.2.13'
        or any(result.get(k) is not True for k in ('passed','binary','disposable_database','application_read_denied',
          'permanent_create_denied','contention_both_directions_passed','normal_and_exception_release_passed','fixture_role_and_schema_removed',
          'inherited_public_temp','temporary_table_creation_possible'))
        or result.get('global_public_acl_changed') is not False or result.get('production_role_created') is not False):
        raise RuntimeError('SLOT_ROLE_ISOLATED_EVIDENCE_MISMATCH')


def read_intent(h):
    path=STATE/'intent.json'
    raw=h.read(path);info=path.stat()
    if info.st_uid!=0 or stat.S_IMODE(info.st_mode)!=0o600:raise RuntimeError('SLOT_ROLE_INTENT_PERMISSIONS')
    value=json.loads(raw)
    if (set(value)!={'owner','password'} or not isinstance(value['owner'],str) or not isinstance(value['password'],str)
        or not re.fullmatch('[a-f0-9]{32}',value['owner']) or not re.fullmatch('[a-f0-9]{64}',value['password'])):
        raise RuntimeError('SLOT_ROLE_INTENT_INVALID')
    return value


def private_endpoint():
    app,db=json.loads(run('docker','inspect','vector-app','vector-postgres'))
    network='vector-internal'
    if (app.get('Name')!='/vector-app' or db.get('Name')!='/vector-postgres'
        or not app['State'].get('Running') or not db['State'].get('Running')
        or network not in app['NetworkSettings']['Networks'] or network not in db['NetworkSettings']['Networks']):
        raise RuntimeError('SLOT_ROLE_PRIVATE_NETWORK_CHANGED')
    value=db['NetworkSettings']['Networks'][network]
    aliases=['vector-postgres',*(value.get('Aliases') or []),*(value.get('DNSNames') or [])]
    service=(db.get('Config',{}).get('Labels') or {}).get('com.docker.compose.service')
    if service:aliases.append(service)
    return {'container':'vector-postgres','container_id':db['Id'],'network':network,
      'aliases':sorted(set(aliases)),
      'addresses':[v for v in (value.get('IPAddress'),value.get('GlobalIPv6Address')) if v]}


def actor(module,action,intent):
    encoded=base64.b64encode(module).decode()
    code="""import pg from 'pg';import dns from 'node:dns/promises';
let data='';for await(const chunk of process.stdin)data+=chunk;
const input=JSON.parse(data);
try{
 const m=await import('data:text/javascript;base64,ENCODED');
 const connect=dsn=>new pg.Client({connectionString:dsn,connectionTimeoutMillis:3000,query_timeout:6000});
 const lookup=async(host,options)=>{
   let timer;try{return await Promise.race([dns.lookup(host,options),new Promise((_,reject)=>{
     timer=setTimeout(()=>reject(Error('DNS_TIMEOUT')),5000);
   })]);}finally{clearTimeout(timer);}
 };
 const args={dsn:process.env.DATABASE_URL,owner:input.owner,password:input.password,connect,endpoint:input.endpoint,lookup};
 const result=input.action==='prepare'?await m.prepareRole(args):input.action==='rollback'?await m.rollbackRole(args):null;
 if(!result)throw Error('INVALID_ACTION');console.log(JSON.stringify(result));
}catch(e){console.error('SLOT_ROLE_DATABASE_OPERATION_FAILED '+(e.name==='RoleGuardError'?e.code:/^[A-Z0-9]{5}$/.test(e.code??'')?e.code:'UNAVAILABLE'));process.exitCode=1;}
""".replace('ENCODED',encoded)
    value=subprocess.run(['docker','exec','-i','vector-app','node','--input-type=module','-e',code],
      input=json.dumps(dict(action=action,owner=intent['owner'],password=intent['password'],endpoint=private_endpoint())).encode(),capture_output=True,timeout=120)
    if value.returncode:
        # Only a fixed guard/SQLSTATE code may leave the privileged actor.
        text=value.stderr.decode(errors='replace').strip()
        if re.fullmatch(r'SLOT_ROLE_DATABASE_OPERATION_FAILED [A-Z0-9_]+',text):raise RuntimeError(text)
        raise RuntimeError('SLOT_ROLE_DATABASE_OPERATION_FAILED')
    return json.loads(value.stdout)


HOLD=r"""import pg from 'pg';import readline from 'node:readline';
const db=new pg.Client({connectionString:process.env.DATABASE_URL,connectionTimeoutMillis:3000,query_timeout:5000});
let owned=false;const timer=setTimeout(()=>process.exit(2),45000);
try{await db.connect();await db.query('BEGIN READ ONLY');await db.query("SET LOCAL statement_timeout='3s'");
 for(let n=0;n<30;n++){owned=(await db.query('SELECT pg_try_advisory_lock($1::bigint) AS ok',['6194261933202610'])).rows[0].ok;if(owned)break;await new Promise(r=>setTimeout(r,500));}
 if(!owned)throw Error('BUSY');console.log(JSON.stringify({ready:true}));
 for await(const line of readline.createInterface({input:process.stdin})){if(line==='release')break;}
}catch(_){process.exitCode=1;}finally{if(owned)await db.query('SELECT pg_advisory_unlock($1::bigint)',['6194261933202610']);await db.end();clearTimeout(timer);}
"""
CHECK=r"""import pg from 'pg';const db=new pg.Client({connectionString:process.env.DATABASE_URL,connectionTimeoutMillis:3000,query_timeout:5000});
try{await db.connect();await db.query('BEGIN READ ONLY');const row=(await db.query('SELECT pg_try_advisory_lock($1::bigint) AS available',['6194261933202610'])).rows[0];if(row.available)await db.query('SELECT pg_advisory_unlock($1::bigint)',['6194261933202610']);console.log(JSON.stringify(row));}catch(_){process.exitCode=1;}finally{await db.end();}
"""


def ready(process,timeout):
    if not select.select([process.stdout],[],[],timeout)[0] or json.loads(process.stdout.readline() or b'{}')!={'ready':True}:
        raise RuntimeError('SLOT_ROLE_READY_TIMEOUT_OR_BUSY')


def release(process):
    try:out,err=process.communicate(input=b'release\n',timeout=10)
    except subprocess.TimeoutExpired:
        process.kill();process.communicate(timeout=5);raise RuntimeError('SLOT_ROLE_LEASE_RELEASE_TIMEOUT')
    if process.returncode:raise RuntimeError('SLOT_ROLE_LEASE_RELEASE_FAILED')
    return out


def no_mounted_secret(secret):
    ids=run('docker','ps','-aq').decode().split()
    if len(ids)>256:raise RuntimeError('SLOT_ROLE_CONTAINER_INVENTORY_REVIEW')
    for value in json.loads(run('docker','inspect',*ids)) if ids else []:
        for mount in value.get('Mounts',[]):
            if mount.get('Type')=='bind' and secret.is_relative_to(Path(mount['Source'])):
                raise RuntimeError('SLOT_ROLE_SECRET_IN_USE_ROLLBACK_REFUSED')


def cleanup(name,owner):
    ids=run('docker','ps','-aq','--filter','name=^/'+name+'$').decode().split()
    for identity in ids:
        value=json.loads(run('docker','inspect',identity))[0]
        if (value['Config'].get('Labels') or {}).get(LABEL)!=owner:raise RuntimeError('SLOT_ROLE_PROBE_OWNER_CHANGED')
        run('docker','rm','-f',identity)


def probe(work,secret,uid,gid,owner):
    def command(mode,name):return ['docker','run','--rm','-i','--name',name,'--label',LABEL+'='+owner,'--pull','never',
      '--network','vector-internal','--read-only','--user',str(uid)+':'+str(gid),'--cap-drop','ALL','--security-opt','no-new-privileges:true',
      '--cpus','1','--memory','192m','--pids-limit','64','--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777',
      '--mount','type=bind,src='+str(work)+',dst=/code,readonly','--mount','type=bind,src='+str(secret)+',dst=/run/secrets/slot-dsn,readonly',
      '--entrypoint','python3',IMAGE,'/code/tests/fegcraft-slot-role-probe.py',mode,'/run/secrets/slot-dsn']
    one='vector-slot-role-ping-'+owner;two='vector-slot-role-busy-'+owner;three='vector-slot-role-hold-'+owner
    coordinator=client=None
    try:
        if json.loads(run(*command('ping',one),timeout=12)).get('passed') is not True:raise RuntimeError('SLOT_ROLE_LOGIN_FAILED')
        coordinator=subprocess.Popen(['docker','exec','-i','vector-app','node','--input-type=module','-e',HOLD],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        ready(coordinator,24)
        if json.loads(run(*command('busy',two),timeout=12))!={'passed':True,'shared_slot_busy_verified':True}:raise RuntimeError('SLOT_ROLE_CONTENTION_FAILED')
        release(coordinator);coordinator=None
        client=subprocess.Popen(command('hold',three),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        ready(client,10)
        if json.loads(run('docker','exec','vector-app','node','--input-type=module','-e',CHECK,timeout=10))!={'available':False}:raise RuntimeError('SLOT_ROLE_REVERSE_CONTENTION_FAILED')
        value=json.loads(release(client));client=None
        if value!={'passed':True,'shared_slot_released':True}:raise RuntimeError('SLOT_ROLE_RELEASE_FAILED')
        if json.loads(run('docker','exec','vector-app','node','--input-type=module','-e',CHECK,timeout=10))!={'available':True}:raise RuntimeError('SLOT_ROLE_RELEASE_NOT_OBSERVED')
        return {'role_login_verified':True,'same_database_shared_slot_verified':True,'both_contention_directions_verified':True,'release_verified':True}
    finally:
        failed=False
        for process in (client,coordinator):
            if process is not None:
                try:release(process)
                except Exception:failed=True
        for name in (three,two,one):
            try:cleanup(name,owner)
            except Exception:failed=True
        if failed:raise RuntimeError('SLOT_ROLE_PROBE_CLEANUP_FAILED')


def main():
    os.umask(0o077)
    revision=os.environ.get('VECTOR_FEGCRAFT_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision):raise RuntimeError('SLOT_ROLE_ROOT_AND_PIN_REQUIRED')
    raw=source(HELPER,'scripts/diagnostics/fegcraft-admission-readiness.py');ast.parse(raw)
    namespace={'__name__':'readiness_support','__file__':str(REPO/'scripts/diagnostics/fegcraft-admission-readiness.py')}
    exec(compile(raw,namespace['__file__'],'exec'),namespace)
    from types import SimpleNamespace
    h=SimpleNamespace(**namespace);h.read(ROOT/'.chat-release.lock')
    with (ROOT/'.chat-release.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        run('git','-C',str(REPO),'merge-base','--is-ancestor',revision,'origin/main')
        module=source(revision,'scripts/lib/fegcraft-slot-role.mjs')
        secret=STATE/'slot-dsn'
        if sys.argv[1:]==['--rollback']:
            intent=read_intent(h);no_mounted_secret(secret)
            result=actor(module,'rollback',intent)
            if secret.exists():secret.unlink()
            print(json.dumps({'role_rollback':result,'production_activated':False}));return
        if sys.argv[1:]:raise RuntimeError('SLOT_ROLE_ARGUMENTS_INVALID')
        driver_evidence(json.loads(h.read(DRIVER)))
        image=json.loads(run('docker','image','inspect',IMAGE))[0]
        if image['Id']!=IMAGE:raise RuntimeError('SLOT_ROLE_DRIVER_IMAGE_CHANGED')
        before=h.snapshot();h.baseline(before);h.addon();h.evidence(json.loads(h.read(h.EVIDENCE)))
        for name in h.SOURCE_FILES:run('git','-C',str(REPO),'diff','--exit-code',h.TESTED,revision,'--','services/fegcraft-assistant/'+name)
        if any(p.is_symlink() for p in (STATE,*STATE.parents)):raise RuntimeError('SLOT_ROLE_STATE_SYMLINK')
        STATE.mkdir(mode=0o700,exist_ok=True)
        if STATE.stat().st_uid!=0 or STATE.stat().st_mode&0o077:raise RuntimeError('SLOT_ROLE_STATE_PERMISSIONS')
        intent_path=STATE/'intent.json'
        if not intent_path.exists():write_new(intent_path,(json.dumps({'owner':secrets.token_hex(16),'password':secrets.token_hex(32)})+'\n').encode())
        intent=read_intent(h)
        directory=ROOT/'releases'/('vector-fegcraft-slot-role-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3))
        if any(p.is_symlink() for p in (directory,*directory.parents)):raise RuntimeError('SLOT_ROLE_RELEASE_SYMLINK')
        directory.mkdir(mode=0o700)
        write_new(directory/'prepare.py',Path(__file__).read_bytes(),0o700)
        write_new(directory/'rollback.sh',('#!/bin/bash\nset -Eeuo pipefail\nexport VECTOR_FEGCRAFT_REV='+revision+'\nexec python3 '+shlex.quote(str(directory/'prepare.py'))+' --rollback\n').encode(),0o700)
        print('Rolle und Sperrverbindung werden geprüft. Minecraft und alle laufenden Dienste bleiben unverändert.',flush=True)
        print('Belege:',directory,flush=True);print('Rollen-Rollback:',directory/'rollback.sh',flush=True)
        record={'revision':revision,'passed':False,'production_activated':False,'eligible_for_activation':False,
          'model_calls':0,'cloud_calls':0,'messages_sent':0,'driver_image':IMAGE,'database_role_writes_authorized':True}
        try:
            prepared=actor(module,'prepare',intent)
            record.update(database_destination_verified=True,role_owned=True,role_created=prepared['created'],privileges=prepared['privileges'])
            profile=json.loads(h.read(h.INSTALL/'compose.json'))['services']['assistant']
            uid,gid=map(int,profile['user'].split(':'))
            if secret.exists() or secret.is_symlink():
                if (h.read(secret)!=prepared['dsn'].encode() or secret.stat().st_uid!=uid or secret.stat().st_gid!=gid
                    or stat.S_IMODE(secret.stat().st_mode)!=0o400):
                    raise RuntimeError('SLOT_ROLE_EXISTING_SECRET_CHANGED')
            else:write_new(secret,prepared['dsn'].encode(),0o400,uid,gid)
            # The private DSN stays only in the root-owned secret tree and this
            # transient result. Never serialize it into a public report/log.
            del prepared
            work=directory/'input';work.mkdir(mode=0o755);work.chmod(0o755)
            for path in ('tests/fegcraft-slot-role-probe.py',*('services/fegcraft-assistant/'+name for name in ('runtime.py','stats.py','policy.py'))):
                target=work/path;target.parent.mkdir(parents=True,exist_ok=True)
                for parent in (target.parent,target.parent.parent):parent.chmod(0o755)
                raw=source(revision,path);ast.parse(raw);write_new(target,raw,0o644)
            record['shared_slot']=probe(work,secret,uid,gid,secrets.token_hex(12))
            record.update(cleanup_verified=True,production_containers_and_profiles_unchanged=h.snapshot()==before)
            if not record['production_containers_and_profiles_unchanged']:raise RuntimeError('SLOT_ROLE_PRODUCTION_CONFIGURATION_CHANGED')
            record.update(passed=True,dedicated_db_role_qualified=True,role_secret_path=str(secret))
        finally:
            (directory/'result.json').write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps(record,indent=2));print('Report:',directory/'result.json')
        print('Sperrrolle bereit. Noch kein Dienst-Rollout, keine Modellanfrage und keine Spielnachricht.')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if type(exc) is RuntimeError else type(exc).__name__)
        raise SystemExit(1)
