#!/usr/bin/env python3
"""Expand the observed mode4 service only; no game stop, model call or message."""
import ast
import copy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import sys
from types import SimpleNamespace

ROOT=Path('/root/vector-workspace'); REPO=ROOT/'github/vector'
BASE='b88c1e4f4e95d94fe02e84d0d8a5b5f7b616f5cf'
PREVIOUS='3cabf8cf82b042deeac88f6bc4ac6ccfde090f30'
PREVIOUS_RELEASE=ROOT/'releases/vector-fegcraft-reviewed-help-20261018T165931Z-e41450'
POINTER=ROOT/'fegcraft-mod-context.json'
FILES=('runtime.py','server.py','stats.py','policy.py','recipes.py','knowledge.py','documentation.py','public-knowledge.json','modrecipes.py')


def candidate(profile,code,recipe_sha):
    value=copy.deepcopy(profile); service=value['services']['assistant']
    if service['environment'].get('VECTOR_FEGCRAFT_KNOWLEDGE')!='4' or 'VECTOR_FEGCRAFT_MOD_RECIPES_SHA256' in service['environment']:
        raise RuntimeError('MOD_CONTEXT_BASE_MODE_CHANGED')
    if any(m['target']=='/inputs/mod-recipes.json' for m in service['volumes']): raise RuntimeError('MOD_CONTEXT_EXISTING_RECIPE_MOUNT')
    for mount in service['volumes']:
        if mount['target']=='/code': mount['source']=str(code)
        elif mount['target']=='/inputs/documentation.json': mount['source']=str(code/'public-knowledge.json')
    service['volumes'].append(dict(type='bind',source=str(code/'mod-recipes.json'),target='/inputs/mod-recipes.json',read_only=True,bind={'create_host_path':False}))
    service['environment']['VECTOR_FEGCRAFT_MOD_RECIPES_SHA256']=recipe_sha
    return value


def verify_current(p,h,support,revision):
    pointer=json.loads(p.read(POINTER)); directory=Path(pointer['release']);p.safe(directory)
    if (pointer.get('revision')!=revision or directory.parent!=ROOT/'releases'
        or not re.fullmatch(r'vector-fegcraft-reviewed-help-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}',directory.name)):
        raise RuntimeError('MOD_CONTEXT_POINTER_CHANGED')
    record=json.loads(p.read(directory/'deployment.json'))
    raw=p.read(p.INSTALL/'compose.json'); manifest_raw=p.read(p.INSTALL/'manifest.json'); manifest=json.loads(manifest_raw)
    previous=p.read(directory/'compose.before.json')
    if (record.get('status')!='deployed' or record.get('revision')!=revision or record.get('prior_revision')!=PREVIOUS
        or record.get('prior_release')!=str(PREVIOUS_RELEASE) or p.sha(previous)!=record['old_profile_sha']
        or p.sha(raw)!=record['new_profile_sha'] or p.sha(manifest_raw)!=record['new_manifest_sha']
        or manifest.get('backend_revision')!=revision or manifest.get('backend_release')!=str(directory)
        or manifest.get('compose_sha256')!=p.sha(raw) or p.read(directory/'compose.candidate.json')!=raw):
        raise RuntimeError('MOD_CONTEXT_DEPLOYMENT_CHANGED')
    recipe_sha=p.sha(p.read(directory/'code/mod-recipes.json'))
    profile=json.loads(raw)
    if profile!=candidate(json.loads(previous),directory/'code',recipe_sha): raise RuntimeError('MOD_CONTEXT_PROFILE_CHANGED')
    support.check_runtime(support.SERVICE,profile['services']['assistant'],manifest['owner'])
    for name in FILES:
        if p.read(directory/'code'/name)!=p.source(revision,'services/fegcraft-assistant/'+name): raise RuntimeError('MOD_CONTEXT_CODE_CHANGED')
    stage=json.loads(p.read(directory/'stage-result.json'))
    if stage.get('passed') is not True or stage.get('model_calls')!=0 or stage.get('cloud_calls')!=0:
        raise RuntimeError('MOD_CONTEXT_STAGE_REQUIRED')
    return directory


