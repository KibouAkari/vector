#!/usr/bin/env python3
"""Offline private HTTP, lifecycle and app-runtime qualification; no deployment."""
import ast
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import uuid

ROOT=Path('/root/vector-workspace')
REPO=ROOT/'github/vector'
BRANCH='feat/privacy-consent-local-20261015'
QUALIFIED_REV='f7b5bb4de3ad99f945050fc23740407839508501'
QUALIFIED_IMAGE='sha256:eca0b83a886fcc9952ef13755853ef63134e5c76733d40564460398776c92dd7'
QUALIFIED_RELEASE=ROOT/'releases/vector-privacy-ner-pilot-20261016t071152z-5a2692'

HARNESS=r'''
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {AsyncLocalStorage} from 'node:async_hooks';
import {readFile} from 'node:fs/promises';
const uri=source=>'data:text/javascript;base64,'+Buffer.from(source).toString('base64');
const rules=uri(await readFile('/work/privacy-rules.mjs','utf8'));
const coreSource=(await readFile('/work/privacy-review-core.mjs','utf8')).replace("'./privacy-rules.mjs'",JSON.stringify(rules));
const coreUri=uri(coreSource);const core=await import(coreUri);
const client=await import(uri((await readFile('/work/privacy-ner-client.mjs','utf8')).replace("'./privacy-review-core.mjs'",JSON.stringify(coreUri))));
const token=(await readFile('/run/secrets/vector_privacy_ner_token','utf8')).trim();
const health=async()=>{const response=await fetch('http://vector-privacy-ner:8091/health',{headers:{Authorization:`Bearer ${token}`},signal:AbortSignal.timeout(5000)});assert.equal(response.status,200);return response.json();};
let ready=false;
for(let n=0;n<100;n++) {try {await health();ready=true;break;}catch{}await new Promise(r=>setTimeout(r,100));}
assert.ok(ready,'Private service did not start.');
assert.equal((await health()).state,'sleeping','Health must not load weights.');
const unauthorized=await fetch('http://vector-privacy-ner:8091/scan',{method:'POST',body:JSON.stringify({text:'Anna'})});assert.equal(unauthorized.status,401);
const post=async body=>fetch('http://vector-privacy-ner:8091/scan',{method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify(body)});
assert.equal((await post({text:'Anna',unexpected:true})).status,400);
assert.equal((await post({text:'é'.repeat(80001)})).status,413);
assert.equal((await health()).state,'sleeping','Rejected requests must not wake the model.');
const fixtures=JSON.parse(await readFile('/work/fixtures.json','utf8'));
const observations=[];
for(const fixture of fixtures){
  const started=Date.now();const result=await client.requestPrivacyScan(fixture.text);
  const plan=core.makePrivacyPlan(fixture.text,[...core.deterministicFindings(fixture.text),...result.findings]);
  for(const value of fixture.expected){assert.ok(plan.mappings.some(m=>m.value===value),fixture.id+': missing expected span');assert.ok(!plan.sanitized.includes(value),fixture.id+': unmasked span');}
  if(!fixture.expected.length)assert.equal(plan.totalFindings,0,fixture.id+': false positive');
  assert.equal(core.literalReplace(plan.sanitized,plan.mappings,true),fixture.text);
  for(const value of fixture.secret_expected||[])assert.ok(plan.selected.map(core.displayFinding).every(f=>!f.displayValue.includes(value)));
  observations.push({id:fixture.id,passed:true,seconds:(Date.now()-started)/1000,...result.metrics});
}
assert.equal(observations.length,32);
assert.equal(observations[0].cold,true);assert.ok(observations.slice(1).every(r=>!r.cold));
const vault=new Map(),events=[];let calls=0;
const deps={crypto,AsyncLocalStorage,...core,
  requestPrivacyScan:async text=>{calls++;return client.requestPrivacyScan(text);},
  withLocalWorkerSlot:execute=>execute(),getPrivacyMappings:async id=>vault.get(id)||[],
  savePrivacyMappings:async({conversationId,mappings})=>vault.set(conversationId,mappings),recordUsage:async event=>events.push(event)};
const source=(await readFile('/work/privacy-review.js','utf8')).replace(/^import\s[\s\S]*?from\s+['"][^'"]+['"];\s*/gm,'').replace(/^export\s+/gm,'');
const runtime=new Function(...Object.keys(deps),source+'\nreturn {reviewPrivacyRequest,withJobPrivacy,protectProviderPayload,protectToolEvidence,restoreLocalToolArguments};')(...Object.values(deps));
process.env.VECTOR_PRIVACY_REVIEW='1';process.env.VECTOR_LOCAL_WORKERS='1';process.env.FILE_ENCRYPTION_KEY='07'.repeat(32);
const fixture=fixtures[0];const request={text:fixture.text,body:{message:fixture.text,mode:'normal'},session:{userId:'synthetic'},scope:'chat',conversationId:'synthetic'};
const reviewed=await runtime.reviewPrivacyRequest(request);assert.equal(reviewed.response.status,409);
const dialog=await reviewed.response.json();
assert.ok(!JSON.stringify(dialog).includes('synthetic privacy phrase'));
const confirm=decision=>runtime.reviewPrivacyRequest({...request,body:{...request.body,privacyDecision:decision,privacyReviewToken:dialog.privacyReview.token}});
const plan=await confirm('replace');assert.equal(calls,1,'Confirmation must reuse the bound ticket.');
assert.equal(core.literalReplace(plan.apply(fixture.text),plan.mappings,true),fixture.text);
vault.set('synthetic',plan.mappings);
await runtime.withJobPrivacy({userId:'synthetic',conversationId:'synthetic',privacyPolicy:plan.policy},async()=>{
  const outgoing=runtime.protectProviderPayload({model:'fixed',input:[{role:'user',content:fixture.text}]});
  for(const value of fixture.expected)assert.ok(!JSON.stringify(outgoing).includes(value));
  const tool=await runtime.protectToolEvidence(JSON.stringify({person:'Élodie Martin',message:'password=synthetic-new-phrase'}));
  assert.ok(!tool.sanitized.includes('Élodie Martin'));assert.ok(!tool.sanitized.includes('synthetic-new-phrase'));
  const wire=runtime.protectProviderPayload({input:[{type:'function_call_output',call_id:'call1',output:tool.sanitized}]});
  assert.doesNotThrow(()=>JSON.parse(wire.input[0].output));
  assert.equal(runtime.restoreLocalToolArguments('server_inspect',{path:plan.apply('Erika Muster')}).path,'Erika Muster');
  assert.notEqual(runtime.restoreLocalToolArguments('web_search',{query:plan.apply('Erika Muster')}).query,'Erika Muster');
});
const original=await confirm('original');assert.equal(original.apply(fixture.text),fixture.text);
await assert.rejects(runtime.reviewPrivacyRequest({...request,text:fixture.text+' changed',body:{...request.body,privacyDecision:'original',privacyReviewToken:dialog.privacyReview.token}}));
const before=calls;const local=await runtime.reviewPrivacyRequest({...request,destination:'local'});assert.equal(local.response,undefined);assert.equal(local.apply(fixture.text),fixture.text);assert.equal(calls,before);
assert.equal(events.length,calls);assert.ok(events.every(e=>e.provider==='local'&&e.costChf===0&&e.inputTokens===0&&e.outputTokens===0&&e.metadata.processedTextTokens>0));
assert.ok(!JSON.stringify(events).includes('Erika Muster'));
let slept=false;
for(let n=0;n<80;n++){if((await health()).state==='sleeping'){slept=true;break;}await new Promise(r=>setTimeout(r,100));}
assert.ok(slept,'Model worker did not exit after idle.');
const waking=await client.requestPrivacyScan('Anna hat Geburtstag.');assert.equal(waking.metrics.cold,true);assert.ok(waking.findings.some(f=>f.value==='Anna'));
assert.equal((await health()).generation,2);
// The isolated driver stops the service next; prove fail-closed in a separate run there.
console.log(JSON.stringify({passed:true,cases:observations,case_count:observations.length,
  runtime_consent_roundtrip:true,explicit_original:true,local_chat_quiet:true,
  tool_evidence_masked:true,auth_and_input_limits:true,idle_unload_and_wake:true,
  encoder_metrics_separate_from_api_tokens:true,local_ledger_events:events.length,
  cloud_calls:0,api_cost_chf:0,ledger_writes:false,production_activated:false}));
'''

