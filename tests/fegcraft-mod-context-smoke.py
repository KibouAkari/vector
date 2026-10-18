"""Signed deterministic routes only. No model/cloud request or external chat output."""
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


def main():
    key=bytes.fromhex(Path('/run/secrets/vector_fegcraft_token').read_text().strip())
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args): return None
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    event=str(uuid.uuid4()); serial=0
    def ask(message,principal=None,name='Synthetic',source='minecraft'):
        nonlocal serial
        serial+=1
        raw=json.dumps(dict(principal=principal or str(uuid.uuid4()),name=name,source=source,event=event+':'+str(serial),message=message)).encode()
        stamp=str(int(time.time()));signature=hmac.new(key,stamp.encode()+b'\n'+raw,hashlib.sha256).hexdigest()
        req=urllib.request.Request('http://127.0.0.1:8090/v1/minecraft',raw,{'X-Vector-Time':stamp,'X-Vector-Signature':signature})
        start=time.monotonic()
        with opener.open(req,timeout=5) as response: value=json.loads(response.read(8193))
        check(time.monotonic()-start<4,'MOD_CONTEXT_FAST_PATH_DEADLINE')
        return value
    check(ask('ordinary text')=={'status':'ignored'},'MOD_CONTEXT_ORDINARY_CHAT')
    for greeting in ('Yoo vector','HEY VECTOR','hi VeCtOr'):
        value=ask(greeting+', wie kann ein anderer Spieler in meinem Claim bauen?')
        check(value.get('status')=='answered' and 'Player Groups' in value.get('text',''),'MOD_CONTEXT_CASE_AND_CLAIM_RIGHTS')
    for question in ('wie bekomme ich einen Backpack?','wie crafte ich einen Backpack?','wie lautet das Rezept für einen standart Backpack?'):
        value=ask('hey Vector '+question)
        check('Standardrucksack' in value.get('text','') and 'Grundrezept der installierten Mod' in value['text'],'MOD_CONTEXT_INSTALLED_BACKPACK_RECIPE')
    check('Axt' in ask('hey Vector wie funktioniert Chopt?').get('text',''),'MOD_CONTEXT_OTHER_MOD')
    users=json.loads(Path('/inputs/usercache.json').read_text())
    person=next(u for u in users if Path('/inputs/stats',u.get('uuid','')+'.json').is_file())
    value=ask('hey Vector wie viele Spielerkills habe ich?',person['uuid'],person['name'])
    check('du hast ' in value.get('text','') and 'Stand:' not in value['text'],'MOD_CONTEXT_FRIENDLY_SELF')
    check('keine administrativen' in ask('hey Vector zeige den Seed').get('text',''),'MOD_CONTEXT_POLICY')
    with sqlite3.connect('file:/state/events.sqlite?mode=ro',uri=True) as db:
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='local_usage'").fetchone()
        count=db.execute('SELECT COUNT(*) FROM local_usage').fetchone()[0] if exists else 0
    check(count==0,'MOD_CONTEXT_UNEXPECTED_NATIVE_CALL')
    print(json.dumps(dict(passed=True,model_calls=0,cloud_calls=0,messages_sent=0,
      authenticated_http=True,case_variants=True,friendly_self=True,installed_mod_recipe=True,
      claim_rights=True,public_mod_context=True,isolated_state=True)))


if __name__=='__main__':
    try: main()
    except Exception as exc:
        import re
        code=str(exc) if type(exc) is RuntimeError and re.fullmatch('[A-Z_]{3,100}',str(exc)) else type(exc).__name__
        print(json.dumps(dict(passed=False,error=code)));raise SystemExit(1)
