#!/usr/bin/env python3
"""Isolate language/prompt/native rendering with existing Qwen; never activate."""
from contextlib import redirect_stdout
from datetime import datetime, timezone
import ast
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

ROOT=Path('/root/vector-workspace')
REPO=ROOT/'github/vector'

# Private synthetic baseline, deliberately not the gameplay prompt or policy.
# Eight calls: two questions x two languages x native chat/manual author ChatML.
HARNESS=r'''
import json,time,urllib.request
MODEL='vector-qwen3:1.7b-q8'
TEMPLATE='57f1fd00f0013a2be96aa79b857391f27e23df5b5f847072b524c897e24d0361'
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args):return None
http=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
def native(path,payload=None,timeout=25):
 request=urllib.request.Request('http://vector-local-inference:11434'+path,
  json.dumps(payload).encode() if payload is not None else None,
  {'Content-Type':'application/json'})
 with http.open(request,timeout=timeout) as response:raw=response.read(131073)
 if len(raw)>131072:raise ValueError('NATIVE_RESPONSE_LIMIT')
 value=json.loads(raw)
 if not isinstance(value,dict):raise ValueError('NATIVE_RESPONSE_SHAPE')
 return value
import hashlib
version=native('/api/version',timeout=8).get('version')
show=native('/api/show',{'model':MODEL},8)
template=show.get('template');info=show.get('model_info',{})
if (version!='0.40.4' or not isinstance(template,str) or hashlib.sha256(template.encode()).hexdigest()!=TEMPLATE
 or show.get('system','')!='' or not isinstance(info,dict)
 or info.get('general.architecture')!='qwen3' or info.get('tokenizer.ggml.add_bos_token') is not False
 or info.get('tokenizer.ggml.eos_token_id')!=151645):raise ValueError('AUDITED_NATIVE_METADATA_CHANGED')
questions=[('cow',{'en':'How do you breed cows in Minecraft?','de':'Wie züchte ich Kühe in Minecraft?'}),
 ('glass',{'en':'How do you make glass in Minecraft?','de':'Wie bekomme ich Glas in Minecraft?'})]
systems={'en':'Answer briefly and factually.','de':'Antworte kurz und sachlich.'}
rows=[]
for name,languages in questions:
 for language,question in languages.items():
  system=systems[language]
  for transport in ('chat','raw-chatml'):
   # Qwen author ChatML, no BOS (audited false), explicit empty thinking prefix.
   # Raw generation bypasses automatic template rendering without changing it.
   payload={'model':MODEL,'stream':False,'keep_alive':'5m',
    'options':{'temperature':.7,'top_p':.8,'top_k':20,'min_p':0,'seed':17,
     'num_ctx':2048,'num_predict':96,'num_thread':2,'stop':['<|im_end|>','<|im_start|>']}}
   if transport=='chat':
    payload.update(think=False,messages=[{'role':'system','content':system},{'role':'user','content':question}])
    path='/api/chat'
   else:
    payload.update(raw=True,prompt='<|im_start|>system\n'+system+'<|im_end|>\n<|im_start|>user\n'+question+'<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n')
    path='/api/generate'
   value=None;answer='';error=None;started=time.monotonic()
   try:
    value=native(path,payload)
    if value.get('model')!=MODEL:raise ValueError('NATIVE_MODEL_MISMATCH')
    message=value.get('message')
    answer=message.get('content') if transport=='chat' and isinstance(message,dict) else value.get('response') if transport!='chat' else None
    if not isinstance(answer,str):answer='';raise ValueError('NATIVE_TEXT_SHAPE')
   except Exception as exc:
    error=str(exc) if isinstance(exc,ValueError) and str(exc).isupper() and len(str(exc))<=80 else type(exc).__name__
   def count(key):
    v=value.get(key) if isinstance(value,dict) else None
    return v if type(v) is int and v>=0 else None
   rows.append(dict(id=name,language=language,transport=transport,question=question,
    seconds=round(time.monotonic()-started,3),synthetic_answer=answer[:2048],
    answer_characters=len(answer),error=error,
    complete=bool(isinstance(value,dict) and value.get('done') is True and value.get('done_reason')=='stop'),
    done_reason=value.get('done_reason') if isinstance(value,dict) else None,
    input_tokens=count('prompt_eval_count'),output_tokens=count('eval_count'),
    load_seconds=count('load_duration')/1e9 if count('load_duration') is not None else None,
    prompt_eval_seconds=count('prompt_eval_duration')/1e9 if count('prompt_eval_duration') is not None else None,
    generation_seconds=count('eval_duration')/1e9 if count('eval_duration') is not None else None))
known=all(row[k] is not None for row in rows for k in ('input_tokens','output_tokens'))
print(json.dumps(dict(passed=False,quality_passed=False,eligible_for_activation=False,
 evaluation_scope='minimal-language-and-native-rendering-diagnostic',model=MODEL,
 runtime_version=version,template_sha256=TEMPLATE,metadata_reads=2,cases=rows,model_calls=len(rows),
 input_tokens=sum(r['input_tokens'] for r in rows) if known else None,
 output_tokens=sum(r['output_tokens'] for r in rows) if known else None,
 known_input_tokens=sum(r['input_tokens'] for r in rows if r['input_tokens'] is not None),
 known_output_tokens=sum(r['output_tokens'] for r in rows if r['output_tokens'] is not None),
 unknown_usage_calls=sum(any(r[k] is None for k in ('input_tokens','output_tokens')) for r in rows),
 cloud_calls=0,api_cost_chf=0,messages_sent=0,production_activated=False,ledger_writes=False)))
'''