def stage(support,directory,profile,owner):
    suffix=secrets.token_hex(8);name='vector-mod-context-stage-'+suffix
    value=copy.deepcopy(profile); service=value['services'].pop('assistant');value['services'][name]=service
    state=directory/'stage-state';state.mkdir(mode=0o700)
    uid,gid=map(int,service['user'].split(':'));os.chown(state,uid,gid)
    for mount in service['volumes']:
        if mount['target']=='/state': mount['source']=str(state)
    service['container_name']=name;service['restart']='no';service['labels'][support.LABEL]=suffix
    path=directory/'stage.json';support.atomic(path,(json.dumps(value,indent=2)+'\n').encode())
    try:
        support.run('docker','compose','-p',name,'-f',str(path),'config','--quiet')
        support.run('docker','compose','-p',name,'-f',str(path),'up','-d','--no-deps','--no-build','--pull','never',name,timeout=45)
        support.healthy(name,service,owner,require_docker=False)
        result=subprocess.run(['docker','exec',name,'python3','/code/rollout-probe.py'],capture_output=True,timeout=30)
        support.atomic(directory/'stage-probe.log',(result.stdout+result.stderr)[:32768])
        if result.returncode: raise RuntimeError('MOD_CONTEXT_STAGE_FAILED_PRIVATE_REPORT_RETAINED')
        value=json.loads(result.stdout)
        if value.get('passed') is not True or value.get('model_calls')!=0: raise RuntimeError('MOD_CONTEXT_ZERO_MODEL_GATE_FAILED')
        return value
    finally: support.cleanup_stage(name,suffix)


