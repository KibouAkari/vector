#!/usr/bin/env python3
"""Owner-run actual Host Agent read; never export records or invoke a model."""
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

ROOT=Path('/root/vector-workspace')
REPO=ROOT/'github/vector'
CURRENT_IMAGE='sha256:c33a1b853a16602e9413f4784de85337135288f55cf2437e6516b46ccfd463c0'
CONTAINERS=('vector-app','vector-worker','vector-runner','vector-postgres','vector-redis',
            'vector-privacy-ner','vector-local-inference','fegcraft-updated')
COMPOSE=(Path('/opt/vector/docker-compose.yml'),Path('/opt/fegcraft-updated/docker-compose.yml'))

def run(args, **kwargs):
    result=subprocess.run(args,capture_output=True,text=True,timeout=75,**kwargs)
    if result.returncode:
        raise RuntimeError('LOCAL_READ_STEP_FAILED')
    return result.stdout

def snapshot():
    return {name:run(['docker','inspect','--format',
        '{{.Id}}|{{.Image}}|{{.State.StartedAt}}|{{.State.Running}}',name]).strip() for name in CONTAINERS}

def uri(source):
    return 'data:text/javascript;base64,'+base64.b64encode(source.encode()).decode()

def program(revision):
    def source(path):
        return run(['git','-C',str(REPO),'show',revision+':'+path])
    controls=uri(source('lib/chat-controls.mjs'))
    statistics=uri(source('lib/local-server-statistics.mjs').replace("'./chat-controls.mjs'",json.dumps(controls)))
    host=uri(source('lib/host-agent.js'))
    return '''
try {
  const host=await import(HOST);
  const {localServerStatistics}=await import(STATISTICS);
  await host.hostSnapshot();
  const result=await localServerStatistics({text:'Zeige die FEGCraft Statistik',allowServer:true,inspect:host.hostInspect});
  if(!Number.isInteger(result?.files)||result.files<1)throw Error('INCOMPLETE');
  console.log(JSON.stringify({snapshot_available:true,statistics_complete:true,files:result.files}));
} catch {
  console.error('HOST_AGENT_READ_FAILED');process.exitCode=1;
}
'''.replace('HOST',json.dumps(host),1).replace('STATISTICS',json.dumps(statistics),1)

def main():
    os.umask(0o077)
    revision=os.environ.get('VECTOR_CHAT_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision):
        raise RuntimeError('ROOT_AND_PINNED_REVISION_REQUIRED')
    before=snapshot()
    if before['vector-app'].split('|')[1]!=CURRENT_IMAGE or not all(value.endswith('|true') for value in before.values()):
        raise RuntimeError('QUALIFIED_RUNTIME_CHANGED')
    hashes={path:hashlib.sha256(path.read_bytes()).hexdigest() for path in COMPOSE}
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3)
    report=ROOT/'releases'/('vector-chat-server-read-'+stamp)
    report.mkdir(mode=0o700)
    result={'revision':revision,'passed':False,'model_calls':0,'cloud_calls':0,
            'records_exported':False,'production_activated':False}
    try:
        output=run(['docker','exec','-i','--user','1001:1001','vector-app','node','--input-type=module','-'],input=program(revision))
        value=json.loads(output)
        if (set(value)!={'snapshot_available','statistics_complete','files'}
                or value.get('snapshot_available') is not True or value.get('statistics_complete') is not True
                or type(value.get('files')) is not int or not 1<=value['files']<=120):
            raise RuntimeError('LOCAL_READ_NOT_QUALIFIED')
        result.update(value)
    except BaseException as failure:
        result['error']=type(failure).__name__
    finally:
        try:
            result['production_unchanged']=snapshot()==before and all(hashlib.sha256(path.read_bytes()).hexdigest()==digest for path,digest in hashes.items())
        except Exception:
            result['production_unchanged']=False
        result['passed']=bool(not result.get('error') and result.get('statistics_complete') and result['production_unchanged'])
        (report/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
    print('Report:',report/'result.json',flush=True)
    if not result['passed']:
        raise RuntimeError('LOCAL_SERVER_READ_CHECK_FAILED; no model called and no deployment performed')

if __name__=='__main__':
    try:
        main()
    except Exception as failure:
        print('ERROR:',str(failure) if isinstance(failure,RuntimeError) else type(failure).__name__)
        raise SystemExit(1)
