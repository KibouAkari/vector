#!/usr/bin/env python3
"""Repair observed chat intents without restarting Minecraft; stage new addon for a later regular restart."""
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
PREVIOUS='9368db9d557246a45bdc590e78dd16bfd6762671'
PREVIOUS_RELEASE=ROOT/'releases/vector-fegcraft-reviewed-help-20261018T175556Z-3ec4f6'
POINTER=ROOT/'fegcraft-intents.json'
IDENTITY_REV='dd407020ba806e0560a41bb014b8022708e8fd3d'
FILES=('runtime.py','server.py','stats.py','policy.py','recipes.py','knowledge.py','documentation.py','public-knowledge.json','modrecipes.py')


def candidate(profile,code,recipe_sha):
    value=copy.deepcopy(profile); service=value['services']['assistant']
    if service['environment'].get('VECTOR_FEGCRAFT_KNOWLEDGE')!='4' or service['environment'].get('VECTOR_FEGCRAFT_MOD_RECIPES_SHA256')!=recipe_sha:
        raise RuntimeError('INTENT_BASE_MODE_OR_RECIPE_CHANGED')
    mounts={m['target']:m for m in service['volumes']}
    if len(mounts)!=len(service['volumes']): raise RuntimeError('INTENT_DUPLICATE_MOUNTS')
    for target,name in (('/code',''),('/inputs/documentation.json','public-knowledge.json'),('/inputs/mod-recipes.json','mod-recipes.json')):
        if target not in mounts or mounts[target].get('read_only') is not True: raise RuntimeError('INTENT_READONLY_INPUT_REQUIRED')
        mounts[target]['source']=str(code/name) if name else str(code)
    return value


def verify_current(p,h,support,revision,*,check_addon=True):
    pointer=json.loads(p.read(POINTER)); directory=Path(pointer['release']);p.safe(directory)
    if (pointer.get('revision')!=revision or directory.parent!=ROOT/'releases'
        or not re.fullmatch(r'vector-fegcraft-reviewed-help-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}',directory.name)):
        raise RuntimeError('INTENT_POINTER_CHANGED')
    record=json.loads(p.read(directory/'deployment.json'))
    raw=p.read(p.INSTALL/'compose.json'); manifest_raw=p.read(p.INSTALL/'manifest.json'); manifest=json.loads(manifest_raw)
    previous=p.read(directory/'compose.before.json')
    if (record.get('status')!='deployed' or record.get('revision')!=revision or record.get('prior_revision')!=PREVIOUS
        or record.get('prior_release')!=str(PREVIOUS_RELEASE) or p.sha(previous)!=record['old_profile_sha']
        or p.sha(raw)!=record['new_profile_sha'] or p.sha(manifest_raw)!=record['new_manifest_sha']
        or manifest.get('backend_revision')!=revision or manifest.get('backend_release')!=str(directory)
        or manifest.get('compose_sha256')!=p.sha(raw) or p.read(directory/'compose.candidate.json')!=raw):
        raise RuntimeError('INTENT_DEPLOYMENT_CHANGED')
    recipe_sha=p.sha(p.read(directory/'code/mod-recipes.json'))
    profile=json.loads(raw)
    if profile!=candidate(json.loads(previous),directory/'code',recipe_sha): raise RuntimeError('INTENT_PROFILE_CHANGED')
    support.check_runtime(support.SERVICE,profile['services']['assistant'],manifest['owner'])
    for name in FILES:
        if p.read(directory/'code'/name)!=p.source(revision,'services/fegcraft-assistant/'+name): raise RuntimeError('INTENT_CODE_CHANGED')
    stage=json.loads(p.read(directory/'stage-result.json'))
    if stage.get('passed') is not True or stage.get('model_calls')!=0 or stage.get('cloud_calls')!=0:
        raise RuntimeError('INTENT_STAGE_REQUIRED')
    if check_addon and record.get('addon_staged') is not True:
        raise RuntimeError('INTENT_ADDON_STAGING_INCOMPLETE_REQUIRES_REVIEW')
    if check_addon:
        addon=json.loads(p.read(directory/'addon-plan.json'))
        if addon.get('path')!=str(h.ADDON) or p.sha(p.read(h.ADDON))!=addon.get('after_sha'):
            raise RuntimeError('INTENT_STAGED_ADDON_CHANGED')
    return directory