def main():
    os.umask(0o077);sys.dont_write_bytecode=True
    revision=os.environ.get('VECTOR_FEGCRAFT_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision): raise RuntimeError('MOD_CONTEXT_ROOT_AND_PIN_REQUIRED')
    raw=subprocess.check_output(['git','-C',str(REPO),'show',BASE+':scripts/deploy/prepare-fegcraft-chat-cutover.py'])
    ns={'__name__':'mod_context_support','__file__':str(REPO/'scripts/deploy/prepare-fegcraft-chat-cutover.py')}
    exec(compile(raw,ns['__file__'],'exec'),ns);p=SimpleNamespace(**ns)
    h=p.load(p.HELPER,'scripts/diagnostics/fegcraft-admission-readiness.py')
    support=p.load(p.DEPLOYED,'scripts/deploy/release-fegcraft-reviewed-help.py')
    p.safe(ROOT/'.chat-release.lock')
    with (ROOT/'.chat-release.lock').open('rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        p.run('git','-C',str(REPO),'merge-base','--is-ancestor',revision,'origin/main')
        if len(sys.argv)==3 and sys.argv[1]=='--rollback':
            directory=Path(sys.argv[2])
            if json.loads(p.read(POINTER))!={'release':str(directory),'revision':revision}: raise RuntimeError('MOD_CONTEXT_ROLLBACK_POINTER_CHANGED')
            support.rollback(directory,h);POINTER.unlink();return
        if sys.argv[1:]: raise RuntimeError('MOD_CONTEXT_ARGUMENTS_INVALID')
        if POINTER.exists():
            verify_current(p,h,support,revision);print('Modwissen bereits installiert und geprüft. Kein Modellaufruf oder Minecraft-Neustart.');return
        previous=p.load(PREVIOUS,'scripts/deploy/update-fegcraft-conversation.py')
        if previous.verify_current(p,h,support,PREVIOUS)!=PREVIOUS_RELEASE: raise RuntimeError('MOD_CONTEXT_PREVIOUS_RELEASE_CHANGED')
        support.protected_live(h)  # Require the recovered game healthy before any update.
        before=h.snapshot();profile_raw=p.read(p.INSTALL/'compose.json');manifest_raw=p.read(p.INSTALL/'manifest.json')
        profile=json.loads(profile_raw);manifest=json.loads(manifest_raw)
        directory=ROOT/'releases'/('vector-fegcraft-reviewed-help-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3))
        p.safe(directory);directory.mkdir(mode=0o700);print('Modwissen und Rückrollbelege:',directory,flush=True)
        code=directory/'code';code.mkdir(mode=0o755);code.chmod(0o755)
        for name in FILES:
            data=p.source(revision,'services/fegcraft-assistant/'+name)
            if name.endswith('.py'): ast.parse(data)
            support.atomic(code/name,data,0o644)
        # Load the exact candidate module with only its public pure dependencies.
        sys.path.insert(0,str(code));import importlib.util
        spec=importlib.util.spec_from_file_location('installed_mod_recipe_export',code/'modrecipes.py')
        recipes=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipes)
        jars=list((p.DATA/'mods').glob('travelersbackpack-*.jar'))
        if len(jars)!=1: raise RuntimeError('MOD_CONTEXT_BACKPACK_JAR_AMBIGUOUS')
        p.safe(jars[0]);export=recipes.export_installed(jars[0])
        recipe_raw=(json.dumps(export,sort_keys=True)+'\n').encode();support.atomic(code/'mod-recipes.json',recipe_raw,0o644)
        book=recipes.ModRecipes(code/'mod-recipes.json',p.sha(recipe_raw))
        if not book.render('travelersbackpack:standard'): raise RuntimeError('MOD_CONTEXT_STANDARD_RECIPE_UNSUPPORTED')
        old_code=next(Path(m['source']) for m in profile['services']['assistant']['volumes'] if m['target']=='/code')
        for name in ('health.py','read-probe.py'): support.atomic(code/name,p.read(old_code/name),0o644)
        support.atomic(code/'rollout-probe.py',p.source(revision,'tests/fegcraft-mod-context-smoke.py'),0o644)
        value=candidate(profile,code,p.sha(recipe_raw))
        print('Kurze signierte HTTP-Prüfung mit isoliertem Zustand. Keine Modellaufrufe, Minecraft bleibt online.',flush=True)
        result=stage(support,directory,value,manifest['owner'])
        support.atomic(directory/'stage-result.json',(json.dumps(result,indent=2)+'\n').encode())
        if h.snapshot()!=before or p.read(p.INSTALL/'compose.json')!=profile_raw or p.read(p.INSTALL/'manifest.json')!=manifest_raw:
            raise RuntimeError('MOD_CONTEXT_BASELINE_CHANGED_DURING_STAGE')
        new_profile=(json.dumps(value,indent=2)+'\n').encode();next_manifest=copy.deepcopy(manifest)
        next_manifest.update(compose_sha256=p.sha(new_profile),backend_revision=revision,backend_release=str(directory))
        new_manifest=(json.dumps(next_manifest,indent=2)+'\n').encode()
        record=dict(status='prepared',revision=revision,prior_revision=PREVIOUS,prior_release=str(PREVIOUS_RELEASE),protected=support.protected(before),
          old_profile_sha=p.sha(profile_raw),old_manifest_sha=p.sha(manifest_raw),new_profile_sha=p.sha(new_profile),new_manifest_sha=p.sha(new_manifest))
        for name,data in (('compose.before.json',profile_raw),('manifest.before.json',manifest_raw),('compose.candidate.json',new_profile),
          ('deployment.json',(json.dumps(record,indent=2)+'\n').encode()),('release.py',Path(__file__).read_bytes())): support.atomic(directory/name,data)
        support.atomic(directory/'rollback.sh',('#!/bin/bash\nset -Eeuo pipefail\nexport VECTOR_FEGCRAFT_REV='+revision+'\nexec python3 '+shlex.quote(str(directory/'release.py'))+' --rollback '+shlex.quote(str(directory))+'\n').encode(),0o700)
        p.run('docker','compose','-p',support.SERVICE,'-f',str(directory/'compose.candidate.json'),'config','--quiet')
        try:
            support.atomic(p.INSTALL/'compose.json',new_profile);support.atomic(p.INSTALL/'manifest.json',new_manifest);support.compose()
            coverage=support.healthy(support.SERVICE,value['services']['assistant'],manifest['owner'])
            if support.protected_live(h)!=record['protected']: raise RuntimeError('MOD_CONTEXT_OTHER_SERVICE_CHANGED')
            record['status']='deployed';support.atomic(directory/'deployment.json',(json.dumps(record,indent=2)+'\n').encode())
            support.atomic(POINTER,(json.dumps({'release':str(directory),'revision':revision})+'\n').encode());verify_current(p,h,support,revision)
        except BaseException:
            support.rollback(directory,h)
            if POINTER.exists() and json.loads(p.read(POINTER))=={'release':str(directory),'revision':revision}: POINTER.unlink()
            raise
        print(json.dumps(dict(deployed=True,only_assistant_recreated=True,minecraft_unchanged=True,other_services_unchanged=True,
              reviewed_mods=63,reviewed_passages=84,installed_backpack_version=export['version'],coverage=coverage,
              qualification=result,model_calls=0,cloud_calls=0,messages_sent=0,game_cutover_still_held=True,rollback=str(directory/'rollback.sh')),indent=2))


if __name__=='__main__':
    try: main()
    except BaseException as exc:
        value=str(exc);code=value if type(exc) in (RuntimeError,ValueError) and re.fullmatch('[A-Z][A-Z0-9_]{2,100}',value) else type(exc).__name__
        print('ERROR: '+code+'. Kein Minecraft-Neustart durch dieses Skript.',file=sys.stderr);raise SystemExit(1)
