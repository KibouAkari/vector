#!/usr/bin/env python3
"""Arm the explicitly owner-authorized second welcome; addon schedules delivery after 15s."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from datetime import datetime

ROOT = Path('/root/vector-workspace')
DATA = Path('/opt/fegcraft-updated/data')
BASE = '8e1c6fcd9b9218f000b0dd4bb704d87d9cd73e66'


def run(*args):
    result = subprocess.run(args, capture_output=True, timeout=25)
    if result.returncode: raise RuntimeError('OWNER_WELCOME_CHECK_FAILED:' + args[0])
    return result.stdout


def safe(path):
    if any(p.is_symlink() for p in (path, *path.parents)): raise RuntimeError('WELCOME_SYMLINK_REFUSED')


def arm(directory, uid, gid, boot):
    if not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', boot): raise RuntimeError('INVALID_WELCOME_SESSION')
    marker = directory / 'owner-welcome-v2.attempted'; request = directory / 'owner-welcome-v2.ready'
    safe(marker); safe(request)
    if marker.exists() or request.exists(): return False
    temporary = directory / ('.owner-ready-' + secrets.token_hex(12))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write((boot + '\n').encode('ascii')); handle.flush()
            os.chown(temporary, uid, gid); os.fsync(handle.fileno())
        # Publish only after ownership is readable by the game; never replace an earlier signal.
        try: os.link(temporary, request, follow_symlinks=False)
        except FileExistsError: return False
    finally: temporary.unlink(missing_ok=True)
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)
    return True


def ready(value):
    state = value['State']
    if not state.get('Running') or state.get('Restarting') or state.get('Health', {}).get('Status') != 'healthy':
        raise RuntimeError('OWNER_WELCOME_SERVICES_NOT_READY')


def same_ready(before, after):
    ready(after)
    if (after['Id'], after['Image'], after['State']['StartedAt']) != (before['Id'], before['Image'], before['State']['StartedAt']):
        raise RuntimeError('WELCOME_CONTAINER_CHANGED')


def main():
    if os.geteuid() != 0 or os.environ.get('VECTOR_OWNER_WELCOME_V2') != '1':
        raise RuntimeError('EXPLICIT_OWNER_WELCOME_V2_REQUIRED')
    # Pinned ownership helper; no mutable current/ script is imported.
    source = run('git', '-C', str(ROOT / 'github/vector'), 'show', BASE + ':scripts/deploy/announce-fegcraft-assistant.py')
    namespace = {'__name__': 'owner_welcome_installation'}
    exec(compile(source, '<pinned-ownership-check>', 'exec'), namespace)
    service = json.loads(run('docker', 'inspect', 'vector-fegcraft-assistant'))[0]
    game = json.loads(run('docker', 'inspect', 'fegcraft-updated'))[0]
    _, manifest = namespace['installation'](service)
    for value in (service, game): ready(value)
    if game['Image'] != manifest['minecraft_image']: raise RuntimeError('WELCOME_GAME_IMAGE_CHANGED')
    directory = DATA / 'DiscordIntegration-Data/vector'; safe(directory)
    legacy = directory / 'introduction-v1.attempted'; safe(legacy)
    before = hashlib.sha256(legacy.read_bytes()).hexdigest()
    config = namespace['read'](directory / 'bridge.properties').decode()
    values = dict(line.split('=', 1) for line in config.splitlines() if '=' in line and not line.startswith('#'))
    if values.get('ownerWelcomeEnabled') != 'true' or values.get('introductionEnabled') != 'false':
        raise RuntimeError('NATIVE_OWNER_WELCOME_NOT_ENABLED')
    instance = directory / 'owner-welcome-v2.instance'; safe(instance)
    if not instance.is_file() or instance.stat().st_size > 64: raise RuntimeError('NATIVE_WELCOME_SESSION_MISSING')
    started = datetime.fromisoformat(game['State']['StartedAt'].replace('Z', '+00:00')).timestamp()
    if instance.stat().st_mtime < started: raise RuntimeError('STALE_WELCOME_SESSION')
    boot = instance.read_text().strip()
    user = service['Config'].get('User', '')
    if not re.fullmatch(r'[1-9][0-9]*:[1-9][0-9]*', user): raise RuntimeError('UNEXPECTED_WELCOME_USER')
    uid, gid = map(int, user.split(':'))
    # Confirm the same game still runs before creating its session-bound signal.
    after = json.loads(run('docker', 'inspect', 'fegcraft-updated'))[0]
    same_ready(game, after)
    same_ready(service, json.loads(run('docker', 'inspect', 'vector-fegcraft-assistant'))[0])
    created = arm(directory, uid, gid, boot)
    if hashlib.sha256(legacy.read_bytes()).hexdigest() != before: raise RuntimeError('LEGACY_WELCOME_MARKER_CHANGED')
    print(json.dumps({'owner_welcome_armed': created, 'duplicate_request_ignored': not created,
                      'delivery_route': 'native-vector-bridge', 'minimum_delay_after_ready_signal_seconds': 15,
                      'delivery_acknowledged': False, 'legacy_marker_retained': True,
                      'console_commands': 0, 'model_calls': 0, 'cloud_calls': 0}, indent=2))


if __name__ == '__main__':
    try:
        with (ROOT / '.chat-release.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            main()
    except Exception as exc:
        print('ERROR: ' + (str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__) + '. No automatic retry.', file=sys.stderr)
        raise SystemExit(1)
