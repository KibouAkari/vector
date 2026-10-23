#!/usr/bin/env python3
"""Explicitly prepare one separate CPU candidate; never activate or generate.

Downloading changes only the local model registry/cache. Baseline service code,
profiles and container generations must remain unchanged. A successful import
does not establish native compatibility, speed, German quality or tool use.
"""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import uuid

MODEL = 'LiquidAI/lfm2.5-1.2b-instruct:latest'
WEIGHT_SHA256 = 'b1b3de114215d9507409a662a501a631095a479a419584e8a2ded6304b19b4f5'
WEIGHT_BYTES = 730895168
SOURCE = 'https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF/blob/main/LFM2.5-1.2B-Instruct-Q4_K_M.gguf'

METADATA = r'''
import hashlib,json,re,urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None

opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
def read(route,body=None):
    raw=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request('http://vector-local-inference:11434/api/'+route,
        data=raw,headers={'Content-Type':'application/json'})
    with opener.open(req,timeout=5) as response:raw=response.read(1048577)
    if len(raw)>1048576:raise RuntimeError('METADATA_RESPONSE_LIMIT')
    return json.loads(raw)

def metadata(model,expected_weight):
    tags=read('tags').get('models',[])
    roster={row['name']:row['digest'] for row in tags}
    matches=[row for row in tags if row['name'].casefold()==model.casefold()]
    if len(matches)>1:raise RuntimeError('AMBIGUOUS_CANDIDATE_TAG')
    result={'registered_models':roster,'candidate_exists':bool(matches),'model_calls':0}
    if not matches:return result
    row=matches[0]
    show=read('show',{'model':row['name'],'verbose':False})
    weights=re.findall(r'^FROM\s+\S*sha256[-:]([a-f0-9]{64})\s*$',show.get('modelfile',''),re.M)
    if weights!=[expected_weight]:raise RuntimeError('CANDIDATE_WEIGHT_DIGEST_MISMATCH')
    details=show.get('details',{})
    if details.get('family')!='lfm2' or details.get('quantization_level')!='Q4_K_M':
        raise RuntimeError('CANDIDATE_ARCHITECTURE_MISMATCH')
    if type(row.get('size')) is not int or not 730895168<=row['size']<=740000000:
        raise RuntimeError('CANDIDATE_SIZE_MISMATCH')
    result.update(model=row['name'],manifest_digest=row['digest'],size_bytes=row['size'],
        family=details['family'],quantization=details['quantization_level'],
        weight_digest_matches_source=True,
        template_sha256=hashlib.sha256(show.get('template','').encode()).hexdigest(),
        template_uses_messages='.Messages' in show.get('template',''),
        template_uses_prompt='.Prompt' in show.get('template',''))
    return result
'''


def registered_models_retained(before,after):
    """Only the separately named candidate may be added; never overwrite tags."""
    old=before['registered_models'];new=after['registered_models']
    return (all(new.get(key)==value for key,value in old.items())
            and all(key in old or key.casefold()==MODEL.casefold() for key in new))


def observed(guard,rows):
    result={}
    for name,row in rows.items():
        state=row['State']
        mounts=sorted(row.get('Mounts',[]),key=lambda value:guard.canonical(value))
        result[name]=(*guard.identity(row),state.get('Running'),state.get('OOMKilled'),
            state.get('Health',{}).get('Status'),guard.digest(guard.canonical({
                'config':row['Config'],'host':row['HostConfig'],'mounts':mounts})))
    return result


