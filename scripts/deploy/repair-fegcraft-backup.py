#!/usr/bin/env python3
"""Install a parsed, tested backup entrypoint; no game operations in this installer."""
import ast
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

ROOT = Path('/root/vector-workspace')
BASE = Path('/opt/fegcraft-updated')
REPO = ROOT / 'github/vector'
SOURCES = {'backup_minecraft.py': 'scripts/maintenance/fegcraft-backup.py',
           'backup_minecraft.sh': 'scripts/maintenance/fegcraft-backup.sh'}


def digest(data): return hashlib.sha256(data).hexdigest()


def safe(path):
    if any(p.is_symlink() for p in (path, *path.parents)): raise RuntimeError('BACKUP_REPAIR_SYMLINK')


def checked(path):
    safe(path)
    meta = path.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
        raise RuntimeError('BACKUP_REPAIR_UNEXPECTED_FILE_PERMISSIONS')
    if meta.st_size > 262144: raise RuntimeError('BACKUP_REPAIR_FILE_TOO_LARGE')
    return path.read_bytes()


def atomic(path, content, mode):
    safe(path)
    fd, name = tempfile.mkstemp(prefix='.vector-backup-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            os.fchmod(handle.fileno(), mode); handle.write(content); handle.flush(); os.fsync(handle.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def install(directory, sources):
    shell, engine = BASE / 'backup_minecraft.sh', BASE / 'backup_minecraft.py'
    previous = checked(shell)
    if engine.exists():
        if checked(engine) == sources[engine.name] and previous == sources[shell.name]:
            print('Backup-Reparatur ist bereits installiert. Kein Überschreiben.'); return False
        raise RuntimeError('BACKUP_REPAIR_ENGINE_ALREADY_EXISTS')
    result = subprocess.run(['bash', '-n'], input=previous, capture_output=True)
    if result.returncode == 0: raise RuntimeError('BACKUP_REPAIR_CURRENT_SCRIPT_VALID_REQUIRES_REVIEW')
    # Parse ALL new Python and Bash before any production write.
    ast.parse(sources[engine.name])
    subprocess.run(['bash', '-n'], input=sources[shell.name], check=True, capture_output=True)
    original = directory / 'original.sh'; atomic(original, previous, 0o600)
    record = {'original_sha256': digest(previous), 'original_mode': stat.S_IMODE(shell.stat().st_mode),
              'installed': {name: digest(value) for name, value in sources.items()}}
    atomic(directory / 'repair.json', (json.dumps(record, indent=2) + '\n').encode(), 0o600)
    # Shell remains broken if installation is interrupted before both replacements.
    atomic(engine, sources[engine.name], 0o700)
    try:
        if checked(shell) != previous: raise RuntimeError('BACKUP_REPAIR_SCRIPT_CHANGED')
        atomic(shell, sources[shell.name], 0o700)
    except BaseException:
        if engine.is_file() and not engine.is_symlink() and digest(engine.read_bytes()) == record['installed'][engine.name]: engine.unlink()
        raise
    print('Backup-Einstieg repariert. Original privat gesichert: ' + str(directory))
    return True


def rollback(directory):
    safe(directory)
    if directory.parent != ROOT / 'releases' or not directory.name.startswith('vector-fegcraft-backup-repair-'):
        raise RuntimeError('BACKUP_REPAIR_ROLLBACK_DIRECTORY_INVALID')
    record = json.loads(checked(directory / 'repair.json'))
    original = checked(directory / 'original.sh')
    if digest(original) != record['original_sha256']: raise RuntimeError('BACKUP_REPAIR_ORIGINAL_CHANGED')
    for name in SOURCES:
        if digest(checked(BASE / name)) != record['installed'][name]: raise RuntimeError('BACKUP_REPAIR_LATER_EDIT_PRESERVED')
    atomic(BASE / 'backup_minecraft.sh', original, record['original_mode'])
    (BASE / 'backup_minecraft.py').unlink()
    print('Nur Backup-Einstieg zurückgesetzt. Kein Containerbetrieb und keine Archivänderung.')


def classify(paths):
    known = {'/etc/hostname': 'docker-hostname', '/etc/hosts': 'docker-hosts',
             '/etc/resolv.conf': 'docker-dns', '/.dockerenv': 'docker-marker',
             '/etc/machine-id': 'system-machine-id', '/etc/localtime': 'system-timezone',
             '/etc/timezone': 'system-timezone', '/root/.bash_history': 'root-shell-history',
             '/home/minecraft/.bash_history': 'game-shell-history'}
    result = []
    for item in paths:
        path = item.get('path', '')
        if not isinstance(path, str) or not path.startswith('/') or item.get('change') not in ('A', 'C', 'D'):
            raise RuntimeError('BACKUP_REPAIR_INVALID_PRIVATE_AUDIT')
        result.append({'category': known.get(path, 'owner-local-review-required'),
                       'change': item['change'], 'path_sha256': digest(path.encode())})
    return result


def main():
    if os.geteuid() != 0: raise RuntimeError('ROOT_OWNER_REQUIRED')
    os.umask(0o077)
    for path in (ROOT, BASE, BASE / 'backups'): safe(path)
    (BASE / 'backups').mkdir(mode=0o700, exist_ok=True)
    for path in (ROOT / '.chat-release.lock', BASE / 'backups/.backup.lock'): safe(path)
    with (ROOT / '.chat-release.lock').open('a') as release_lock, (BASE / 'backups/.backup.lock').open('a') as backup_lock:
        fcntl.flock(release_lock, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.flock(backup_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if len(sys.argv) == 3 and sys.argv[1] == '--rollback': return rollback(Path(sys.argv[2]))
        if len(sys.argv) != 1: raise RuntimeError('BACKUP_REPAIR_UNEXPECTED_ARGUMENTS')
        revision = os.environ.get('VECTOR_BACKUP_REV', '')
        if not re.fullmatch('[a-f0-9]{40}', revision): raise RuntimeError('BACKUP_REPAIR_PIN_REQUIRED')
        sources = {}
        for name, source in SOURCES.items():
            sources[name] = subprocess.check_output(['git', '-C', str(REPO), 'show', revision + ':' + source], timeout=20)
        directory = Path(tempfile.mkdtemp(prefix='vector-fegcraft-backup-repair-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-', dir=ROOT / 'releases'))
        changed = install(directory, sources)
        # Explain the existing gate without exposing arbitrary host filenames/content.
        audit = ROOT / 'releases/vector-fegcraft-safe-cutover-20261017T150617Z-3f2b4c/before-private-writable-paths.json'
        if audit.exists():
            print(json.dumps({'writable_layer_review': classify(json.loads(checked(audit))), 'recreation_still_blocked': True}, indent=2))
        print('Keine Containeraktion durchgeführt. Backup jetzt separat starten: /opt/fegcraft-updated/backup_minecraft.sh')
        if changed: print('Rückrollaufruf: python3 ' + str(Path(__file__).resolve()) + ' --rollback ' + str(directory))


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print('ERROR: ' + (str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__) + '. Keine Neuerstellung oder Begrüssung.', file=sys.stderr)
        raise SystemExit(1)
