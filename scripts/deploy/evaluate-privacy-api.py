#!/usr/bin/env python3
"""Privacy-enabled built app + native service + new disposable DB; no deployment."""
import ast
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
import uuid

ROOT=Path('/root/vector-workspace')
REPO=ROOT/'github/vector'
SERVICE_QUALIFIED_REV='b91604860fc192aa4bde94cc9be5d29107312633'
STAGED_REV=os.environ.get('VECTOR_PRIVACY_API_APP_REV',SERVICE_QUALIFIED_REV)
APP_USER='1001:1001'
APP_IMAGE=os.environ.get('VECTOR_PRIVACY_API_APP_IMAGE_ID',
    'sha256:ea6917c94e64d96af103206ed75eec7d77194ed0221bb0057a0baa67d60d4f00')
SERVICE_REPORT=ROOT/'releases/vector-privacy-ner-service-evaluation-20261016T074701Z-2563de/result.json'


def run(*args,data=None,timeout=60,error_path=None):
    result=subprocess.run(args,input=data,capture_output=True,timeout=timeout)
    if result.returncode:
        if error_path:error_path.write_bytes(result.stderr)
        raise RuntimeError('Isolated privacy API check failed.'+(f' Details: {error_path}' if error_path else ''))
    return result.stdout


def source(revision,path):
    return run('git','-C',str(REPO),'show',revision+':'+path).decode()


def namespace(revision,path,name):
    content=source(revision,path);ast.parse(content)
    module={'__name__':name};exec(compile(content,path,'exec'),module);return module


def require_staged_app_unchanged(revision):
    if not re.fullmatch('[a-f0-9]{40}',STAGED_REV) or not re.fullmatch('sha256:[a-f0-9]{64}',APP_IMAGE):
        raise RuntimeError('Invalid staged application revision/image handoff.')
    # Reuse the observed built image only if every runtime/build input is equal.
    run('git','-C',str(REPO),'diff','--quiet',STAGED_REV,revision,'--','.',
        ':!docs/**',':!tests/**',':!scripts/**',':!.github/**',':!CHANGELOG.md')
    metadata=json.loads(run('docker','image','inspect',APP_IMAGE))[0]
    if metadata['Id']!=APP_IMAGE:raise RuntimeError('Observed staged image missing.')


def private_limits(name,network,user,memory='512m'):
    return ['--name',name,'--pull','never','--network',network,'--user',user,
        '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--cpus','1','--memory',memory,'--memory-swap',memory,'--pids-limit','128',
        '--tmpfs','/tmp:rw,nosuid,nodev,size=128m,mode=1777']



CLIENT_PREFLIGHT = r"""
const fs=require('node:fs');
const {createRequire}=require('node:module');
let stage='identity';
try {
  if(process.getuid()!==1001||process.getgid()!==1001)throw Error('Wrong application identity.');
  stage='package';JSON.parse(fs.readFileSync('/app/package.json','utf8'));
  stage='pg';const {Client}=createRequire('/app/package.json')('pg');
  if(typeof Client!=='function')throw Error('PostgreSQL client unavailable.');
  stage='test-script';fs.readFileSync('/work/api-test.mjs');
  console.log(JSON.stringify({uid:process.getuid(),gid:process.getgid(),
    package_readable:true,pg_client_available:true,script_readable:true}));
} catch(error) {
  console.error(JSON.stringify({error:'API_CLIENT_PREFLIGHT_FAILED',stage,code:error.code||'INVALID_SETUP'}));
  process.exitCode=1;
}
"""


def api_client_args(name,network,work,environment):
    # App dependencies are owned by the app user; never loosen image permissions
    # or run the test client as root to load them.
    return ['docker','run',*private_limits(name,network,APP_USER),
        '--env-file',str(environment),'--mount',f'type=bind,src={work},dst=/work,readonly',
        '--workdir','/app','--entrypoint','node',APP_IMAGE,'/work/api-test.mjs']


def validate_client_preflight(result):
    if result!={'uid':1001,'gid':1001,'package_readable':True,
                'pg_client_available':True,'script_readable':True}:
        raise RuntimeError('Application-user package preflight did not pass.')


