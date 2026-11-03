#!/usr/bin/env python3
"""Three synthetic native requests; no production model or resource changes."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import uuid

SYSTEM=('Du bist Vector, ein lockerer, hilfreicher Minecraft-Kumpel. '
    'Antworte auf Deutsch in höchstens zwei kurzen Sätzen. '
    'Gehe konkret auf Frage und Verlauf ein; trockener Humor ist willkommen. '
    'Spielerstatistiken nur aus Werkzeugdaten. Keine erfundenen Serverwerte, '
    'Geheimnisse, Befehle oder privaten Inventare.')
TOOL={'type':'function','function':{
    'name':'compare_player_statistics',
    'description':'Vergleicht gespeicherte öffentliche Spielwerte zweier Minecraft-Spieler.',
    'parameters':{'type':'object','properties':{
        'player_a':{'type':'string'},'player_b':{'type':'string'},
        'metric':{'type':'string','enum':['mob_kills','player_kills','deaths','play_time','distance']}},
        'required':['player_a','player_b','metric'],'additionalProperties':False}}}

def private_json(path,guard):
    path=guard.checked_path(str(path))
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as source:
        meta=os.fstat(source.fileno())
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid!=os.geteuid()
                or stat.S_IMODE(meta.st_mode)&0o077 or meta.st_size>2000000):
            raise RuntimeError('OWNED_PRIVATE_EVIDENCE_REQUIRED')
        return json.loads(source.read())

def load(path,name,guard=None):
    if guard:path=guard.checked_path(str(path))
    elif not path.is_absolute() or any(p.is_symlink() for p in (path,*path.parents)):
        raise RuntimeError('UNSAFE_HELPER')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

WATCHDOG=r'''
import json,os,signal,subprocess,sys,tempfile
payload=json.load(sys.stdin);program=payload.pop('program')
with tempfile.TemporaryDirectory(prefix='vector-qwen35-watchdog-') as temporary:
    payload['temporary_parent']=temporary
    child=subprocess.Popen([sys.executable,'-c',program,'--vector-dialogue-evaluation',payload['evaluation_id']],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    try:output,error=child.communicate(json.dumps(payload).encode(),timeout=210)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGKILL);output,error=child.communicate()
    finally:
        if child.poll() is None:os.killpg(child.pid,signal.SIGKILL)
        child.wait()
    sys.stdout.buffer.write(output);sys.stdout.buffer.flush()
    sys.stderr.buffer.write(error);sys.stderr.buffer.flush()
print('VECTOR_DIALOGUE_TERMINATED='+payload['evaluation_id'],flush=True)
raise SystemExit(child.returncode if child.returncode>=0 else 128-child.returncode)
'''

INNER=r'''
import http.client,json,re,sys,tempfile,time
from pathlib import Path
payload=json.load(sys.stdin)
MODEL='vector-qwen35:9b-q4km-candidate'
def api(body,entry):
    started=time.monotonic()
    connection=http.client.HTTPConnection('vector-local-inference',11434,timeout=60)
    value=None
    try:
        connection.request('POST','/api/chat',json.dumps(body,ensure_ascii=False).encode(),{'Content-Type':'application/json'})
        response=connection.getresponse();raw=response.read(65537)
        if response.status!=200:
            print('QWEN35_HTTP_ERROR='+str(response.status)+' '+raw[:4096].decode(errors='replace'),file=sys.stderr,flush=True)
            raise RuntimeError('NATIVE_HTTP_'+str(response.status))
        if len(raw)>65536:raise ValueError('NATIVE_RESPONSE_LIMIT')
        value=json.loads(raw)
        if not isinstance(value,dict):raise ValueError('INVALID_NATIVE_OBJECT')
        for target,source in [('input_tokens','prompt_eval_count'),('output_tokens','eval_count')]:
            n=value.get(source)
            if type(n) is int and n>=0:entry[target]=n
        for key in ('load_duration','prompt_eval_duration','eval_duration'):
            n=value.get(key)
            if type(n) is int and n>=0:entry[key+'_seconds']=round(n/1e9,3)
        message=value.get('message')
        if not isinstance(message,dict):raise ValueError('INVALID_NATIVE_MESSAGE')
        thinking=message.get('thinking','')
        entry['thinking_characters']=len(thinking) if isinstance(thinking,str) else None
        if (value.get('model')!=MODEL or value.get('done') is not True
                or value.get('done_reason')!='stop' or thinking):
            raise ValueError('INCOMPLETE_OR_THINKING_RESPONSE')
        if message.get('role')!='assistant':raise ValueError('INVALID_NATIVE_ROLE')
        if entry['input_tokens'] is None or entry['output_tokens'] is None:
            raise ValueError('NATIVE_USAGE_MISSING')
        return message
    finally:
        entry['transport_seconds']=round(time.monotonic()-started,3)
        if not isinstance(value,dict) or value.get('done') is not True:
            entry['server_completion_unknown']=True
        connection.close()

def social_checks(text):
    q=text.casefold()
    return {'brief':len(text)<=320,
        'german_address':bool(re.search(r'\b(?:du|dir|dein\w*|dich|ich|mir|mal)\b',q)),
        'rest_context':bool(re.search(r'pause|akku|energie|müd|mued|platt|ruh|bett|sofa|kaffee|schlaf|entspann|erhol|auszeit|ausruhen',q)),
        'not_generic_fallback':not any(x in q for x in ('was möchtest du genau','beschreibe kurz dein ziel','versuche es später')),
        'not_addressing_itself':not re.search(r'^\s*(hey|hallo|hi|yoo)\s+vector\b',q)}

def synthetic_tool(message):
    calls=message.get('tool_calls')
    if not isinstance(calls,list) or len(calls)!=1:raise ValueError('EXPECTED_SINGLE_STATISTICS_TOOL')
    function=calls[0].get('function',{}) if isinstance(calls[0],dict) else {}
    args=function.get('arguments')
    if (function.get('name')!='compare_player_statistics' or not isinstance(args,dict)
            or set(args)!={'player_a','player_b','metric'}
            or args.get('metric')!='mob_kills'
            or any(not isinstance(args.get(k),str) for k in ('player_a','player_b'))
            or {args['player_a'].casefold(),args['player_b'].casefold()}!={'exampleone','exampletwo'}):
        raise ValueError('UNEXPECTED_STATISTICS_ARGUMENTS')
    values={'exampleone':1200,'exampletwo':950}
    return function,{'metric':'mob_kills','values':{'ExampleOne':1200,'ExampleTwo':950},
        'absolute_difference':abs(values[args['player_a'].casefold()]-values[args['player_b'].casefold()]),
        'leader':'ExampleOne','source':'synthetic-fixture-only'}

sys.path.insert(0,'/code')
from runtime import State,local_slot,safe_answer,request_forbidden
from server import knowledge_for
results=[];history=[];attempts=0
with tempfile.TemporaryDirectory(prefix='vector-qwen35-native-',dir=payload.get('temporary_parent')) as directory:
    admission=knowledge_for('6',State(Path(directory)/'events.sqlite',b'q'*32))
    cases=[
        ('smalltalk','Ich bin heute völlig platt. Muntere mich mit einem kurzen, frechen Spruch auf.'),
        ('followup','Und was würdest du mir dafür konkret vorschlagen?'),
        ('statistics-tool','Wie gross ist der Unterschied bei den Mobkills zwischen ExampleOne und ExampleTwo?')]
    for case,question in cases:
        print(json.dumps({'case_started':case}),flush=True)
        messages=[{'role':'system','content':payload['system']}]
        if case=='followup':messages+=history
        messages.append({'role':'user','content':question})
        body={'model':MODEL,'think':False,'stream':False,'keep_alive':'5m','messages':messages,
            'options':{'temperature':0.7,'top_p':0.8,'top_k':20,'min_p':0,'presence_penalty':1.5,
                       'repeat_penalty':1,'seed':17,'num_ctx':8192,'num_thread':2,'num_predict':96}}
        if case=='statistics-tool':body['tools']=[payload['tool']]
        entry={'id':case,'protocol_passed':False,'input_tokens':None,'output_tokens':None,'request_attempted':False}
        started=time.monotonic();message=None
        try:
            with local_slot(admission.dsn):
                entry['request_attempted']=True;attempts+=1
                message=api(body,entry)
            if case=='statistics-tool':
                function,value=synthetic_tool(message)
                entry.update(tool_call=function,synthetic_tool_result=value,checks={'correct_tool_and_subjects':True})
            else:
                if message.get('tool_calls'):raise ValueError('UNEXPECTED_SOCIAL_TOOL')
                text=message.get('content')
                if not isinstance(text,str) or not 1<=len(text.strip())<=400:raise ValueError('INVALID_SOCIAL_ANSWER')
                text=safe_answer(text)
                if request_forbidden(text):raise ValueError('FORBIDDEN_SOCIAL_ANSWER')
                if not re.search(r'[.!?][\"»”)]*$',text):raise ValueError('INCOMPLETE_SOCIAL_SENTENCE')
                entry.update(synthetic_answer=text,checks=social_checks(text))
                history=[{'role':'user','content':question},{'role':'assistant','content':text}]
            entry['protocol_passed']=True
        except Exception as exc:
            entry['error']=type(exc).__name__
            if isinstance(exc,(ValueError,RuntimeError)) and re.fullmatch('[A-Z][A-Z0-9_]{2,79}',str(exc)):
                entry['error_code']=str(exc)
        entry['seconds']=round(time.monotonic()-started,3)
        entry['within_existing_backend_budget']=entry['seconds']<=24
        entry['checks_passed']=bool(entry.get('checks')) and all(entry['checks'].values())
        duration=entry.get('eval_duration_seconds',0)
        if duration>0 and entry['output_tokens'] is not None:
            entry['generation_tokens_per_second']=round(entry['output_tokens']/duration,2)
        results.append(entry);print(json.dumps({'case':entry},ensure_ascii=False),flush=True)
        # Semantic heuristics remain advisory; technical/protocol failures stop.
        if not entry['protocol_passed']:break
    completed=len(results)==3 and all(r['protocol_passed'] for r in results)
    result={'diagnostic_completed':completed,
        'passed':completed and all(r['checks_passed'] and r['within_existing_backend_budget'] for r in results),
        'cases':results,'model':MODEL,'candidate_pins':payload['pins'],'model_calls':attempts,
        'known_input_tokens':sum(r['input_tokens'] or 0 for r in results),
        'known_output_tokens':sum(r['output_tokens'] or 0 for r in results),
        'unknown_usage_calls':sum(r['request_attempted'] and (r['input_tokens'] is None or r['output_tokens'] is None) for r in results),
        'cloud_calls':0,'messages_sent':0,'production_activated':False,'eligible_for_activation':False,
        'production_ledger_writes':False,'temporary_state_only':True,'production_request_contract_tested':False,
        'live_player_routes_tested':False,'tool_result_composition_tested':False,
        'humor_and_language_require_manual_review':True,'model_residency_may_have_changed':attempts>0,
        'evaluation_scope':'qwen35-nonthinking-social-context-and-native-tool-request'}
    print('VECTOR_QWEN35_RESULT='+json.dumps(result,ensure_ascii=False),flush=True)
'''

def main():
    parser=argparse.ArgumentParser()
    for name in ('guard-helper','prepare-helper','process-helper','preparation','workspace-root','lock-file'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();sys.dont_write_bytecode=True;os.umask(0o077)
    guard=load(args.guard_helper,'qwen35_native_guard')
    prep=load(args.prepare_helper,'qwen35_native_prep',guard)
    process=load(args.process_helper,'qwen35_native_process',guard)
    directory=guard.checked_path(str(args.preparation),directory=True)
    evidence=private_json(directory/'result.json',guard)
    op=prep.operator(directory/'operator.json',guard)
    if (evidence.get('prepared') is not True or evidence.get('model')!=prep.MODEL
            or evidence.get('production_activated') is not False
            or evidence.get('weight_sha256')!=prep.WEIGHT or evidence.get('projector_sha256')!=prep.PROJECTOR
            or evidence.get('actual_memory_limit_bytes')!=prep.TARGET):
        raise RuntimeError('PREPARED_QWEN35_EVIDENCE_REQUIRED')
    lockpath=guard.checked_path(str(args.lock_file))
    fd=os.open(lockpath,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);meta=os.fstat(fd)
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid!=os.geteuid():
        os.close(fd);raise RuntimeError('OWNED_RELEASE_LOCK_REQUIRED')
    with os.fdopen(fd,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        before=guard.inventory();inference=before[op['inference']];assistant=before[op['assistant']]
        if list(guard.identity(inference))!=evidence.get('inference_identity'):
            raise RuntimeError('PREPARED_INFERENCE_GENERATION_CHANGED')
        if (inference['HostConfig']['Memory']!=prep.TARGET
                or inference['HostConfig'].get('MemorySwap',0)!=evidence.get('actual_memory_swap_bytes')
                or inference['HostConfig'].get('NanoCpus')!=2000000000):
            raise RuntimeError('PREPARED_RESOURCE_LIMITS_CHANGED')
        for name in (op['assistant'],op['inference'],*op['protected']):
            state=before[name]['State']
            if not state['Running'] or state.get('OOMKilled') or state.get('Health',{}).get('Status') not in (None,'healthy'):
                raise RuntimeError('HEALTHY_REQUIRED_SERVICES_NEEDED')
        if assistant['Config'].get('User','').split(':')[0] in ('','0','root'):
            raise RuntimeError('UNPRIVILEGED_ASSISTANT_REQUIRED')
        code_mounts=[m for m in assistant.get('Mounts',[]) if m.get('Destination')=='/code']
        if len(code_mounts)!=1 or code_mounts[0].get('RW') is not False:
            raise RuntimeError('READ_ONLY_CODE_MOUNT_REQUIRED')
        initial=prep.metadata(op['assistant']);prep.verify_model(initial)
        if (initial['sources']!=op['source_hashes'] or initial['manifest_digest']!=evidence.get('manifest_digest')
                or initial['template_sha256']!=evidence.get('template_sha256')):
            raise RuntimeError('PREPARED_MODEL_OR_CODE_CHANGED')
        pins={k:initial[k] for k in ('manifest_digest','template_sha256')}
        report=guard.checked_path(str(args.workspace_root/'releases'),directory=True)/('qwen35-native-evaluation-'+uuid.uuid4().hex)
        report.mkdir(mode=0o700)
        guard.write_private(report/'evaluation.py',Path(__file__).read_bytes())
        manifest={'preparation':str(directory),'preparation_sha256':guard.digest((directory/'result.json').read_bytes()),
            'source_hashes':op['source_hashes'],'pins':pins,'system':SYSTEM,'tool':TOOL,
            'evaluation_sha256':guard.digest(Path(__file__).read_bytes()),
            'helpers':{str(p.name):guard.digest(p.read_bytes()) for p in (args.guard_helper,args.prepare_helper,args.process_helper)}}
        guard.write_private(report/'manifest.json',guard.canonical(manifest))
        print('Höchstens drei lokale Anfragen, Thinking aus. Keine Aktivierung und kein Neustart.',flush=True)
        print('Belege: '+str(report),flush=True)
        evaluation_id=uuid.uuid4().hex;child=None;result=None;terminated=False;termination_error=None
        try:
            try:
                child=subprocess.run(['docker','exec','-i','-w','/code',op['assistant'],'python3','-c',WATCHDOG],
                    input=json.dumps({'program':INNER,'evaluation_id':evaluation_id,'system':SYSTEM,'tool':TOOL,'pins':pins}).encode(),
                    capture_output=True,timeout=240,start_new_session=True)
            except subprocess.TimeoutExpired as exc:
                from types import SimpleNamespace
                child=SimpleNamespace(stdout=exc.stdout or b'',stderr=exc.stderr or b'',returncode=124)
            except OSError as exc:
                from types import SimpleNamespace
                child=SimpleNamespace(stdout=b'',stderr=type(exc).__name__.encode(),returncode=125)
        finally:
            try:
                process.ensure_native_terminated(op['assistant'],evaluation_id);terminated=True
            except Exception as exc:
                termination_error=type(exc).__name__
        guard.write_private(report/'exec.stdout',child.stdout)
        guard.write_private(report/'exec.stderr',child.stderr)
        for line in child.stdout.decode(errors='replace').splitlines():
            if line.startswith('VECTOR_QWEN35_RESULT='):result=json.loads(line.split('=',1)[1])
            elif line.startswith('{'):print(line,flush=True)
        if result is None:
            result={'passed':False,'diagnostic_completed':False,'error':'NATIVE_PROCESS_FAILED',
                'exit_code':child.returncode,'production_activated':False,'eligible_for_activation':False,
                'cloud_calls':0,'messages_sent':0}
        try:
            after=guard.inventory();final=prep.metadata(op['assistant']);prep.verify_model(final)
            unchanged=(set(before)==set(after) and all(prep.configuration(guard,before[n])==prep.configuration(guard,after[n]) for n in before)
                and final['sources']==op['source_hashes'] and final['registry']==initial['registry']
                and final['manifest_digest']==pins['manifest_digest'] and final['template_sha256']==pins['template_sha256'])
        except Exception as exc:
            unchanged=False;result['verification_error']=type(exc).__name__
        result['service_configurations_and_identities_unchanged']=unchanged
        result['native_client_termination_verified']=terminated
        if termination_error:result['termination_error']=termination_error
        result['manifest_sha256']=guard.digest(guard.canonical(manifest))
        result['diagnostic_completed']=bool(result.get('diagnostic_completed') and child.returncode==0 and unchanged and terminated)
        result['passed']=bool(result.get('passed') and result['diagnostic_completed'])
        guard.write_private(report/'result.json',guard.canonical(result))
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        print('Messung ist keine Produktionsfreigabe. Inhalt und Antwortzeiten anhand des Berichts beurteilen.',flush=True)
        if not result['diagnostic_completed']:raise SystemExit(1)

if __name__=='__main__':main()
