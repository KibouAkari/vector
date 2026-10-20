#!/usr/bin/env python3
"""Evaluate an opt-in dialogue candidate in a short-lived exec process only.

No activation, restart, model download, real channel message or application DB
write. Uses the installed restricted CPU-slot role and local model transport.
"""
import argparse
import ast
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import stat
import sys
import time
import uuid


INNER = r'''
import hashlib,json,os,sys,tempfile,time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

payload=json.load(sys.stdin)
with tempfile.TemporaryDirectory(prefix='vector-dialogue-eval-',dir=payload.get('temporary_parent')) as temporary:
    root=Path(temporary)
    for name,content in payload['files'].items():
        if name not in ('runtime.py','dialogue.py','server.py','knowledge.py'):raise RuntimeError('INVALID_CANDIDATE_FILE')
        (root/name).write_text(content)
    sys.path[:0]=[str(root),'/code']
    from runtime import Assistant,State
    from portraits import PlayerPortraits
    from dialogue import GroundedDialogue,PublicObservations,MODEL
    from server import knowledge_for
    state=State(root/'events.sqlite',b'q'*32)
    provider=knowledge_for('6',state)
    if provider.model!=MODEL:raise RuntimeError('QUALIFIED_MODEL_REQUIRED')
    usage=[]
    provider.usage=lambda model,inp,out,accepted:usage.append(dict(model=model,input_tokens=inp,output_tokens=out,accepted=accepted))
    directory=root/'stats';directory.mkdir()
    ids=['10000000-0000-0000-0000-'+str(i).zfill(12) for i in (1,2)]
    names=['ExampleOne','ExampleTwo']
    cache=root/'users.json';cache.write_text(json.dumps([dict(uuid=u,name=n) for u,n in zip(ids,names)]))
    for uid,kills in zip(ids,(25,90)):
        (directory/(uid+'.json')).write_text(json.dumps({'stats':{'minecraft:custom':{'minecraft:mob_kills':kills,'minecraft:player_kills':kills//10}}}))
    mods=root/'mods.json';mods.write_bytes(Path('/inputs/mods.json').read_bytes())
    ai=Assistant(state,directory,cache,mods,knowledge=provider,portraits=PlayerPortraits(directory,cache))
    dialogue=GroundedDialogue(provider)
    scope=('minecraft',ids[0])
    facts=lambda:PublicObservations(ai,scope,ids[0],timezone='Europe/Zurich',wall_clock=lambda:datetime(2026,10,20,12,34,tzinfo=ZoneInfo('Europe/Zurich')))
    cases=[('clock','Wie spät haben wir es eigentlich?',lambda a:'12:34' in a),
           ('unlisted-gameplay','Wie wird Sand zu Glas?',lambda a:'sand' in a.casefold() and any(w in a.casefold() for w in ('ofen','schmelz'))),
           ('player-opinion','Roaste ExampleTwo kurz anhand seines Monsterkontos.',lambda a:'ExampleTwo' in a and '90' in a),
           ('own-context','Und wie viele habe dann ich?',lambda a:'25' in a and any(w in a.casefold() for w in ('du','dein','exampleone')))]
    results=[]
    for key,question,check in cases:
        before=len(usage);start=time.monotonic()
        print(json.dumps({'case_started':key}),flush=True)
        try:
            answer=dialogue.answer(question,scope,facts())
            passed=bool(check(answer));error=None
        except Exception as exc:
            answer=None;passed=False;error=type(exc).__name__
        results.append(dict(id=key,passed=passed,seconds=round(time.monotonic()-start,3),model_calls=len(usage)-before,synthetic_answer=answer,error=error))
        print(json.dumps({'case':results[-1]},ensure_ascii=False),flush=True)
    result=dict(passed=all(c['passed'] for c in results),cases=results,usage=usage,
        model_calls=len(usage),input_tokens=sum(c['input_tokens'] or 0 for c in usage),
        output_tokens=sum(c['output_tokens'] or 0 for c in usage),
        unknown_usage_calls=sum(c['input_tokens'] is None or c['output_tokens'] is None for c in usage),
        model=MODEL,cloud_calls=0,api_cost_chf=0,messages_sent=0,production_activated=False,
        production_ledger_writes=False,temporary_state_only=True,
        native_semantics_require_manual_review=True,eligible_for_activation=False)
    print('VECTOR_DIALOGUE_RESULT='+json.dumps(result,ensure_ascii=False),flush=True)
'''



