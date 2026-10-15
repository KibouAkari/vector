#!/usr/bin/env python3
"""Evaluate actual worker code against installed models in a disposable container.
Uses synthetic evidence only. Does not activate Vector or write its database.
"""
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request
import uuid

REPO = Path('/root/vector-workspace/github/vector')
ROOT = Path('/root/vector-workspace/releases')
SERVICE = 'vector-local-inference'
IMAGE = 'ollama/ollama@sha256:7434bb6d6a423b8c4060c4cf0bfa1b49a6540d080d6a3c98acc2cbe36a786158'
MODELS = {
    'vector-hermes3:8b-q4km': 'ddd98889feddbec419ccb27c2839214c100ce4ebae74f16b12fe17f5c6572a20',
    'vector-qwen3:0.6b-q8': '4a1154fa3f6bd4afad6cfce6e0e15094204d48f5053646a8e0d815c6c49d224a',
}
FILES = ['lib/local-worker-core.mjs', 'lib/provider-call-usage.mjs', 'lib/provider-usage-normalization.mjs']
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
HARNESS = r'''
import assert from 'node:assert/strict';
import {runLocalWorker} from './lib/local-worker-core.mjs';
import {withProviderUsageScope,providerUsageEvent} from './lib/provider-call-usage.mjs';
const results=[];
const events=[];
const fixtures=[
  {role:'extract',task:'Return exactly the JSON keys players and deaths.',
   evidence:'Players: 3. Deaths were not measured.',fields:[{name:'players',type:'integer'},{name:'deaths',type:'integer'}],expected:{players:3,deaths:null}},
  {role:'extract',task:'Extrahiere ausschliesslich die JSON Schluessel dienste und temperatur.',
   evidence:'Es laufen 7 Dienste. Die Temperatur ist unbekannt.',fields:[{name:'dienste',type:'integer'},{name:'temperatur',type:'number'}],expected:{dienste:7,temperatur:null}},
  {role:'extract',task:'Return the count of alerts and the unknown latency in milliseconds.',
   evidence:'Alerts: 0. Latency was not measured.',fields:[{name:'alerts',type:'integer'},{name:'latency_ms',type:'number'}],expected:{alerts:0,latency_ms:null}},
  {role:'extract',task:'Extrahiere die Anzahl Benutzer und Abstuerze.',
   evidence:'Es sind 12 Benutzer angemeldet und 2 Abstuerze gemeldet.',fields:[{name:'benutzer',type:'integer'},{name:'abstuerze',type:'integer'}],expected:{benutzer:12,abstuerze:2}},
  {role:'extract',task:'Return the measured memory and temperature, or null if not supplied.',
   evidence:'This note contains no resource measurements.',fields:[{name:'memory_mb',type:'number'},{name:'temperature',type:'number'}],expected:{memory_mb:null,temperature:null}},
  {role:'summarize',fields:[{name:'dienste',type:'integer'},{name:'status',type:'string'}],task:'Fasse die Angaben ausschliesslich als JSON mit den Schluesseln dienste und status zusammen. status soll den Wert unbekannt haben, wenn keine Messung vorhanden ist.',
   evidence:'3 Dienste sind vorhanden. Ihr Status wurde nicht gemessen.',expected:{dienste:3,status:'unbekannt'}}
];
await withProviderUsageScope(async(runtime,response)=>{
  const event=providerUsageEvent({runtime,response,userId:'synthetic-evaluation',jobId:'synthetic-evaluation',exchangeRate:1});
  events.push(event); return event;
},async()=>{
  for(const [index,fixture] of fixtures.entries()){
    const {expected,...args}=fixture;
    try {
      const result=await runLocalWorker(args,{userId:'synthetic-evaluation',jobId:'synthetic-fixture-'+index,allowLocalWorkers:true},
        {enabled:true,exclusive:execute=>execute()});
      let passed=false;
      try {assert.deepEqual(JSON.parse(result.text),expected);passed=true;}catch{}
      results.push({...result,fixture_index:index,expected,fixture_passed:passed});
    } catch(error) {
      results.push({fixture_index:index,worker_role:args.role,expected,fixture_passed:false,error:error.message});
    }
  }
});
console.log(JSON.stringify({results,accounted_calls:events.length,
  input_tokens:events.reduce((n,e)=>n+e.inputTokens,0),output_tokens:events.reduce((n,e)=>n+e.outputTokens,0),
  api_cost_chf:events.reduce((n,e)=>n+e.costChf,0),usage_complete:events.every(e=>e.metadata.usageKnown),
  ledger_writes:false,cloud_calls:0,vector_activated:false,
  passed:results.every(r=>r.fixture_passed) && events.length===fixtures.length && events.every(e=>e.metadata.usageKnown)}));
'''


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, timeout=600, **kwargs).strip()


def inspect(name):
    return json.loads(run('docker', 'inspect', name))[0]


