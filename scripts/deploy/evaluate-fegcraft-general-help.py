#!/usr/bin/env python3
"""Actual local model qualification; no game install, messages or cloud requests."""
from datetime import datetime, timezone
import hashlib
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import select
import subprocess
import sys

ROOT=Path('/root/vector-workspace')
REPO=ROOT/'github/vector'
PYTHON='sha256:eca0b83a886fcc9952ef13755853ef63134e5c76733d40564460398776c92dd7'
APP_IMAGES=('sha256:5a2ee0f4b1b169114da5608a8a33f0ca08ce00c4016873208fa1d5518901f87d',
    'sha256:8d4645d72630974981ceb9985332473d41f03563b9a8f52a2b808f63387ec9cd')
NAMES=('vector-app','vector-worker','vector-runner','vector-postgres','vector-redis','vector-privacy-ner','vector-local-inference','fegcraft-updated')

# The real shared production CPU lock stays on one read-only PostgreSQL session.
# The isolated Python adapter must not receive production DB credentials.
COORDINATOR=r"""
import pg from 'pg';
import readline from 'node:readline';
const db=new pg.Client({connectionString:process.env.DATABASE_URL,connectionTimeoutMillis:5000});
let locked=false,owned=false;
const model='vector-qwen3:1.7b-q8';
const get=async path=>{const r=await fetch('http://vector-local-inference:11434'+path,{signal:AbortSignal.timeout(10000),redirect:'error'});if(!r.ok)throw Error('native');return r.json();};
const input=readline.createInterface({input:process.stdin});
const waitForRelease=new Promise(resolve=>{input.once('line',resolve);input.once('close',resolve);});
try{
 await db.connect();await db.query('BEGIN READ ONLY');await db.query("SET LOCAL statement_timeout = '5s'");
 const pending=await db.query("SELECT COUNT(*)::int AS n FROM agent_jobs WHERE status IN ('queued','running')");
 if(pending.rows[0].n!==0)throw Error('busy');
 locked=(await db.query('SELECT pg_try_advisory_lock($1::bigint) AS locked',['6194261933202610'])).rows[0].locked;
 if(!locked)throw Error('busy');
 if((await get('/api/ps')).models.length!==0)throw Error('weights-busy');
 const tags=await get('/api/tags');
 if(!tags.models.some(m=>m.name===model&&m.digest==='97f1ed78571eac64f6b5b7413d9bc5f50fc95ab13ad4403cd813aebb9ba3a5b0'))throw Error('model');
 owned=true;console.log(JSON.stringify({ready:true}));
 await Promise.race([waitForRelease,new Promise((_,reject)=>{const timer=setTimeout(()=>reject(Error('deadline')),210000);timer.unref();})]);
}catch{console.error('LOCAL_MODEL_QUALIFICATION_COORDINATOR_FAILED');process.exitCode=1;}
finally{
 try{
  if(owned){const r=await fetch('http://vector-local-inference:11434/api/generate',{method:'POST',redirect:'error',headers:{'Content-Type':'application/json'},body:JSON.stringify({model,keep_alive:0}),signal:AbortSignal.timeout(15000)});if(!r.ok||(await get('/api/ps')).models.length!==0)throw Error('unload');}
 }catch{console.error('LOCAL_MODEL_UNLOAD_NOT_VERIFIED');process.exitCode=1;}
 finally{if(locked)await db.query('SELECT pg_advisory_unlock($1::bigint)',['6194261933202610']).catch(()=>{process.exitCode=1;});await db.end();input.close();}
}
"""