def stage(support,directory,profile,owner):
    suffix=secrets.token_hex(8);name='vector-intent-stage-'+suffix
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
        support.atomic(stats_dir/(uid+'.json'),json.dumps({'stats':{'minecraft:custom':{},'minecraft:mined':{
          'minecraft:diamond_ore':normal,'minecraft:deepslate_diamond_ore':deep}}}).encode(),0o644)
    support.atomic(fixture/'usercache.json',json.dumps(users).encode(),0o644)
    for mount in service['volumes']:
        if mount['target']=='/inputs/stats': mount['source']=str(stats_dir)
        elif mount['target']=='/inputs/usercache.json': mount['source']=str(fixture/'usercache.json')
    service['container_name']=name;service['restart']='no';service['labels'][support.LABEL]=suffix
    path=directory/'stage.json';support.atomic(path,(json.dumps(value,indent=2)+'\n').encode())
    try:
        support.run('docker','compose','-p',name,'-f',str(path),'config','--quiet')
        support.run('docker','compose','-p',name,'-f',str(path),'up','-d','--no-deps','--no-build','--pull','never',name,timeout=45)
        support.healthy(name,service,owner,require_docker=False)
        result=subprocess.run(['docker','exec',name,'python3','/code/rollout-probe.py'],capture_output=True,timeout=30)
        support.atomic(directory/'stage-probe.log',(result.stdout+result.stderr)[:32768])
        if result.returncode: raise RuntimeError('INTENT_STAGE_FAILED_PRIVATE_REPORT_RETAINED')
        value=json.loads(result.stdout)
        if value.get('passed') is not True or value.get('model_calls')!=0: raise RuntimeError('INTENT_ZERO_MODEL_GATE_FAILED')
        return value
    finally: support.cleanup_stage(name,suffix)


def completed_identity(p,h,support,identity):
    pointer=json.loads(p.read(identity.POINTER)); directory=Path(pointer['release']);p.safe(directory)
    if (pointer.get('revision')!=IDENTITY_REV or directory.parent!=ROOT/'releases'
        or not re.fullmatch(r'vector-fegcraft-chat-identity-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}',directory.name)):
        raise RuntimeError('INTENT_COMPLETED_IDENTITY_REQUIRED')
    plan=json.loads(p.read(directory/'plan.json'))
    if plan.get('status')!='deployed_pending_client_test' or plan.get('revision')!=IDENTITY_REV:
        raise RuntimeError('INTENT_COMPLETED_IDENTITY_REQUIRED')
    old=p.load(identity.BASE,'scripts/deploy/release-fegcraft-dialogue.py')
    identity.check_files(old,directory,plan);identity.check_protected(p,h,old,plan)
    game=json.loads(p.run('docker','inspect','fegcraft-updated'))[0]
    if (not game['State']['Running'] or game['State'].get('Health',{}).get('Status')!='healthy'
        or game['Image']!=plan['preservation']['image'] or p.sha(p.read(h.ADDON))!=identity.ADDON_SHA):
        raise RuntimeError('INTENT_GAME_OR_ADDON_CHANGED')
    return dict(container=game['Id'],started_at=game['State']['StartedAt'],identity_release=str(directory))


