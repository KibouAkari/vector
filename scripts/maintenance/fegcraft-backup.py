#!/usr/bin/env python3
"""Consistent persistent-folder backup; never recreate a container or purge archives."""
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
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


def backup():
    os.umask(0o077)
    for command in ('docker', 'tar', 'gzip'):
        if shutil.which(command) is None: raise RuntimeError('BACKUP_DEPENDENCY_MISSING:' + command)
    for path in (BASE, DATA, DATA / 'world', DATA / 'world/level.dat', BASE / 'docker-compose.yml', BACKUPS): safe(path)
    if not (DATA / 'world/level.dat').is_file() or not (BASE / 'docker-compose.yml').is_file():
        raise RuntimeError('BACKUP_EXPECTED_SERVER_FILES_MISSING')
    game = inspect()
    if game['State'].get('Restarting'): raise RuntimeError('BACKUP_GAME_IS_RESTARTING')
    if game.get('HostConfig', {}).get('AutoRemove'): raise RuntimeError('BACKUP_AUTO_REMOVE_CONTAINER_REFUSED')
    verify_bind(game)
    required = required_space(); free = shutil.disk_usage(BACKUPS).free
    if free < required: raise RuntimeError('BACKUP_INSUFFICIENT_SPACE_BEFORE_STOP')
    work = Path(tempfile.mkdtemp(prefix='.fegcraft-backup-', dir=BACKUPS))
    log('Privater Arbeitsordner: ' + str(work))
    plain, compressed = work / 'snapshot.tar', work / 'snapshot.tar.gz'
    was_running = game['State']['Running']; restart_needed = False; stop_confirmed = False
    try:
        if was_running:
            current = owned(game)
            if current['State']['StartedAt'] != game['State']['StartedAt']: raise RuntimeError('BACKUP_GAME_RESTARTED_DURING_PREFLIGHT')
            verify_bind(current)
            restart_needed = True  # Also recover after an ambiguous stop timeout.
            log('Stoppe Minecraft regulär für den Dateisnapshot ...')
            run(['docker', 'stop', '--time', '120', game['Id']], timeout=180)
            stop_confirmed = True
        check_cancel()
        stopped = owned(game)
        if stopped['State']['Running'] or stopped['State'].get('OOMKilled') or stopped['State'].get('ExitCode', 0) not in (0, 143):
            raise RuntimeError('BACKUP_CLEAN_STOP_NOT_CONFIRMED')
        log('Erstelle und vergleiche den Dateisnapshot ...')
        run(['tar', '--create', '--file', str(plain), '--directory', str(BASE), '--acls', '--xattrs', '--numeric-owner',
             '--exclude=./backups', '--exclude=./backup.log', '.'], timeout=21600, diagnostic=work / 'tar-create.stderr')
        check_cancel()
        if owned(game)['State']['Running']: raise RuntimeError('BACKUP_GAME_STARTED_DURING_SNAPSHOT')
        run(['tar', '--compare', '--file', str(plain), '--directory', str(BASE), '--acls', '--xattrs', '--numeric-owner'],
            timeout=21600, diagnostic=work / 'tar-compare.stderr')
        check_cancel()
        if owned(game)['State']['Running']: raise RuntimeError('BACKUP_GAME_STARTED_DURING_COMPARE')
    finally:
        if restart_needed:
            # Never start a same-named replacement or start an initially stopped game.
            restart(game, wait_for_stop=not stop_confirmed)
    log('Komprimiere und prüfe das Archiv; Minecraft darf inzwischen wieder laufen ...')
    with compressed.open('xb') as output:
        run(['gzip', '-1', '--stdout', str(plain)], output=output, timeout=21600, diagnostic=work / 'gzip.stderr')
        output.flush(); os.fsync(output.fileno())
    check_cancel()
    run(['gzip', '--test', str(compressed)], timeout=21600, diagnostic=work / 'gzip-test.stderr')
    run(['tar', '--list', '--gzip', '--file', str(compressed), './data/world/level.dat', './docker-compose.yml'],
        timeout=21600, diagnostic=work / 'tar-members.stderr')
    hashed = hashlib.sha256()
    with compressed.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''): hashed.update(block)
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M-%S')
    target = BACKUPS / ('fegcraft-updated_' + stamp + '_' + work.name.rsplit('-', 1)[-1] + '.tar.gz')
    os.link(compressed, target, follow_symlinks=False)  # Exclusive publication; no old archive overwritten.
    with Path(str(target) + '.sha256').open('x') as handle:
        handle.write(hashed.hexdigest() + '  ' + target.name + '\n'); handle.flush(); os.fsync(handle.fileno())
    fd = os.open(BACKUPS, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)
    result = {'archive': str(target), 'sha256': hashed.hexdigest(), 'source_compared_while_stopped': True,
              'gzip_verified': True, 'required_members_present': True, 'container_recreated': False,
              'same_container_id': game['Id'], 'initially_running': was_running,
              'container_writable_layer_included': False, 'old_backups_deleted': 0, 'messages_sent': 0}
    (work / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    # Delete only this run's redundant temporaries AFTER verified exclusive publication.
    plain.unlink(); compressed.unlink()
    log('Geprüftes Archiv: ' + str(target))
    if was_running: ready(game)
    print(json.dumps(result, indent=2))


def main():
    for path in (ROOT, BASE, BACKUPS, ROOT / '.chat-release.lock', BACKUPS / '.backup.lock'): safe(path)
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    with (ROOT / '.chat-release.lock').open('a') as global_lock, (BACKUPS / '.backup.lock').open('a') as backup_lock:
        fcntl.flock(global_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(backup_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, request_cancel)
        backup()


if __name__ == '__main__':
    try:
        if len(sys.argv) != 1: raise RuntimeError('BACKUP_UNEXPECTED_ARGUMENTS')
        main()
    except BaseException as exc:
        log('FEHLER: ' + (str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__) + '. Arbeitsdateien bleiben erhalten; kein altes Backup wird gelöscht.')
        raise SystemExit(1)
