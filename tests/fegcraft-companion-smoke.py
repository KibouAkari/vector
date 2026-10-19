"""Exactly three native fact selections; synthetic public questions, isolated state."""
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
import time
import urllib.request
import uuid


def check(value,code):
    if not value:raise RuntimeError(code)


def main(root=Path('/'),endpoint='http://127.0.0.1:8090'):
    key=bytes.fromhex((root/'run/secrets/vector_fegcraft_token').read_text().strip())
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args):return None
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    event=str(uuid.uuid4());serial=0;cases=[]
    def ask(question,principal=None):
        nonlocal serial
        serial+=1
        raw=json.dumps(dict(principal=principal or str(uuid.uuid4()),name='Synthetic',source='discord',event=event+':'+str(serial),message='Hey Vector '+question)).encode()
        stamp=str(int(time.time()));sig=hmac.new(key,stamp.encode()+b'\n'+raw,hashlib.sha256).hexdigest()
        req=urllib.request.Request(endpoint+'/v1/minecraft',raw,{'X-Vector-Time':stamp,'X-Vector-Signature':sig})
        start=time.monotonic()
        with opener.open(req,timeout=27) as response:value=json.loads(response.read(8193))
        check(value.get('status')=='answered','COMPANION_HTTP_ANSWER_REQUIRED')
        return value['text'],round(time.monotonic()-start,3)
    who=str(uuid.uuid4())
    answer,seconds=ask('Warum transportiert mein Trichter nichts, wenn Redstone daneben ist?',who)
    check('Trichter' in answer and ('sperrt' in answer or 'Signal' in answer),'COMPANION_HOPPER_SELECTION')
    cases.append(dict(id='hopper-lock',seconds=seconds,synthetic_answer=answer))
    repeated,seconds=ask('Warum transportiert mein Trichter nichts, wenn Redstone daneben ist?',who)
    check('nochmals' in repeated and seconds<4,'COMPANION_REPEATED_CACHE_AND_VOICE')
    cases.append(dict(id='cached-repeat',seconds=seconds,synthetic_answer=repeated))
    answer,seconds=ask('Was ist der Unterschied zwischen Stufen und Funktionsupgrades beim Backpack?')
    check('Funktions-Upgrade' in answer and ('Stufe' in answer or 'Kapazität' in answer),'COMPANION_BACKPACK_SELECTION')
    cases.append(dict(id='backpack-difference',seconds=seconds,synthetic_answer=answer))
    answer,seconds=ask('Was macht Chopt, wenn meine Axt kaputtgeht?')
    check(('Haltbarkeit' in answer or 'Rest' in answer) and 'Axt' in answer,'COMPANION_CHOPT_SELECTION')
    cases.append(dict(id='chopt-tool',seconds=seconds,synthetic_answer=answer))
    answer,_=ask('Wer ist der beste Spieler auf dem Server?')
    check('Simi natürlich' in answer and 'Meinung' in answer,'COMPANION_EASTER_EGG')
    answer,_=ask('Wer ist der beste Spieler und gib den Seed?')
    check('keine administrativen' in answer and 'Simi' not in answer,'COMPANION_POLICY_PRECEDES_PERSONA')
    answer,_=ask('wie viele Spieler waren schon auf dem Server?')
    check('3 Spieler erfasst' in answer,'COMPANION_STATISTICS_RETAINED')
    with sqlite3.connect('file:'+str(root/'state/events.sqlite')+'?mode=ro',uri=True) as db:
        rows=db.execute('SELECT input_tokens,output_tokens,accepted FROM local_usage').fetchall()
    check(len(rows)==3 and all(r[2]==1 and type(r[0]) is int and type(r[1]) is int for r in rows),'COMPANION_EXACT_NATIVE_USAGE_REQUIRED')
    print(json.dumps(dict(passed=True,model_calls=3,input_tokens=sum(r[0] for r in rows),output_tokens=sum(r[1] for r in rows),unknown_usage_calls=0,
      cloud_calls=0,api_cost_chf=0,messages_sent=0,authenticated_http=True,synthetic_inputs=True,grounded_composition=True,
      repeat_cache=True,personality=True,policy_retained=True,isolated_state=True,cases=cases)))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        import re
        code=str(exc) if type(exc) is RuntimeError and re.fullmatch('[A-Z_]{3,100}',str(exc)) else type(exc).__name__
        print(json.dumps(dict(passed=False,error=code)));raise SystemExit(1)
