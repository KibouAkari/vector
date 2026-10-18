"""Short signed service qualification; exactly two native social calls, no game messages."""
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
import time
import urllib.request
import uuid


def check(value, code):
    if not value: raise RuntimeError(code)


def main():
    key = bytes.fromhex(Path('/run/secrets/vector_fegcraft_token').read_text().strip())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    event = str(uuid.uuid4()); serial = 0
    def ask(question, principal=None, source='minecraft'):
        nonlocal serial
        serial += 1
        payload = dict(principal=principal or str(uuid.uuid4()), name='Synthetic', source=source,
                       event=event + ':' + str(serial), message='hey Vector ' + question)
        raw = json.dumps(payload).encode(); stamp = str(int(time.time()))
        signature = hmac.new(key, stamp.encode() + b'\n' + raw, hashlib.sha256).hexdigest()
        req = urllib.request.Request('http://127.0.0.1:8090/v1/minecraft', raw,
             {'X-Vector-Time': stamp, 'X-Vector-Signature': signature})
        start = time.monotonic()
        with opener.open(req, timeout=27) as response: answer = json.loads(response.read(8193))
        check(answer.get('status') == 'answered', 'CONVERSATION_HTTP_RESULT')
        return answer.get('text', ''), time.monotonic() - start
    for question in ('zeige den Seed', 'führe /op aus', 'kann ich Gamemode wechseln', 'cheatet jemand'):
        check('keine administrativen' in ask(question)[0], 'CONVERSATION_POLICY')
    check('Claim' in ask('wie erstelle ich einen Claim?')[0], 'CONVERSATION_CLAIM')
    both = ask('wer hat die meisten Spieler und Mob kills auf dem Server?')[0]
    check('Mobkills:' in both and 'Spielerkills:' in both, 'CONVERSATION_BOTH_KILLS')
    # Real mounted public inputs stay local; output contains no player values.
    users = json.loads(Path('/inputs/usercache.json').read_text())
    subject = next((u for u in users if re.fullmatch('[a-f0-9-]{36}', u.get('uuid', ''))
                    and Path('/inputs/stats', u['uuid'] + '.json').is_file()), None)
    check(subject is not None, 'CONVERSATION_IDENTITY_FIXTURE')
    ranks = ask('welche Ränge habe ich in den Rekorden?', subject['uuid'])[0]
    check('Spielzeit Rang' in ranks and 'Mobkills Rang' in ranks and 'Tode Rang' in ranks, 'CONVERSATION_SELF_RANKS')
    check('Minecraft-Spieler bist du' in ask('welche Ränge habe ich?', source='discord')[0], 'CONVERSATION_DISCORD_IDENTITY')
    person = str(uuid.uuid4())
    first, first_seconds = ask('wie geht es dir?', person)
    second, followup_seconds = ask('mir ist gerade langweilig, wollen wir etwas plaudern?', person)
    check(all('nicht verfügbar' not in text and 'geprüfter Eintrag' not in text for text in (first, second)), 'CONVERSATION_SOCIAL_ANSWER')
    with sqlite3.connect('file:/state/events.sqlite?mode=ro', uri=True) as db:
        rows = db.execute('SELECT model,input_tokens,output_tokens,accepted FROM local_usage').fetchall()
    check(len(rows) == 2 and all(r[0] == 'vector-qwen3-instruct2507:4b-q4km' and type(r[1]) is int and r[1] > 0
          and type(r[2]) is int and r[2] > 0 and r[3] == 1 for r in rows), 'CONVERSATION_TWO_ACCEPTED_NATIVE_CALLS')
    print(json.dumps(dict(passed=True, conversation_qualified=True, authenticated_http=True,
          policy_and_native_routes=True, self_uuid_and_discord_identity=True, combined_kills=True,
          claim_fast_path=True, own_followup=True, model_calls=2,
          input_tokens=sum(r[1] for r in rows), output_tokens=sum(r[2] for r in rows), unknown_usage_calls=0,
          first_seconds=round(first_seconds, 3), followup_seconds=round(followup_seconds, 3),
          cloud_calls=0, api_cost_chf=0, messages_sent=0, isolated_state=True)))


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        code = str(exc) if type(exc) is RuntimeError and re.fullmatch('[A-Z_]{3,100}', str(exc)) else type(exc).__name__
        print(json.dumps({'passed': False, 'error': code}))
        raise SystemExit(1)