def prepare_addon(p,support,directory,revision):
    """Compile cached, pinned installed API offline; no game interaction or downloads."""
    import hashlib,hmac,zipfile
    compiler=p.load(IDENTITY_REV,'scripts/deploy/evaluate-fegcraft-bridge.py')
    image=compiler.inspect('image',compiler.JDK)
    if not image or image.get('Architecture')!='amd64' or image.get('Os')!='linux':
        raise RuntimeError('INTENT_CACHED_JDK_REQUIRED')
    p.safe(compiler.INTEGRATION)
    if compiler.INTEGRATION.stat().st_size>24_000_000: raise RuntimeError('INTENT_INTEGRATION_LIMIT')
    if p.sha(compiler.INTEGRATION.read_bytes())!=compiler.INTEGRATION_SHA:
        raise RuntimeError('INTENT_INSTALLED_API_CHANGED')
    with zipfile.ZipFile(compiler.INTEGRATION) as archive:
        item=archive.getinfo('META-INF/jars/dcintegration.common-3.2.1.jar')
        if item.file_size>30_000_000: raise RuntimeError('INTENT_API_LIMIT')
        common=archive.read(item)
    if hashlib.sha256(common).hexdigest()!=compiler.COMMON_DIGEST: raise RuntimeError('INTENT_COMMON_API_CHANGED')
    source=directory/'addon-source';source.mkdir(mode=0o755);source.chmod(0o755)
    files=('integrations/fegcraft-addon/src/main/java/com/kibouakari/vector/VectorAddon.java',
           'integrations/fegcraft-addon/src/main/resources/DiscordIntegrationAddon.toml',
           'tests/VectorAddonTest.java','scripts/build-fegcraft-addon.py')
    for name in files:
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        for parent in target.parents:
            if parent==source: break
            parent.chmod(0o755)
        support.atomic(target,p.source(revision,name),0o644)
    inputs=directory/'addon-inputs';inputs.mkdir(mode=0o755);inputs.chmod(0o755)
    support.atomic(inputs/'common.jar',common,0o444)
    build=directory/'addon-build';build.mkdir(mode=0o755);build.chmod(0o755);os.chown(build,65534,65534)
    owner=secrets.token_hex(8);names=[]
    try:
        name='vector-intent-compile-'+owner;names.append(name)
        args=compiler.container_args(name,owner,'none','768m')+compiler.mount(source,'/source')+compiler.mount(inputs,'/inputs')+compiler.mount(build,'/build',True)
        args+=['--pull','never','--entrypoint','javac',compiler.JDK,'-J-Xmx256m','-J-XX:ActiveProcessorCount=2','--release','17','-g:none','-encoding','UTF-8','-classpath','/inputs/common.jar','-d','/build/classes',
               '/source/integrations/fegcraft-addon/src/main/java/com/kibouakari/vector/VectorAddon.java','/source/tests/VectorAddonTest.java']
        compiler.run(args,timeout=120,log=directory/'addon-compile.log')
        name='vector-intent-unit-'+owner;names.append(name)
        args=compiler.container_args(name,owner,'none')+compiler.mount(inputs,'/inputs')+compiler.mount(build,'/build')
        signature=hmac.new(bytes.fromhex('ab'*32),b'1000000000\n{}',hashlib.sha256).hexdigest()
        args+=['--pull','never','--entrypoint','java',compiler.JDK,'-Xmx192m','-classpath','/build/classes:/inputs/common.jar','com.kibouakari.vector.VectorAddonTest',signature]
        compiler.run(args,timeout=45,log=directory/'addon-unit.log')
        builder=compiler.load_module(source/'scripts/build-fegcraft-addon.py','intent_addon_builder')
        artifact=directory/'vector-minecraft-0.1.0.jar';builder.package_addon(build/'classes',artifact);artifact.chmod(0o600)
        support.atomic(directory/'addon-proof.json',(json.dumps(dict(revision=revision,sha256=p.sha(p.read(artifact)),
            installed_common_api_sha256=compiler.COMMON_DIGEST,compiler_image=image['Id'],offline_unit_passed=True,model_calls=0,messages_sent=0))+'\n').encode())
    finally:
        for name in names: compiler.remove_owned('container',name,owner)