def report_checked():
    if SERVICE_REPORT.is_symlink() or SERVICE_REPORT.parent.is_symlink():raise RuntimeError('Unexpected service report path.')
    report=json.loads(SERVICE_REPORT.read_text())
    for key in ['passed','runtime_consent_roundtrip','tool_evidence_masked','auth_and_input_limits',
                'idle_unload_and_wake','service_outage_blocked','production_unchanged','private_network']:
        if report.get(key) is not True:raise RuntimeError('Observed native service qualification is incomplete.')
    if report.get('revision')!=SERVICE_QUALIFIED_REV or report.get('case_count')!=32 or report.get('cloud_calls')!=0:
        raise RuntimeError('Unexpected native service qualification revision or fixture count.')
    return report


def main():
    os.umask(0o077)
    revision=os.environ.get('VECTOR_PRIVACY_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision):
        raise RuntimeError('Run as root with exact VECTOR_PRIVACY_REV.')
    fetched=run('git','-C',str(REPO),'rev-parse','refs/remotes/origin/feat/privacy-composer-review-20261016').decode().strip()
    if fetched!=revision:raise RuntimeError('Fetched branch revision changed.')
    with (ROOT/'.chat-release.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        helper=namespace(revision,'scripts/deploy/evaluate-privacy-review.py','privacy_api_helpers')
        service=namespace(revision,'scripts/deploy/evaluate-privacy-ner-service.py','privacy_api_native')
        qualified=report_checked();require_staged_app_unchanged(revision)
        if qualified['qualified_image']!=service['QUALIFIED_IMAGE']:
            raise RuntimeError('Native image differs from the observed qualified image.')
        before=helper['fingerprint']()
        if before['/vector-app']['image']!='sha256:e59160f17f47b2b8231e417bc64c25ce82a5a7320be6a0b47c6d8b226f699a80':raise RuntimeError('Production image changed.')
        idle="""import pg from 'pg';const c=new pg.Client({connectionString:process.env.DATABASE_URL,connectionTimeoutMillis:5000});try{await c.connect();await c.query('BEGIN READ ONLY');await c.query(\"SET LOCAL statement_timeout = '5s'\");const r=await c.query(\"SELECT COUNT(*)::int AS n FROM agent_jobs WHERE status IN ('queued','running')\");if(r.rows[0].n!==0)throw Error('busy');}finally{await c.end();}"""
        run('docker','exec','-i','vector-app','node','--input-type=module',data=idle.encode())
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
        release=ROOT/'releases'/('vector-privacy-api-evaluation-'+stamp);release.mkdir(mode=0o700)
        work=service['prepare_work_directory'](release/'input')
        for name,path in {'server.py':'services/privacy-ner/server.py','privacy-ner-core.py':'lib/privacy-ner-core.py',
                          'api-test.mjs':'tests/privacy-api.integration.mjs'}.items():
            target=work/name;target.write_text(source(revision,path));target.chmod(0o644)
        token=work/'service-token';token.write_text(secrets.token_hex(32));token.chmod(0o444)
        password=secrets.token_hex(24)
        db_url='postgres://vector_privacy_test:'+password+'@privacy-test-db:5432/vector_privacy_api_test'
        environment=release/'test.env'
        environment.write_text('\n'.join([
            'DATABASE_URL='+db_url,'VECTOR_SECRET='+secrets.token_hex(32),
            'FILE_ENCRYPTION_KEY='+secrets.token_hex(32),
            'VECTOR_PRIVACY_TEST_PASSWORD='+secrets.token_hex(24),
            'VECTOR_PRIVACY_API_EVALUATION=1','VECTOR_PRIVACY_REVIEW=1','VECTOR_LOCAL_WORKERS=1',
            'FILE_STORAGE_PATH=/tmp/vector-privacy-api-files','COOKIE_SECURE=false',
            'HOSTNAME=0.0.0.0','PORT=3000','NEXT_TELEMETRY_DISABLED=1'])+'\n')
        pg_env=release/'postgres.env';pg_env.write_text('\n'.join([
            'POSTGRES_USER=vector_privacy_test','POSTGRES_PASSWORD='+password,
            'POSTGRES_DB=vector_privacy_api_test','PGDATA=/var/lib/postgresql/data/pgdata'])+'\n')
        suffix=stamp.lower();network='vector-privacy-api-'+suffix
        pg_name='vector-privacy-api-db-'+suffix;app_name='vector-privacy-api-app-'+suffix
        ner_name='vector-privacy-api-ner-'+suffix;client_name='vector-privacy-api-client-'+suffix
        owned=[];network_created=False
        try:
            run('docker','network','create','--internal',network);network_created=True
            owned.append(pg_name)
            run('docker','run','--detach',*private_limits(pg_name,network,'postgres'),
                '--network-alias','privacy-test-db','--env-file',str(pg_env),
                '--tmpfs','/var/lib/postgresql/data:rw,nosuid,nodev,size=512m,mode=1777',
                '--tmpfs','/var/run/postgresql:rw,nosuid,nodev,size=16m,mode=1777',
                before['/vector-postgres']['image'],'postgres','-c','shared_buffers=32MB','-c','max_connections=30')
            ready=False
            for _ in range(60):
                result=subprocess.run(['docker','exec',pg_name,'pg_isready','-U','vector_privacy_test','-d','vector_privacy_api_test'],capture_output=True)
                if result.returncode==0:ready=True;break
                time.sleep(.25)
            if not ready:raise RuntimeError('Disposable PostgreSQL did not become ready.')
            owned.append(ner_name)
            run(*service['service_args'](ner_name,qualified['qualified_image'],network,work,token))
            owned.append(app_name)
            run('docker','run','--detach',*private_limits(app_name,network,APP_USER,'1g'),
                '--network-alias','privacy-test-app','--env-file',str(environment),
                '--mount',f'type=bind,src={token},dst=/run/secrets/vector_privacy_ner_token,readonly',
                '--workdir','/app','--entrypoint','node',APP_IMAGE,'server.js')
            args=api_client_args(client_name,network,work,environment)
            print('Verify application package, PostgreSQL client and test script as UID/GID 1001.',flush=True)
            owned.append(client_name)
            preflight=json.loads(run(*args[:-1],'--eval',CLIENT_PREFLIGHT,timeout=30,
                error_path=release/'client-preflight-stderr.log'))
            validate_client_preflight(preflight)
            run('docker','rm','-v',client_name);owned.remove(client_name)
            print('Test the actual privacy-enabled app, native model, real login and disposable database. No worker or cloud credentials.',flush=True)
            owned.append(client_name)
            normal=json.loads(run(*args,timeout=600,error_path=release/'api-stderr.log'))
            run('docker','rm','-v',client_name);owned.remove(client_name)
            run('docker','stop','--time','10',ner_name,timeout=30)
            image_index=args.index(APP_IMAGE);args[image_index:image_index]=['--env','VECTOR_PRIVACY_API_PHASE=outage']
            owned.append(client_name)
            outage=json.loads(run(*args,timeout=120,error_path=release/'outage-stderr.log'))
            for name in owned:
                metadata=json.loads(run('docker','inspect',name))[0]
                if metadata['HostConfig']['PortBindings']:raise RuntimeError('Unexpected published port.')
            if not json.loads(run('docker','network','inspect',network))[0]['Internal']:
                raise RuntimeError('Evaluation network is not internal.')
            result=dict(passed=normal['passed'] and outage['passed'],revision=revision,app_runtime_revision=STAGED_REV,
                app_image=APP_IMAGE,native_image=qualified['qualified_image'],client_preflight=preflight,normal=normal,outage=outage,
                isolated_database=True,production_unchanged=helper['fingerprint']()==before,
                cloud_calls=0,api_cost_chf=0,production_activated=False)
            result['passed']=result['passed'] and result['production_unchanged']
            (release/'result.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result,indent=2));print('Report:',release/'result.json')
            if not result['passed']:raise RuntimeError('Privacy-enabled app qualification failed.')
        finally:
            # Logs contain synthetic test data only; preserve diagnostics before cleanup.
            for name,label in [(app_name,'app'),(ner_name,'native'),(pg_name,'database')]:
                if name in owned:
                    log=subprocess.run(['docker','logs',name],capture_output=True)
                    (release/(label+'-container.log')).write_bytes(log.stdout+log.stderr)
            errors=[]
            for name in reversed(owned):
                if subprocess.run(['docker','rm','-f','-v',name],capture_output=True).returncode:errors.append(name)
            if network_created and subprocess.run(['docker','network','rm',network],capture_output=True).returncode:errors.append(network)
            for path in [token,environment,pg_env]:path.unlink(missing_ok=True)
            if errors:raise RuntimeError('Isolated resource cleanup could not be verified: '+', '.join(errors))
            print('Temporary app, native service, client, database, synthetic secret files and network removed.',flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)
        raise SystemExit(1)