def production_fingerprint(info=None):
    info = inspect('vector-app') if info is None else info
    # Docker does not promise a stable Mounts/alias list order.
    networks = {}
    for name, network in info['NetworkSettings']['Networks'].items():
        networks[name] = {key: network.get(key) for key in
            ('NetworkID', 'EndpointID', 'IPAddress', 'GlobalIPv6Address')}
        networks[name]['Aliases'] = sorted(network.get('Aliases') or [])
    return {
        'container_id': info['Id'], 'image_id': info['Image'],
        'configured_image': info['Config']['Image'], 'started_at': info['State']['StartedAt'],
        'running': info['State']['Running'],
        'mounts': sorted(info['Mounts'], key=lambda item: json.dumps(item, sort_keys=True)),
        'networks': networks,
    }


def private_json(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(value, output, indent=2)
        output.write('\n')


def create_evaluation_directory(directory):
    directory.mkdir(mode=0o755)
    directory.chmod(0o755)
    library = directory / 'lib'
    library.mkdir(mode=0o755)
    library.chmod(0o755)


def main():
    revision = os.environ.get('VECTOR_LOCAL_WORKER_REV', '')
    if os.geteuid() != 0 or not re.fullmatch('[0-9a-f]{40}', revision):
        raise RuntimeError('Root and exact VECTOR_LOCAL_WORKER_REV required.')
    service = inspect(SERVICE)
    if not service['State']['Running'] or service['Config']['Image'] != IMAGE:
        raise RuntimeError('Pinned inference service is not running.')
    if service['HostConfig']['PortBindings'] or list(service['NetworkSettings']['Networks']) != [SERVICE]:
        raise RuntimeError('Unexpected inference network or published ports.')
    network = json.loads(run('docker', 'network', 'inspect', SERVICE))[0]
    if network['Internal'] is not True:
        raise RuntimeError('Inference network must be internal.')
    base = 'http://' + service['NetworkSettings']['Networks'][SERVICE]['IPAddress'] + ':11434'

    def api(path, body=None):
        request = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type':'application/json'})
        with HTTP.open(request, timeout=30) as response:
            return json.load(response)

    manifest = {m['name']:m['digest'] for m in api('/api/tags')['models']}
    if any(manifest.get(name) != digest for name,digest in MODELS.items()):
        raise RuntimeError('Installed model digest differs from the successful pilot.')
    if api('/api/ps').get('models'):
        raise RuntimeError('Models are already in use; evaluate during an idle period.')
    before = production_fingerprint()
    if before['image_id'] != 'sha256:0131e29a797cb74b04ceeeea6765cc0ccc46e331e62b4b8fe73a98794df8ea28' or not before['running']:
        raise RuntimeError('Current production app differs from the confirmed running release. Actual image: ' + before['image_id'])
    name = 'vector-local-worker-eval-' + uuid.uuid4().hex[:8]
    directory = ROOT / (name + '-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    create_evaluation_directory(directory)
    private_json(directory / 'production-before.json', before)
    for source in FILES:
        destination = directory / source
        destination.write_text(run('git', '-C', str(REPO), 'show', revision + ':' + source) + '\n')
        destination.chmod(0o644)
    (directory / 'evaluate.mjs').write_text(HARNESS)
    (directory / 'evaluate.mjs').chmod(0o644)
    created = False
    report = None
    try:
        run('docker', 'create', '--name', name, '--network', SERVICE, '--cpus', '0.5', '--memory', '256m',
            '--pids-limit', '64', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
            '--read-only', '--user', '1001:1001', '--entrypoint', 'node',
            '-v', str(directory) + ':/evaluation:ro', inspect('vector-app')['Image'], '/evaluation/evaluate.mjs')
        created = True
        subprocess.run(['docker','start','-a',name], check=True, timeout=420)
        state = inspect(name)['State']
        if state['ExitCode'] != 0:
            raise RuntimeError('Worker evaluation failed. Inspect the preceding synthetic error.')
        output = run('docker', 'logs', name)
        report = json.loads(output)
        report['tested_commit'] = revision
    finally:
        if created:
            subprocess.run(['docker','rm','-f',name], check=True, stdout=subprocess.DEVNULL)
        for model in MODELS:
            api('/api/generate', {'model':model,'keep_alive':0})
        after = production_fingerprint()
        private_json(directory / 'production-after.json', after)
        unchanged = after == before
        changed_fields = [key for key in before if before[key] != after.get(key)]
        if report is not None:
            report['production_unchanged'] = unchanged
            report['production_changed_fields'] = changed_fields
            report['loaded_models_after_unload'] = len(api('/api/ps').get('models', []))
            report['passed'] = report['passed'] and unchanged and report['loaded_models_after_unload'] == 0
            path = directory / 'worker-result.json'
            private_json(path, report)
            print('Report:', path, flush=True)
            print(json.dumps(report,indent=2), flush=True)
        if not unchanged:
            raise RuntimeError('Production fingerprint changed in: ' + ', '.join(changed_fields) + '. Inspect the saved before/after snapshots.')
    if not report or not report['passed']:
        raise RuntimeError('Worker fixtures did not pass. Vector remains unactivated.')


if __name__ == '__main__':
    main()