def addon_guard(p,h,support,directory,record,*,before=False):
    addon=json.loads(p.read(directory/'addon-plan.json'))
    if addon['path']!=str(h.ADDON): raise RuntimeError('INTENT_ADDON_PATH_CHANGED')
    game=json.loads(p.run('docker','inspect','fegcraft-updated'))[0]
    if game['Id']!=addon['container'] or game['State']['StartedAt']!=addon['started_at']:
        raise RuntimeError('INTENT_GAME_RESTART_REQUIRES_REVIEW')
    expected=addon['before_sha'] if before else addon['after_sha']
    if p.sha(p.read(h.ADDON))!=expected: raise RuntimeError('INTENT_ADDON_LATER_EDIT_PRESERVED')
    return addon


def stage_addon(p,h,support,identity,directory,record,game):
    if support.protected_live(h)!=record['protected']: raise RuntimeError('INTENT_PROTECTED_CHANGED_BEFORE_ADDON')
    artifact=directory/'vector-minecraft-0.1.0.jar';proof=json.loads(p.read(directory/'addon-proof.json'))
    if proof.get('offline_unit_passed') is not True or proof['sha256']!=p.sha(p.read(artifact)):
        raise RuntimeError('INTENT_ADDON_PROOF_CHANGED')
    meta=h.ADDON.stat();raw=p.read(h.ADDON);old=p.load(identity.BASE,'scripts/deploy/release-fegcraft-dialogue.py')
    addon=dict(game,path=str(h.ADDON),before_sha=p.sha(raw),after_sha=proof['sha256'],uid=meta.st_uid,gid=meta.st_gid,mode=meta.st_mode&0o777)
    support.atomic(directory/'addon.before.jar',raw)
    support.atomic(directory/'addon-plan.json',(json.dumps(addon,indent=2)+'\n').encode())
    addon_guard(p,h,support,directory,record,before=True)
    expected=dict(record['protected']);expected[str(h.ADDON)]=p.sha(json.dumps(proof['sha256'],sort_keys=True).encode())
    record['protected_before_addon']=record['protected'];record['protected']=expected
    record['addon_staged']=False
    support.atomic(directory/'deployment.json',(json.dumps(record,indent=2)+'\n').encode())
    try:
        old.atomic(h.ADDON,p.read(artifact),meta.st_uid,meta.st_gid,meta.st_mode&0o777)
        addon_guard(p,h,support,directory,record)
        if support.protected_live(h)!=expected: raise RuntimeError('INTENT_PROTECTED_CHANGED_DURING_ADDON')
        record['addon_staged']=True
        support.atomic(directory/'deployment.json',(json.dumps(record,indent=2)+'\n').encode())
    except BaseException:
        if p.sha(p.read(h.ADDON))==proof['sha256']:
            old.atomic(h.ADDON,raw,meta.st_uid,meta.st_gid,meta.st_mode&0o777)
        record['protected']=record['protected_before_addon']
        support.atomic(directory/'deployment.json',(json.dumps(record,indent=2)+'\n').encode())
        raise


def rollback(p,h,support,directory):
    p.safe(directory)
    if directory.parent!=ROOT/'releases' or not re.fullmatch(r'vector-fegcraft-reviewed-help-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}',directory.name):
        raise RuntimeError('INTENT_ROLLBACK_PATH')
    record=json.loads(p.read(directory/'deployment.json'))
    if record.get('revision')!=os.environ.get('VECTOR_FEGCRAFT_REV'):
        raise RuntimeError('INTENT_ROLLBACK_REVISION')
    if record.get('addon_staged'):
        addon=addon_guard(p,h,support,directory,record)
        if support.protected_live(h)!=record['protected']: raise RuntimeError('INTENT_ROLLBACK_PROTECTED_CHANGED')
        raw=p.read(directory/'addon.before.jar')
        if p.sha(raw)!=addon['before_sha']: raise RuntimeError('INTENT_ADDON_BACKUP_CHANGED')
        identity=p.load(IDENTITY_REV,'scripts/deploy/install-fegcraft-chat-identity.py')
        old=p.load(identity.BASE,'scripts/deploy/release-fegcraft-dialogue.py')
        old.atomic(h.ADDON,raw,addon['uid'],addon['gid'],addon['mode'])
        record['protected']=record['protected_before_addon'];record['addon_staged']=False
        support.atomic(directory/'deployment.json',(json.dumps(record,indent=2)+'\n').encode())
    support.rollback(directory,h);POINTER.unlink()