def inspect_metadata(container):
    program=METADATA+'\nprint(json.dumps(metadata('+repr(MODEL)+','+repr(WEIGHT_SHA256)+')))\n'
    result=subprocess.run(['docker','exec',container,'python3','-c',program],
        capture_output=True,timeout=20)
    if result.returncode:
        # Expose only our bounded diagnostic codes, never raw transport stderr.
        codes=re.findall(rb'^RuntimeError: ([A-Z][A-Z0-9_]{2,79})$',result.stderr,re.M)
        raise RuntimeError(codes[-1].decode() if codes else 'CANDIDATE_METADATA_CHECK_FAILED')
    return json.loads(result.stdout)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--guard-helper',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--workspace-root',type=Path,required=True)
    parser.add_argument('--lock-file',type=Path,required=True)
    parser.add_argument('--download',action='store_true')
    args=parser.parse_args()
    if not args.download:parser.error('This command requires explicit --download authorization')
    sys.dont_write_bytecode=True
    os.umask(0o077)
    if any(p.is_symlink() for p in (args.guard_helper,*args.guard_helper.parents)):
        raise RuntimeError('UNSAFE_GUARD_PATH')
    spec=importlib.util.spec_from_file_location('model_candidate_guard',args.guard_helper)
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    guard.checked_path(args.lock_file)
    descriptor=os.open(args.lock_file,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    meta=os.fstat(descriptor)
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid!=os.geteuid():
        os.close(descriptor);raise RuntimeError('EXISTING_OWNED_RELEASE_LOCK_REQUIRED')
    with os.fdopen(descriptor,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        baseline=guard.checked_path(str(args.baseline),directory=True)
        config=guard.read_config(baseline/'operator.json')
        record=json.loads((baseline/'record.json').read_bytes())
        saved=guard.checked_path(str(baseline/'compose.candidate.json'))
        active=guard.checked_path(config['compose'])
        if guard.digest(saved.read_bytes())!=record['candidate_compose_sha256'] or active.read_bytes()!=saved.read_bytes():
            raise RuntimeError('CONFIRMED_BASELINE_PROFILE_CHANGED')
        profile=guard.compose(config,active);code=guard.code_source(profile,config['service'])
        if str(code)!=record['candidate_code'] or guard.tree_files(code)!=record['candidate_files']:
            raise RuntimeError('CONFIRMED_BASELINE_CODE_CHANGED')
        before=guard.inventory();assistant=before[config['container']]
        if guard.identity(assistant)!=tuple(record['deployed_identity']):
            raise RuntimeError('CONFIRMED_ASSISTANT_GENERATION_CHANGED')
        if not assistant['State']['Running'] or assistant['State'].get('Health',{}).get('Status')!='healthy':
            raise RuntimeError('HEALTHY_ASSISTANT_REQUIRED')
        inference=before.get('vector-local-inference')
        if not inference or not inference['State']['Running']:
            raise RuntimeError('EXISTING_INFERENCE_REQUIRED')
        releases=guard.checked_path(str(args.workspace_root/'releases'),directory=True)
        report=releases/('local-model-preparation-'+uuid.uuid4().hex);report.mkdir(mode=0o700)
        result=dict(prepared=False,model=MODEL,source=SOURCE,expected_weight_sha256=WEIGHT_SHA256,
            expected_weight_bytes=WEIGHT_BYTES,model_calls=0,cloud_calls=0,messages_sent=0,
            production_activated=False,eligible_for_activation=False,native_execution_tested=False,
            download_attempted=False)
        print('Kandidat separat vorbereiten: etwa 731 MB Download, keine Modellanfrage oder Aktivierung.',flush=True)
        print('Belege: '+str(report),flush=True)
        guard.write_private(report/'preparation.py',Path(__file__).read_bytes())
        guard.write_private(report/'result.json',guard.canonical(result))
        error=None
        try:
            initial=inspect_metadata(config['container'])
            guard.write_private(report/'registry.before.json',guard.canonical(initial))
            if not initial['candidate_exists']:
                result['download_attempted']=True
                # Pull contains only a public model name, no user or game input.
                with (report/'pull.stdout').open('xb') as stdout,(report/'pull.stderr').open('xb') as stderr:
                    try:
                        child=subprocess.run(['docker','exec','vector-local-inference','ollama','pull',MODEL],
                            stdout=stdout,stderr=stderr,timeout=300)
                    except subprocess.TimeoutExpired:
                        result['download_completion_unknown']=True
                        raise RuntimeError('CANDIDATE_DOWNLOAD_TIMEOUT')
                if child.returncode:raise RuntimeError('CANDIDATE_DOWNLOAD_FAILED')
            final=inspect_metadata(config['container'])
            if not final['candidate_exists'] or not registered_models_retained(initial,final):
                raise RuntimeError('EXISTING_MODEL_REGISTRY_CHANGED')
            guard.write_private(report/'registry.after.json',guard.canonical(final))
            result.update({key:value for key,value in final.items() if key!='registered_models'})
            result['prepared']=True
        except Exception as exc:
            error=exc
            result.update(prepared=False,error=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)
        finally:
            unchanged=(observed(guard,before)==observed(guard,guard.inventory())
                and active.read_bytes()==saved.read_bytes()
                and guard.tree_files(code)==record['candidate_files'])
            result['service_configuration_and_identities_unchanged']=unchanged
            result['prepared']=bool(result['prepared'] and unchanged)
            result['model_cache_may_have_changed']=result['download_attempted']
            guard.write_private(report/'result.json',guard.canonical(result))
            print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        if error or not result['prepared']:raise SystemExit(1)
        print('Nur Modellbereitstellung abgeschlossen. Gesprächsqualität und Laufzeit sind noch ungeprüft.',flush=True)


if __name__=='__main__':main()
