#!/usr/bin/env python3
"""Compare existing local weights/formats, never qualify or activate gameplay."""
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
MODELS={
 'vector-qwen3:1.7b-q8':'97f1ed78571eac64f6b5b7413d9bc5f50fc95ab13ad4403cd813aebb9ba3a5b0',
 'vector-hermes3:8b-q4km':'ddd98889feddbec419ccb27c2839214c100ce4ebae74f16b12fe17f5c6572a20'}
PROMPT='Minecraft 26.2. Deutsch, maximal 200 Zeichen. JSON {"answer":"Text"}. Keine Begrüssung, Emojis, Links, Befehle oder Nachsätze. Nutze die Fakten. Antworte konkret auf die aktuelle Frage; bei Wie-Fragen nenne einen belegten Handlungsschritt. Ohne sichere Bedienschritte frage nach dem geöffneten Menü. Keine Serverrechte oder Einstellungen erfinden.'

# Only manifest metadata, no inference, configuration dump or credential output.
MANIFEST_JS=r"""
const r=await fetch('http://vector-local-inference:11434/api/tags',{redirect:'error',signal:AbortSignal.timeout(10000)});
if(!r.ok)throw Error('native-manifest');
const value=await r.json();if(!Array.isArray(value.models)||value.models.length>200)throw Error('manifest-shape');
const allowed=new Set(['vector-qwen3:1.7b-q8','vector-hermes3:8b-q4km']);
console.log(JSON.stringify(value.models.filter(m=>allowed.has(m.name)).map(m=>({name:m.name,digest:m.digest}))));
"""

