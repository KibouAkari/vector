#!/usr/bin/env python3
"""Read-only persistence audit. No restart, delete, model request or chat message."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
import secrets

ROOT = Path('/root/vector-workspace')
DATA = Path('/opt/fegcraft-updated/data')
COMPOSE = DATA.parent / 'docker-compose.yml'
GAME = 'fegcraft-updated'


def run(*args):
    result = subprocess.run(args, capture_output=True, timeout=30)
    if result.returncode: raise RuntimeError('PERSISTENCE_COMMAND_FAILED:' + args[0])
    if len(result.stdout) > 2_000_000: raise RuntimeError('PERSISTENCE_DIAGNOSTIC_TOO_LARGE')
    return result.stdout


def safe(path):
    if any(p.is_symlink() for p in (path, *path.parents)): raise RuntimeError('PERSISTENCE_SYMLINK_REFUSED')


def validate(game, profile, data):
    state = game['State']
    if not state.get('Running') or state.get('Restarting') or state.get('Health', {}).get('Status') != 'healthy':
        raise RuntimeError('GAME_NOT_READY')
    labels = game['Config'].get('Labels') or {}
    service = labels.get('com.docker.compose.service', '')
    if (not re.fullmatch(r'[A-Za-z0-9_-]+', service)
            or labels.get('com.docker.compose.project.config_files') != str(data.parent / 'docker-compose.yml')
            or labels.get('com.docker.compose.project.working_dir') != str(data.parent)):
        raise RuntimeError('GAME_COMPOSE_OWNERSHIP_CHANGED')
    mounts = game.get('Mounts', [])
    if len(mounts) != 1 or any(m.get('Type') != 'bind' or m.get('Source') != str(data)
            or m.get('Destination') != '/data' or m.get('RW') is not True for m in mounts):
        raise RuntimeError('GAME_MOUNTS_REQUIRE_PERSISTENCE_REVIEW')
    config = profile.get('services', {}).get(service, {})
    if any(config.get(key) for key in ('tmpfs', 'volumes_from', 'configs', 'secrets', 'devices', 'use_api_socket')):
        raise RuntimeError('ADDITIONAL_COMPOSE_MOUNTS_REQUIRE_REVIEW')
    volumes = config.get('volumes', [])
    if len(volumes) != 1 or any(v.get('type') != 'bind' or v.get('source') != str(data)
            or v.get('target') != '/data' or v.get('read_only', False) is not False for v in volumes):
        raise RuntimeError('PERSISTENT_COMPOSE_DATA_MOUNT_DIFFERS')
    if any(config.get(key) is not None for key in ('command', 'entrypoint', 'pre_start', 'post_start', 'pre_stop', 'build')):
        raise RuntimeError('CUSTOM_STARTUP_REQUIRES_REVIEW')
    env = config.get('environment', {})
    running = dict(value.split('=', 1) for value in game['Config'].get('Env', []) if '=' in value)
    if any(running.get(key) != value for key, value in env.items()):
        raise RuntimeError('PENDING_GAME_ENVIRONMENT_CHANGES_REQUIRE_REVIEW')
    if env.get('VERSION') != '26.2' or running.get('VERSION') != '26.2':
        raise RuntimeError('PERSISTENT_GAME_VERSION_NOT_QUALIFIED')
    if str(env.get('TYPE', '')).lower() != 'fabric' or str(running.get('TYPE', '')).lower() != 'fabric':
        raise RuntimeError('PERSISTENT_SERVER_TYPE_NOT_FABRIC')
    # Refuse startup download/replacement mechanisms until their effects are reviewed.
    for key in ('REMOVE_OLD_MODS', 'REMOVE_OLD_CONFIGS', 'FORCE_WORLD_COPY', 'FORCE_REDOWNLOAD'):
        if any(str(source.get(key, '')).lower() not in ('', 'false', '0', 'none') for source in (env, running)):
            raise RuntimeError('DESTRUCTIVE_STARTUP_OPTION_REQUIRES_REVIEW')
    for key in ('WORLD', 'MODPACK', 'GENERIC_PACK', 'PACKWIZ_URL', 'MODRINTH_MODPACK', 'FTB_MODPACK_ID',
                'PRE_START_SCRIPT', 'POST_START_SCRIPT', 'RCON_CMDS_STARTUP'):
        if env.get(key) or running.get(key): raise RuntimeError('STARTUP_DOWNLOAD_REQUIRES_REVIEW')
    for key in ('UID', 'GID'):
        if str(env.get(key, '1000')) != str(running.get(key, '1000')):
            raise RuntimeError('PERSISTENT_GAME_USER_DIFFERS')
    if game['HostConfig'].get('AutoRemove'): raise RuntimeError('AUTO_REMOVE_CONTAINER_REFUSED')
    return service


def unpersisted(diff):
    # Only known runtime directories/account metadata are disposable. Unknown
    # writable-layer paths are recorded privately and block the readiness gate.
    accounts = {'/etc/passwd', '/etc/group', '/etc/shadow', '/etc/gshadow',
                '/etc/passwd-', '/etc/group-', '/etc/shadow-', '/etc/gshadow-'}
    parents = {'/etc', '/home', '/home/minecraft', '/var'}
    runtime = ('/tmp', '/run', '/var/run', '/var/tmp')
    unknown = []
    for line in diff.decode().splitlines():
        kind, separator, path = line.partition(' ')
        if kind not in ('A', 'C', 'D') or not separator or not path.startswith('/'):
            raise RuntimeError('INVALID_WRITABLE_LAYER_REPORT')
        if path in accounts or (kind == 'C' and path in parents): continue
        if any(path == base or path.startswith(base + '/') for base in runtime): continue
        unknown.append({'change': kind, 'path': path})
    return unknown


def live_identity(raw, root_meta, world_meta):
    lines = raw.decode().splitlines()
    if len(lines) != 2 or any(not re.fullmatch(r'[0-9]+:[0-9]+', line) for line in lines):
        raise RuntimeError('LIVE_DIRECTORY_IDENTITY_INVALID')
    values = [tuple(map(int, line.split(':'))) for line in lines]
    if values != [(root_meta.st_dev, root_meta.st_ino), (world_meta.st_dev, world_meta.st_ino)]:
        raise RuntimeError('LIVE_BIND_DIFFERS_FROM_HOST_DIRECTORY')


def audit():
    game = json.loads(run('docker', 'inspect', GAME))[0]
    project = (game['Config'].get('Labels') or {}).get('com.docker.compose.project', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', project): raise RuntimeError('GAME_PROJECT_NOT_IDENTIFIED')
    safe(COMPOSE); before = hashlib.sha256(COMPOSE.read_bytes()).hexdigest()
    profile = json.loads(run('docker', 'compose', '--project-directory', str(DATA.parent), '-p', project,
                             '-f', str(COMPOSE), 'config', '--format', 'json'))
    service = validate(game, profile, DATA)
    for path in (DATA, DATA / 'world', DATA / 'world/players/stats', DATA / 'mods', DATA / 'config'):
        safe(path)
        if not path.is_dir(): raise RuntimeError('EXPECTED_PERSISTENT_DIRECTORY_MISSING')
    level = DATA / 'world/level.dat'; safe(level)
    meta = level.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_size <= 0: raise RuntimeError('WORLD_LEVEL_FILE_UNAVAILABLE')
    properties = (DATA / 'server.properties'); safe(properties)
    fields = {}
    for line in properties.read_text().splitlines():
        key, separator, value = line.partition('=')
        if separator and not line.startswith(('#', '!')): fields[key.strip()] = value.strip()
    if fields.get('level-name', 'world') != 'world' or profile['services'][service].get('environment', {}).get('LEVEL', 'world') != 'world':
        raise RuntimeError('WORLD_PATH_REQUIRES_REVIEW')
    image = profile['services'][service].get('image', '')
    if not image or json.loads(run('docker', 'image', 'inspect', image))[0]['Id'] != game['Image']:
        raise RuntimeError('LOCAL_IMAGE_TAG_DIFFERS_FROM_RUNNING_GAME')
    root_meta = DATA.stat(); world_meta = (DATA / 'world').stat()
    env = dict(value.split('=', 1) for value in game['Config'].get('Env', []) if '=' in value)
    uid, gid = env.get('UID', '1000'), env.get('GID', '1000')
    if not all(re.fullmatch(r'[1-9][0-9]{0,5}', value) for value in (uid, gid)):
        raise RuntimeError('GAME_STAT_USER_INVALID')
    def check_live():
        live_identity(run('docker', 'exec', '--user', uid + ':' + gid, GAME, 'stat', '-Lc', '%d:%i', '/data', '/data/world'), root_meta, world_meta)
    check_live()
    unknown = unpersisted(run('docker', 'diff', GAME))
    after = json.loads(run('docker', 'inspect', GAME))[0]
    if (after['Id'], after['Image'], after['State']['StartedAt']) != (game['Id'], game['Image'], game['State']['StartedAt']):
        raise RuntimeError('GAME_CHANGED_DURING_AUDIT')
    validate(after, profile, DATA)
    check_live()
    if hashlib.sha256(COMPOSE.read_bytes()).hexdigest() != before: raise RuntimeError('COMPOSE_CHANGED_DURING_AUDIT')
    if (DATA.stat().st_dev, DATA.stat().st_ino, (DATA / 'world').stat().st_dev, (DATA / 'world').stat().st_ino) != (root_meta.st_dev, root_meta.st_ino, world_meta.st_dev, world_meta.st_ino):
        raise RuntimeError('PERSISTENT_DIRECTORIES_CHANGED')
    return {'persistence_checks_passed': not unknown, 'same_host_data_bind': True, 'same_world_directory': True, 'live_container_directories_match_host': True,
            'persistent_version': '26.2', 'extra_writable_layer_paths': len(unknown),
            'fabric_loader_pinned_to_0_19_5': profile['services'][service].get('environment', {}).get('FABRIC_LOADER_VERSION') == '0.19.5',
            'data_directory_identity': [root_meta.st_dev, root_meta.st_ino],
            'world_directory_identity': [world_meta.st_dev, world_meta.st_ino],
            'game_container': game['Id'], 'game_image': game['Image'], 'compose_sha256': before,
            'production_unchanged': True, 'backup_verified': False, 'restart_performed': False,
            'messages_sent': 0, 'data_loss_guarantee': False}, unknown


def main():
    if os.geteuid() != 0: raise RuntimeError('ROOT_OWNER_REQUIRED')
    os.umask(0o077)
    with (ROOT / '.chat-release.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        report, paths = audit()
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
        directory = ROOT / 'releases' / ('vector-fegcraft-persistence-' + stamp)
        directory.mkdir(mode=0o700)
        (directory / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        (directory / 'private-writable-paths.json').write_text(json.dumps(paths, indent=2) + '\n')
        print(json.dumps(report, indent=2)); print('Report: ' + str(directory / 'result.json'))
        if paths: raise RuntimeError('UNPERSISTED_PATHS_REQUIRE_REVIEW_NO_RESTART')


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print('ERROR: ' + (str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__) + '. No restart or message.', file=sys.stderr)
        raise SystemExit(1)
