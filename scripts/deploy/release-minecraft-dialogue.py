#!/usr/bin/env python3
"""Guarded opt-in of a captured local dialogue candidate; no Minecraft action."""
import argparse
import ast
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import uuid
from zoneinfo import ZoneInfo


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def constant(source,name):
    nodes=[node.value for node in ast.parse(source).body if isinstance(node,ast.Assign)
           and any(isinstance(target,ast.Name) and target.id==name for target in node.targets)]
    if len(nodes)!=1:raise RuntimeError('UNIQUE_MODEL_CONTRACT_REQUIRED')
    return ast.literal_eval(nodes[0])


def capsule(guard,transport,path,pin):
    manifest=json.loads(transport.read_private(guard,path/'manifest.json'))
    result=json.loads(transport.read_private(guard,path/'result.json'))
    if guard.digest(guard.canonical(manifest))!=pin or result.get('manifest_sha256')!=pin:
        raise RuntimeError('TRANSPORT_MANIFEST_PIN_MISMATCH')
    for key in ('transport_qualified','native_evidence_retained','service_bindings_retained',
                'temporary_container_cleanup_verified','production_unchanged'):
        if result.get(key) is not True:raise RuntimeError('COMPLETE_TRANSPORT_EVIDENCE_REQUIRED')
    if result.get('production_activated') is not False or any(result.get(k)!=0 for k in ('model_calls','cloud_calls','messages_sent')):
        raise RuntimeError('ISOLATED_TRANSPORT_EVIDENCE_REQUIRED')
    code=guard.checked_path(str(path/'code'),directory=True)
    if guard.tree_files(code)!=manifest['candidate_sha256']:raise RuntimeError('TRANSPORT_CODE_CHANGED')
    if guard.digest((path/'transport.test.py').read_bytes())!=manifest['transport_test_sha256']:
        raise RuntimeError('TRANSPORT_TEST_CHANGED')
    transport.verify_native(guard,guard.checked_path(manifest['native_report'],directory=True),manifest['native_manifest_sha256'])
    return manifest,code


def profile_for_dialogue(guard,transport,profile,service,code,timezone,*,expected_mode='5'):
    ZoneInfo(timezone)
    _,bindings=transport.service_bindings((code/'server.py').read_text())
    if not {'KNOWLEDGE','TIMEZONE'}<=set(bindings):raise RuntimeError('BOUND_DIALOGUE_ENV_REQUIRED')
    mode=bindings['KNOWLEDGE'][0].value;zone=bindings['TIMEZONE'][0].value
    environment=profile['services'][service].get('environment')
    if not isinstance(environment,dict) or environment.get(mode)!=expected_mode:
        raise RuntimeError('CONFIRMED_REVIEWED_MODE_REQUIRED')
    candidate=guard.changed_profile(profile,service,code)
    candidate['services'][service]['environment'].update({mode:'6',zone:timezone})
    return candidate


def previous_release(guard,transport,path,captured,pin):
    """Use an immutable successful mode6 release as the next baseline."""
    record=json.loads(transport.read_private(guard,path/'record.json'))
    result=json.loads(transport.read_private(guard,path/'result.json'))
    for key in ('deployed','only_assistant_recreated','other_services_unchanged','native_model_contract_retained'):
        if result.get(key) is not True:raise RuntimeError('SUCCESSFUL_DIALOGUE_RELEASE_REQUIRED')
    if (result.get('game_restart') is not False or result.get('knowledge_mode')!='grounded-conversation'
            or any(result.get(k)!=0 for k in ('model_calls','cloud_calls','messages_sent'))
            or result.get('release')!=str(path)):
        raise RuntimeError('SUCCESSFUL_DIALOGUE_RELEASE_REQUIRED')
    if record.get('transport_capsule')!=str(captured) or record.get('transport_manifest_sha256')!=pin:
        raise RuntimeError('PREVIOUS_RELEASE_CAPSULE_MISMATCH')
    if not isinstance(record.get('deployed_identity'),list) or len(record['deployed_identity'])!=3:
        raise RuntimeError('DEPLOYED_GENERATION_REQUIRED')
    raw=transport.read_private(guard,path/'compose.candidate.json')
    if guard.digest(raw)!=record['candidate_compose_sha256']:
        raise RuntimeError('PREVIOUS_RELEASE_PROFILE_CHANGED')
    code=guard.checked_path(record['candidate_code'],directory=True)
    if code!=path/'code' or guard.tree_files(code)!=record['candidate_files']:
        raise RuntimeError('PREVIOUS_RELEASE_CODE_CHANGED')
    return guard.read_config(path/'operator.json'),record,raw


