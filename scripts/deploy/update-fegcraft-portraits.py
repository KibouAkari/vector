#!/usr/bin/env python3
"""Qualify social routing and fresh portraits, then update only the owned assistant; no game changes."""
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
PREVIOUS='a0ea5de2348ad14788949d15c006e4282738fc36'
PREVIOUS_RELEASE=ROOT/'releases/vector-fegcraft-reviewed-help-20261019T064939Z-d1f1fc'
POINTER=ROOT/'fegcraft-portraits.json'
FILES=('runtime.py','server.py','stats.py','policy.py','recipes.py','knowledge.py','documentation.py','public-knowledge.json','modrecipes.py','companion.py','knowledge-pack.json','portraits.py')


def qualified(result):
    return (result.get('passed') is True and result.get('model_calls')==1
        and result.get('cloud_calls')==0 and result.get('messages_sent')==0
        and result.get('unknown_usage_calls')==0
        and all(result.get(k) is True for k in ('authenticated_http','synthetic_inputs','fresh_portraits',
               'self_and_aliases','personality','policy_retained','isolated_state'))
        and all(type(result.get(k)) is int and result[k]>0 for k in ('input_tokens','output_tokens')))


def candidate(profile,code,recipe_sha,advancements):
    value=copy.deepcopy(profile);service=value['services']['assistant'];env=service['environment']
    if env.get('VECTOR_FEGCRAFT_KNOWLEDGE')!='5' or env.get('VECTOR_FEGCRAFT_MOD_RECIPES_SHA256')!=recipe_sha or 'VECTOR_FEGCRAFT_PORTRAITS' in env:
        raise RuntimeError('PORTRAIT_BASE_MODE_OR_RECIPE_CHANGED')
    mounts={m['target']:m for m in service['volumes']}
    if len(mounts)!=len(service['volumes']) or '/inputs/advancements' in mounts:raise RuntimeError('PORTRAIT_DUPLICATE_OR_EXISTING_MOUNT')
    for target,name in (('/code',''),('/inputs/documentation.json','public-knowledge.json'),('/inputs/mod-recipes.json','mod-recipes.json'),('/inputs/knowledge-pack.json','knowledge-pack.json')):
        if target not in mounts or mounts[target].get('read_only') is not True:raise RuntimeError('PORTRAIT_READONLY_INPUT_REQUIRED')
        mounts[target]['source']=str(code/name) if name else str(code)
    if advancements is not None:
        if advancements not in ('/opt/fegcraft-updated/data/world/players/advancements','/opt/fegcraft-updated/data/world/advancements'):
            raise RuntimeError('PORTRAIT_ADVANCEMENT_SOURCE_INVALID')
        service['volumes'].append(dict(type='bind',source=advancements,target='/inputs/advancements',read_only=True,bind={'create_host_path':False}))
    env.update(VECTOR_FEGCRAFT_PORTRAITS='1',VECTOR_FEGCRAFT_ADVANCEMENTS='1' if advancements else '0')
    return value


def advancement_source(p):
    found=[]
    for directory in (Path('/opt/fegcraft-updated/data/world/players/advancements'),Path('/opt/fegcraft-updated/data/world/advancements')):
        p.safe(directory)
        if directory.exists():
            if not directory.is_dir():raise RuntimeError('PORTRAIT_ADVANCEMENT_DIRECTORY_INVALID')
            entries=list(directory.iterdir())
            if len(entries)>10000:raise RuntimeError('PORTRAIT_ADVANCEMENT_ENTRY_LIMIT')
            if any(re.fullmatch(r'[a-fA-F0-9-]{36}\.json',x.name) and x.is_file() and not x.is_symlink() for x in entries):found.append(str(directory))
    if len(found)>1:raise RuntimeError('PORTRAIT_AMBIGUOUS_ADVANCEMENT_DIRECTORIES')
    return found[0] if found else None


