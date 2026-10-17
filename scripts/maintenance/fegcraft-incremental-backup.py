#!/usr/bin/env python3
"""Incremental staging while online, bounded stopped delta, owned Restic snapshots."""
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import secrets
import stat
import subprocess
import sys
import tempfile
import time

ROOT = Path('/root/vector-workspace')
BASE = Path('/opt/fegcraft-updated')
DATA = BASE / 'data'
BACKUPS = BASE / 'backups'
GAME = 'fegcraft-updated'
CANCELLED = False


def log(text):
    print('[' + datetime.now().astimezone().isoformat(timespec='seconds') + '] ' + text, flush=True)


def request_cancel(_signal, _frame):
    global CANCELLED
    CANCELLED = True
    log('Abbruch vorgemerkt. Laufender Schritt wird beendet; derselbe Container wird gegebenenfalls wieder gestartet.')


def check_cancel():
    if CANCELLED: raise RuntimeError('BACKUP_CANCELLED_AFTER_ACTIVE_COMMAND')


def safe(path):
    if any(p.is_symlink() for p in (path, *path.parents)): raise RuntimeError('UNEXPECTED_BACKUP_SYMLINK')


def run(args, *, output=None, timeout=30, diagnostic=None):
    if diagnostic is None:
        result = subprocess.run(args, stdout=output or subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    else:
        with diagnostic.open('wb') as errors:
            result = subprocess.run(args, stdout=output or subprocess.DEVNULL, stderr=errors, timeout=timeout)
    if result.returncode: raise RuntimeError('BACKUP_COMMAND_FAILED:' + args[0])
    return result.stdout


def inspect():
    return json.loads(run(['docker', 'inspect', GAME]))[0]


def owned(expected):
    value = inspect()
    if (value['Id'], value['Image']) != (expected['Id'], expected['Image']):
        raise RuntimeError('BACKUP_CONTAINER_REPLACED_NO_START')
    return value


def restart(expected, *, wait_for_stop=False):
    value = owned(expected)
    if wait_for_stop and value['State']['Running']:
        # A timed-out CLI does not cancel the daemon operation. Wait for its
        # original target to stop before attempting recovery, never a replacement.
        log('Kläre den ausstehenden Stop-Vorgang am ursprünglichen Container ...')
        try: run(['docker', 'wait', expected['Id']], timeout=180)
        except (RuntimeError, subprocess.TimeoutExpired):
            if owned(expected)['State']['Running']:
                raise RuntimeError('BACKUP_STOP_UNRESOLVED_OWNER_CHECK_REQUIRED')
        value = owned(expected)
        if value['State']['Running']: raise RuntimeError('BACKUP_STOP_UNRESOLVED_OWNER_CHECK_REQUIRED')
    if value['State'].get('Restarting'): raise RuntimeError('BACKUP_CONTAINER_RESTARTING')
    if not value['State']['Running']:
        log('Starte denselben Minecraft-Container ...')
        try: run(['docker', 'start', expected['Id']], timeout=90)
        except (RuntimeError, subprocess.TimeoutExpired):
            if not owned(expected)['State']['Running']: raise
    if not owned(expected)['State']['Running']: raise RuntimeError('BACKUP_SERVER_START_FAILED')


def ready(expected):
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        value = owned(expected); state = value['State']
        if not state['Running'] or state.get('OOMKilled') or state.get('Restarting'):
            raise RuntimeError('BACKUP_SERVER_NOT_RUNNING_AFTER_RESTART')
        if state.get('Health', {}).get('Status', 'healthy') == 'healthy': return
        time.sleep(2)
    raise RuntimeError('BACKUP_SERVER_HEALTH_TIMEOUT_ARCHIVE_RETAINED')


def required_space():
    total = 0
    for directory, dirs, files in os.walk(BASE, followlinks=False):
        parent = Path(directory)
        dirs[:] = [name for name in dirs if parent / name != BACKUPS]
        for name in [*dirs, *files]:
            path = parent / name
            if path == BASE / 'backup.log': continue
            meta = path.lstat()
            total += (meta.st_size if stat.S_ISREG(meta.st_mode) else 4096) + 1024
    # Uncompressed snapshot + gzip output, plus save/growth margin.
    return total * 2 + 512 * 1024 * 1024


def verify_bind(game):
    mounts = game.get('Mounts', [])
    if len(mounts) != 1 or not any(m.get('Type') == 'bind' and m.get('Source') == str(DATA)
               and m.get('Destination') == '/data' and m.get('RW') is True for m in mounts):
        raise RuntimeError('BACKUP_GAME_DATA_MOUNT_CHANGED')
    if game['State']['Running']:
        env = dict(v.split('=', 1) for v in game['Config'].get('Env', []) if '=' in v)
        uid, gid = env.get('UID', '1000'), env.get('GID', '1000')
        if not uid.isdecimal() or not gid.isdecimal() or int(uid) == 0 or int(gid) == 0:
            raise RuntimeError('BACKUP_GAME_USER_INVALID')
        raw = run(['docker', 'exec', '--user', uid + ':' + gid, game['Id'], 'stat', '-Lc', '%d:%i', '/data', '/data/world'])
        expected = ''.join(str(p.stat().st_dev) + ':' + str(p.stat().st_ino) + '\n' for p in (DATA, DATA / 'world'))
        if raw.decode() != expected: raise RuntimeError('BACKUP_LIVE_DATA_DIFFERS_FROM_HOST')


STATE = BACKUPS / '.vector-incremental'
STAGE = STATE / 'staging'
REPOSITORY = STATE / 'repository'
PASSWORD = STATE / 'password'
CONFIG = STATE / 'owner.json'
FINAL_SECONDS = 45
EXCLUDES = ('/backups/***', '/backup.log', '/data/logs/***', '/data/crash-reports/***', '/data/.cache/***')


def long_run(args, *, deadline, diagnostic, background=False, accepted=(0,)):
    """Private command output; public progress contains only phase elapsed time."""
    check_cancel(); started = time.monotonic(); last = started
    if background: args = ['ionice','-c','3','nice','-n','19',*args]
    with diagnostic.open('wb') as output:
        process = subprocess.Popen(args,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while process.poll() is None:
                if CANCELLED or time.monotonic() >= deadline:
                    raise RuntimeError('INCREMENTAL_CANCELLED' if CANCELLED else 'INCREMENTAL_PHASE_TIMEOUT')
                if time.monotonic() - last >= 30:
                    log('Schritt arbeitet weiter; vergangen: '+str(int(time.monotonic()-started))+' Sekunden.')
                    last = time.monotonic()
                time.sleep(.2)
            if process.returncode not in accepted: raise RuntimeError('INCREMENTAL_COMMAND_FAILED')
        finally:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGTERM)
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL); process.wait(timeout=5)