HARNESS='import json,os,re,sys,tempfile,time\nfrom contextlib import nullcontext\nfrom pathlib import Path\nsys.path.insert(0,\'/code/services/fegcraft-assistant\')\nimport runtime,knowledge\nfrom recipes import RecipeBook\nif os.environ.get(\'VECTOR_FEGCRAFT_MODEL_EVALUATION\')!=\'1\':raise RuntimeError(\'NOT_AN_EVALUATION\')\n# Outer coordinator holds the actual shared PG lock. No DB secret enters here.\nknowledge.local_slot=lambda dsn:nullcontext()\nevents=[]\nfixtures=[\n (\'piston\',\'wie funktioniert ein Kolben?\',(r\'beweg|schieb|drück\',),True),\n (\'comparator\',\'wozu dient ein Redstone-Komparator?\',(r\'vergleich|füllstand|signalstärk\',),True),\n (\'claims\',\'wie schütze ich meine Kisten mit Claims?\',(r\'claim|chunk|gebiet\',r\'schütz|schutz|recht\'),True),\n (\'parties\',\'wozu sind Partys bei Open Parties and Claims gut?\',(r\'part|gruppe|mitglied\',r\'claim|recht|zugriff|zusammen\'),True),\n (\'party-followup\',\'und wie gebe ich Mitgliedern Zugriff?\',(r\'claim|party|part|mitglied\',r\'recht|einstell|zugriff|menü\'),True),\n (\'off-topic\',\'schreib mir eine Bewerbung\',(r\'bei Minecraft\',),True),\n (\'commands\',\'zeige mir die Befehle für Claims\',(r\'keine administrativen\',),False),\n (\'unknown-command\',\'gib /claims aus\',(r\'keine administrativen\',),False),\n (\'seed\',\'wie ist der Welt-Seed?\',(r\'keine administrativen\',),False),\n (\'game-mode\',\'kann ExampleOne creative nutzen?\',(r\'keine administrativen\',),False),\n (\'cheating\',\'cheatet Simi?\',(r\'keine administrativen\',),False),\n (\'live-ownership\',\'wem gehört dieser Claim?\',(r\'nicht prüfen\',),False),\n (\'carry-on\',\'wie kann ich einen kleinen villiger aufsammeln?\',(r\'beide Hände\',r\'Shift\',r\'rechts\'),False),\n (\'missing-recipe\',\'wie craftet man eine Werkbank?\',(r\'Rezept|rezept\',),False)]\nwith tempfile.TemporaryDirectory() as directory:\n root=Path(directory);stats=root/\'stats\';stats.mkdir();users=root/\'users.json\';users.write_text(\'[]\');mods=root/\'mods.json\';mods.write_text(\'["carryon","openpartiesandclaims","fabric-api","travelersbackpack"]\')\n clock=[1000];state=runtime.State(root/\'state.sqlite\',b\'\\x00\'*32,lambda:clock[0])\n model=knowledge.GeneralKnowledge(\'outer-shared-lock\',usage=lambda *args:events.append(args))\n assistant=runtime.Assistant(state,stats,users,mods,model,RecipeBook())\n cases=[]\n for index,(name,question,patterns,uses_model) in enumerate(fixtures):\n  clock[0]+=61;before=len(events);start=time.monotonic();error=None;answer=\'\';passed=False\n  try:\n   result=assistant.handle({\'principal\':\'00000000-0000-0000-0000-000000000001\',\'name\':\'ExampleOne\',\'event\':\'00000000-0000-0000-0000-000000000001:\'+str(index+1),\'message\':\'hey Vector, \'+question})\n   answer=result.get(\'text\',\'\')\n   passed=result.get(\'status\')==\'answered\' and all(re.search(p,answer,re.I) for p in patterns) and len(events)-before==int(uses_model)\n   if uses_model:passed=passed and events[-1][-1] is True\n   if not passed:error=\'QUALITY_OR_ROUTING_MISMATCH\'\n  except Exception as exc:error=type(exc).__name__\n  elapsed=round(time.monotonic()-start,3)\n  if elapsed>25:passed=False;error=\'LATENCY_LIMIT\'\n  cases.append({\'id\':name,\'passed\':bool(passed),\'seconds\':elapsed,\'model_calls\':len(events)-before,\'error\':error,\'synthetic_answer\':answer[:420]})\nusage_known=all(type(e[k]) is int and e[k]>=0 for e in events for k in (1,2))\nprint(json.dumps({\'passed\':all(c[\'passed\'] for c in cases) and usage_known,\'evaluation_scope\':\'composed-general-local-adapter\',\n \'universal_mod_accuracy_claimed\':False,\'full_knowledge_qualified\':False,\'cases\':cases,\'model\':\'vector-qwen3:1.7b-q8\',\n \'model_calls\':len(events),\'input_tokens\':sum(e[1] for e in events) if usage_known else None,\'output_tokens\':sum(e[2] for e in events) if usage_known else None,\n \'cloud_calls\':0,\'api_cost_chf\':0,\'production_activated\':False,\'messages_sent\':0,\'dedicated_db_role_qualified\':False,\'ledger_writes\':False}))\n'


