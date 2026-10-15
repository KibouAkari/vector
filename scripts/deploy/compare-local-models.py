#!/usr/bin/env python3
"""Compare pinned local candidates; no application build, database write or activation."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request
import uuid

REPO = Path('/root/vector-workspace/github/vector')
ROOT = Path('/root/vector-workspace/releases')
SERVICE = 'vector-local-inference'
CANDIDATE = dict(name='vector-qwen3:1.7b-q8', repo='Qwen/Qwen3-1.7B-GGUF',
    revision='90862c4b9d2787eaed51d12237eafdfe7c5f6077', file='Qwen3-1.7B-Q8_0.gguf',
    sha256='061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a', size=1834426016)
MODELS = ['vector-qwen3:0.6b-q8', CANDIDATE['name'], 'vector-hermes3:8b-q4km']
HARNESS = r'''
import assert from 'node:assert/strict';
import {localWorkerPayload,requestLocalChat,validateExtraction} from './lib/local-worker-core.mjs';
import {providerUsageEvent} from './lib/provider-call-usage.mjs';
import {normalizedOpenAiUsage} from './lib/provider-usage-normalization.mjs';
import crypto from 'node:crypto';
__FIXTURES__
fixtures.push(
  {role:'extract',task:'Return exactly players and deaths. Missing values must be null.',
   evidence:'There are 14 players. Deaths were not recorded.',fields:[{name:'players',type:'integer'},{name:'deaths',type:'integer'}],expected:{players:14,deaths:null}},
  {role:'extract',task:'Return exactly players and deaths.',
   evidence:'Players: 5. Deaths recorded as 0.',fields:[{name:'players',type:'integer'},{name:'deaths',type:'integer'}],expected:{players:5,deaths:0}}
);
const results=[],events=[];
for(const model of __MODELS__){
  console.error('Compare candidate:',model);
  for(const [index,fixture] of fixtures.entries()){
    const {expected,...args}=fixture;
    const payload=localWorkerPayload(args); payload.model=model;
    const started=Date.now();let body;
    try {
      body=await requestLocalChat(payload);
      const runtime={id:'candidate-'+model,provider:'local',model,
        pricing:{inputPerMillionUsd:0,cachedInputPerMillionUsd:0,outputPerMillionUsd:0}};
      const response={id:crypto.randomUUID(),status:body.done && body.done_reason==='stop'?'completed':'incomplete',
        usage:normalizedOpenAiUsage({prompt_tokens:body.prompt_eval_count,completion_tokens:body.eval_count,
          ...(body.prompt_eval_cached_count===undefined?{}:{prompt_tokens_details:{cached_tokens:body.prompt_eval_cached_count}})}),output:[]};
      const event=providerUsageEvent({runtime,response,userId:'synthetic-comparison',jobId:'synthetic-comparison',exchangeRate:1});
      events.push(event);
      assert.equal(response.status,'completed');assert.ok(!body.message?.tool_calls?.length);
      const data=validateExtraction(JSON.parse(body.message.content),payload.format);
      let passed=false;try {assert.deepEqual(data,expected);passed=true;}catch{}
      results.push({model,fixture_index:index,role:args.role,expected,data,fixture_passed:passed,
        elapsed_ms:Date.now()-started,input_tokens:body.prompt_eval_count,output_tokens:body.eval_count,
        tokens_per_second:body.eval_duration?body.eval_count*1e9/body.eval_duration:null,
        load_ms:(body.load_duration||0)/1e6});
    }catch(error){results.push({model,fixture_index:index,role:args.role,expected,fixture_passed:false,
      elapsed_ms:Date.now()-started,error:error.message,text:body?.message?.content?.slice(0,2000)});}
  }
}
const summaries=__MODELS__.map(model=>{
  const rows=results.filter(r=>r.model===model),passed=rows.filter(r=>r.fixture_passed).length;
  return {model,passed,total:fixtures.length,all_fixtures_passed:passed===fixtures.length};
});
console.log(JSON.stringify({results,summaries,passing_candidates:summaries.filter(s=>s.all_fixtures_passed).map(s=>s.model),
  accounted_calls:events.length,expected_calls:fixtures.length*__MODELS__.length,
  usage_complete:events.length===fixtures.length*__MODELS__.length && events.every(e=>e.metadata.usageKnown && e.metadata.cacheValid),
  input_tokens:events.reduce((n,e)=>n+e.inputTokens,0),output_tokens:events.reduce((n,e)=>n+e.outputTokens,0),
  api_cost_chf:events.reduce((n,e)=>n+e.costChf,0),ledger_writes:false,cloud_calls:0,vector_activated:false,
  scope:'Synthetic structured-output comparison; no automatic selection or production promotion.'}));
'''


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_harness(existing):
    start = existing.index('const fixtures=')
    end = existing.index('\n];', start) + len('\n];')
    return HARNESS.replace('__FIXTURES__', existing[start:end]).replace('__MODELS__', json.dumps(MODELS))


def main():
    revision = os.environ.get('VECTOR_LOCAL_WORKER_REV', '')
    if os.geteuid() != 0 or not re.fullmatch('[0-9a-f]{40}', revision):
        raise RuntimeError('Root and exact VECTOR_LOCAL_WORKER_REV required.')
    directory = ROOT / ('vector-model-comparison-' + uuid.uuid4().hex)
    directory.mkdir(mode=0o755)
    directory.chmod(0o755)
    (directory / 'lib').mkdir(mode=0o755)
    (directory / 'lib').chmod(0o755)

    def copy_reviewed(source, target):
        content = subprocess.check_output(['git','-C',str(REPO),'show',revision+':'+source])
        path = directory / target
        path.write_bytes(content)
        path.chmod(0o644)
        return path

    evaluation = load_module('comparison_evaluation', copy_reviewed('scripts/deploy/evaluate-local-workers.py','evaluation.py'))
    pilot = load_module('comparison_pilot', copy_reviewed('scripts/deploy/local-inference-pilot.py','pilot.py'))
    service = evaluation.inspect(SERVICE)
    if not service['State']['Running'] or service['Config']['Image'] != evaluation.IMAGE:
        raise RuntimeError('Pinned inference service must be running.')
    if service['HostConfig']['PortBindings'] or list(service['NetworkSettings']['Networks']) != [SERVICE]:
        raise RuntimeError('Unexpected inference network exposure.')
    network = json.loads(evaluation.run('docker','network','inspect',SERVICE))[0]
    if not network['Internal']:
        raise RuntimeError('Inference network must remain internal.')
    if service['HostConfig']['NanoCpus'] != 2000000000 or service['HostConfig']['Memory'] != 12*1024**3:
        raise RuntimeError('Inference resource limits differ from the installed pilot.')
    if not any(m.get('Destination')=='/imports' and m.get('Source')==str(pilot.ROOT) and m.get('RW') is False for m in service['Mounts']):
        raise RuntimeError('Verified read-only model import mount missing.')
    base = 'http://' + service['NetworkSettings']['Networks'][SERVICE]['IPAddress'] + ':11434'
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def api(path, body=None):
        req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with http.open(req,timeout=30) as response:
            return json.load(response)

    if api('/api/ps').get('models'):
        raise RuntimeError('Inference service is busy; compare during an idle period.')
    manifest={m['name']:m['digest'] for m in api('/api/tags')['models']}
    if any(manifest.get(n)!=d for n,d in evaluation.MODELS.items()):
        raise RuntimeError('Existing model digests changed.')
    before=evaluation.production_fingerprint()
    evaluation.private_json(directory/'production-before.json',before)
    if before['image_id']!='sha256:0131e29a797cb74b04ceeeea6765cc0ccc46e331e62b4b8fe73a98794df8ea28' or not before['running']:
        raise RuntimeError('Production differs from the confirmed running release.')
    if shutil.disk_usage(pilot.ROOT).free < 8*1024**3:
        raise RuntimeError('At least 8 GiB free disk space required.')
    memory=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    if int(memory['MemAvailable'].strip().split()[0]) < 16*1024**2:
        raise RuntimeError('At least 16 GiB available RAM required.')
    marker=pilot.ROOT/'vector-qwen3-1.7b-import.json'
    if CANDIDATE['name'] in manifest:
        if not marker.is_file() or marker.is_symlink():
            raise RuntimeError('Candidate already exists without verified import evidence; inspect manually.')
        saved=json.loads(marker.read_text())
        if saved.get('artifact')!=CANDIDATE or saved.get('model_digest')!=manifest[CANDIDATE['name']]:
            raise RuntimeError('Candidate import evidence mismatch; refusing replacement.')
    else:
        pilot.download(CANDIDATE)
        modelfile=pilot.ROOT/'vector-qwen3-1.7b.Modelfile'
        content=f"FROM /imports/{CANDIDATE['file']}\nPARAMETER num_ctx 2048\nPARAMETER num_thread 2\nPARAMETER num_predict 256\nPARAMETER temperature 0\n"
        if modelfile.is_symlink() or (modelfile.exists() and modelfile.read_text()!=content):
            raise RuntimeError('Existing candidate Modelfile differs; refusing replacement.')
        if not modelfile.exists():
            fd=os.open(modelfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as output: output.write(content)
        print('Import checksum-verified Qwen3 1.7B candidate.',flush=True)
        evaluation.run('docker','exec',SERVICE,'ollama','create',CANDIDATE['name'],'-f','/imports/'+modelfile.name)
        manifest={m['name']:m['digest'] for m in api('/api/tags')['models']}
        evaluation.private_json(marker,{'artifact':CANDIDATE,'model_digest':manifest[CANDIDATE['name']]})
    for source in evaluation.FILES:
        copy_reviewed(source,source)
    script=directory/'compare.mjs'
    script.write_text(build_harness(evaluation.HARNESS))
    script.chmod(0o644)
    name='vector-model-comparison-'+uuid.uuid4().hex[:8]
    created=False
    report=None
    try:
        evaluation.run('docker','create','--name',name,'--network',SERVICE,'--cpus','0.5','--memory','256m',
            '--pids-limit','64','--cap-drop','ALL','--security-opt','no-new-privileges:true','--read-only',
            '--user','1001:1001','--entrypoint','node','-v',str(directory)+':/evaluation:ro',before['image_id'],'/evaluation/compare.mjs')
        created=True
        subprocess.run(['docker','start','-a',name],check=True,timeout=900)
        if evaluation.inspect(name)['State']['ExitCode']!=0:
            raise RuntimeError('Comparison process failed; inspect its synthetic output.')
        report=json.loads(evaluation.run('docker','logs',name))
        report.update(tested_commit=revision,candidate_artifact=CANDIDATE,model_manifest=manifest)
    finally:
        if created: subprocess.run(['docker','rm','-f',name],check=True,stdout=subprocess.DEVNULL)
        for model in MODELS: api('/api/generate',{'model':model,'keep_alive':0})
        after=evaluation.production_fingerprint()
        evaluation.private_json(directory/'production-after.json',after)
        if report is not None:
            report.update(production_unchanged=before==after,
                production_changed_fields=[k for k in before if before[k]!=after.get(k)],
                loaded_models_after_unload=len(api('/api/ps').get('models',[])))
            report['passed']=bool(report['passing_candidates']) and report['usage_complete'] and report['production_unchanged'] and report['loaded_models_after_unload']==0
            evaluation.private_json(directory/'comparison-result.json',report)
            print('Report:',directory/'comparison-result.json',flush=True)
            print(json.dumps(report,indent=2),flush=True)
    if report is None or not report['passed']:
        raise RuntimeError('No fully passing candidate or comparison guard failed. Vector remains disabled.')
    print('Comparison completed. Passing candidates are evaluation results, not a production activation.')


if __name__=='__main__':
    main()