def restic(*args):
    return ['restic','--repo',str(REPOSITORY),'--password-file',str(PASSWORD),*args]


def repository_owner():
    for path in (STATE,STAGE,REPOSITORY,PASSWORD,CONFIG): safe(path)
    config=json.loads(CONFIG.read_bytes())
    if set(config) != {'schema','repository_id'} or config['schema'] != 1 or not isinstance(config['repository_id'],str) or not re_full_snapshot(config['repository_id']):
        raise RuntimeError('INCREMENTAL_OWNER_INVALID')
    for path in (STATE,PASSWORD,CONFIG):
        meta=path.stat()
        if meta.st_uid != 0 or meta.st_mode & 0o077: raise RuntimeError('INCREMENTAL_PRIVATE_PERMISSIONS_REQUIRED')
    actual=json.loads(run(restic('cat','config')))
    if actual.get('id') != config['repository_id'] or actual.get('version') != 2:
        raise RuntimeError('INCREMENTAL_REPOSITORY_ID_CHANGED')
    return config


def sync_stage(path, *, stopped=False):
    safe(STAGE); safe(BASE)
    if STAGE != BACKUPS/'.vector-incremental/staging' or not STAGE.is_dir(): raise RuntimeError('INCREMENTAL_STAGE_INVALID')
    args=['rsync','-aHAX','--numeric-ids','--modify-window=-1','--delete-delay','--stats']
    args += ['--exclude='+value for value in EXCLUDES]
    args += [str(BASE)+'/',str(STAGE)+'/']
    long_run(args,deadline=time.monotonic()+(FINAL_SECONDS if stopped else 10800),diagnostic=path,
             background=not stopped,accepted=(0,) if stopped else (0,24))