def main():
    os.umask(0o077);sys.dont_write_bytecode=True
    revision=os.environ.get('VECTOR_FEGCRAFT_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision): raise RuntimeError('INTENT_ROOT_AND_PIN_REQUIRED')
    raw=subprocess.check_output(['git','-C',str(REPO),'show',BASE+':scripts/deploy/prepare-fegcraft-chat-cutover.py'])
    ns={'__name__':'intent_support','__file__':str(REPO/'scripts/deploy/prepare-fegcraft-chat-cutover.py')}
    exec(compile(raw,ns['__file__'],'exec'),ns);p=SimpleNamespace(**ns)
    h=p.load(p.HELPER,'scripts/diagnostics/fegcraft-admission-readiness.py')
    support=p.load(p.DEPLOYED,'scripts/deploy/release-fegcraft-reviewed-help.py')
    p.safe(ROOT/'.chat-release.lock')
    with (ROOT/'.chat-release.lock').open('rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        p.run('git','-C',str(REPO),'merge-base','--is-ancestor',revision,'origin/main')
        if len(sys.argv)==3 and sys.argv[1]=='--rollback':
            directory=Path(sys.argv[2])
            if json.loads(p.read(POINTER))!={'release':str(directory),'revision':revision}: raise RuntimeError('INTENT_ROLLBACK_POINTER_CHANGED')
            rollback(p,h,support,directory);return
        if sys.argv[1:]: raise RuntimeError('INTENT_ARGUMENTS_INVALID')
        if POINTER.exists():
            verify_current(p,h,support,revision);print('Antwortverbesserungen bereits installiert und geprüft. Minecraft wird nicht neu gestartet.');return
        previous=p.load(PREVIOUS,'scripts/deploy/update-fegcraft-mod-context.py')
        if previous.verify_current(p,h,support,PREVIOUS)!=PREVIOUS_RELEASE: raise RuntimeError('INTENT_PREVIOUS_RELEASE_CHANGED')
        identity=p.load(IDENTITY_REV,'scripts/deploy/install-fegcraft-chat-identity.py')
        identity_plan=completed_identity(p,h,support,identity)
        support.protected_live(h)
        before=h.snapshot();profile_raw=p.read(p.INSTALL/'compose.json');manifest_raw=p.read(p.INSTALL/'manifest.json')
        profile=json.loads(profile_raw);manifest=json.loads(manifest_raw)
        directory=ROOT/'releases'/('vector-fegcraft-reviewed-help-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3))
        p.safe(directory);directory.mkdir(mode=0o700);print('Antwortverbesserungen und Rückrollbelege:',directory,flush=True)
        code=directory/'code';code.mkdir(mode=0o755);code.chmod(0o755)
        for name in FILES:
            data=p.source(revision,'services/fegcraft-assistant/'+name)
            if name.endswith('.py'): ast.parse(data)
            support.atomic(code/name,data,0o644)
        previous_recipe=PREVIOUS_RELEASE/'code/mod-recipes.json'
        recipe_raw=p.read(previous_recipe); support.atomic(code/'mod-recipes.json',recipe_raw,0o644)
        old_code=next(Path(m['source']) for m in profile['services']['assistant']['volumes'] if m['target']=='/code')
        for name in ('health.py','read-probe.py'): support.atomic(code/name,p.read(old_code/name),0o644)
        support.atomic(code/'rollout-probe.py',p.source(revision,'tests/fegcraft-intent-smoke.py'),0o644)
        value=candidate(profile,code,p.sha(recipe_raw))
        print('Kurze signierte HTTP-Prüfung mit isoliertem Zustand. Keine Modellaufrufe, Minecraft bleibt online.',flush=True)
        result=stage(support,directory,value,manifest['owner'])
        support.atomic(directory/'stage-result.json',(json.dumps(result,indent=2)+'\n').encode())
        if h.snapshot()!=before or p.read(p.INSTALL/'compose.json')!=profile_raw or p.read(p.INSTALL/'manifest.json')!=manifest_raw:
            raise RuntimeError('INTENT_BASELINE_CHANGED_DURING_STAGE')
        new_profile=(json.dumps(value,indent=2)+'\n').encode();next_manifest=copy.deepcopy(manifest)
        next_manifest.update(compose_sha256=p.sha(new_profile),backend_revision=revision,backend_release=str(directory))
        new_manifest=(json.dumps(next_manifest,indent=2)+'\n').encode()
        record=dict(status='prepared',revision=revision,prior_revision=PREVIOUS,prior_release=str(PREVIOUS_RELEASE),protected=support.protected(before),
          old_profile_sha=p.sha(profile_raw),old_manifest_sha=p.sha(manifest_raw),new_profile_sha=p.sha(new_profile),new_manifest_sha=p.sha(new_manifest))
        for name,data in (('compose.before.json',profile_raw),('manifest.before.json',manifest_raw),('compose.candidate.json',new_profile),
          ('deployment.json',(json.dumps(record,indent=2)+'\n').encode()),('release.py',Path(__file__).read_bytes())): support.atomic(directory/name,data)
        support.atomic(directory/'rollback.sh',('#!/bin/bash\nset -Eeuo pipefail\nexport VECTOR_FEGCRAFT_REV='+revision+'\nexec python3 '+shlex.quote(str(directory/'release.py'))+' --rollback '+shlex.quote(str(directory))+'\n').encode(),0o700)
        prepare_addon(p,support,directory,revision)
        p.run('docker','compose','-p',support.SERVICE,'-f',str(directory/'compose.candidate.json'),'config','--quiet')
        try:
            support.atomic(p.INSTALL/'compose.json',new_profile);support.atomic(p.INSTALL/'manifest.json',new_manifest);support.compose()
            coverage=support.healthy(support.SERVICE,value['services']['assistant'],manifest['owner'])
            if support.protected_live(h)!=record['protected']: raise RuntimeError('INTENT_OTHER_SERVICE_CHANGED')
            record['status']='deployed';support.atomic(directory/'deployment.json',(json.dumps(record,indent=2)+'\n').encode())
            support.atomic(POINTER,(json.dumps({'release':str(directory),'revision':revision})+'\n').encode());verify_current(p,h,support,revision,check_addon=False)
        except BaseException:
            support.rollback(directory,h)
            if POINTER.exists() and json.loads(p.read(POINTER))=={'release':str(directory),'revision':revision}: POINTER.unlink()
            raise
        # Backend is healthy. Staging only changes the owned JAR on disk; the
        # running game keeps its loaded classes until its next regular restart.
        stage_addon(p,h,support,identity,directory,record,identity_plan)
        verify_current(p,h,support,revision)
        print(json.dumps(dict(deployed=True,only_assistant_recreated=True,minecraft_container_unchanged=True,
              statistics_intents_fixed=True,qualification=result,model_calls=0,cloud_calls=0,messages_sent=0,
              addon_staged=True,new_greetings_active_after_next_regular_restart=True,
              welcome_replayed=False,rollback=str(directory/'rollback.sh')),indent=2))


if __name__=='__main__':
    try: main()
    except BaseException as exc:
        value=str(exc);code=value if type(exc) in (RuntimeError,ValueError) and re.fullmatch('[A-Z][A-Z0-9_]{2,100}',value) else type(exc).__name__
        print('ERROR: '+code+'. Kein Minecraft-Neustart durch dieses Skript.',file=sys.stderr);raise SystemExit(1)
