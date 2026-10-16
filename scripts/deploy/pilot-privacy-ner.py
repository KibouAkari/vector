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

EXTENDED_CASES = [
    {'id':'credential-german-phrase','text':'Passwort: "synthetic long privacy phrase".',
     'expected':['synthetic long privacy phrase'],'secret_expected':['synthetic long privacy phrase']},
    {'id':'credential-email-shaped','text':'password=synthetic@example.invalid',
     'expected':['synthetic@example.invalid'],'secret_expected':['synthetic@example.invalid']},
    {'id':'credential-github','text':'Token: '+('ghp_'+'x'*36),
     'expected':['ghp_'+'x'*36],'secret_expected':['ghp_'+'x'*36]},
    {'id':'credential-openai','text':'API key: '+('sk-'+'synthetic_example_'*3),
     'expected':['sk-'+'synthetic_example_'*3],'secret_expected':['sk-'+'synthetic_example_'*3]},
    {'id':'credential-aws','text':'AWS: '+('AKIA'+'X'*16),
     'expected':['AKIA'+'X'*16],'secret_expected':['AKIA'+'X'*16]},
    {'id':'credential-gemini','text':'Key: '+('AIza'+'x'*35),
     'expected':['AIza'+'x'*35],'secret_expected':['AIza'+'x'*35]},
    {'id':'credential-url','text':'postgres://demo:synthetic_phrase@db.example.invalid/database',
     'expected':['synthetic_phrase'],'secret_expected':['synthetic_phrase']},
    {'id':'credential-private-key','text':'-----BEGIN '+'PRIVATE KEY-----\nSYNTHETIC_ONLY_NOT_A_KEY\n-----END '+'PRIVATE KEY-----',
     'expected':['-----BEGIN '+'PRIVATE KEY-----\nSYNTHETIC_ONLY_NOT_A_KEY\n-----END '+'PRIVATE KEY-----'],
     'secret_expected':['-----BEGIN '+'PRIVATE KEY-----\nSYNTHETIC_ONLY_NOT_A_KEY\n-----END '+'PRIVATE KEY-----']},
    {'id':'context-name-at-end','text':'Allgemeine Notiz. '*170+'Bitte schreibe an Zoë Beispiel.',
     'expected':['Zoë Beispiel']},
    {'id':'context-boundary-name','text':'Notiz '*63+'Zoë Beispiel hat Geburtstag. Schreibe ihr eine Gratulation.',
     'expected':['Zoë Beispiel']},
    {'id':'context-benign','text':'Technische Notiz zum System. '*170,'expected':[]},
    {'id':'context-unicode-prefix','text':'😀 '*250+'Gratuliere Élodie Martin zum Geburtstag.',
     'expected':['Élodie Martin']},
]

EXTENDED_INFERENCE = r'''
import importlib.util,json,os,resource,sys,time
from pathlib import Path
assert os.environ.get('HF_HUB_OFFLINE')=='1'
spec=importlib.util.spec_from_file_location('privacy_ner_core','/work/privacy-ner-core.py')
core=importlib.util.module_from_spec(spec);sys.modules[spec.name]=core;spec.loader.exec_module(core)
started=time.monotonic();detector=core.LocalPersonDetector();load=time.monotonic()-started
results=[]
for fixture in json.loads(Path('/work/fixtures.json').read_text()):
    started=time.monotonic();observed=detector.inspect(fixture['text'])
    results.append(dict(id=fixture['id'],seconds=round(time.monotonic()-started,3),**observed))
print(json.dumps(dict(cases=results,load_seconds=round(load,3),
    peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    scope='PERSON and deterministic credentials; bounded complete chunk coverage',
    long_context_exercised=True,threshold=0.35)))
'''

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

WEIGHT_ACCESS = r'''
import hashlib,json,stat
from pathlib import Path

def normalize_weight_access(root,expected_hash=None):
    path=root/'entity/model.safetensors'
    if root.is_symlink() or (root/'entity').is_symlink() or path.is_symlink():
        raise RuntimeError('Unexpected symlink in model weights path.')
    if not path.is_file():
        raise RuntimeError('Weights are missing even for the image owner. No permission fix applied.')
    with path.open('rb') as handle:
        actual=hashlib.file_digest(handle,'sha256').hexdigest()
    if expected_hash is not None and actual!=expected_hash:
        raise RuntimeError('Weights checksum differs from the original setup manifest.')
    before=stat.S_IMODE(path.stat().st_mode)
    path.chmod(0o444)
    return dict(file=str(path),sha256=actual,mode_before=oct(before),mode_after=oct(stat.S_IMODE(path.stat().st_mode)))
'''

# Safetensors atomically saves via a private 0600 temporary file. Public model
# assets need explicit read permission for the isolated inference UID.
SETUP += '\n' + WEIGHT_ACCESS + "\nnormalize_weight_access(Path('/models'))\n"