WATCHDOG = r"""
import json,os,signal,subprocess,sys,tempfile
payload=json.load(sys.stdin)
program=payload.pop('program')
evaluation_id=payload['evaluation_id']
with tempfile.TemporaryDirectory(prefix='vector-dialogue-watchdog-') as temporary:
    payload['temporary_parent']=temporary
    child=subprocess.Popen([sys.executable,'-c',program,'--vector-dialogue-evaluation',evaluation_id],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    try:
        output,error=child.communicate(json.dumps(payload).encode(),timeout=110)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGKILL)
        output,error=child.communicate()
    finally:
        if child.poll() is None:
            os.killpg(child.pid,signal.SIGKILL)
        child.wait()
    sys.stdout.buffer.write(output);sys.stdout.buffer.flush()
    sys.stderr.buffer.write(error);sys.stderr.buffer.flush()
print('VECTOR_DIALOGUE_TERMINATED='+evaluation_id,flush=True)
raise SystemExit(child.returncode if child.returncode>=0 else 128-child.returncode)
"""

CANCEL = r"""
import json,os,signal,sys,time
from pathlib import Path
identity=sys.argv[1].encode()
self_status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
namespace_depth=len(self_status.get('NSpid',str(os.getpid())).split())
def targets():
    found=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():continue
        try:
            args=(p/'cmdline').read_bytes().rstrip(b'\0').split(b'\0')
            state=(p/'stat').read_text().rsplit(')',1)[1].strip().split()[0]
            if args[-2:]==[b'--vector-dialogue-evaluation',identity] and state!='Z':
                status=dict(line.split(':',1) for line in (p/'status').read_text().splitlines() if ':' in line)
                identifiers=status.get('NSpid',p.name).split()
                if len(identifiers)==namespace_depth:found.append(int(identifiers[-1]))
        except (OSError,ValueError,IndexError):continue
    return found
for pid in targets():
    descriptor=None
    try:
        descriptor=os.pidfd_open(pid)
        if pid in targets():signal.pidfd_send_signal(descriptor,signal.SIGKILL)
    except ProcessLookupError:pass
    finally:
        if descriptor is not None:os.close(descriptor)
for attempt in range(20):
    if not targets():break
    time.sleep(.1)
print(json.dumps({'terminated':not targets()}))
"""


