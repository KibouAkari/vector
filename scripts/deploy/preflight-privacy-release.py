#!/usr/bin/env python3
"""Read-only release inventory and archived helper structure; no activation."""
import ast
import builtins
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import subprocess

ROOT=Path('/root/vector-workspace')
REPO=ROOT/'github/vector'
MERGED='ba30c82f0a7b66a29272c1711858ac78ad522238'
TESTED='a20b9a650546e9cf8fbbba9b0fbc9f85acaf88a5'
APP_IMAGE='sha256:e59160f17f47b2b8231e417bc64c25ce82a5a7320be6a0b47c6d8b226f699a80'
API_REPORT=ROOT/'releases/vector-privacy-api-evaluation-20261016T085057Z-e2680b/result.json'
ACTIVATION=ROOT/'releases/vector-local-worker-activation-20261015T134202Z-74e562/activation.json'
SOURCE_RELEASE=ROOT/'releases/vector-local-worker-release-20261015T133651Z-38f67b/release.json'


def helper_inventory(h,captured):
    result={}
    names=('main','prepare','rollback','config','compose_up','tree_hash','verify_others','atomic','save_record')
    for key in names:
        function=h.get(key)
        if not inspect.isfunction(function):continue
        found=None
        for filename,tree in captured:
            if filename!=function.__code__.co_filename:continue
            if isinstance(tree,str):tree=ast.parse(tree)
            for node in tree.body:
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==function.__name__:
                    found=node
        if found is not None:result[key]=ast.unparse(found)
    return result


def factory_inventory(captured):
    result={};seen=set()
    for filename,tree in captured:
        if not filename.startswith(str(ROOT/'archive')):continue
        if isinstance(tree,str):tree=ast.parse(tree)
        for node in tree.body:
            if isinstance(node,ast.FunctionDef) and node.name in ('prepare','main'):
                source=ast.unparse(node)
                if source not in seen:
                    seen.add(source);result[filename+' :: '+node.name]=source
    return result


def main():
    if os.geteuid()!=0:raise RuntimeError('Run as root for read-only release inventory.')
    report=json.loads(API_REPORT.read_text())
    if not report.get('passed') or report.get('revision')!=TESTED or report.get('app_image')!=APP_IMAGE or not report.get('production_unchanged'):
        raise RuntimeError('Expected the observed successful enabled API qualification.')
    code=subprocess.check_output(['git','-C',str(REPO),'show',MERGED+':scripts/deploy/activate-local-workers.py'],text=True)
    module={'__name__':'privacy_release_inventory'}
    exec(compile(ast.parse(code),'pinned-local-worker-helper-factory','exec'),module)
    captured=[];real_compile=builtins.compile
    def capture(source,filename,mode,*args,**kwargs):
        if mode=='exec' and isinstance(source,(str,ast.Module)):
            captured.append((str(filename),copy.deepcopy(source)))
        return real_compile(source,filename,mode,*args,**kwargs)
    try:
        builtins.compile=capture
        h=module['helpers']()
    finally:builtins.compile=real_compile
    compose=Path('/opt/vector/docker-compose.yml')
    before=compose.read_bytes();config=h['config'](compose);app=config['services']['app']
    previous=json.loads(ACTIVATION.read_text());source_release=json.loads(SOURCE_RELEASE.read_text())
    current=h['obj']('vector-app')
    summary=dict(api_qualification_passed=True,compose_sha256=hashlib.sha256(before).hexdigest(),
        compose_matches_local_worker_activation=hashlib.sha256(before).hexdigest()==previous['candidate_sha256'],
        source_matches_current_release=h['tree_hash'](h['LIVE'])==source_release['new_source_hash'],
        current_image_matches_previous_release=current['Image']==source_release['image_id'],
        tested_image_available=json.loads(h['run']('docker','image','inspect',APP_IMAGE))[0]['Id']==APP_IMAGE,
        app_networks=sorted(app.get('networks',{})),local_workers_enabled=str(app.get('environment',{}).get('VECTOR_LOCAL_WORKERS'))=='1',
        privacy_enabled=str(app.get('environment',{}).get('VECTOR_PRIVACY_REVIEW','0'))=='1',
        app_volume_count=len(app.get('volumes',[])),helper_keys=sorted(h),
        persistent_privacy_directory_exists=Path('/opt/vector/privacy-ner').exists())
    if compose.read_bytes()!=before:raise RuntimeError('Compose changed during read-only inventory.')
    print(json.dumps(summary,indent=2))
    definitions={**helper_inventory(h,captured),**factory_inventory(captured)}
    seen=set()
    for key,source in definitions.items():
        if source in seen:continue
        seen.add(source)
        # Only trusted program definitions, never resolved Compose/env values.
        source=re.sub(r'(?:postgres(?:ql)?|redis|https?)://[^\s\'\"]+:[^\s\'\"]+@','<redacted-credential-url>@',source)
        print('\nHELPER '+key+'\n'+source)
    print('\nRead-only inventory complete. No restart, inference, database write or activation requested.')

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)
        raise SystemExit(1)
