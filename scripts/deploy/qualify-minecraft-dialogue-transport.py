#!/usr/bin/env python3
"""Qualify signed chat construction against a confirmed native candidate; never deploy."""
import argparse
import ast
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import uuid

FILES={'runtime.py','dialogue.py','server.py','knowledge.py','portraits.py'}
ENV_SUFFIXES=('KNOWLEDGE','RECIPES','MOD_RECIPES_SHA256','PORTRAITS','ADVANCEMENTS','TIMEZONE')


def main_node(text):
    found=[node for node in ast.parse(text).body if isinstance(node,ast.FunctionDef) and node.name=='main']
    if len(found)!=1:raise RuntimeError('UNIQUE_SERVICE_MAIN_REQUIRED')
    return found[0]


def service_bindings(text):
    """Read literals only; never open a token or inspect environment values."""
    main=main_node(text)
    tokens=[node.value for node in ast.walk(main) if isinstance(node,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='token' for t in node.targets)]
    if len(tokens)!=1:raise RuntimeError('UNIQUE_SERVICE_TOKEN_REQUIRED')
    paths=[node.args[0] for node in ast.walk(tokens[0]) if isinstance(node,ast.Call)
           and isinstance(node.func,ast.Name) and node.func.id=='Path' and len(node.args)==1]
    if (len(paths)!=1 or not isinstance(paths[0],ast.Constant) or not isinstance(paths[0].value,str)
            or not paths[0].value.startswith('/run/secrets/') or '/' in paths[0].value[len('/run/secrets/'):] ):
        raise RuntimeError('BOUND_SERVICE_TOKEN_PATH_REQUIRED')
    env={}
    for node in ast.walk(main):
        key=None
        if (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
                and ast.unparse(node.func)=='os.environ.get' and node.args):key=node.args[0]
        if isinstance(node,ast.Subscript) and ast.unparse(node.value)=='os.environ':key=node.slice
        if key is None:continue
        if not isinstance(key,ast.Constant) or not isinstance(key.value,str):raise RuntimeError('LITERAL_SERVICE_ENV_REQUIRED')
        matches=[suffix for suffix in ENV_SUFFIXES if key.value.endswith('_'+suffix)]
        # MOD_RECIPES_SHA256 is distinct from the short RECIPES suffix.
        if len(matches)!=1 or not key.value.startswith('VECTOR_'):raise RuntimeError('UNSUPPORTED_SERVICE_ENV_BINDING')
        suffix=matches[0]
        if suffix in env and env[suffix][0].value!=key.value:raise RuntimeError('AMBIGUOUS_SERVICE_ENV_BINDING')
        env.setdefault(suffix,[]).append(key)
    return paths[0],env


def preserve_service_bindings(installed,candidate,mounts):
    old_token,old_env=service_bindings(installed)
    new_token,new_env=service_bindings(candidate)
    bound=[m for m in mounts if m.get('Destination')==old_token.value]
    if len(bound)!=1 or bound[0].get('RW') is not False:
        raise RuntimeError('EXISTING_READ_ONLY_SERVICE_TOKEN_REQUIRED')
    if 'KNOWLEDGE' not in old_env or 'KNOWLEDGE' not in new_env:
        raise RuntimeError('EXISTING_KNOWLEDGE_BINDING_REQUIRED')
    replacements=[(new_token,old_token.value)]
    for suffix,nodes in new_env.items():
        if suffix in old_env:
            replacements.extend((node,old_env[suffix][0].value) for node in nodes)
    raw=candidate.encode();lines=raw.splitlines(keepends=True)
    changes=[]
    for node,value in replacements:
        start=sum(map(len,lines[:node.lineno-1]))+node.col_offset
        end=sum(map(len,lines[:node.end_lineno-1]))+node.end_col_offset
        changes.append((start,end,repr(value).encode()))
    for start,end,value in sorted(changes,reverse=True):raw=raw[:start]+value+raw[end:]
    result=raw.decode();service_bindings(result)
    # Only main's approved literals may change; factory, HMAC and handlers stay exact.
    old_tree=ast.parse(candidate);new_tree=ast.parse(result)
    old_tree.body=[n for n in old_tree.body if not isinstance(n,ast.FunctionDef) or n.name!='main']
    new_tree.body=[n for n in new_tree.body if not isinstance(n,ast.FunctionDef) or n.name!='main']
    if ast.dump(old_tree)!=ast.dump(new_tree):raise RuntimeError('NON_BINDING_SERVICE_CHANGE')
    return result


def read_private(guard,path):
    path=guard.checked_path(str(path));meta=path.stat()
    if meta.st_uid!=os.geteuid() or stat.S_IMODE(meta.st_mode)&0o077 or meta.st_size>2_000_000:
        raise RuntimeError('PRIVATE_EVIDENCE_REQUIRED')
    return path.read_bytes()