FAIL_CLOSED=r'''
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const uri=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
const rules=uri(await readFile('/work/privacy-rules.mjs','utf8'));
const core=uri((await readFile('/work/privacy-review-core.mjs','utf8')).replace("'./privacy-rules.mjs'",JSON.stringify(rules)));
const {requestPrivacyScan}=await import(uri((await readFile('/work/privacy-ner-client.mjs','utf8')).replace("'./privacy-review-core.mjs'",JSON.stringify(core))));
await assert.rejects(requestPrivacyScan('Anna hat Geburtstag.'),/nichts extern/);
console.log(JSON.stringify({service_outage_blocked:true}));
'''


def run(*args,data=None,timeout=60,error_path=None):
    result=subprocess.run(args,input=data,capture_output=True,timeout=timeout)
    if result.returncode:
        if error_path:error_path.write_bytes(result.stderr)
        raise RuntimeError('Isolated service check failed. Production was not activated.'+(f' Details: {error_path}' if error_path else ''))
    return result.stdout


def source(revision,path):
    return run('git','-C',str(REPO),'show',revision+':'+path).decode()


def load_module(revision,path,name):
    text=source(revision,path);ast.parse(text)
    namespace={'__name__':name};exec(compile(text,path,'exec'),namespace);return namespace


def service_args(name,image,network,work,token):
    return ['docker','run','--detach','--pull','never','--name',name,'--network',network,
        '--network-alias','vector-privacy-ner','--user','65534:65534','--read-only',
        '--cpus','2','--memory','4g','--memory-swap','4g','--pids-limit','128',
        '--cap-drop','ALL','--security-opt','no-new-privileges',
        '--tmpfs','/tmp:rw,nosuid,nodev,size=256m,mode=1777',
        '--mount',f'type=bind,src={work},dst=/work,readonly',
        '--mount',f'type=bind,src={token},dst=/run/secrets/vector_privacy_ner_token,readonly',
        '--env','HF_HOME=/tmp/hf','--env','HF_HUB_OFFLINE=1','--env','TRANSFORMERS_OFFLINE=1',
        '--env','TOKENIZERS_PARALLELISM=false','--env','VECTOR_PRIVACY_NER_IDLE_SECONDS=3',
        image,'python','/work/server.py']


