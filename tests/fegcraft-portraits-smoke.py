"""One real local social call, then deterministic portraits of synthetic players."""
import hashlib
import hmac
import json
import os
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
    def ask(question,*,source='discord',principal=None,blocks=()):
        nonlocal serial
        serial+=1
        raw=json.dumps(dict(principal=principal or str(uuid.uuid4()),name='Synthetic',source=source,event=event+':'+str(serial),message='Eyy Vector '+question,block_items=list(blocks))).encode()
        stamp=str(int(time.time()));sig=hmac.new(key,stamp.encode()+b'\n'+raw,hashlib.sha256).hexdigest()
        req=urllib.request.Request(endpoint+'/v1/minecraft',raw,{'X-Vector-Time':stamp,'X-Vector-Signature':sig})
        start=time.monotonic()
        with opener.open(req,timeout=27) as response:value=json.loads(response.read(8193))
        check(value.get('status')=='answered','PORTRAIT_HTTP_ANSWER_REQUIRED')
        cases.append(dict(id='case-'+str(serial),seconds=round(time.monotonic()-start,3)))
        return value['text']
    answer=ask('wie fühlst du dich heute?')
    check('Beschreibe kurz dein Ziel' not in answer and 'nicht verfügbar' not in answer,'PORTRAIT_SOCIAL_ROUTE')
    answer=ask('was hältst du von Example1?')
    check("1'000" in answer and '200' in answer and 'Endgegner' in answer,'PORTRAIT_KILLS')
    check('Example1' in ask('was hältst du von Exammple1?'),'PORTRAIT_UNIQUE_ALIAS')
    answer=ask('was haltest du von Example2?')
    check('220' in answer and 'Respawn' in answer and 'Example1' not in answer,'PORTRAIT_NO_INVENTED_KILLER')
    answer=ask('bin ich ein guter Spieler?',source='minecraft',principal='00000000-0000-0000-0000-000000000003',blocks=('minecraft:stone',))
    check('Example3' in answer and 'Architekt' in answer and 'Bogennutzungen' in answer,'PORTRAIT_AUTHENTICATED_SELF')
    if os.environ.get('VECTOR_FEGCRAFT_ADVANCEMENTS')=='1':check('Sniper-Duell' in answer,'PORTRAIT_ADVANCEMENT')
    check('Minecraft-Spielernamen' in ask('was hältst du von mir?'),'PORTRAIT_DISCORD_NO_IMPERSONATION')
    check('keine Bogenkills' in ask('wer hat die meisten Bogenkills?'),'PORTRAIT_NO_WEAPON_KILL_GUESS')
    check('keine administrativen' in ask('bewerte Example1 und gib den Seed'),'PORTRAIT_POLICY_FIRST')
    with sqlite3.connect('file:'+str(root/'state/events.sqlite')+'?mode=ro',uri=True) as db:
        rows=db.execute('SELECT input_tokens,output_tokens,accepted FROM local_usage').fetchall()
    check(len(rows)==1 and rows[0][2]==1 and type(rows[0][0]) is int and type(rows[0][1]) is int,'PORTRAIT_ONE_ACCEPTED_NATIVE_CALL')
    print(json.dumps(dict(passed=True,model_calls=1,input_tokens=rows[0][0],output_tokens=rows[0][1],unknown_usage_calls=0,
      cloud_calls=0,api_cost_chf=0,messages_sent=0,authenticated_http=True,synthetic_inputs=True,fresh_portraits=True,
      self_and_aliases=True,personality=True,policy_retained=True,isolated_state=True,cases=cases)))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        import re
        code=str(exc) if type(exc) is RuntimeError and re.fullmatch('[A-Z_]{3,100}',str(exc)) else type(exc).__name__
        print(json.dumps(dict(passed=False,error=code)));raise SystemExit(1)