INFERENCE = r'''
import json,os,resource,time
from pathlib import Path
assert os.environ.get('HF_HUB_OFFLINE')=='1'
# Fail with the actual OS error before library fallback can hide access errors.
with Path('/models/entity/model.safetensors').open('rb') as weights:
    assert weights.read(8), 'Empty model weights'
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
    const leaked=fixture.expected.filter(value=>plan.sanitized.includes(value));
    const secrets_hidden=(fixture.secret_expected || []).every(value=>
        plan.selected.map(core.displayFinding).every(f=>!f.displayValue.includes(value)));
    return {id:fixture.id,passed:!missing.length&&!extra&&roundtrip&&!leaked.length&&secrets_hidden,seconds:actual.seconds,
        missing_expected:missing,unmasked_expected:leaked,secrets_hidden,findings:found,unexpected_findings:extra};
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
        extended=os.environ.get('VECTOR_PRIVACY_NER_EXTENDED','0')
        if extended not in ('0','1'):raise RuntimeError('Invalid extended qualification mode.')
        if extended=='1' and not os.environ.get('VECTOR_PRIVACY_NER_REUSE_RELEASE'):
            raise RuntimeError('Extended qualification requires the existing offline pilot image.')
        additional=HOLDOUTS+(EXTENDED_CASES if extended=='1' else [])
        fixtures += additional
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        suffix=stamp.lower()+'-'+uuid.uuid4().hex[:6]
        release=ROOT/'releases'/('vector-privacy-ner-pilot-'+suffix)
        release.mkdir(mode=0o700)
        work=release/'input';work.mkdir(mode=0o755);work.chmod(0o755)
        for name,text in {'setup.py':SETUP,'qualify.py':EXTENDED_INFERENCE if extended=='1' else INFERENCE,
                          'fixtures.json':json.dumps(fixtures)}.items():
            path=work/name;path.write_text(text);path.chmod(0o644)
        if extended=='1':
            backend=work/'privacy-ner-core.py'
            backend.write_text(source(revision,'lib/privacy-ner-core.py'));backend.chmod(0o644)
        setup='vector-ner-setup-'+suffix
        inference='vector-ner-test-'+suffix
        image='vector-privacy-ner:pilot-'+suffix
        owned=[]
        try:
            reuse=os.environ.get('VECTOR_PRIVACY_NER_REUSE_RELEASE','')
            weight_access=None
            if reuse:
                previous=Path(reuse)
                if previous.is_symlink() or previous.parent!=ROOT/'releases' or not re.fullmatch(
                        r'vector-privacy-ner-pilot-[0-9]{8}t[0-9]{6}z-[a-f0-9]{6}',previous.name):
                    raise RuntimeError('Unexpected pilot reuse path.')
                manifest_path=previous/'input/setup-manifest.json'
                if manifest_path.is_symlink() or not manifest_path.is_file():
                    raise RuntimeError('Original setup manifest is missing.')
                manifest=json.loads(manifest_path.read_text())
                if manifest.get('downloaded_weights_sha256')!='3003753fba99e40645cf088c7367a2c6211fc174897dc64f1f9c147c29d18d2d':
                    raise RuntimeError('Original weights pin mismatch.')
                expected=manifest.get('files_sha256',{}).get('entity/model.safetensors','')
                if not re.fullmatch('[a-f0-9]{64}',expected):
                    raise RuntimeError('Converted weights checksum missing.')
                existing='vector-privacy-ner:pilot-'+previous.name.removeprefix('vector-privacy-ner-pilot-')
                metadata=json.loads(command('docker','image','inspect',existing))[0]
                base_id=metadata['Id']
                expected_image=os.environ.get('VECTOR_PRIVACY_NER_REUSE_IMAGE_ID','')
                if extended=='1' and not re.fullmatch('sha256:[a-f0-9]{64}',expected_image):
                    raise RuntimeError('Extended qualification requires the observed source image ID.')
                if expected_image and base_id!=expected_image:
                    raise RuntimeError('Retained pilot image ID changed.')
                (work/'setup-manifest.json').write_text(json.dumps(manifest))
                repair=work/'weight-access.py'
                repair.write_text(WEIGHT_ACCESS+'\nprint(json.dumps(normalize_weight_access(Path("/models"),'+repr(expected)+')))\n')
                repair.chmod(0o644)
                print('Reuse existing pilot image. Verify weights and fix public-asset read access offline.',flush=True)
                args=limited_container(setup,base_id,'/work/weight-access.py',work)
                args[-3:-3]=['--network','none','--user','0:0']
                owned.append(setup)
                weight_access=json.loads(command(*args,timeout=180,error_path=release/'weight-access-stderr.log'))
                print(json.dumps(weight_access),flush=True)
                (release/'weight-access.json').write_text(json.dumps(weight_access,indent=2)+'\n')
            else:
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
            payload=dict(fixtures=fixtures,inference=observed,original_case_count=9,additional_case_count=len(additional),
                core=source(revision,'lib/privacy-review-core.mjs'),rules=source(revision,'lib/privacy-rules.mjs'))
            checked=json.loads(command('docker','exec','-i','vector-app','node','--input-type=module',
                data=VERIFY.replace('INPUT_JSON',json.dumps(payload)).encode()))
            result=dict(checked,extended_qualification=extended=='1',revision=revision,model=MODEL,model_revision=MODEL_REV,
                backbone_revision=BACKBONE_REV,base_image_id=base_id,pilot_image=image,pilot_image_id=image_id,
                resources=observed,reused_release=reuse or None,weight_access=weight_access,offline_inference=True,production_activated=False,cloud_calls=0,
                api_cost_chf=0,ledger_writes=False,production_unchanged=helper['fingerprint']()==before,
                setup_manifest=json.loads((work/'setup-manifest.json').read_text()))
            result['passed']=result['passed'] and result['production_unchanged']
            result['context_fixture_qualification_passed']=extended=='1' and result['passed']
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