def main():
    os.umask(0o077)
    revision=os.environ.get('VECTOR_PRIVACY_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision):
        raise RuntimeError('Run as root with exact VECTOR_PRIVACY_REV.')
    fetched=run('git','-C',str(REPO),'rev-parse','refs/remotes/origin/'+BRANCH).decode().strip()
    if fetched!=revision:raise RuntimeError('Fetched branch revision changed.')
    with (ROOT/'.chat-release.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        helper=load_module(revision,'scripts/deploy/evaluate-privacy-review.py','privacy_service_helpers')
        pilot=load_module(revision,'scripts/deploy/pilot-privacy-ner.py','privacy_service_fixtures')
        before=helper['fingerprint']()
        if before['/vector-app']['image']!=helper['IMAGE']:raise RuntimeError('Production image changed.')
        report_path=QUALIFIED_RELEASE/'result.json'
        if QUALIFIED_RELEASE.is_symlink() or report_path.is_symlink() or not report_path.is_file():raise RuntimeError('Qualified report is missing.')
        qualified=json.loads(report_path.read_text())
        if qualified.get('revision')!=QUALIFIED_REV or not qualified.get('context_fixture_qualification_passed') or \
            qualified.get('pilot_image_id')!=QUALIFIED_IMAGE or len(qualified.get('cases',[]))!=32 or \
            not all(c.get('passed') is True for c in qualified['cases']):
            raise RuntimeError('Expected the observed complete 32-case qualification.')
        if json.loads(run('docker','image','inspect',QUALIFIED_IMAGE))[0]['Id']!=QUALIFIED_IMAGE:
            raise RuntimeError('Qualified local image missing.')
        idle="""import pg from 'pg';const c=new pg.Client({connectionString:process.env.DATABASE_URL,connectionTimeoutMillis:5000});try{await c.connect();await c.query('BEGIN READ ONLY');await c.query(\"SET LOCAL statement_timeout = '5s'\");const r=await c.query(\"SELECT COUNT(*)::int AS n FROM agent_jobs WHERE status IN ('queued','running')\");if(r.rows[0].n!==0)throw Error('busy');}finally{await c.end();}"""
        run('docker','exec','-i','vector-app','node','--input-type=module',data=idle.encode())
        fixtures=json.loads(run('docker','exec','-i','vector-app','node','--input-type=module',
            data=pilot['fixture_expression'](helper['HARNESS']).encode()))+pilot['HOLDOUTS']+pilot['EXTENDED_CASES']
        if len(fixtures)!=32:raise RuntimeError('Fixture set changed.')
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
        release=ROOT/'releases'/('vector-privacy-ner-service-evaluation-'+stamp);release.mkdir(mode=0o700)
        work=release/'input';work.mkdir(mode=0o755)
        sources={'server.py':'services/privacy-ner/server.py','privacy-ner-core.py':'lib/privacy-ner-core.py',
            'privacy-ner-client.mjs':'lib/privacy-ner-client.mjs','privacy-review.js':'lib/privacy-review.js',
            'privacy-review-core.mjs':'lib/privacy-review-core.mjs','privacy-rules.mjs':'lib/privacy-rules.mjs'}
        files={name:source(revision,path) for name,path in sources.items()}
        files.update({'integration.mjs':HARNESS,'fail-closed.mjs':FAIL_CLOSED,'fixtures.json':json.dumps(fixtures)})
        for name,content in files.items():
            target=work/name;target.write_text(content);target.chmod(0o644)
        token=work/'service-token';token.write_text(secrets.token_hex(32));token.chmod(0o444)
        network='vector-privacy-eval-'+stamp.lower();service='vector-privacy-ner-eval-'+stamp.lower()
        client='vector-privacy-client-eval-'+stamp.lower();owned=[];network_created=False
        try:
            run('docker','network','create','--internal',network);network_created=True
            owned.append(service)
            run(*service_args(service,QUALIFIED_IMAGE,network,work,token))
            owned.append(client)
            args=['docker','run','--name',client,'--pull','never','--network',network,
                '--user','65534:65534','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
                '--cpus','1','--memory','512m','--memory-swap','512m','--pids-limit','64',
                '--tmpfs','/tmp:rw,nosuid,nodev,size=32m,mode=1777',
                '--mount',f'type=bind,src={work},dst=/work,readonly',
                '--mount',f'type=bind,src={token},dst=/run/secrets/vector_privacy_ner_token,readonly',
                '--entrypoint','node',helper['IMAGE'],'/work/integration.mjs']
            print('Evaluate private authenticated HTTP, all 32 cases, consent, tool protection and sleep/wake. No production activation.',flush=True)
            observed=json.loads(run(*args,timeout=600,error_path=release/'client-stderr.log'))
            run('docker','stop','--time','10',service,timeout=30)
            stopped=json.loads(run('docker','inspect',service))[0]
            if stopped['State']['Running'] or stopped['State']['ExitCode']!=0:raise RuntimeError('Service did not stop cleanly.')
            run('docker','rm',client);owned.remove(client)
            args[-1]='/work/fail-closed.mjs'
            owned.append(client)
            outage=json.loads(run(*args,timeout=30,error_path=release/'outage-stderr.log'))
            metadata=json.loads(run('docker','inspect',service))[0]
            if metadata['HostConfig']['PortBindings'] or not json.loads(run('docker','network','inspect',network))[0]['Internal']:
                raise RuntimeError('Unexpected network exposure.')
            result=dict(observed,**outage,revision=revision,qualified_image=QUALIFIED_IMAGE,
                production_unchanged=helper['fingerprint']()==before,private_network=True,
                service_stopped_cleanly=True,production_activated=False)
            result['passed']=bool(result.get('passed') and result['production_unchanged'] and result['service_outage_blocked'])
            (release/'result.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result,indent=2));print('Report:',release/'result.json')
            if not result['passed']:raise RuntimeError('Service qualification failed; privacy remains inactive.')
        finally:
            errors=[]
            for name in reversed(owned):
                removed=subprocess.run(['docker','rm','-f',name],capture_output=True)
                if removed.returncode:errors.append(name)
            if network_created:
                removed=subprocess.run(['docker','network','rm',network],capture_output=True)
                if removed.returncode:errors.append(network)
            token.unlink(missing_ok=True)
            if errors:raise RuntimeError('Cleanup could not be verified: '+', '.join(errors))
            print('Temporary service/client containers, token and private evaluation network removed.',flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)
        raise SystemExit(1)
