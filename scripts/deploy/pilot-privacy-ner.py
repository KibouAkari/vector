#!/usr/bin/env python3
"""Isolated PERSON recognition pilot. Synthetic fixtures only; no activation."""
import ast
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

ROOT = Path('/root/vector-workspace')
REPO = ROOT / 'github/vector'
BASE_IMAGE = 'python:3.12-slim-bookworm'
MODEL = 'urchade/gliner_multi_pii-v1'
MODEL_REV = '1fcf13e85f4eef5394e1fcd406cf2ca9ea82351d'
BACKBONE_REV = 'a0484667b22365f84929a935b5e50a51f71f159d'


HOLDOUTS = [
    {'id':'holdout-first-name','text':'Schreibe Noah eine kurze Einladung.','expected':['Noah']},
    {'id':'holdout-accented-name','text':'Please welcome Élodie Martin to the team.','expected':['Élodie Martin']},
    {'id':'holdout-greeting','text':'Danke, Daniel!','expected':['Daniel']},
    {'id':'holdout-two-people','text':'Luca und Sofia kommen morgen zu Besuch.','expected':['Luca','Sofia']},
    {'id':'holdout-other-software','text':'Kannst du Kubernetes und PostgreSQL erklären?','expected':[]},
    {'id':'holdout-ordinary-sentence','text':'Heute ist ein schöner Tag.','expected':[]},
    {'id':'holdout-security-task','text':'Analysiere einen SSH-Loginfehler unter Debian.','expected':[]},
]

SETUP = r'''
import hashlib,json,subprocess,sys
from pathlib import Path
subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--no-cache-dir',
    '--index-url','https://download.pytorch.org/whl/cpu','torch==2.10.0+cpu'],check=True)
subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--no-cache-dir',
    '--index-url','https://pypi.org/simple','gliner==0.2.29','transformers==4.57.6','protobuf==6.33.5'],check=True)
from huggingface_hub import snapshot_download
root=Path('/models')
snapshot_download('urchade/gliner_multi_pii-v1',revision='1fcf13e85f4eef5394e1fcd406cf2ca9ea82351d',
    local_dir=root/'entity',allow_patterns=['gliner_config.json','pytorch_model.bin','README.md'],max_workers=2)
snapshot_download('microsoft/mdeberta-v3-base',revision='a0484667b22365f84929a935b5e50a51f71f159d',
    local_dir=root/'backbone',allow_patterns=['*.json','spm.model'],max_workers=2)
# Never unpickle arbitrary objects. Convert the official tensor-only state
# dictionary using PyTorch's restricted weights-only loader, then use safetensors.
import torch
from safetensors.torch import save_file
binary=root/'entity/pytorch_model.bin'
with binary.open('rb') as handle:
    downloaded_weights_sha256=hashlib.file_digest(handle,'sha256').hexdigest()
assert downloaded_weights_sha256=='3003753fba99e40645cf088c7367a2c6211fc174897dc64f1f9c147c29d18d2d', 'Pinned weights checksum mismatch'
weights=torch.load(binary,map_location='cpu',weights_only=True)
assert isinstance(weights,dict) and all(isinstance(v,torch.Tensor) for v in weights.values())
save_file({k:v.contiguous() for k,v in weights.items()},root/'entity/model.safetensors')
del weights
binary.unlink()
assert (root/'entity/model.safetensors').is_file()
assert not list(root.rglob('*.bin'))
config=root/'entity/gliner_config.json'
original=hashlib.sha256(config.read_bytes()).hexdigest()
value=json.loads(config.read_text());value['model_name']='/models/backbone'
config.write_text(json.dumps(value))
files={}
for path in root.rglob('*'):
    if not path.is_file() or '.cache' in path.parts:continue
    with path.open('rb') as handle:
        files[str(path.relative_to(root))]=hashlib.file_digest(handle,'sha256').hexdigest()
manifest=dict(original_config_sha256=original,downloaded_weights_sha256=downloaded_weights_sha256,files_sha256=files,
    packages=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True).splitlines())
Path('/work/setup-manifest.json').write_text(json.dumps(manifest,indent=2))
'''