def verify_current(p,h,support,revision):
    pointer=json.loads(p.read(POINTER)); directory=Path(pointer['release']);p.safe(directory)
    if (pointer.get('revision')!=revision or directory.parent!=ROOT/'releases'
        or not re.fullmatch(r'vector-fegcraft-reviewed-help-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}',directory.name)):
        raise RuntimeError('PORTRAIT_POINTER_CHANGED')
    record=json.loads(p.read(directory/'deployment.json'))
    raw=p.read(p.INSTALL/'compose.json'); manifest_raw=p.read(p.INSTALL/'manifest.json'); manifest=json.loads(manifest_raw)
    previous=p.read(directory/'compose.before.json')
    if (record.get('status')!='deployed' or record.get('revision')!=revision or record.get('prior_revision')!=PREVIOUS
        or record.get('prior_release')!=str(PREVIOUS_RELEASE) or p.sha(previous)!=record['old_profile_sha']
        or p.sha(raw)!=record['new_profile_sha'] or p.sha(manifest_raw)!=record['new_manifest_sha']
        or manifest.get('backend_revision')!=revision or manifest.get('backend_release')!=str(directory)
        or manifest.get('compose_sha256')!=p.sha(raw) or p.read(directory/'compose.candidate.json')!=raw):
        raise RuntimeError('PORTRAIT_DEPLOYMENT_CHANGED')
    recipe_sha=p.sha(p.read(directory/'code/mod-recipes.json'))
    profile=json.loads(raw)
    if profile!=candidate(json.loads(previous),directory/'code',recipe_sha,record.get('advancements_source')): raise RuntimeError('PORTRAIT_PROFILE_CHANGED')
    support.check_runtime(support.SERVICE,profile['services']['assistant'],manifest['owner'])
    for name in FILES:
        if p.read(directory/'code'/name)!=p.source(revision,'services/fegcraft-assistant/'+name): raise RuntimeError('PORTRAIT_CODE_CHANGED')
    stage=json.loads(p.read(directory/'stage-result.json'))
    if not qualified(stage):
        raise RuntimeError('PORTRAIT_STAGE_REQUIRED')
    return directory


def stage(support,directory,profile,owner):
    suffix=secrets.token_hex(8);name='vector-companion-stage-'+suffix
    value=copy.deepcopy(profile); service=value['services'].pop('assistant');value['services'][name]=service
    state=directory/'stage-state';state.mkdir(mode=0o700)
    uid,gid=map(int,service['user'].split(':'));os.chown(state,uid,gid)
    for mount in service['volumes']:
        if mount['target']=='/state': mount['source']=str(state)
    fixture=directory/'synthetic-inputs';fixture.mkdir(mode=0o755);fixture.chmod(0o755)
    stats_dir=fixture/'stats';stats_dir.mkdir(mode=0o755);stats_dir.chmod(0o755)
    users=[]
    for n,normal,deep in ((1,10,20),(2,15,15),(3,0,5)):
        uid='00000000-0000-0000-0000-'+str(n).zfill(12); users.append(dict(uuid=uid,name='Example'+str(n)))
        support.atomic(stats_dir/(uid+'.json'),json.dumps({'stats':{'minecraft:custom':{'minecraft:mob_kills':1000 if n==1 else n*10,'minecraft:player_kills':200 if n==1 else 0,'minecraft:deaths':220 if n==2 else 5,'minecraft:play_time':n*72000,'minecraft:walk_one_cm':n*100000},'minecraft:mined':{
          'minecraft:diamond_ore':normal,'minecraft:deepslate_diamond_ore':deep},'minecraft:used':{'minecraft:bow':n*10,'minecraft:stone':n*1000}}}).encode(),0o644)
    support.atomic(fixture/'usercache.json',json.dumps(users).encode(),0o644)
    adv=fixture/'advancements';adv.mkdir(mode=0o755);adv.chmod(0o755)
    for user in users:
        support.atomic(adv/(user['uuid']+'.json'),json.dumps({'minecraft:adventure/sniper_duel':{'done':True,'criteria':{'event':'2026-10-19 00:00:00 +0000'}}}).encode(),0o644)
    for mount in service['volumes']:
        if mount['target']=='/inputs/advancements':mount['source']=str(adv)
        elif mount['target']=='/inputs/stats': mount['source']=str(stats_dir)
        elif mount['target']=='/inputs/usercache.json': mount['source']=str(fixture/'usercache.json')
    service['container_name']=name;service['restart']='no';service['labels'][support.LABEL]=suffix
    path=directory/'stage.json';support.atomic(path,(json.dumps(value,indent=2)+'\n').encode())
    try:
        support.run('docker','compose','-p',name,'-f',str(path),'config','--quiet')
        support.run('docker','compose','-p',name,'-f',str(path),'up','-d','--no-deps','--no-build','--pull','never',name,timeout=45)
        support.healthy(name,service,owner,require_docker=False)
        result=subprocess.run(['docker','exec',name,'python3','/code/rollout-probe.py'],capture_output=True,timeout=100)
        support.atomic(directory/'stage-probe.log',(result.stdout+result.stderr)[:32768])
        if result.returncode: raise RuntimeError('PORTRAIT_STAGE_FAILED_PRIVATE_REPORT_RETAINED')
        value=json.loads(result.stdout)
        if not qualified(value): raise RuntimeError('PORTRAIT_NATIVE_QUALITY_GATE_FAILED')
        return value
    finally: support.cleanup_stage(name,suffix)