def make_snapshot(work):
    log('Minecraft darf wieder laufen. Restic speichert nur neue Datenblöcke im verwalteten Repository ...')
    diagnostic=work/'restic-backup.jsonl'
    long_run(restic('backup','--json','--host','fegcraft-updated','--tag','vector-nightly-v1',str(STAGE)),
             deadline=time.monotonic()+21600,diagnostic=diagnostic,background=True)
    summary=None
    with diagnostic.open('rb') as handle:
        for line in handle:
            if len(line)>1024*1024: raise RuntimeError('INCREMENTAL_SUMMARY_LIMIT')
            try: value=json.loads(line)
            except (ValueError,UnicodeError):continue
            if value.get('message_type')=='summary': summary=value
    if not summary or not isinstance(summary.get('snapshot_id'),str) or not re_full_snapshot(summary['snapshot_id']):
        raise RuntimeError('INCREMENTAL_SNAPSHOT_NOT_CONFIRMED')
    return summary


def re_full_snapshot(value):
    return len(value)==64 and all(c in '0123456789abcdef' for c in value)


def backup():
    os.umask(0o077)
    for command in ('docker','rsync','restic','ionice','nice'):
        if shutil.which(command) is None: raise RuntimeError('INCREMENTAL_DEPENDENCY_MISSING:'+command)
    repository_owner()
    for path in (BASE,DATA,DATA/'world',DATA/'world/level.dat',BASE/'docker-compose.yml'):safe(path)
    if not (DATA/'world/level.dat').is_file() or not (BASE/'docker-compose.yml').is_file(): raise RuntimeError('INCREMENTAL_SOURCE_MISSING')
    game=inspect(); verify_bind(game)
    if game.get('HostConfig',{}).get('AutoRemove') or game['State'].get('Restarting'): raise RuntimeError('INCREMENTAL_GAME_STATE_INVALID')
    needed=20*1024**3 if (STATE/'seeded').is_file() else max(20*1024**3,required_space())
    if shutil.disk_usage(BACKUPS).free < needed: raise RuntimeError('INCREMENTAL_LOW_SPACE_BEFORE_STOP')
    if (DATA/'world/level.dat').stat().st_size>16*1024**2: raise RuntimeError('INCREMENTAL_WORLD_HEADER_LIMIT')
    initial=[(p.stat().st_dev,p.stat().st_ino) for p in (DATA,DATA/'world')]
    work=STATE/('run-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3));work.mkdir(mode=0o700)
    log('Arbeitsbelege: '+str(work))
    log('Vorabgleich bei laufendem Minecraft. Die erste Kopie kann länger dauern; der Server wird dafür nicht angehalten.')
    sync_stage(work/'rsync-online.log')
    (STATE/'seeded').write_text('online-precopy-complete\n')
    check_cancel()
    was_running=game['State']['Running'];restart_needed=False;stop_confirmed=False
    with (ROOT/'.chat-release.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        current=owned(game)
        if (current['State']['Running']!=was_running or current['State']['StartedAt']!=game['State']['StartedAt']
                or initial!=[(p.stat().st_dev,p.stat().st_ino) for p in (DATA,DATA/'world')]):
            raise RuntimeError('INCREMENTAL_GAME_CHANGED_BEFORE_STOP')
        verify_bind(current)
        try:
            if was_running:
                log('Regulärer Stop desselben Containers; finaler Dateiabgleich danach auf 45 Sekunden begrenzt.')
                restart_needed=True
                run(['docker','stop','--time','120',game['Id']],timeout=180);stop_confirmed=True
            check_cancel();stopped=owned(game)
            if stopped['State']['Running'] or stopped['State'].get('OOMKilled') or stopped['State'].get('ExitCode',0) not in (0,143):
                raise RuntimeError('INCREMENTAL_CLEAN_STOP_NOT_CONFIRMED')
            sync_stage(work/'rsync-final.log',stopped=True)
            if owned(game)['State']['Running']:raise RuntimeError('INCREMENTAL_GAME_STARTED_DURING_FINAL_COPY')
            if initial!=[(p.stat().st_dev,p.stat().st_ino) for p in (DATA,DATA/'world')]:raise RuntimeError('INCREMENTAL_SOURCE_CHANGED_DURING_FINAL_COPY')
            for path in (STAGE/'data/world/level.dat',STAGE/'docker-compose.yml'):safe(path)
            expected=hashlib.sha256((STAGE/'data/world/level.dat').read_bytes()).hexdigest()
            if expected!=hashlib.sha256((DATA/'world/level.dat').read_bytes()).hexdigest():raise RuntimeError('INCREMENTAL_WORLD_HEADER_MISMATCH')
        finally:
            if restart_needed:restart(game,wait_for_stop=not stop_confirmed)
        if was_running:ready(game)
    # The stable staging tree is no longer modified until this locked run ends.
    check_cancel(); summary=make_snapshot(work); snapshot=summary['snapshot_id']
    restored=run(restic('dump',snapshot,str(STAGE/'data/world/level.dat')),timeout=120)
    if hashlib.sha256(restored).hexdigest()!=expected:raise RuntimeError('INCREMENTAL_RESTORE_PROBE_FAILED')
    repository_owner()
    result={'snapshot':snapshot,'consistent_staging_completed':True,'world_restore_probe_passed':True,
            'container_recreated':False,'same_container_id':game['Id'],'final_sync_limit_seconds':FINAL_SECONDS,
            'offline_total_limit_claimed':False,'initially_running':was_running,'old_archives_deleted':0,
            'writable_container_layer_included':False,
            'data_added_bytes':summary.get('data_added'),'files_unmodified':summary.get('files_unmodified'),
            'retention':{'daily':7,'weekly':4,'monthly':2}}
    (work/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    # Destructive maintenance is confined to the explicitly owned NEW repository.
    long_run(restic('forget','--host','fegcraft-updated','--tag','vector-nightly-v1','--keep-last','1',
             '--keep-daily','7','--keep-weekly','4','--keep-monthly','2'),deadline=time.monotonic()+3600,
             diagnostic=work/'retention.log',background=True)
    if datetime.now().weekday()==6:
        repository_owner()
        long_run(restic('prune'),deadline=time.monotonic()+21600,diagnostic=work/'prune.log',background=True)
    print(json.dumps(result,indent=2))
    log('Inkrementelles Backup mit Wiederleseprüfung abgeschlossen.')


def main():
    for path in (ROOT,BASE,BACKUPS,STATE,STAGE,ROOT/'.chat-release.lock',BACKUPS/'.backup.lock'):safe(path)
    with (BACKUPS/'.backup.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            log('Ein Backup läuft bereits. Kein weiterer Lauf gestartet.');return
        for signum in (signal.SIGINT,signal.SIGTERM):signal.signal(signum,request_cancel)
        backup()


if __name__=='__main__':
    try:
        if len(sys.argv)!=1:raise RuntimeError('INCREMENTAL_ARGUMENTS_INVALID')
        main()
    except BaseException as exc:
        log('FEHLER: '+(str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)+'. Bestehende tar/zip-Archive bleiben unangetastet; Arbeitsbelege bleiben erhalten.')
        raise SystemExit(1)