INFERENCE = r'''
import json,os,resource,time
from pathlib import Path
assert os.environ.get('HF_HUB_OFFLINE')=='1'
import torch
from gliner import GLiNER
torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(42)
started=time.monotonic()
model=GLiNER.from_pretrained('/models/entity',local_files_only=True,map_location='cpu',strict=True).eval()
load=time.monotonic()-started
results=[]
for fixture in json.loads(Path('/work/fixtures.json').read_text()):
    text=fixture['text']
    # This pilot certifies short fixtures only; long-context handling is separate.
    assert len(list(model.data_processor.words_splitter(text)))<=128
    started=time.monotonic()
    with torch.inference_mode():
        entities=model.predict_entities(text,['person','organization','software'],threshold=0.35)
    findings=[]
    for entity in entities:
        start,end=entity['start'],entity['end']
        assert isinstance(start,int) and isinstance(end,int) and 0<=start<end<=len(text)
        assert entity['text']==text[start:end]
        assert entity['label'] in ['person','organization','software']
        if entity['label']!='person':continue
        findings.append(dict(type='PERSON',value=text[start:end]))
    results.append(dict(id=fixture['id'],findings=findings,seconds=round(time.monotonic()-started,3)))
print(json.dumps(dict(cases=results,load_seconds=round(load,3),
    peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    scope='PERSON only; existing deterministic rules cover credentials',
    long_context_qualified=False,threshold=0.35)))
'''

VERIFY = r'''
import assert from 'node:assert/strict';
const data=INPUT_JSON;
const uri=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
const rules=uri(data.rules);
const core=await import(uri(data.core.replace("'./privacy-rules.mjs'",JSON.stringify(rules))));
assert.equal(data.original_case_count,9);
assert.equal(data.fixtures.length,9+data.additional_case_count);
assert.equal(data.inference.cases.length,data.fixtures.length);
const cases=data.fixtures.map((fixture,index)=>{
    const actual=data.inference.cases[index];assert.equal(actual.id,fixture.id);
    const found=core.validateLocalFindings(fixture.text,{findings:actual.findings});
    const plan=core.makePrivacyPlan(fixture.text,[...core.deterministicFindings(fixture.text),...found]);
    const missing=fixture.expected.filter(v=>!plan.selected.some(m=>m.value===v));
    const extra=fixture.expected.length===0&&plan.totalFindings!==0;
    const roundtrip=core.literalReplace(plan.sanitized,plan.mappings,true)===fixture.text;
    return {id:fixture.id,passed:!missing.length&&!extra&&roundtrip,seconds:actual.seconds,
        missing_expected:missing,findings:found,unexpected_findings:extra};
});
console.log(JSON.stringify({cases,passed:cases.every(c=>c.passed)}));
'''


def command(*args, timeout=60, live=False, data=None, error_path=None):
    result = subprocess.run(args, input=data, capture_output=not live, timeout=timeout)
    if error_path is not None and result.stderr:
        error_path.write_bytes(result.stderr)
    if result.returncode:
        detail = f' Details: {error_path}' if error_path is not None else ''
        raise RuntimeError('Pilot command failed. Production was not changed.' + detail)
    return result.stdout


def source(revision, path):
    return command('git','-C',str(REPO),'show',revision+':'+path).decode()


def fixture_expression(harness):
    matches = re.findall(r'  const cases=(\[[\s\S]*?\n  \]);', harness)
    if len(matches) != 1:
        raise RuntimeError('Qualification fixtures changed; inspect before rerun.')
    return 'console.log(JSON.stringify(' + matches[0] + '));'


def limited_container(name, image, script, work, offline=False):
    args=['docker','run','--name',name,'--cpus','2','--memory','4g','--memory-swap','4g',
          '--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',
          '--env','HF_HUB_DISABLE_TELEMETRY=1','--env','DO_NOT_TRACK=1',
          '--env','OMP_NUM_THREADS=2','--env','MKL_NUM_THREADS=2',
          '--mount',f'type=bind,src={work},dst=/work'+(',readonly' if offline else '')]
    if offline:
        args += ['--network','none','--read-only','--user','65534:65534',
                 '--tmpfs','/tmp:rw,noexec,nosuid,size=256m',
                 '--env','HF_HOME=/tmp/hf','--env','HF_HUB_OFFLINE=1',
                 '--env','TRANSFORMERS_OFFLINE=1','--env','TOKENIZERS_PARALLELISM=false']
    args += [image,'python',script]
    return args


