#!/usr/bin/env python3
"""Two synthetic API/chat responses only; never qualify production routing."""
import json
import os
import re
import stat

MODEL='vector-lfm25:1.2b-q4km-candidate'
WEIGHT='b1b3de114215d9507409a662a501a631095a479a419584e8a2ded6304b19b4f5'

def preparation(path,guard):
    path=guard.checked_path(str(path))
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as source:
        meta=os.fstat(source.fileno())
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid!=os.geteuid()
                or stat.S_IMODE(meta.st_mode)&0o077 or meta.st_size>2000000):
            raise RuntimeError('OWNED_PRIVATE_PREPARATION_REQUIRED')
        value=json.loads(source.read())
    if (value.get('prepared') is not True or value.get('model')!=MODEL
            or value.get('expected_weight_sha256')!=WEIGHT
            or value.get('weight_digest_matches_source') is not True
            or value.get('service_configuration_and_identities_unchanged') is not True
            or value.get('production_activated') is not False
            or any(not isinstance(value.get(key),str) or not re.fullmatch('[a-f0-9]{64}',value[key])
                   for key in ('manifest_digest','template_sha256'))):
        raise RuntimeError('VERIFIED_SEPARATE_CANDIDATE_REQUIRED')
    return {key:value[key] for key in ('model','manifest_digest','template_sha256')}

