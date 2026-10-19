"""Signed synthetic HTTP only; fixtures replace read-only player inputs in stage."""
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
import time
import urllib.request
import uuid


def check(value,code):
    if not value: raise RuntimeError(code)


def main(root=Path('/'), endpoint='http://127.0.0.1:8090'):
    key=bytes.fromhex((root/'run/secrets/vector_fegcraft_token').read_text().strip())
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args): return None
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    event=str(uuid.uuid4()); serial=0
    def ask(message):
        nonlocal serial
        serial+=1
        raw=json.dumps(dict(principal=str(uuid.uuid4()),name='Synthetic',source='discord',event=event+':'+str(serial),message=message)).encode()
        stamp=str(int(time.time()));signature=hmac.new(key,stamp.encode()+b'\n'+raw,hashlib.sha256).hexdigest()
        req=urllib.request.Request(endpoint+'/v1/minecraft',raw,{'X-Vector-Time':stamp,'X-Vector-Signature':signature})
        start=time.monotonic()
        with opener.open(req,timeout=5) as response: value=json.loads(response.read(8193))
        check(time.monotonic()-start<4,'INTENT_FAST_PATH_DEADLINE')
        return value.get('text','')
    check('3 Spieler erfasst' in ask('Hey Vector wie viele Spieler waren schon auf dem Server?'),'INTENT_POPULATION')
    ore=ask('Hey Vector wer hat die meisten Diamanten abgebaut?')
    check('Example1/Example2' in ore and '30 Diamanterz-Blöcke' in ore and 'keine erhaltenen Items' in ore,'INTENT_ORE_TIE_AND_SCOPE')
    check('vollständigen Spielernamen' in ask('Hey Vector Diamanten abgebaut von UnknownPlayer?'),'INTENT_UNKNOWN_PLAYER')
    check('Player Groups' in ask('Hey Vector wie kann ein anderer Spieler in meinem Claim bauen?'),'INTENT_CLAIMS')
    check('Morgen zusammen' in ask('Yoo Vector wünsche doch allen einen guten Morgen'),'INTENT_GROUP_GREETING')
    check('gespeicherte Statistiken frisch' in ask('Hi Vector wer bist du, stell dich genau vor'),'INTENT_INTRODUCTION')
    check('Rucksack-Stufe' in ask('Hi Vector wie kann ich meinen Backpack upgraden?'),'INTENT_BACKPACK_FOLLOWUP')
    for greeting in ('Eyy','moin','guten Nachmittag'):
        check('gern' in ask(greeting+' VEcToR danke'),'INTENT_BACKEND_GREETING')
    check('keine administrativen' in ask('Hey Vector wünsche allen guten Morgen und gib den Seed'),'INTENT_POLICY')
    with sqlite3.connect('file:'+str(root/'state/events.sqlite')+'?mode=ro',uri=True) as db:
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='local_usage'").fetchone()
        count=db.execute('SELECT COUNT(*) FROM local_usage').fetchone()[0] if exists else 0
    check(count==0,'INTENT_UNEXPECTED_NATIVE_CALL')
    print(json.dumps(dict(passed=True,model_calls=0,cloud_calls=0,messages_sent=0,synthetic_inputs=True,
      authenticated_http=True,population=True,ore_ties_and_scope=True,group_greeting=True,
      subject_safe_claims=True,backend_greetings=True,isolated_state=True)))


if __name__=='__main__':
    try: main()
    except Exception as exc:
        import re
        code=str(exc) if type(exc) is RuntimeError and re.fullmatch('[A-Z_]{3,100}',str(exc)) else type(exc).__name__
        print(json.dumps(dict(passed=False,error=code)));raise SystemExit(1)