def main():
    os.umask(0o077)
    revision=os.environ.get('VECTOR_PRIVACY_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision):
        raise RuntimeError('Run as root with the exact VECTOR_PRIVACY_REV.')
    if shutil.disk_usage(ROOT).free < 12*1024**3:
        raise RuntimeError('At least 12 GiB free disk space required for the isolated pilot.')
    with (ROOT/'.chat-release.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        helper_source=source(revision,'scripts/deploy/evaluate-privacy-review.py')
        ast.parse(helper_source)
        helper={'__name__':'ner_pilot_helpers'}
        exec(compile(helper_source,'pinned-privacy-evaluation','exec'),helper)
        before=helper['fingerprint']()
        if before['/vector-app']['image']!=helper['IMAGE']:
            raise RuntimeError('Production image changed. Inspect before running.')
        idle="""import pg from 'pg';const c=new pg.Client({connectionString:process.env.DATABASE_URL,connectionTimeoutMillis:5000});try{await c.connect();await c.query('BEGIN READ ONLY');await c.query(\"SET LOCAL statement_timeout = '5s'\");const r=await c.query(\"SELECT COUNT(*)::int AS count FROM agent_jobs WHERE status IN ('queued','running')\");if(r.rows[0].count!==0)throw Error('busy');}finally{await c.end();}"""
        command('docker','exec','-i','vector-app','node','--input-type=module',data=idle.encode())
        fixtures=json.loads(command('docker','exec','-i','vector-app','node','--input-type=module',
            data=fixture_expression(helper['HARNESS']).encode()))
        if len(fixtures)!=9:raise RuntimeError('Expected all nine unchanged fixtures.')
        fixtures += HOLDOUTS
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        suffix=stamp.lower()+'-'+uuid.uuid4().hex[:6]
        release=ROOT/'releases'/('vector-privacy-ner-pilot-'+suffix)
        release.mkdir(mode=0o700)
        work=release/'input';work.mkdir(mode=0o755);work.chmod(0o755)
        for name,text in {'setup.py':SETUP,'qualify.py':INFERENCE,
                          'fixtures.json':json.dumps(fixtures)}.items():
            path=work/name;path.write_text(text);path.chmod(0o644)
        setup='vector-ner-setup-'+suffix
        inference='vector-ner-test-'+suffix
        image='vector-privacy-ner:pilot-'+suffix
        owned=[]
        try:
            print('Download isolated Python runtime and CPU-only dependencies.',flush=True)
            command('docker','pull',BASE_IMAGE,timeout=600,live=True)
            metadata=json.loads(command('docker','image','inspect',BASE_IMAGE))[0]
            base_id=metadata['Id']
            owned.append(setup)
            command(*limited_container(setup,base_id,'/work/setup.py',work),timeout=2400,live=True)
            command('docker','commit',setup,image,timeout=180)
            image_id=json.loads(command('docker','image','inspect',image))[0]['Id']
            print('Run the unchanged fixtures offline, with 2 CPUs and 4 GiB RAM.',flush=True)
            owned.append(inference)
            observed=json.loads(command(*limited_container(inference,image_id,'/work/qualify.py',work,True),timeout=600,error_path=release/'inference-stderr.log'))
            payload=dict(fixtures=fixtures,inference=observed,original_case_count=9,additional_case_count=len(HOLDOUTS),
                core=source(revision,'lib/privacy-review-core.mjs'),rules=source(revision,'lib/privacy-rules.mjs'))
            checked=json.loads(command('docker','exec','-i','vector-app','node','--input-type=module',
                data=VERIFY.replace('INPUT_JSON',json.dumps(payload)).encode()))
            result=dict(checked,revision=revision,model=MODEL,model_revision=MODEL_REV,
                backbone_revision=BACKBONE_REV,base_image_id=base_id,pilot_image=image,pilot_image_id=image_id,
                resources=observed,offline_inference=True,production_activated=False,cloud_calls=0,
                api_cost_chf=0,ledger_writes=False,production_unchanged=helper['fingerprint']()==before,
                setup_manifest=json.loads((work/'setup-manifest.json').read_text()))
            result['passed']=result['passed'] and result['production_unchanged']
            (release/'result.json').write_text(json.dumps(result,indent=2)+'\n')
            display={k:v for k,v in result.items() if k!='setup_manifest'}
            print(json.dumps(display,indent=2));print('Report:',release/'result.json')
            if not result['passed']:
                raise RuntimeError('NER qualification failed. Privacy remains inactive.')
        finally:
            cleanup_failed=[]
            for name in reversed(owned):
                removed=subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                if removed.returncode:cleanup_failed.append(name)
            if cleanup_failed:
                raise RuntimeError('Pilot cleanup could not be verified: '+', '.join(cleanup_failed))
            print('Temporary pilot containers removed. No persistent service activated.',flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)
        raise SystemExit(1)