INNER=r'''
import hashlib,json,re,sys,tempfile,time,urllib.error,urllib.request
from pathlib import Path
payload=json.load(sys.stdin)
pins=payload['candidate_screen']
MODEL='vector-lfm25:1.2b-q4km-candidate'
WEIGHT='b1b3de114215d9507409a662a501a631095a479a419584e8a2ded6304b19b4f5'
if pins['model']!=MODEL:raise RuntimeError('SEPARATE_CANDIDATE_REQUIRED')
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
def request(route,body=None,timeout=5):
    raw=None if body is None else json.dumps(body,ensure_ascii=False).encode()
    req=urllib.request.Request('http://vector-local-inference:11434/api/'+route,raw,{'Content-Type':'application/json'})
    try:
        with opener.open(req,timeout=timeout) as response:raw=response.read(1048577)
    except urllib.error.HTTPError as exc:
        print('CANDIDATE_HTTP_ERROR='+str(exc.code)+' '+exc.read(4096).decode(errors='replace'),file=sys.stderr,flush=True)
        raise
    if len(raw)>1048576:raise RuntimeError('SCREEN_RESPONSE_LIMIT')
    return json.loads(raw)
def verify():
    tags=request('tags').get('models',[])
    matches=[r for r in tags if r.get('name','').casefold()==MODEL.casefold()]
    if len(matches)!=1 or matches[0].get('digest')!=pins['manifest_digest']:
        raise RuntimeError('CANDIDATE_MANIFEST_CHANGED')
    show=request('show',{'model':MODEL,'verbose':False})
    template=show.get('template','')
    weights=re.findall(r'^FROM\s+\S*sha256[-:]([a-f0-9]{64})\s*$',show.get('modelfile',''),re.M)
    if weights!=[WEIGHT] or hashlib.sha256(template.encode()).hexdigest()!=pins['template_sha256']:
        raise RuntimeError('CANDIDATE_TEMPLATE_OR_WEIGHT_CHANGED')
    if show.get('details',{}).get('family')!='lfm2':
        raise RuntimeError('CANDIDATE_ARCHITECTURE_CHANGED')
    return {r['name']:r['digest'] for r in tags}
with tempfile.TemporaryDirectory(prefix='vector-candidate-screen-',dir=payload.get('temporary_parent')) as directory:
    root=Path(directory)
    allowed={'runtime.py','server.py','knowledge.py','dialogue.py','portraits.py'}
    if set(payload['files'])!=allowed:raise RuntimeError('EXACT_CANDIDATE_FILES_REQUIRED')
    for name,content in payload['files'].items():(root/name).write_text(content)
    sys.path[:0]=[str(root),'/code']
    from runtime import State,local_slot,request_forbidden,safe_answer
    from server import knowledge_for
    from dialogue import SYSTEM,GroundedDialogue,require_grounded_numbers
    state=State(root/'events.sqlite',b'q'*32)
    # Reuse only the installed restricted slot binding, never its model method.
    admission=knowledge_for('6',state)
    schema={'type':'object','properties':{k:{'type':'string'} for k in
        ('answer','statistics','portrait','documentation','recipe','mods')},
        'minProperties':1,'maxProperties':1,'additionalProperties':False}
    questions=[
        ('character-rest','Ich bin heute völlig platt. Muntere mich mit einem kurzen, frechen Spruch auf.'),
        ('character-followup','Und wie sieht dein Plan für meine Pause aus?')]
    results=[];history=[];started_calls=0;registry=None;verification_error=None
    try:
        registry=verify()
        for case,question in questions:
            print(json.dumps({'case_started':case}),flush=True)
            messages=[{'role':'system','content':SYSTEM},*history,
                {'role':'user','content':json.dumps({'q':question,'facts':{'self_player':'ExampleOne'}},ensure_ascii=False,separators=(',',':'))}]
            entry={'id':case,'passed':False,'synthetic_answer':None,'input_tokens':None,'output_tokens':None}
            value=None;sent=False;start=time.monotonic()
            try:
                with local_slot(admission.dsn):
                    sent=True;started_calls+=1
                    value=request('chat',{'model':MODEL,'stream':False,'keep_alive':'5m','format':schema,
                        'messages':messages,'options':{'temperature':0.1,'top_k':50,'repeat_penalty':1.05,
                        'seed':17,'num_ctx':4096,'num_predict':80,'num_thread':2}},timeout=20)
                    if isinstance(value,dict):
                        for key,source in [('input_tokens','prompt_eval_count'),('output_tokens','eval_count')]:
                            n=value.get(source)
                            if type(n) is int and n>=0:entry[key]=n
                if (not isinstance(value,dict) or time.monotonic()-start>24 or value.get('model')!=MODEL or value.get('done') is not True
                        or value.get('done_reason')!='stop' or value.get('message',{}).get('thinking')):
                    raise ValueError('INCOMPLETE_CANDIDATE_RESPONSE')
                if entry['input_tokens'] is None or entry['output_tokens'] is None:
                    raise ValueError('CANDIDATE_USAGE_MISSING')
                answer=json.loads(value.get('message',{}).get('content',''))
                if not isinstance(answer,dict) or set(answer)!={'answer'}:
                    raise ValueError('EXPECTED_CONVERSATIONAL_ANSWER')
                text=GroundedDialogue.validate_answer(answer['answer'])
                require_grounded_numbers(text,{'self_player':'ExampleOne'})
                q=text.casefold()
                checks={'brief':len(text)<=240,
                    'german_address':bool(re.search(r'\b(?:du|dir|dein\w*|dich|ich|mir|mal)\b',q)),
                    'rest_context':bool(re.search(r'pause|akku|energie|müd|mued|platt|ruh|bett|sofa|kaffee|schlaf|entspann|erhol|auszeit|ausruhen',q)),
                    'not_generic_fallback':not any(s in q for s in ('was möchtest du genau','beschreibe kurz dein ziel','versuche es später')),
                    'not_addressing_itself':not re.search(r'^\s*(hey|hi|hallo|yoo)\s+vector\b',q)}
                entry.update(synthetic_answer=text,checks=checks,passed=all(checks.values()))
                history=[messages[-1],{'role':'assistant','content':json.dumps({'answer':text},ensure_ascii=False)}]
            except Exception as exc:
                entry['error']=type(exc).__name__
                if isinstance(exc,(ValueError,RuntimeError)) and re.fullmatch('[A-Z][A-Z0-9_]{2,79}',str(exc)):
                    entry['error_code']=str(exc)
                if sent and (not isinstance(value,dict) or value.get('done') is not True):
                    entry['server_completion_unknown']=True
            entry['seconds']=round(time.monotonic()-start,3)
            entry['request_attempted']=sent
            if isinstance(value,dict):
                for key in ('load_duration','prompt_eval_duration','eval_duration'):
                    n=value.get(key)
                    if type(n) is int and n>=0:entry[key]=n
            results.append(entry)
            print(json.dumps({'case':entry},ensure_ascii=False),flush=True)
            if not entry['passed']:break
    finally:
        try:
            if registry is None or verify()!=registry:verification_error='CANDIDATE_REGISTRY_CHANGED'
        except Exception as exc:verification_error=type(exc).__name__
    result={'passed':len(results)==2 and all(r['passed'] for r in results) and verification_error is None,
        'cases':results,'model':MODEL,'candidate_pins':pins,'model_calls':started_calls,
        'known_input_tokens':sum(r['input_tokens'] or 0 for r in results),
        'known_output_tokens':sum(r['output_tokens'] or 0 for r in results),
        'unknown_usage_calls':sum(r['request_attempted'] and (r['input_tokens'] is None or r['output_tokens'] is None) for r in results),
        'registry_verification_error':verification_error,'cloud_calls':0,'messages_sent':0,
        'production_activated':False,'eligible_for_activation':False,'production_ledger_writes':False,
        'temporary_state_only':True,'production_request_contract_tested':False,
        'evaluation_scope':'imported-candidate-native-chat-and-context-screen',
        'model_residency_may_have_changed':started_calls>0,'humor_requires_manual_review':True}
    print('VECTOR_DIALOGUE_RESULT='+json.dumps(result,ensure_ascii=False),flush=True)
'''