def verify_native(guard,report,expected):
    manifest_raw=read_private(guard,report/'manifest.json')
    manifest=json.loads(manifest_raw);result=json.loads(read_private(guard,report/'result.json'))
    if guard.digest(guard.canonical(manifest))!=expected or result.get('manifest_sha256')!=expected:
        raise RuntimeError('NATIVE_MANIFEST_PIN_MISMATCH')
    if (manifest.get('profile_only') or manifest.get('preload') or manifest.get('diagnose_rejection')
            or result.get('passed') is not True or result.get('production_activated') is not False
            or result.get('production_containers_and_profiles_unchanged') is not True
            or result.get('native_process_termination_verified') is not True
            or result.get('expected_cases')!=4 or result.get('completed_cases')!=4
            or result.get('model_calls')!=1 or result.get('cloud_calls')!=0 or result.get('messages_sent')!=0):
        raise RuntimeError('COMPLETE_NATIVE_QUALIFICATION_REQUIRED')
    cases={case['id']:case for case in result.get('cases',[])}
    if set(cases)!={'smalltalk','unlisted-gameplay','player-opinion','own-context'}:
        raise RuntimeError('NATIVE_CASE_SET_MISMATCH')
    if any(case.get('passed') is not True for case in cases.values()):raise RuntimeError('NATIVE_CASE_FAILED')
    if set(manifest.get('candidate_sha256',{}))!=FILES:raise RuntimeError('NATIVE_CANDIDATE_FILE_SET')
    sources={name:read_private(guard,report/'candidate'/name) for name in FILES}
    if {name:guard.digest(raw) for name,raw in sources.items()}!=manifest['candidate_sha256']:
        raise RuntimeError('NATIVE_CANDIDATE_CHANGED')
    return manifest,sources


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guard-helper',type=Path,required=True)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--native-report',type=Path,required=True)
    parser.add_argument('--expected-native-manifest',required=True)
    parser.add_argument('--release-root',type=Path,required=True)
    parser.add_argument('--lock-file',type=Path,required=True)
    args=parser.parse_args();sys.dont_write_bytecode=True;os.umask(0o077)
    spec=importlib.util.spec_from_file_location('transport_guard',args.guard_helper)
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    guard.checked_path(str(args.release_root),directory=True)
    guard.checked_path(str(args.lock_file))
    fd=os.open(args.lock_file,os.O_WRONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    metadata=os.fstat(fd)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=os.geteuid():
        os.close(fd);raise RuntimeError('EXISTING_OWNED_RELEASE_LOCK_REQUIRED')
    with os.fdopen(fd,'a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        report=guard.checked_path(str(args.native_report),directory=True)
        manifest,sources=verify_native(guard,report,args.expected_native_manifest)
        baseline=guard.checked_path(manifest['baseline'],directory=True)
        config=guard.read_config(baseline/'operator.json')
        record_raw=read_private(guard,baseline/'record.json');record=json.loads(record_raw)
        if (guard.digest(record_raw)!=manifest['baseline_record_sha256']
                or read_private(guard,report/'baseline.record.json')!=record_raw
                or guard.canonical(config)!=read_private(guard,report/'baseline.operator.json')):
            raise RuntimeError('NATIVE_BASELINE_EVIDENCE_CHANGED')
        active=guard.checked_path(config['compose']);saved=read_private(guard,baseline/'compose.candidate.json')
        if guard.digest(saved)!=record['candidate_compose_sha256'] or active.read_bytes()!=saved:
            raise RuntimeError('CONFIRMED_BASELINE_PROFILE_CHANGED')
        before=guard.inventory();row=before[config['container']]
        if list(guard.identity(row))!=manifest['container_identity']:
            raise RuntimeError('CONFIRMED_ASSISTANT_GENERATION_CHANGED')
        if row['Config'].get('User','').split(':',1)[0] in ('','0','root') or row['State'].get('OOMKilled'):
            raise RuntimeError('UNPRIVILEGED_ASSISTANT_REQUIRED')
        profile=guard.compose(config,active);code=guard.code_source(profile,config['service'])
        if str(code)!=record['candidate_code'] or guard.tree_files(code)!=record['candidate_files']:
            raise RuntimeError('CONFIRMED_BASELINE_CODE_CHANGED')
        expected=dict(config);expected.pop('expected_portraits_sha256',None)
        expected.update(expected_runtime_sha256=record['candidate_files']['runtime.py'],
            expected_compose_sha256=record['candidate_compose_sha256'],
            expected_profile_sha256=guard.digest(guard.canonical(profile)))
        guard.validate_live(expected,before,profile)
        # Reuse the captured provider and fact modules. Only the reviewed native
        # routing additions and main's installed service bindings are projected.
        for name in ('runtime.py','dialogue.py'):
            path=guard.checked_path(str(args.source_root/'services/minecraft-assistant'/name))
            value=path.read_text();ast.parse(value)
            if name=='runtime.py':
                old=(code/name).read_text()
                value=guard.preserve_joke(old,guard.preserve_server_literals(old,value)).decode()
            sources[name]=value.encode()
        sources['server.py']=preserve_service_bindings((code/'server.py').read_text(),sources['server.py'].decode(),row['Mounts']).encode()
        release=args.release_root/('minecraft-dialogue-transport-'+uuid.uuid4().hex);release.mkdir(mode=0o700)
        candidate=release/'code';shutil.copytree(code,candidate,ignore=shutil.ignore_patterns('__pycache__'))
        for name,raw in sources.items():(candidate/name).write_bytes(raw)
        for path in [candidate,*candidate.rglob('*')]:
            os.chmod(path,0o755 if path.is_dir() else 0o644)
        test=guard.checked_path(str(args.source_root/'tests/minecraft-dialogue-transport.test.py'))
        guard.write_private(release/'transport.test.py',test.read_bytes())
        os.chmod(release/'transport.test.py',0o644)
        guard.write_private(release/'operator.json',guard.canonical(config))
        guard.write_private(release/'baseline.record.json',record_raw)
        guard.write_private(release/'baseline.compose.json',saved)
        guard.write_private(release/'native.manifest.json',read_private(guard,report/'manifest.json'))
        guard.write_private(release/'native.result.json',read_private(guard,report/'result.json'))
        proof={'native_report':str(report),'native_manifest_sha256':args.expected_native_manifest,
            'native_source_sha256':manifest['candidate_sha256'],
            'candidate_sha256':guard.tree_files(candidate),
            'transport_test_sha256':guard.digest(test.read_bytes()),'container_identity':guard.identity(row)}
        guard.write_private(release/'manifest.json',guard.canonical(proof))
        print('Belege: '+str(release),flush=True)
        name='vector-dialogue-http-'+uuid.uuid4().hex
        try:
            completed=subprocess.run(['docker','run','--name',name,'--rm','--pull','never','--network','none','--read-only',
                '--user','65534:65534','--cpus','1','--memory','256m','--memory-swap','256m','--pids-limit','64',
                '--cap-drop','ALL','--security-opt','no-new-privileges',
                '--tmpfs','/tmp:rw,nosuid,nodev,size=16m,mode=1777','-e','PYTHONDONTWRITEBYTECODE=1',
                '--mount','type=bind,src='+str(candidate)+',dst=/qualification/services/minecraft-assistant,readonly',
                '--mount','type=bind,src='+str(release/'transport.test.py')+',dst=/qualification/tests/check.py,readonly',
                '--entrypoint','python3',config['expected_image'],'/qualification/tests/check.py'],
                capture_output=True,timeout=30)
        finally:
            subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=15)
            cleanup=subprocess.run(['docker','inspect',name],capture_output=True,timeout=10)
            if cleanup.returncode!=1:raise RuntimeError('TEMPORARY_CONTAINER_CLEANUP_UNVERIFIED')
        guard.write_private(release/'exec.stdout',completed.stdout)
        guard.write_private(release/'exec.stderr',completed.stderr)
        after=guard.inventory()
        def observed(value):
            state=value['State']
            return (*guard.identity(value),state.get('Running'),state.get('OOMKilled'),state.get('Health',{}).get('Status'))
        unchanged=({name:observed(value) for name,value in before.items()}==
                   {name:observed(value) for name,value in after.items()}
                   and active.read_bytes()==saved and guard.tree_files(code)==record['candidate_files']
                   and guard.tree_files(candidate)==proof['candidate_sha256']
                   and guard.digest((release/'transport.test.py').read_bytes())==proof['transport_test_sha256']
                   and guard.canonical(guard.compose(config,active))==guard.canonical(profile))
        result={'transport_qualified':completed.returncode==0 and unchanged,
            'native_evidence_retained':True,'service_bindings_retained':True,
            'temporary_container_cleanup_verified':True,
            'production_unchanged':unchanged,'production_activated':False,
            'eligible_for_activation':False,'model_calls':0,'cloud_calls':0,'messages_sent':0,
            'manifest_sha256':guard.digest(guard.canonical(proof))}
        guard.write_private(release/'result.json',guard.canonical(result))
        print(json.dumps(result,indent=2),flush=True)
        if not result['transport_qualified']:raise RuntimeError('SIGNED_CHAT_TRANSPORT_FAILED')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        raise SystemExit('Transport qualification failed: '+(str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__))