def ensure_native_terminated(container, evaluation_id):
    result=subprocess.run(['docker','exec',container,'python3','-c',CANCEL,evaluation_id],capture_output=True,timeout=15)
    if result.returncode or json.loads(result.stdout).get('terminated') is not True:
        raise RuntimeError('NATIVE_EVALUATION_TERMINATION_UNVERIFIED')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--guard-helper', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--workspace-root', type=Path, required=True)
    parser.add_argument('--lock-file', type=Path, required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('dialogue_guard', args.guard_helper)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    guard.checked_path(args.lock_file.parent,directory=True)
    if args.lock_file.is_symlink():raise RuntimeError('UNSAFE_LOCK')
    descriptor=os.open(args.lock_file,os.O_WRONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    metadata=os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=os.geteuid():
        os.close(descriptor);raise RuntimeError('EXISTING_OWNED_RELEASE_LOCK_REQUIRED')
    with os.fdopen(descriptor,'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        baseline = guard.checked_path(str(args.baseline), directory=True)
        config = guard.read_config(baseline/'operator.json')
        record = json.loads((baseline/'record.json').read_bytes())
        saved = guard.checked_path(str(baseline/'compose.candidate.json'))
        active = guard.checked_path(config['compose'])
        if guard.digest(saved.read_bytes()) != record['candidate_compose_sha256'] or active.read_bytes() != saved.read_bytes():
            raise RuntimeError('CONFIRMED_BASELINE_PROFILE_CHANGED')
        profile = guard.compose(config, active)
        code = guard.code_source(profile, config['service'])
        if str(code) != record['candidate_code'] or guard.tree_files(code) != record['candidate_files']:
            raise RuntimeError('CONFIRMED_BASELINE_CODE_CHANGED')
        before = guard.inventory()
        row = before[config['container']]
        if guard.identity(row) != tuple(record['deployed_identity']):
            raise RuntimeError('CONFIRMED_ASSISTANT_GENERATION_CHANGED')
        if (not row['State']['Running'] or row['State'].get('Health',{}).get('Status') != 'healthy'
                or row['Config'].get('User','').split(':',1)[0] in ('','0','root')):
            raise RuntimeError('HEALTHY_UNPRIVILEGED_ASSISTANT_REQUIRED')
        expected = dict(config)
        expected.pop('expected_portraits_sha256',None)
        expected['expected_runtime_sha256'] = record['candidate_files']['runtime.py']
        expected['expected_compose_sha256'] = record['candidate_compose_sha256']
        expected['expected_profile_sha256'] = guard.digest(guard.canonical(profile))
        guard.validate_live(expected, before, profile)
        sources = {}
        for name in ('runtime.py','dialogue.py','server.py','knowledge.py'):
            path = guard.checked_path(str(args.source_root/'services/minecraft-assistant'/name))
            text = path.read_text()
            ast.parse(text)
            if name == 'runtime.py':
                old = (code/name).read_text()
                text = guard.preserve_joke(old, guard.preserve_server_literals(old,text)).decode()
            if name == 'server.py':
                old_tree=ast.parse((code/name).read_text())
                new_tree=ast.parse(text)
                swaps=[]
                lines=text.encode().splitlines(keepends=True)
                for pin in ('KNOWLEDGE_PACK_SHA256','DOCUMENTATION_SHA256'):
                    def find(tree):
                        found=[n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==pin for t in n.targets)]
                        if len(found)!=1 or not isinstance(found[0],ast.Constant) or not isinstance(found[0].value,str):raise RuntimeError('UNIQUE_CATALOG_PIN_REQUIRED')
                        if len(found[0].value)!=64 or any(c not in '0123456789abcdef' for c in found[0].value):raise RuntimeError('CATALOG_PIN_FORMAT')
                        return found[0]
                    old_pin,new_pin=find(old_tree),find(new_tree)
                    start=sum(map(len,lines[:new_pin.lineno-1]))+new_pin.col_offset
                    end=sum(map(len,lines[:new_pin.end_lineno-1]))+new_pin.end_col_offset
                    swaps.append((start,end,repr(old_pin.value).encode()))
                raw=text.encode()
                for start,end,value in sorted(swaps,reverse=True):raw=raw[:start]+value+raw[end:]
                text=raw.decode();ast.parse(text)
            sources[name] = text
        report = args.workspace_root/'releases'/('minecraft-dialogue-evaluation-'+uuid.uuid4().hex)
        report.mkdir(mode=0o700)
        candidate=report/'candidate';candidate.mkdir(mode=0o700)
        for name,source in sources.items():guard.write_private(candidate/name,source.encode())
        guard.write_private(report/'baseline.record.json',(baseline/'record.json').read_bytes())
        guard.write_private(report/'baseline.operator.json',guard.canonical(config))
        guard.write_private(report/'baseline.compose.json',saved.read_bytes())
        program=Path(__file__).read_bytes()
        guard.write_private(report/'evaluation.py',program)
        manifest=dict(baseline=str(baseline),container_identity=guard.identity(row),
            candidate_sha256={name:guard.digest(source.encode()) for name,source in sources.items()},
            baseline_record_sha256=guard.digest((baseline/'record.json').read_bytes()),
            evaluation_sha256=guard.digest(program),lock_file=str(args.lock_file))
        guard.write_private(report/'manifest.json',guard.canonical(manifest))
        print('Vier synthetische Fragen an das bestehende lokale Modell. Kein Rollout oder Minecraft-Neustart.',flush=True)
        print('Belege: '+str(report),flush=True)
        evaluation_id=uuid.uuid4().hex
        command = ['docker','exec','-i','-w','/code',config['container'],'python3','-c',WATCHDOG]
        try:
            child = subprocess.run(command,input=json.dumps({'files':sources,'program':INNER,'evaluation_id':evaluation_id}).encode(),capture_output=True,timeout=150,start_new_session=True)
        except subprocess.TimeoutExpired as exc:
            from types import SimpleNamespace
            child=SimpleNamespace(stdout=exc.stdout or b'',stderr=exc.stderr or b'',returncode=124)
        finally:
            # Targets only the unique test child, never the assistant service.
            ensure_native_terminated(config['container'],evaluation_id)
        output = child.stdout.decode(errors='replace')
        guard.write_private(report/'exec.stdout',child.stdout)
        guard.write_private(report/'exec.stderr',child.stderr)
        result = None
        for line in output.splitlines():
            if line.startswith('VECTOR_DIALOGUE_RESULT='):
                result=json.loads(line.split('=',1)[1])
            elif line.startswith('{'):
                print(line,flush=True)
        after = guard.inventory()
        def observed(value):
            state=value['State']
            return (*guard.identity(value),state.get('Running'),state.get('OOMKilled'),state.get('Health',{}).get('Status'))
        unchanged = ({name:observed(value) for name,value in before.items()} ==
                     {name:observed(value) for name,value in after.items()}
                     and active.read_bytes() == saved.read_bytes()
                     and guard.tree_files(code) == record['candidate_files'])
        if result is None:
            result=dict(passed=False,error='NATIVE_EVALUATION_FAILED',exit_code=child.returncode,
                        production_activated=False,messages_sent=0,cloud_calls=0)
        result['native_process_termination_verified']=True
        result['manifest_sha256']=guard.digest(guard.canonical(manifest))
        result['production_containers_and_profiles_unchanged']=unchanged
        result['passed']=bool(result.get('passed') and child.returncode==0 and unchanged)
        guard.write_private(report/'result.json',guard.canonical(result))
        print(json.dumps(result,indent=2,ensure_ascii=False),flush=True)
        print('Kein automatischer Rollout. Echte Modellqualität und Antwortzeiten vor Aktivierung prüfen.',flush=True)
        if not result['passed']:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