def main():
    os.umask(0o077);sys.dont_write_bytecode=True
    revision=os.environ.get('VECTOR_FEGCRAFT_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision): raise RuntimeError('PORTRAIT_ROOT_AND_PIN_REQUIRED')
    raw=subprocess.check_output(['git','-C',str(REPO),'show',BASE+':scripts/deploy/prepare-fegcraft-chat-cutover.py'])
    ns={'__name__':'portrait_support','__file__':str(REPO/'scripts/deploy/prepare-fegcraft-chat-cutover.py')}
    exec(compile(raw,ns['__file__'],'exec'),ns);p=SimpleNamespace(**ns)
    h=p.load(p.HELPER,'scripts/diagnostics/fegcraft-admission-readiness.py')
    support=p.load(p.DEPLOYED,'scripts/deploy/release-fegcraft-reviewed-help.py')
    p.safe(ROOT/'.chat-release.lock')
    with (ROOT/'.chat-release.lock').open('rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        p.run('git','-C',str(REPO),'merge-base','--is-ancestor',revision,'origin/main')
        if len(sys.argv)==3 and sys.argv[1]=='--rollback':
            directory=Path(sys.argv[2])
            if json.loads(p.read(POINTER))!={'release':str(directory),'revision':revision}: raise RuntimeError('PORTRAIT_ROLLBACK_POINTER_CHANGED')
            support.rollback(directory,h);POINTER.unlink();return
        if sys.argv[1:]: raise RuntimeError('PORTRAIT_ARGUMENTS_INVALID')
        if POINTER.exists():
            verify_current(p,h,support,revision);print('Spielerporträts und Smalltalk bereits installiert und geprüft. Kein erneuter Modelltest oder Minecraft-Neustart.');return
        previous=p.load(PREVIOUS,'scripts/deploy/update-fegcraft-companion.py')
        if previous.verify_current(p,h,support,PREVIOUS)!=PREVIOUS_RELEASE: raise RuntimeError('PORTRAIT_PREVIOUS_RELEASE_CHANGED')
        restart=json.loads(p.read(ROOT/'fegcraft-addon-restart.json'))
        live=json.loads(p.run('docker','inspect','fegcraft-updated'))[0]
        if restart.get('status')!='verified' or restart.get('container')!=live['Id'] or restart.get('started_at')!=live['State']['StartedAt'] or restart.get('addon_sha256')!=p.sha(p.read(h.ADDON)):
            raise RuntimeError('PORTRAIT_CURRENT_ADDON_LOAD_NOT_VERIFIED')
        support.protected_live(h)
        before=h.snapshot();profile_raw=p.read(p.INSTALL/'compose.json');manifest_raw=p.read(p.INSTALL/'manifest.json')
        profile=json.loads(profile_raw);manifest=json.loads(manifest_raw)
        directory=ROOT/'releases'/('vector-fegcraft-reviewed-help-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3))
        p.safe(directory);directory.mkdir(mode=0o700);print('Spielerporträts, Smalltalk und Rückrollbelege:',directory,flush=True)
        code=directory/'code';code.mkdir(mode=0o755);code.chmod(0o755)
        for name in FILES:
            data=p.source(revision,'services/fegcraft-assistant/'+name)
            if name.endswith('.py'): ast.parse(data)
            support.atomic(code/name,data,0o644)
        previous_recipe=PREVIOUS_RELEASE/'code/mod-recipes.json'
        recipe_raw=p.read(previous_recipe); support.atomic(code/'mod-recipes.json',recipe_raw,0o644)
        old_code=next(Path(m['source']) for m in profile['services']['assistant']['volumes'] if m['target']=='/code')
        for name in ('health.py','read-probe.py'): support.atomic(code/name,p.read(old_code/name),0o644)
        support.atomic(code/'rollout-probe.py',p.source(revision,'tests/fegcraft-portraits-smoke.py'),0o644)
        advancements=advancement_source(p)
        value=candidate(profile,code,p.sha(recipe_raw),advancements)
        print('Eine lokale Smalltalk-Antwort plus schnelle synthetische Spielerporträts über signiertes HTTP. Minecraft bleibt online.',flush=True)
        result=stage(support,directory,value,manifest['owner'])
        support.atomic(directory/'stage-result.json',(json.dumps(result,indent=2)+'\n').encode())
        if h.snapshot()!=before or p.read(p.INSTALL/'compose.json')!=profile_raw or p.read(p.INSTALL/'manifest.json')!=manifest_raw:
            raise RuntimeError('PORTRAIT_BASELINE_CHANGED_DURING_STAGE')
        new_profile=(json.dumps(value,indent=2)+'\n').encode();next_manifest=copy.deepcopy(manifest)
        next_manifest.update(compose_sha256=p.sha(new_profile),backend_revision=revision,backend_release=str(directory))
        new_manifest=(json.dumps(next_manifest,indent=2)+'\n').encode()
        record=dict(status='prepared',revision=revision,prior_revision=PREVIOUS,prior_release=str(PREVIOUS_RELEASE),advancements_source=advancements,protected=support.protected(before),
          old_profile_sha=p.sha(profile_raw),old_manifest_sha=p.sha(manifest_raw),new_profile_sha=p.sha(new_profile),new_manifest_sha=p.sha(new_manifest))
        for name,data in (('compose.before.json',profile_raw),('manifest.before.json',manifest_raw),('compose.candidate.json',new_profile),
          ('deployment.json',(json.dumps(record,indent=2)+'\n').encode()),('release.py',Path(__file__).read_bytes())): support.atomic(directory/name,data)
        support.atomic(directory/'rollback.sh',('#!/bin/bash\nset -Eeuo pipefail\nexport VECTOR_FEGCRAFT_REV='+revision+'\nexec python3 '+shlex.quote(str(directory/'release.py'))+' --rollback '+shlex.quote(str(directory))+'\n').encode(),0o700)
        p.run('docker','compose','-p',support.SERVICE,'-f',str(directory/'compose.candidate.json'),'config','--quiet')
        try:
            support.atomic(p.INSTALL/'compose.json',new_profile);support.atomic(p.INSTALL/'manifest.json',new_manifest);support.compose()
            coverage=support.healthy(support.SERVICE,value['services']['assistant'],manifest['owner'])
            if support.protected_live(h)!=record['protected']: raise RuntimeError('PORTRAIT_OTHER_SERVICE_CHANGED')
            record['status']='deployed';support.atomic(directory/'deployment.json',(json.dumps(record,indent=2)+'\n').encode())
            support.atomic(POINTER,(json.dumps({'release':str(directory),'revision':revision})+'\n').encode());verify_current(p,h,support,revision)
        except BaseException:
            support.rollback(directory,h)
            if POINTER.exists() and json.loads(p.read(POINTER))=={'release':str(directory),'revision':revision}: POINTER.unlink()
            raise
        print(json.dumps(dict(deployed=True,only_assistant_recreated=True,minecraft_container_unchanged=True,
              knowledge_mode='grounded-fact-composition-with-character',fresh_player_portraits=True,advancements_available=bool(advancements),
              qualification=result,model_calls=1,cloud_calls=0,messages_sent=0,
              pending_greeting_addon_retained=True,welcome_replayed=False,
              rollback=str(directory/'rollback.sh')),indent=2))


if __name__=='__main__':
    try: main()
    except BaseException as exc:
        value=str(exc);code=value if type(exc) in (RuntimeError,ValueError) and re.fullmatch('[A-Z][A-Z0-9_]{2,100}',value) else type(exc).__name__
        print('ERROR: '+code+'. Kein Minecraft-Neustart durch dieses Skript.',file=sys.stderr);raise SystemExit(1)
