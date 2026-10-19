"""Role-only connection and shared advisory contract; no app rows/model calls."""
import json
from pathlib import Path
import signal
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/minecraft-assistant'))
import psycopg
from psycopg.conninfo import conninfo_to_dict
from runtime import local_slot


def main():
    mode,path=sys.argv[1:]
    if mode not in ('busy','hold','ping'):raise RuntimeError('INVALID_PROBE_MODE')
    dsn=Path(path).read_text().strip()
    if conninfo_to_dict(dsn).get('user')!='vector_minecraft_slot':raise RuntimeError('ROLE_IDENTITY_REQUIRED')
    signal.alarm(15)
    if mode=='ping':
        with psycopg.connect(dsn,autocommit=True,connect_timeout=3) as db:
            row=db.execute('SELECT current_user, current_setting(\'default_transaction_read_only\')').fetchone()
            if row!=('vector_minecraft_slot','on'):raise RuntimeError('ROLE_SESSION_DEFAULTS_MISMATCH')
        print(json.dumps({'passed':True,'role_identity_and_default_verified':True}),flush=True)
    elif mode=='busy':
        try:
            with local_slot(dsn):raise RuntimeError('SLOT_WAS_NOT_BLOCKED')
        except RuntimeError as exc:
            if str(exc)!='LOCAL_BUSY':raise
        print(json.dumps({'passed':True,'shared_slot_busy_verified':True}),flush=True)
    else:
        with local_slot(dsn):
            print(json.dumps({'ready':True}),flush=True)
            if sys.stdin.readline().strip()!='release':raise RuntimeError('RELEASE_REQUIRED')
        print(json.dumps({'passed':True,'shared_slot_released':True}),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'passed':False,'error':str(exc) if type(exc) is RuntimeError else type(exc).__name__}),flush=True)
        raise SystemExit(1)