CORE=r'''
import hashlib,json,re,sys,time,urllib.request
sys.path.insert(0,'/code/services/fegcraft-assistant')
import knowledge,runtime
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args):return None
http=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
endpoint='http://vector-local-inference:11434'
def native(path,payload,timeout):
 request=urllib.request.Request(endpoint+path,json.dumps(payload).encode(),{'Content-Type':'application/json'})
 with http.open(request,timeout=timeout) as response:raw=response.read(131073)
 if len(raw)>131072:raise ValueError('NATIVE_RESPONSE_LIMIT')
 return json.loads(raw)
metadata={}
try:
 show=native('/api/show',{'model':CONFIG['model']},8)
 template=show.get('template','');system=show.get('system','')
 if not isinstance(template,str) or not isinstance(system,str):raise ValueError('MODEL_METADATA_SHAPE')
 metadata={'template_sha256':hashlib.sha256(template.encode()).hexdigest(),
  'template_chatml_start':'<|im_start|>' in template,'template_chatml_end':'<|im_end|>' in template,
  'template_thinking_marker':'<think>' in template,'system_characters':len(system),
  'system_sha256':hashlib.sha256(system.encode()).hexdigest()}
except Exception as exc:metadata={'error':type(exc).__name__}
fixtures=[
 ('cow','Wie züchte ich Kühe in Minecraft?',(r'weizen',r'fütter|zwei|\b2\b'),[]),
 ('sheep','Wie vermehre ich Schafe in Minecraft?',(r'weizen',r'fütter|zwei|\b2\b'),[]),
 ('party-followup','Und wie gebe ich Mitgliedern Zugriff?',(r'recht|zugriff|menü',r'öffn|wähl|prüf|\b(?:welche[snmr]?|was)\b.*menü'),[
  {'role':'user','content':'Wozu sind Partys bei Open Parties and Claims gut?'},
  {'role':'assistant','content':'Partys verwalten Spielergruppen und Claim-Zugriffsrechte.'}]),
 ('glass','Wie bekomme ich Glas in Minecraft?',(r'sand',r'ofen|schmelz'),[])]
rows=[]
for index,(name,question,patterns,history) in enumerate(fixtures):
 if knowledge.forbidden(question):raise ValueError('SYNTHETIC_INPUT_FORBIDDEN')
 facts=[knowledge.FACTS['openpartiesandclaims']] if name=='party-followup' else []
 system=CONFIG['prompt'] if CONFIG['format']=='schema' else CONFIG['prompt'].replace('JSON {"answer":"Text"}.','Nur den Antworttext.')
 payload={'model':CONFIG['model'],'stream':False,'keep_alive':'5m',
  'options':{'temperature':.7,'top_p':.8,'top_k':20,'min_p':0,'seed':17,'num_ctx':2048,'num_predict':96,'num_thread':2},
  'messages':[{'role':'system','content':system},*history,{'role':'user','content':json.dumps({'facts':facts,'question':question},ensure_ascii=False)}]}
 if CONFIG['model']=='vector-qwen3:1.7b-q8':payload['think']=False
 if CONFIG['format']=='schema':payload['format']={'type':'object','properties':{'answer':{'type':'string','minLength':1,'maxLength':200,'pattern':knowledge.ANSWER_PATTERN}},'required':['answer'],'additionalProperties':False}
 started=time.monotonic();value=None;answer='';error=None;safe=False;complete=False;factual=False;schema_ok=False
 try:
  value=native('/api/chat',payload,25)
  if not isinstance(value,dict) or value.get('model')!=CONFIG['model']:raise ValueError('NATIVE_MODEL_MISMATCH')
  complete=value.get('done') is True and value.get('done_reason')=='stop'
  raw=value.get('message',{}).get('content','')
  if not isinstance(raw,str):raise ValueError('NATIVE_TEXT_SHAPE')
  if CONFIG['format']=='schema':
   content=json.loads(raw)
   if not isinstance(content,dict) or set(content)!={'answer'} or not isinstance(content['answer'],str):raise ValueError('ANSWER_SCHEMA')
   answer=content['answer']
  else:answer=raw
  schema_ok=True
  try:
   runtime.safe_answer(answer)
   safe=bool(re.fullmatch(knowledge.ANSWER_PATTERN,answer)) and not knowledge.forbidden(answer)
  except ValueError:pass
  factual=all(re.search(pattern,answer,re.I) for pattern in patterns)
  if name in ('cow','sheep') and re.search(r'mutterkuh|eggelung|16\s*tagen|nicht\s+(?:vermehr|zücht)',answer,re.I):factual=False
 except Exception as exc:error=str(exc) if isinstance(exc,ValueError) and re.fullmatch('[A-Z_]{1,80}',str(exc)) else type(exc).__name__
 seconds=round(time.monotonic()-started,3)
 def count(key):
  v=value.get(key) if isinstance(value,dict) else None
  return v if type(v) is int and v>=0 else None
 rows.append({'id':name,'seconds':seconds,'complete':complete,'format_valid':schema_ok,'display_safe':safe,'factual_fixture_passed':bool(factual),
  'latency_passed':seconds<=(25 if index==0 else 12),'error':error,'synthetic_answer':answer[:1000],
  'synthetic_raw_text':value.get('message',{}).get('content','')[:2048] if isinstance(value,dict) and isinstance(value.get('message'),dict) and isinstance(value['message'].get('content'),str) else '',
  'done_reason':value.get('done_reason') if isinstance(value,dict) else None,'input_tokens':count('prompt_eval_count'),'output_tokens':count('eval_count'),
  'thinking_present':bool(value.get('message',{}).get('thinking')) if isinstance(value,dict) and isinstance(value.get('message'),dict) else False,
  'load_seconds':count('load_duration')/1e9 if count('load_duration') is not None else None})
known=all(r[k] is not None for r in rows for k in ('input_tokens','output_tokens'))
print(json.dumps({'passed':False,'quality_passed':False,'eligible_for_activation':False,'evaluation_scope':'existing-model-format-diagnostic',
 'model':CONFIG['model'],'format':CONFIG['format'],'metadata':metadata,'cases':rows,'model_calls':len(rows),
 'input_tokens':sum(r['input_tokens'] for r in rows) if known else None,'output_tokens':sum(r['output_tokens'] for r in rows) if known else None,
 'known_input_tokens':sum(r['input_tokens'] for r in rows if r['input_tokens'] is not None),'known_output_tokens':sum(r['output_tokens'] for r in rows if r['output_tokens'] is not None),
 'unknown_usage_calls':sum(any(r[k] is None for k in ('input_tokens','output_tokens')) for r in rows),
 'cloud_calls':0,'api_cost_chf':0,'messages_sent':0,'production_activated':False,'ledger_writes':False}))
'''


def harness(model,output_format):
    if model not in MODELS or output_format not in ('schema','plain'):raise ValueError('UNAPPROVED_DIAGNOSTIC_VARIANT')
    return 'CONFIG='+repr(dict(model=model,format=output_format,prompt=PROMPT))+'\n'+CORE


def coordinator(source,model):
    if model not in MODELS:raise ValueError('UNAPPROVED_DIAGNOSTIC_MODEL')
    old="const model='vector-qwen3:1.7b-q8';"
    digest=MODELS['vector-qwen3:1.7b-q8']
    if source.count(old)!=1 or source.count(digest)!=1:raise RuntimeError('Coordinator source changed; no diagnostic.')
    return source.replace(old,'const model='+json.dumps(model)+';').replace(digest,MODELS[model])


def select_models(manifest):
    if not isinstance(manifest,list):raise RuntimeError('Invalid model manifest.')
    available={}
    for item in manifest:
        if not isinstance(item,dict) or item.get('name') not in MODELS or item['name'] in available:raise RuntimeError('Unexpected model manifest entry.')
        if item.get('digest')!=MODELS[item['name']]:raise RuntimeError('Model digest changed; no diagnostic.')
        available[item['name']]=item['digest']
    if 'vector-qwen3:1.7b-q8' not in available:raise RuntimeError('Baseline model missing; no diagnostic.')
    return [model for model in MODELS if model in available]