def activate(guard,config,release,record,candidate_raw,original):
    """Only replace this service's profile; reuse the immutable rollback guard."""
    active=Path(config['compose'])
    try:
        guard.replace_atomic(active,candidate_raw)
        guard.recreate(config)
        print('Warte auf die Gesundheitsprüfung des Assistenten ...',flush=True)
        guard.await_health(config,{name:tuple(value) for name,value in record['other_containers'].items()},Path(record['candidate_code']))
        actual=guard.compose(config,active)
        if active.read_bytes()!=candidate_raw or guard.digest(guard.canonical(actual))!=record['candidate_profile_sha256']:
            raise RuntimeError('DEPLOYED_PROFILE_CHANGED')
        live=dict(config)
        live.update(expected_runtime_sha256=record['candidate_files']['runtime.py'],
            expected_compose_sha256=record['candidate_compose_sha256'],
            expected_profile_sha256=record['candidate_profile_sha256'])
        rows=guard.inventory();guard.validate_live(live,rows,actual)
        if guard.others(rows,config['container'])!={name:tuple(value) for name,value in record['other_containers'].items()}:
            raise RuntimeError('UNRELATED_CONTAINERS_CHANGED')
        if guard.tree_files(Path(record['candidate_code']))!=record['candidate_files']:
            raise RuntimeError('DEPLOYED_CODE_CHANGED')
        record['deployed_identity']=guard.identity(rows[config['container']])
        guard.replace_atomic(release/'record.json',guard.canonical(record))
    except BaseException:
        # Interrupts cannot interrupt the recovery itself. Its existing progress
        # marker supports a guarded resume after a process/host interruption.
        signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM})
        try:
            if active.read_bytes()==candidate_raw:
                guard.rollback(release,allow_missing=True)
            elif active.read_bytes()!=original:
                raise RuntimeError('ROLLBACK_PROFILE_DRIFT')
        except BaseException as error:
            raise RuntimeError('AUTOMATIC_ROLLBACK_FAILED; private release: '+str(release)) from error
        finally:signal.pthread_sigmask(signal.SIG_UNBLOCK,{signal.SIGINT,signal.SIGTERM})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guard-helper',type=Path,required=True)
    parser.add_argument('--transport-helper',type=Path)
    parser.add_argument('--capsule',type=Path)
    parser.add_argument('--expected-capsule-manifest')
    parser.add_argument('--source-root',type=Path)
    parser.add_argument('--previous-release',type=Path)
    parser.add_argument('--release-root',type=Path,required=True)
    parser.add_argument('--lock-file',type=Path,required=True)
    parser.add_argument('--timezone',default='UTC')
    parser.add_argument('--activate',action='store_true')
    parser.add_argument('--rollback',type=Path)
    args=parser.parse_args();sys.dont_write_bytecode=True;os.umask(0o077)
    guard=module(args.guard_helper,'dialogue_release_guard')
    guard.checked_path(str(args.release_root),directory=True);guard.checked_path(str(args.lock_file))
    descriptor=os.open(args.lock_file,os.O_WRONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    meta=os.fstat(descriptor)
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid!=os.geteuid():
        os.close(descriptor);raise RuntimeError('EXISTING_OWNED_RELEASE_LOCK_REQUIRED')
    with os.fdopen(descriptor,'a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.rollback:
            guard.rollback(args.rollback);return
        if any(value is None for value in (args.transport_helper,args.capsule,args.expected_capsule_manifest,args.source_root)):
            raise RuntimeError('PINNED_CAPSULE_AND_SOURCE_REQUIRED')
        transport=module(args.transport_helper,'dialogue_transport_guard')
        captured=guard.checked_path(str(args.capsule),directory=True)
        proof,captured_code=capsule(guard,transport,captured,args.expected_capsule_manifest)
        if args.previous_release:
            previous=guard.checked_path(str(args.previous_release),directory=True)
            config,baseline,confirmed_profile=previous_release(guard,transport,previous,captured,args.expected_capsule_manifest)
            confirmed_identity=baseline['deployed_identity']
        else:
            config=guard.read_config(captured/'operator.json')
            baseline=json.loads(transport.read_private(guard,captured/'baseline.record.json'))
            confirmed_profile=transport.read_private(guard,captured/'baseline.compose.json')
            confirmed_identity=proof['container_identity']
        active=guard.checked_path(config['compose']);original=active.read_bytes()
        if original!=confirmed_profile:
            raise RuntimeError('CONFIRMED_PROFILE_CHANGED')
        before=guard.inventory();row=before[config['container']]
        if list(guard.identity(row))!=confirmed_identity:
            raise RuntimeError('CONFIRMED_ASSISTANT_GENERATION_CHANGED')
        profile=guard.compose(config,active);old_code=guard.code_source(profile,config['service'])
        original_files=guard.tree_files(old_code)
        if str(old_code)!=baseline['candidate_code'] or original_files!=baseline['candidate_files']:
            raise RuntimeError('CONFIRMED_CODE_CHANGED')
        config.pop('expected_portraits_sha256',None)
        config.update(expected_runtime_sha256=original_files['runtime.py'],
            expected_compose_sha256=guard.digest(original),expected_profile_sha256=guard.digest(guard.canonical(profile)))
        guard.validate_live(config,before,profile)
        if row['Config'].get('User','').split(':',1)[0] in ('','0','root'):
            raise RuntimeError('UNPRIVILEGED_ASSISTANT_REQUIRED')
        release=args.release_root/('minecraft-dialogue-release-'+uuid.uuid4().hex);release.mkdir(mode=0o700)
        print('Release und Rückrollbelege: '+str(release),flush=True)
        guard.COMMAND_EVIDENCE=release
        candidate_code=release/'code';shutil.copytree(captured_code,candidate_code,ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('runtime.py','dialogue.py','portraits.py'):
            raw=guard.checked_path(str(args.source_root/'services/minecraft-assistant'/name)).read_bytes();ast.parse(raw)
            if name=='runtime.py':
                installed=(old_code/name).read_text()
                raw=guard.preserve_joke(installed,guard.preserve_server_literals(installed,raw.decode()))
            if name=='dialogue.py':
                for key in ('MODEL','SYSTEM'):
                    if constant(raw,key)!=constant((captured_code/name).read_bytes(),key):
                        raise RuntimeError('NATIVE_MODEL_CONTRACT_CHANGED')
            (candidate_code/name).write_bytes(raw)
        for path in [candidate_code,*candidate_code.rglob('*')]:os.chmod(path,0o755 if path.is_dir() else 0o644)
        candidate_files=guard.tree_files(candidate_code)
        allowed={'runtime.py','dialogue.py','portraits.py'}
        if {k:v for k,v in candidate_files.items() if k not in allowed}!={k:v for k,v in proof['candidate_sha256'].items() if k not in allowed}:
            raise RuntimeError('UNQUALIFIED_SUPPORT_MODULE_CHANGE')
        candidate=profile_for_dialogue(guard,transport,profile,config['service'],candidate_code,args.timezone,expected_mode='6' if args.previous_release else '5')
        candidate_raw=json.dumps(candidate,indent=2).replace('$','$$').encode()+b'\n'
        guard.write_private(release/'compose.candidate.json',candidate_raw)
        if guard.compose(config,release/'compose.candidate.json')!=candidate:
            raise RuntimeError('CANDIDATE_PROFILE_RENDER_CHANGED')
        test=guard.checked_path(str(args.source_root/'tests/minecraft-dialogue-transport.test.py'))
        guard.write_private(release/'transport.test.py',test.read_bytes());os.chmod(release/'transport.test.py',0o644)
        test_hash=guard.digest(test.read_bytes())
        temporary='vector-dialogue-release-check-'+uuid.uuid4().hex
        print('Prüfe signiertes HTTP und Startkonfiguration isoliert, ohne Modellanfrage.',flush=True)
        try:
            check=subprocess.run(['docker','run','--name',temporary,'--rm','--pull','never','--network','none','--read-only',
                '--user','65534:65534','--cpus','1','--memory','256m','--memory-swap','256m','--pids-limit','64',
                '--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,nosuid,nodev,size=16m,mode=1777',
                '-e','PYTHONDONTWRITEBYTECODE=1','--mount','type=bind,src='+str(candidate_code)+',dst=/qualification/services/minecraft-assistant,readonly',
                '--mount','type=bind,src='+str(release/'transport.test.py')+',dst=/qualification/tests/check.py,readonly',
                '--entrypoint','python3',config['expected_image'],'/qualification/tests/check.py'],capture_output=True,timeout=30)
        finally:
            subprocess.run(['docker','rm','-f',temporary],capture_output=True,timeout=15)
            if subprocess.run(['docker','inspect',temporary],capture_output=True,timeout=10).returncode!=1:
                raise RuntimeError('TEMPORARY_CONTAINER_CLEANUP_UNVERIFIED')
        guard.write_private(release/'check.stdout',check.stdout);guard.write_private(release/'check.stderr',check.stderr)
        if check.returncode:raise RuntimeError('SIGNED_HTTP_QUALIFICATION_FAILED; private release: '+str(release))
        after=guard.inventory()
        if ({name:guard.identity(value) for name,value in after.items()}!={name:guard.identity(value) for name,value in before.items()}
                or active.read_bytes()!=original or guard.tree_files(old_code)!=original_files
                or guard.tree_files(candidate_code)!=candidate_files or guard.digest((release/'transport.test.py').read_bytes())!=test_hash
                or guard.canonical(guard.compose(config,active))!=guard.canonical(profile)):
            raise RuntimeError('PRODUCTION_OR_CANDIDATE_CHANGED_DURING_QUALIFICATION')
        record=dict(original_identity=guard.identity(row),original_code=str(old_code),candidate_code=str(candidate_code),
            original_files=original_files,candidate_files=candidate_files,other_containers=guard.others(before,config['container']),
            candidate_compose_sha256=guard.digest(candidate_raw),transport_capsule=str(captured),transport_manifest_sha256=args.expected_capsule_manifest,
            candidate_profile_sha256=guard.digest(guard.canonical(candidate)),
            transport_test_sha256=test_hash)
        guard.write_private(release/'operator.json',guard.canonical(config));guard.write_private(release/'record.json',guard.canonical(record))
        guard.write_private(release/'compose.original',original)
        for name,path in (('guard.py',args.guard_helper),('transport-guard.py',args.transport_helper),('release.py',Path(__file__))):
            guard.write_private(release/name,guard.checked_path(str(path)).read_bytes())
        rollback=release/'rollback.py'
        arguments=[str(release/'release.py'),'--guard-helper',str(release/'guard.py'),'--release-root',str(args.release_root),
            '--lock-file',str(args.lock_file),'--rollback',str(release)]
        launcher='#!/usr/bin/env python3\nimport runpy, sys\nsys.dont_write_bytecode=True\nsys.argv='+repr(arguments)+'\nrunpy.run_path(sys.argv[0],run_name="__main__")\n'
        guard.write_private(rollback,launcher.encode());rollback.chmod(0o700)
        print('Rückrollaufruf: python3 '+str(rollback),flush=True)
        if not args.activate:
            print(json.dumps(dict(prepared=True,production_activated=False,release=str(release),model_calls=0,messages_sent=0)));return
        def interrupted(signum,frame):raise InterruptedError('RELEASE_INTERRUPTED')
        signal.signal(signal.SIGTERM,interrupted)
        print('Übernehme nur den Assistenten. Minecraft bleibt online.',flush=True)
        activate(guard,config,release,record,candidate_raw,original)
        result=dict(deployed=True,only_assistant_recreated=True,game_restart=False,other_services_unchanged=True,
            knowledge_mode='grounded-conversation',native_model_contract_retained=True,model_calls=0,cloud_calls=0,messages_sent=0,
            real_chat_tested=False,release=str(release),rollback=str(rollback))
        guard.write_private(release/'result.json',guard.canonical(result));print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    try:main()
    except BaseException as exc:raise SystemExit('Dialogue release failed: '+(str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__))