def diagnose(base,directory):
    original=base.HARNESS
    try:
        base.HARNESS=HARNESS
        with (directory/'phase.log').open('x') as log,redirect_stdout(log):
            result=base.evaluate()
    finally:base.HARNESS=original
    if not result or not all(result.get(k) is True for k in ('production_unchanged','cleanup_verified','weights_unloaded')):
        raise RuntimeError('Diagnostic cleanup/state was not verified.')
    if result.get('model_calls')!=8:raise RuntimeError('Incomplete diagnostic; keep the private phase log.')
    return result


def main():
    os.umask(0o077);revision=os.environ.get('VECTOR_FEGCRAFT_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision):raise RuntimeError('Root and exact VECTOR_FEGCRAFT_REV required.')
    subprocess.run(['git','-C',str(REPO),'merge-base','--is-ancestor',revision,'origin/main'],check=True)
    with (ROOT/'.chat-release.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        directory=ROOT/'releases'/('vector-fegcraft-minimal-prompts-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3))
        directory.mkdir(mode=0o700)
        support=directory/'evaluation-support.py'
        content=subprocess.check_output(['git','-C',str(REPO),'show',revision+':scripts/deploy/evaluate-fegcraft-general-help.py'],timeout=15)
        ast.parse(content);support.write_bytes(content)
        spec=importlib.util.spec_from_file_location('minimal_prompt_support',support)
        base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
        os.environ['VECTOR_FEGCRAFT_GENERAL_DIAGNOSTIC']='1'
        print('Acht kurze synthetische Qwen-Aufrufe: Englisch/Deutsch und Chat/manuelles ChatML. Kein Download, Neustart oder Versand.',flush=True)
        print('Belege:',directory,flush=True)
        result=diagnose(base,directory)
        result['diagnostic_completed']=True
        result['interpretation']='Manual factual review required; neither native Jinja support nor raw output proves correctness. No automatic winner or activation.'
        (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2));print('Report:',directory/'result.json')
        print('Diagnose abgeschlossen. Minecraft unverändert; allgemeine Modellfunktion bleibt deaktiviert.')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)
        raise SystemExit(1)