def compare(base,directory,manifest):
    reports=[];selected=select_models(manifest);original_command=base.command
    def bounded(*args,**kwargs):
        if args[:2]==('docker','run'):kwargs['timeout']=150
        return original_command(*args,**kwargs)
    base.command=bounded
    source=base.COORDINATOR;original_harness=base.HARNESS
    try:
        for model in selected:
            for output_format in ('schema','plain'):
                print('Lokaler Vergleich:',model,output_format,flush=True)
                base.COORDINATOR=coordinator(source,model);base.HARNESS=harness(model,output_format)
                phase=directory/(str(len(reports)+1)+'-phase.log')
                with phase.open('x') as log,redirect_stdout(log):result=base.evaluate()
                if not result or not result.get('production_unchanged') or not result.get('cleanup_verified') or not result.get('weights_unloaded'):
                    raise RuntimeError('Phase cleanup/state not verified; comparison stopped.')
                reports.append(result)
                print('Fertig:',sum(r['factual_fixture_passed'] and r['display_safe'] and r['complete'] for r in result['cases']),
                    '/',len(result['cases']),'Antworten bestehen die Diagnosekriterien.',flush=True)
    finally:base.command=original_command;base.COORDINATOR=source;base.HARNESS=original_harness
    complete=all(r[k] is not None for r in reports for k in ('input_tokens','output_tokens'))
    return dict(diagnostic_completed=True,passed=False,eligible_for_activation=False,production_activated=False,
        skipped_models=[model for model in MODELS if model not in selected],phases=reports,
        model_calls=sum(r['model_calls'] for r in reports),
        input_tokens=sum(r['input_tokens'] for r in reports) if complete else None,
        output_tokens=sum(r['output_tokens'] for r in reports) if complete else None,
        known_input_tokens=sum(r['known_input_tokens'] for r in reports),known_output_tokens=sum(r['known_output_tokens'] for r in reports),
        unknown_usage_calls=sum(r['unknown_usage_calls'] for r in reports),cloud_calls=0,api_cost_chf=0,messages_sent=0)


def main():
    os.umask(0o077);revision=os.environ.get('VECTOR_FEGCRAFT_REV','')
    if os.geteuid()!=0 or not re.fullmatch('[a-f0-9]{40}',revision):raise RuntimeError('Root and exact VECTOR_FEGCRAFT_REV required.')
    subprocess.run(['git','-C',str(REPO),'merge-base','--is-ancestor',revision,'origin/main'],check=True)
    with (ROOT/'.chat-release.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        directory=ROOT/'releases'/('vector-fegcraft-model-format-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3));directory.mkdir(mode=0o700)
        support=directory/'evaluation-support.py'
        content=subprocess.check_output(['git','-C',str(REPO),'show',revision+':scripts/deploy/evaluate-fegcraft-general-help.py'],timeout=15)
        ast.parse(content);support.write_bytes(content)
        spec=importlib.util.spec_from_file_location('format_diagnostic_support',support)
        base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
        before=base.fingerprint()
        if before['/vector-app']['image'] not in base.APP_IMAGES:raise RuntimeError('Observed app image changed.')
        manifest=json.loads(base.command('docker','exec','-i','vector-app','node','--input-type=module','-e',MANIFEST_JS,timeout=20))
        os.environ['VECTOR_FEGCRAFT_GENERAL_DIAGNOSTIC']='1'
        print('Nur vorhandene Modelle, synthetische Fragen und lokale Inferenz. Kein Download, Neustart oder Versand.',flush=True)
        print('Belege:',directory,flush=True)
        result=compare(base,directory,manifest)
        result.update(revision=revision,runtime_image=before['/vector-local-inference']['image'],production_unchanged=base.fingerprint()==before,cleanup_verified=True,weights_unloaded=True)
        (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        summary={k:v for k,v in result.items() if k!='phases'}
        summary['phases']=[dict(model=r['model'],format=r['format'],metadata=r['metadata'],report_path=r['report_path'],cases=[{k:c[k] for k in ('id','seconds','complete','format_valid','display_safe','factual_fixture_passed','latency_passed','error','synthetic_answer','input_tokens','output_tokens','load_seconds')} for c in r['cases']]) for r in result['phases']]
        print(json.dumps(summary,indent=2));print('Report:',directory/'result.json')
        if not result['production_unchanged']:raise RuntimeError('Production changed; no model may be activated.')
        print('Diagnose abgeschlossen. Allgemeine Modellfunktion bleibt deaktiviert; vollständige Qualifikation bleibt erforderlich.')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR:',str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)
        raise SystemExit(1)
