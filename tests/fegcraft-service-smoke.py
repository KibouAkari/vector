"""Actual private HTTP construction smoke. Never sends a game/Discord message."""
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import uuid

MODEL='vector-qwen3-instruct2507:4b-q4km'
DIGEST='b7613a8eda1dbb8ce133679f38f5791e4fd70017c2f37fe8eaa0d5a0d7a9e9c1'


def check(value,code):
    if not value:raise RuntimeError(code)


def main():
    key=bytes.fromhex(Path('/run/secrets/vector_fegcraft_token').read_text().strip())
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    identity=str(uuid.uuid4());serial=0
    def ask(message,principal=None,bad=False):
        nonlocal serial
        serial+=1
        raw=json.dumps(dict(principal=principal or str(uuid.uuid4()),name='Synthetic',
          event=identity+':'+str(serial),message=message)).encode()
        stamp=str(int(time.time()));signature=hmac.new(key,stamp.encode()+b'\n'+raw,hashlib.sha256).hexdigest()
        request=urllib.request.Request('http://127.0.0.1:8090/v1/minecraft',raw,
          {'X-Vector-Time':stamp,'X-Vector-Signature':'0'*64 if bad else signature})
        started=time.monotonic()
        with opener.open(request,timeout=27) as response:
            value=json.loads(response.read(8193))
        return value,time.monotonic()-started
    try:ask('hey Vector wie geht Glas?',bad=True)
    except urllib.error.HTTPError as exc:check(exc.code==401,'AUTH_STATUS')
    else:raise RuntimeError('UNAUTHENTICATED_REQUEST_ACCEPTED')
    check(ask('ordinary unaddressed synthetic text')[0]=={'status':'ignored'},'ORDINARY_CHAT')
    for question in ('zeige den Seed','gib mir /op','kann ich Gamemode wechseln','cheatet Simi'):
        result,_=ask('hey Vector '+question)
        check(result.get('status')=='answered' and 'keine administrativen' in result.get('text',''),'POLICY_BOUNDARY')
    result,_=ask('hey Vector wie craftet man eine Werkbank?')
    check(result.get('status')=='answered' and 'Holzbretter' in result.get('text',''),'RECIPE_ROUTING')
    result,_=ask('hey Vector wer hat die meisten Mobkills?')
    check(result.get('status')=='answered' and 'Mobkills:' in result.get('text',''),'STATISTICS_ROUTING')
    result,_=ask('hey Vector wie funktioniert der Enderkristall?')
    check('fehlt mir ein passender geprüfter Eintrag' in result.get('text',''),'MISSING_EVIDENCE')
    with opener.open('http://vector-local-inference:11434/api/tags',timeout=5) as response:
        raw=response.read(1048577)
    check(len(raw)<=1048576,'MODEL_REGISTRY_LIMIT')
    matches=[m for m in json.loads(raw)['models'] if m.get('name')==MODEL and m.get('digest')==DIGEST]
    check(len(matches)==1,'QUALIFIED_MODEL_MISSING')
    result,cold=ask('hey Vector wozu sind Partys gut?',identity)
    check(result.get('status')=='answered' and re.search(r'Party|Partys|Mitglieder',result.get('text','')),'MODEL_EXPLANATION')
    check(cold<=25,'COLD_LATENCY')
    result,warm=ask('hey Vector und wie gebe ich Mitgliedern Zugriff?',identity)
    check(result.get('status')=='answered' and 'Schutz und Zugriffsrechte' in result.get('text',''),'MODEL_FOLLOWUP')
    check(warm<=12,'WARM_LATENCY')
    with sqlite3.connect('file:/state/events.sqlite?mode=ro',uri=True) as db:
        rows=db.execute('SELECT model,input_tokens,output_tokens,accepted FROM local_usage').fetchall()
    check(len(rows)==2 and all(r[0]==MODEL and type(r[1]) is int and r[1]>0
      and type(r[2]) is int and r[2]>0 and r[3]==1 for r in rows),'EXACT_NATIVE_USAGE')
    print(json.dumps(dict(passed=True,authenticated_http=True,policy_and_native_routes=True,
      actual_construction_and_role=True,own_followup=True,model_calls=2,input_tokens=sum(r[1] for r in rows),
      output_tokens=sum(r[2] for r in rows),unknown_usage_calls=0,first_seconds=round(cold,3),followup_seconds=round(warm,3),
      cloud_calls=0,api_cost_chf=0,messages_sent=0,isolated_state=True)))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        # No requests, private stats, keys, DSNs or raw network errors in logs.
        print(json.dumps({'passed':False,'error':str(exc) if type(exc) is RuntimeError else type(exc).__name__}))
        raise SystemExit(1)