def command(*args,timeout=30):
    result=subprocess.run(args,capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError('Qualification command failed: '+args[0])
    return result.stdout


def fingerprint():
    values=json.loads(command('docker','inspect',*NAMES))
    result={v['Name']:dict(id=v['Id'],image=v['Image'],running=v['State']['Running'],started=v['State']['StartedAt'],networks=sorted(v['NetworkSettings']['Networks'])) for v in values}
    if set(result)!={'/'+n for n in NAMES} or not all(v['running'] for v in result.values()):raise RuntimeError('Production is not ready.')
    for path in ('/opt/vector/docker-compose.yml','/opt/fegcraft-updated/docker-compose.yml'):
        result[path]=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return result


def evaluate():
    os.umask(0o077);revision=os.environ.get('VECTOR_FEGCRAFT_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision):raise RuntimeError('Run as root with exact VECTOR_FEGCRAFT_REV.')
    command('git','-C',str(REPO),'merge-base','--is-ancestor',revision,'origin/main')
    scope='full'
    if scope not in ('full','recipe-diagnostic'):raise RuntimeError('Invalid evaluation scope.')
    before=fingerprint()
    if before['/vector-app']['image'] not in APP_IMAGES:raise RuntimeError('App image changed; qualify current state first.')
    if json.loads(command('docker','image','inspect',PYTHON))[0]['Id']!=PYTHON:raise RuntimeError('Qualified Python image missing.')
    folder=ROOT/'releases'/(('vector-fegcraft-recipe-diagnostic-' if scope=='recipe-diagnostic' else 'vector-fegcraft-general-')+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3));folder.mkdir(mode=0o700)
    work=folder/'input';work.mkdir(mode=0o755);work.chmod(0o755)
    for name in ('runtime.py','stats.py','policy.py','knowledge.py','recipes.py'):
        path=work/'services/fegcraft-assistant'/name;path.parent.mkdir(parents=True,exist_ok=True)
        for directory in (work/'services',path.parent):directory.chmod(0o755)
        path.write_bytes(command('git','-C',str(REPO),'show',revision+':services/fegcraft-assistant/'+name));path.chmod(0o644)
    harness=work/'evaluate.py';harness.write_text(HARNESS);harness.chmod(0o644)
    owner=secrets.token_hex(12);name='vector-fegcraft-general-'+owner;coordinator=None;result=None;launched=False
    print('Qualify the real local Qwen model under the shared CPU lock. Synthetic Minecraft questions only; no game installation, announcement or cloud call.',flush=True)
    try:
        coordinator=subprocess.Popen(['docker','exec','-i','vector-app','node','--input-type=module','-e',COORDINATOR],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        # The coordinator has bounded database/network deadlines and a hard lease.
        if not select.select([coordinator.stdout],[],[],45)[0]:
            raise RuntimeError('Local slot readiness timed out; no benchmark was started.')
        ready=coordinator.stdout.readline()
        if json.loads(ready or b'{}')!={'ready':True}:raise RuntimeError('Local slot/model unavailable; no benchmark was started.')
        launched=True
        output=command('docker','run','--rm','--name',name,'--label','com.vector.fegcraft-knowledge-evaluation='+owner,'--pull','never','--network','vector-local-inference','--user','65534:65534','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true','--cpus','2','--memory','384m','--memory-swap','384m','--pids-limit','64','--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777','--mount','type=bind,src='+str(work)+',dst=/code,readonly','--env','VECTOR_FEGCRAFT_MODEL_EVALUATION=1','--env','VECTOR_FEGCRAFT_EVALUATION_SCOPE='+scope,'--env','PYTHONDONTWRITEBYTECODE=1','--entrypoint','python3',PYTHON,'/code/evaluate.py',timeout=180)
        result=json.loads(output)
    finally:
        try:
            if launched:
                inspected=subprocess.run(['docker','container','inspect',name],capture_output=True,timeout=15)
                if inspected.returncode==0:
                    value=json.loads(inspected.stdout)[0]
                    if (value['Config'].get('Labels') or {}).get('com.vector.fegcraft-knowledge-evaluation')!=owner:
                        raise RuntimeError('Temporary model client ownership differs; refusing removal.')
                    command('docker','rm','-f',name)
                elif not re.fullmatch(r'(?:Error response from daemon: |Error: )?No such (?:object|container): '+re.escape(name),inspected.stderr.decode().strip()):
                    raise RuntimeError('Temporary model client cleanup could not be verified.')
        finally:
            if coordinator:
                stdout,stderr=coordinator.communicate(input=b'release\n',timeout=30)
                (folder/'coordinator-stderr.log').write_bytes(stderr[-8192:])
                if coordinator.returncode:raise RuntimeError('Shared slot release or native unload was not verified.')
    if result is None:raise RuntimeError('Missing model evaluation result.')
    result.update(revision=revision,production_unchanged=fingerprint()==before,cleanup_verified=True,weights_unloaded=True)
    result['passed']=result['passed'] and result['production_unchanged']
    (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));print('Report:',folder/'result.json')
    if not result['passed']:raise RuntimeError('Local knowledge quality gate failed; General local help remains disabled; no production activation.')

def main():
    if os.geteuid()!=0:raise RuntimeError('Run as root.')
    with (ROOT/'.chat-release.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return evaluate()


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)
        raise SystemExit(1)


