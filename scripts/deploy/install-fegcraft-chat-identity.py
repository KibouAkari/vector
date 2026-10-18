#!/usr/bin/env python3
"""Preserve the current root layer, then install captured Discord/head presentation."""
import copy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
import time
import traceback
from urllib.parse import urlsplit, urlunsplit

ROOT = Path('/root/vector-workspace')
REPO = ROOT / 'github/vector'
DATA = Path('/opt/fegcraft-updated/data')
BASE = 'b88c1e4f4e95d94fe02e84d0d8a5b5f7b616f5cf'
PREPARED = ROOT / 'releases/vector-fegcraft-chat-preparation-20261018T133907Z-40c47c'
CAPTURE = ROOT / 'releases/vector-fegcraft-bridge-evaluation-20261018T133909Z-16ca1f'
ADDON_SHA = '440d4231e5e5711e14250b39528f9b9702b4b8e29f8ecedf4bbfbe671b02da1f'
PATH_SHA = 'a42629617a16e4fea0486435eb0d4924ee109613684cf5c5e6674fc6a65370d9'
POINTER = ROOT / 'fegcraft-chat-identity.json'
BRIDGE = DATA / 'DiscordIntegration-Data/vector/bridge.properties'
CONTROL = BRIDGE.parent
FAILED_RELEASE = ROOT / 'releases/vector-fegcraft-chat-identity-20261018T154321Z-403dfd'
FAILED_REVISION = '4fc136eb67f20c7b0beccc38b00dfa46bf73e151'


def safe_error(exc):
    value = str(exc)
    if type(exc) is RuntimeError and (
            re.fullmatch('[A-Z][A-Z0-9_]{2,100}', value)
            or re.fullmatch('RELEASE_COMMAND_FAILED:(?:docker|curl|nginx|systemctl)', value)):
        return value
    return type(exc).__name__


def phase(old, directory, plan, name):
    plan['phase'] = name
    old.save(directory, plan)
    print('Schritt: ' + name, flush=True)


def record_failure(old, directory, plan, exc, kind='primary'):
    # Keep parser/command details private. Only a fixed error code leaves the host.
    name = 'failure-' + kind
    old.atomic(directory / (name + '-private.txt'), traceback.format_exc().encode(), 0, 0, 0o600)
    summary = {'phase': plan.get('phase', 'unknown'), 'error': safe_error(exc), 'exception_type': type(exc).__name__}
    old.atomic(directory / (name + '.json'), (json.dumps(summary) + '\n').encode(), 0, 0, 0o600)
    plan[name] = summary
    old.save(directory, plan)
    print('Fehler bei ' + summary['phase'] + ': ' + summary['error'], flush=True)


def http_probe(old, directory, name, origin, expected, timeout):
    location = urlsplit(old.URL)
    if location.scheme != 'https' or location.hostname != old.DOMAIN or location.username or location.password:
        raise RuntimeError('CHAT_IDENTITY_PROBE_TARGET_REFUSED')
    target = old.URL + name if name != 'health' else urlunsplit(('https', location.netloc, '/api/health', '', ''))
    with tempfile.NamedTemporaryFile(dir=directory, prefix='.https-check-') as body:
        args = ['curl', '--silent', '--show-error', '--noproxy', '*', '--proto', '=https',
                '--max-time', str(timeout), '--connect-timeout', str(min(2, timeout)),
                '--max-filesize', '32768', '--header', 'Cache-Control: no-cache',
                '--output', body.name, '--write-out', '%{http_code}']
        if origin:
            args += ['--resolve', old.DOMAIN + ':' + str(location.port or 443) + ':127.0.0.1']
        try:
            result = subprocess.run(args + [target], capture_output=True, timeout=timeout + 1)
            code = result.returncode
            status = int(result.stdout) if re.fullmatch(b'[0-9]{3}', result.stdout) else 0
        except subprocess.TimeoutExpired:
            code, status = 28, 0
        body.seek(0)
        raw = body.read(32769)
        match = expected is None or (len(raw) <= 32768 and old.sha(raw) == expected)
    return {'asset': name, 'route': 'origin' if origin else 'public', 'curl_exit': code,
            'http_status': status, 'digest_matches': match if expected is not None else None,
            'ready': code == 0 and status == 200 and match}


def verify_assets_ready(old, directory, *, timeout=30, clock=time.monotonic, sleep=time.sleep, probe=http_probe):
    deadline = clock() + timeout
    observations, attempt = [], 0
    checks = [(name, origin, expected) for name, expected in old.ASSETS.items() for origin in (True, False)]
    checks.append(('health', True, None))
    transient_curl = {6, 7, 28, 52, 55, 56}
    transient_http = {200, 404, 408, 425, 429, 500, 502, 503, 504}
    while clock() < deadline:
        attempt += 1
        complete = True
        for name, origin, expected in checks:
            remaining = deadline - clock()
            if remaining <= .01:
                complete = False
                break
            row = probe(old, directory, name, origin, expected, min(5, remaining))
            row['attempt'] = attempt
            observations.append(row)
            observations = observations[-128:]
            old.atomic(directory / 'https-checks.json', (json.dumps(observations, indent=2) + '\n').encode(), 0, 0, 0o600)
            if not row['ready']:
                complete = False
                if (row['curl_exit'] not in ({0} | transient_curl)
                        or (row['curl_exit'] == 0 and row['http_status'] not in transient_http)):
                    print(json.dumps({'https_check_failed': row}), flush=True)
                    raise RuntimeError('CHAT_IDENTITY_HTTPS_CHECK_REJECTED')
                break
        if complete:
            print('Logo-Dateien über HTTPS und App-Gesundheit geprüft.', flush=True)
            return
        if clock() < deadline:
            print('HTTPS-Veröffentlichung noch nicht bereit; prüfe erneut.', flush=True)
            sleep(min(1, max(0, deadline - clock())))
    if observations:
        print(json.dumps({'https_check_failed': observations[-1]}), flush=True)
    raise RuntimeError('CHAT_IDENTITY_HTTPS_READINESS_TIMEOUT')


def owned_empty_directory(meta, earliest, latest):
    return (stat.S_ISDIR(meta.st_mode) and meta.st_uid == 0
            and stat.S_IMODE(meta.st_mode) == 0o755
            and earliest <= meta.st_ctime_ns <= latest and earliest <= meta.st_mtime_ns <= latest)


def retire_failed_public_directory(p, h, old, game):
    if not old.PUBLIC.exists():
        return
    p.safe(old.PUBLIC); p.safe(FAILED_RELEASE)
    if not old.PUBLIC.is_dir() or any(old.PUBLIC.iterdir()):
        raise RuntimeError('CHAT_IDENTITY_PUBLIC_DIRECTORY_NOT_EMPTY')
    previous = json.loads(p.read(FAILED_RELEASE / 'plan.json'))
    expected = {str(old.nginx_site()), str(h.ADDON), str(BRIDGE)} | {str(old.PUBLIC / n) for n in old.ASSETS}
    protected_files = {str(CONTROL / 'token'), str(CONTROL / 'introduction-v1.attempted'),
                       str(DATA / 'config/Discord-Integration.toml')}
    if (previous.get('revision') != FAILED_REVISION or previous.get('status') != 'rolled_back'
            or previous.get('recreation_started') is not False or 'preservation' in previous
            or previous.get('original_container') != game['Id'] or previous.get('original_image') != game['Image']
            or len(previous.get('files', [])) != len(expected)
            or {r['path'] for r in previous['files']} != expected
            or set(previous.get('protected_files', {})) != protected_files
            or any(r['backup'] != 'before-' + str(i) for i, r in enumerate(previous['files']))
            or protected_live(p, h, previous) != previous['protected']):
        raise RuntimeError('CHAT_IDENTITY_FAILED_RELEASE_NOT_OWNED')
    if p.read(FAILED_RELEASE / 'installer.py') != p.source(FAILED_REVISION, 'scripts/deploy/install-fegcraft-chat-identity.py'):
        raise RuntimeError('CHAT_IDENTITY_FAILED_INSTALLER_CHANGED')
    for row in previous['files']:
        path = Path(row['path']); p.safe(path)
        current = old.digest(path) if path.exists() else None
        if current != row['before'] or (path.parent == old.PUBLIC and row['before'] is not None):
            raise RuntimeError('CHAT_IDENTITY_FAILED_FILES_NOT_RESTORED')
    for path, checksum in previous['protected_files'].items():
        if old.digest(Path(path)) != checksum:
            raise RuntimeError('CHAT_IDENTITY_FAILED_PROTECTED_FILE_CHANGED')
    earliest = (FAILED_RELEASE / 'installer.py').stat().st_mtime_ns
    latest = (FAILED_RELEASE / 'plan.json').stat().st_mtime_ns
    if not owned_empty_directory(old.PUBLIC.stat(), earliest, latest):
        raise RuntimeError('CHAT_IDENTITY_EMPTY_DIRECTORY_METADATA_CHANGED')
    old.PUBLIC.rmdir()  # Only this proven empty directory; never recursive deletion.
    print('Leeres Logo-Verzeichnis des zurückgerollten Versuchs bereinigt.', flush=True)


def bootstrap():
    import ast
    import subprocess
    from types import SimpleNamespace
    raw = subprocess.run(['git', '-C', str(REPO), 'show', BASE + ':scripts/deploy/prepare-fegcraft-chat-cutover.py'],
                         capture_output=True, timeout=15, check=True).stdout
    ast.parse(raw)
    namespace = {'__name__': 'identity_preparation', '__file__': str(REPO / 'scripts/deploy/prepare-fegcraft-chat-cutover.py')}
    exec(compile(raw, namespace['__file__'], 'exec'), namespace)
    return SimpleNamespace(**namespace)


def scope(h, snapshot):
    # Keep the entire current assistant/app/DB/native configuration and identities.
    excluded = {'/fegcraft-updated', str(DATA.parent / 'docker-compose.yml'), str(h.ADDON)}
    return {k: h.sha(json.dumps(v, sort_keys=True).encode()) for k, v in snapshot.items() if k not in excluded}


def patch_loader(raw, service):
    text = raw.decode()
    if 'FABRIC_LOADER_VERSION' in text or 'FABRIC_LAUNCHER_VERSION' in text:
        raise RuntimeError('CHAT_IDENTITY_EXISTING_LOADER_SETTING_REQUIRES_REVIEW')
    lines = text.splitlines(keepends=True)
    start = lines.index('  ' + service + ':\n')
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip()
                and not lines[i].lstrip().startswith('#') and len(lines[i]) - len(lines[i].lstrip()) <= 2), len(lines))
    env = next(i for i in range(start + 1, end) if lines[i].strip() == 'environment:')
    first = next(line for line in lines[env + 1:end] if line.strip() and not line.lstrip().startswith('#'))
    addition = ('      - FABRIC_LOADER_VERSION=0.19.5\n      - FABRIC_LAUNCHER_VERSION=1.1.2\n'
                if first.startswith('      - ') else
                '      FABRIC_LOADER_VERSION: "0.19.5"\n      FABRIC_LAUNCHER_VERSION: "1.1.2"\n')
    lines.insert(env + 1, addition)
    return ''.join(lines).encode()


def image_only(raw, service, image):
    lines = raw.decode().splitlines(keepends=True)
    start = lines.index('  ' + service + ':\n')
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip()
                and not lines[i].lstrip().startswith('#') and len(lines[i]) - len(lines[i].lstrip()) <= 2), len(lines))
    indexes = [i for i in range(start + 1, end) if re.match('    image\\s*:', lines[i])]
    if len(indexes) != 1:
        raise RuntimeError('CHAT_IDENTITY_IMAGE_LAYOUT_CHANGED')
    lines[indexes[0]] = '    image: ' + json.dumps(image) + '\n'
    return ''.join(lines).encode()


def validate_profile(before, after, service, image, pack, old):
    expected = copy.deepcopy(before)
    expected['services'][service]['image'] = image
    expected['services'][service].setdefault('environment', {})['FABRIC_LOADER_VERSION'] = '0.19.5'
    expected['services'][service]['environment']['FABRIC_LAUNCHER_VERSION'] = '1.1.2'
    if pack:
        expected['services'][service]['environment'].update(old.PACK_ENV)
    if expected != after:
        raise RuntimeError('CHAT_IDENTITY_UNAPPROVED_COMPOSE_CHANGE')


def bridge_settings(old, raw):
    value = old.properties(raw)
    if (set(value) != {'enabled', 'introductionEnabled', 'tokenFile', 'avatarUrl'}
            or value['enabled'] != 'true' or value['introductionEnabled'] != 'false'
            or value['tokenFile'] != '/data/DiscordIntegration-Data/vector/token' or value['avatarUrl']):
        raise RuntimeError('CHAT_IDENTITY_BRIDGE_BASELINE_CHANGED')
    value.update(avatarUrl=old.URL + 'vector-avatar.png', logoTexture='vector:entity/vector',
                 discordInputEnabled='true', ownerWelcomeEnabled='true')
    return ''.join(k + '=' + v + '\n' for k, v in value.items()).encode()


def wait_game(old, image):
    started = time.monotonic()
    while time.monotonic() - started < 240:
        value = old.inspect(old.GAME)
        if value['Image'] != image or value['State'].get('OOMKilled') or value['State'].get('Restarting'):
            raise RuntimeError('CHAT_IDENTITY_GAME_START_FAILED')
        if value['State'].get('Running') and value['State'].get('Health', {}).get('Status') == 'healthy':
            return value
        print('Minecraft startet; vergangen: ' + str(int(time.monotonic() - started)) + ' Sekunden.', flush=True)
        time.sleep(10)
    raise RuntimeError('CHAT_IDENTITY_GAME_READINESS_TIMEOUT')


def check_protected(p, h, old, plan):
    if protected_live(p, h, plan) != plan['protected']:
        raise RuntimeError('CHAT_IDENTITY_UNRELATED_PRODUCTION_CHANGED')
    for path, checksum in plan['protected_files'].items():
        if p.sha(p.read(Path(path))) != checksum:
            raise RuntimeError('CHAT_IDENTITY_TOKEN_MARKER_OR_DISCORD_CONFIG_CHANGED')


def protected_live(p, h, plan):
    # Recovery must work when the game is unhealthy, stopped or temporarily absent.
    names = tuple(name for name in h.NAMES if name != 'fegcraft-updated')
    values = json.loads(p.run('docker', 'inspect', *names))
    if {v['Name'].lstrip('/') for v in values} != set(names):
        raise RuntimeError('CHAT_IDENTITY_PROTECTED_SET_CHANGED')
    snapshot = {}
    for value in values:
        state = value['State']
        if not state.get('Running') or state.get('Restarting') or state.get('OOMKilled'):
            raise RuntimeError('CHAT_IDENTITY_UNRELATED_SERVICE_DOWN')
        row = {k: value[k] for k in ('Id', 'Image', 'Config', 'HostConfig', 'Mounts')}
        row['Mounts'] = h.canonical_mounts(row['Mounts'])
        row['StartedAt'] = state['StartedAt']; row['networks'] = sorted(value['NetworkSettings']['Networks'])
        snapshot[value['Name']] = row
    files = (Path('/opt/vector/docker-compose.yml'), p.INSTALL / 'compose.json', p.INSTALL / 'manifest.json')
    for path in files:
        snapshot[str(path)] = p.sha(p.read(path))
    return scope(h, snapshot)


def check_files(old, directory, plan):
    old.validate_records(directory, plan)
    if any(old.digest(Path(r['path'])) != r['after'] for r in plan['files']):
        raise RuntimeError('CHAT_IDENTITY_MANAGED_FILE_CHANGED')


def arm_welcome(p, old, game, directory, plan):
    marker = CONTROL / 'owner-welcome-v2.attempted'
    request = CONTROL / 'owner-welcome-v2.ready'
    instance = CONTROL / 'owner-welcome-v2.instance'
    for path in (marker, request, instance):
        p.safe(path)
    if marker.exists() or request.exists():
        raise RuntimeError('CHAT_IDENTITY_WELCOME_ALREADY_ATTEMPTED_OR_UNCERTAIN')
    value = p.read(instance)
    if not re.fullmatch(b'[a-f0-9-]{36}\n', value):
        raise RuntimeError('CHAT_IDENTITY_WELCOME_INSTANCE_INVALID')
    born = datetime.fromisoformat(game['State']['StartedAt'].replace('Z', '+00:00')).timestamp()
    info = instance.stat()
    if info.st_mtime < born:
        raise RuntimeError('CHAT_IDENTITY_WELCOME_INSTANCE_IS_OLD')
    # Readiness and all installation checks precede this signal; addon waits >=15s.
    plan['welcome'] = 'arming_once'
    old.save(directory, plan)
    fd = os.open(request, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        os.fchown(handle.fileno(), info.st_uid, info.st_gid)
        handle.write(value); handle.flush(); os.fsync(handle.fileno())
    fd = os.open(CONTROL, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    plan['welcome'] = 'armed_once'
    old.save(directory, plan)
    print('Vector-Begrüssung einmalig freigegeben; das Addon wartet mindestens 15 Sekunden.', flush=True)
    for _ in range(5):
        if marker.exists():
            return True
        time.sleep(5)
    return marker.exists()


def recover_original(p, old, engine, game, directory, plan, stopped_game):
    try:
        old.write_records(directory, plan, reverse=True)
        p.run('nginx', '-t'); p.run('systemctl', 'reload', 'nginx')
        if plan.get('public_directory_created'):
            p.safe(old.PUBLIC)
            if old.PUBLIC.is_dir() and not any(old.PUBLIC.iterdir()) and old.PUBLIC.stat().st_uid == 0:
                old.PUBLIC.rmdir()
        plan['status'] = 'rolled_back'; old.save(directory, plan)
    finally:
        # A changed public/config file must never prevent recovery of the original game.
        if stopped_game:
            engine.restart(game, wait_for_stop=True)
            engine.ready(game)


def rollback(p, h, old, directory):
    p.safe(directory)
    if directory.parent != ROOT / 'releases' or not re.fullmatch('vector-fegcraft-chat-identity-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}', directory.name):
        raise RuntimeError('CHAT_IDENTITY_ROLLBACK_PATH_REFUSED')
    plan = json.loads(p.read(directory / 'plan.json'))
    if plan['status'] == 'rolled_back':
        print('Bereits zurückgerollt. Kein Neustart und keine Nachricht.'); return
    expected = {str(old.GAME_COMPOSE), plan['site'], str(h.ADDON), str(BRIDGE)}
    expected.update(str(old.PUBLIC / name) for name in old.ASSETS)
    if ({r['path'] for r in plan['files']} != expected or len(plan['files']) != len(expected)
            or any(r['backup'] != 'before-' + str(i) for i, r in enumerate(plan['files']))):
        raise RuntimeError('CHAT_IDENTITY_ROLLBACK_SCOPE_CHANGED')
    old.validate_records(directory, plan, reverse=True)
    for path, checksum in plan['protected_files'].items():
        if old.digest(Path(path)) != checksum:
            raise RuntimeError('CHAT_IDENTITY_ROLLBACK_PROTECTED_FILE_CHANGED')
    # The only allowed excluded live records are game, owned compose and addon.
    if protected_live(p, h, plan) != plan['protected']:
        raise RuntimeError('CHAT_IDENTITY_ROLLBACK_UNRELATED_STATE_CHANGED')
    present = bool(p.run('docker', 'ps', '-aq', '--filter', 'name=^/' + old.GAME + '$').strip())
    if present:
        game = old.inspect(old.GAME)
        labels = game['Config'].get('Labels') or {}
        if (labels.get('com.docker.compose.project') != plan['game_project']
                or labels.get('com.docker.compose.service') != plan['game_service']
                or game['Image'] not in (plan['preservation']['image'], plan['original_image'])
                or (game['Image'] == plan['original_image'] and game['Id'] != plan['original_container'])
                or len(game['Mounts']) != 1
                or any(m.get('Type') != 'bind' or m.get('Source') != str(DATA)
                       or m.get('Destination') != '/data' or m.get('RW') is not True for m in game['Mounts'])):
            raise RuntimeError('CHAT_IDENTITY_ROLLBACK_GAME_OWNER_CHANGED')
    rollback_raw = p.read(directory / 'compose.rollback.yml')
    if p.sha(rollback_raw) != plan['rollback_compose_sha256']:
        raise RuntimeError('CHAT_IDENTITY_ROLLBACK_PROFILE_CHANGED')
    image = json.loads(p.run('docker', 'image', 'inspect', plan['preservation']['image']))[0]
    if (image['Id'] != plan['preservation']['image']
            or image['Config'].get('Labels', {}).get('com.vector.fegcraft-root-preservation') != plan['preservation']['owner']):
        raise RuntimeError('CHAT_IDENTITY_ROLLBACK_PRESERVED_IMAGE_CHANGED')
    properties = old.restore_properties(p.read(DATA / 'server.properties'), plan['properties_before'])
    print('Stelle die vorherige Chat-Anbindung wieder her; Welt und Spielerdateien bleiben bestehen.', flush=True)
    if present:
        p.run('docker', 'stop', '--time', '120', old.GAME, timeout=180)
    old.write_records(directory, plan, reverse=True)
    # Keep preserved root state + observed loader even on rollback; never go back to an image lacking it.
    meta = old.GAME_COMPOSE.stat()
    old.atomic(old.GAME_COMPOSE, rollback_raw, meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode))
    path = DATA / 'server.properties'; meta = path.stat()
    properties = old.restore_properties(p.read(path), plan['properties_before'])
    old.atomic(path, properties, meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode))
    p.run('nginx', '-t'); p.run('systemctl', 'reload', 'nginx')
    old.game_up(plan); wait_game(old, plan['preservation']['image'])
    check_protected(p, h, old, plan)
    if POINTER.exists():
        pointer = json.loads(p.read(POINTER))
        if pointer.get('release') != str(directory):
            raise RuntimeError('CHAT_IDENTITY_POINTER_OWNER_CHANGED')
        POINTER.unlink()
    plan['status'] = 'rolled_back'; old.save(directory, plan)
    print('Vorherige Chat-Anbindung wiederhergestellt; Containerschicht, Welt und Begrüssungsmarker behalten.')


def install(p, h, support, old, layer, revision):
    if POINTER.exists():
        pointer = json.loads(p.read(POINTER)); directory = Path(pointer['release']); p.safe(directory)
        if directory.parent != ROOT / 'releases' or not re.fullmatch('vector-fegcraft-chat-identity-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}', directory.name):
            raise RuntimeError('CHAT_IDENTITY_POINTER_INVALID')
        plan = json.loads(p.read(directory / 'plan.json'))
        if plan['status'] != 'deployed_pending_client_test' or pointer['revision'] != plan['revision']:
            raise RuntimeError('CHAT_IDENTITY_PREVIOUS_RELEASE_REQUIRES_REVIEW')
        check_files(old, directory, plan); check_protected(p, h, old, plan)
        wait_game(old, plan['preservation']['image']); verify_assets_ready(old, directory)
        actual = old.properties(p.read(DATA / 'server.properties'))
        if any(actual.get(k) != v for k, v in old.PACK_PROPERTIES.items()):
            raise RuntimeError('CHAT_IDENTITY_COMPLETED_PACK_CHANGED')
        print('Bereits installiert und erneut geprüft. Kein Neustart und keine erneute Begrüssung.'); return
    prepared = json.loads(p.read(PREPARED / 'result.json'))
    captured = json.loads(p.read(CAPTURE / 'result.json'))
    p.capture_report(captured, BASE)
    if (prepared.get('revision') != BASE or prepared.get('audit_completed') is not True
            or prepared.get('capture') != str(CAPTURE) or prepared.get('production_unchanged') is not True
            or prepared.get('addon_sha256') != ADDON_SHA or p.sha(p.read(CAPTURE / 'vector-minecraft-0.1.0.jar')) != ADDON_SHA):
        raise RuntimeError('CHAT_IDENTITY_OWNER_CAPTURE_CHANGED')
    # Reuse qualified addon/backend/assets. No build, native model calls or repeated bootstrap gates.
    for path in ('integrations/fegcraft-addon/src', 'services/fegcraft-assistant', 'scripts/build-fegcraft-identity.py'):
        p.run('git', '-C', str(REPO), 'diff', '--exit-code', BASE, revision, '--', path)
    p.current_assistant(h, support); h.addon()
    auditor = p.load(BASE, 'scripts/diagnostics/fegcraft-recreation-safety.py')
    persistence, paths = auditor.audit()
    if (persistence['game_container'] != prepared['persistence']['game_container']
            or persistence['compose_sha256'] != prepared['persistence']['compose_sha256']
            or len(paths) != 1 or paths[0]['change'] != 'C' or p.sha(paths[0]['path'].encode()) != PATH_SHA):
        raise RuntimeError('CHAT_IDENTITY_RECREATION_BASELINE_CHANGED')
    engine = p.readonly_backup_engine(p.load(p.BACKUP_REV, 'scripts/maintenance/fegcraft-incremental-backup.py'))
    backup = p.backup_evidence(engine, datetime.now(timezone.utc))
    if not backup['verified']:
        raise RuntimeError('CHAT_IDENTITY_RECENT_BACKUP_REQUIRED')
    game = old.inspect(old.GAME); original = game['Id']
    env = dict(value.split('=', 1) for value in game['Config']['Env'] if '=' in value)
    for key in ('FABRIC_LAUNCHER', 'FABRIC_LAUNCHER_URL', 'MODS', 'MODS_FILE', 'MODRINTH_PROJECTS', 'CURSEFORGE_FILES'):
        if env.get(key):
            raise RuntimeError('CHAT_IDENTITY_STARTUP_DOWNLOAD_REQUIRES_REVIEW')
    if str(env.get('FABRIC_FORCE_REINSTALL', '')).lower() not in ('', 'false', '0'):
        raise RuntimeError('CHAT_IDENTITY_FORCED_REINSTALL_REFUSED')
    launcher = DATA / 'fabric-server-mc.26.2-loader.0.19.5-launcher.1.1.2.jar'
    if not p.read(launcher):
        raise RuntimeError('CHAT_IDENTITY_OBSERVED_LAUNCHER_MISSING')
    labels = game['Config']['Labels']; project = labels['com.docker.compose.project']; service = labels['com.docker.compose.service']
    before = h.snapshot()
    identity = p.identity_settings()
    if not identity['existing_webhook_enabled'] or any(identity[k] for k in ('discord_input_enabled', 'avatar_configured', 'head_texture_configured')):
        raise RuntimeError('CHAT_IDENTITY_BASELINE_SETTINGS_CHANGED')
    for name, digest in old.ASSETS.items():
        if old.digest(PREPARED / 'public-assets' / name) != digest:
            raise RuntimeError('CHAT_IDENTITY_PUBLIC_ASSET_CHANGED')
    retire_failed_public_directory(p, h, old, game)
    if old.PUBLIC.exists() or any((CONTROL / ('owner-welcome-v2.' + suffix)).exists() for suffix in ('ready', 'attempted', 'instance')):
        raise RuntimeError('CHAT_IDENTITY_EXISTING_ASSETS_OR_WELCOME_REQUIRE_REVIEW')
    prop = old.properties(p.read(DATA / 'server.properties'))
    if prop.get('resource-pack') or prop.get('resource-pack-sha1') or prop.get('require-resource-pack', 'false') != 'false':
        raise RuntimeError('CHAT_IDENTITY_EXISTING_PACK_REQUIRES_REVIEW')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
    directory = ROOT / 'releases' / ('vector-fegcraft-chat-identity-' + stamp); p.safe(directory); directory.mkdir(mode=0o700)
    print('Installation und Rückrollbelege:', directory, flush=True)
    site = old.nginx_site(); bridge = bridge_settings(old, p.read(BRIDGE))
    protect = (CONTROL / 'token', CONTROL / 'introduction-v1.attempted', DATA / 'config/Discord-Integration.toml')
    plan = {'status': 'prepared', 'revision': revision, 'files': [], 'site': str(site),
            'protected': scope(h, before), 'protected_files': {str(path): old.digest(path) for path in protect},
            'game_project': project, 'game_service': service, 'original_container': original,
            'original_image': game['Image'],
            'properties_before': {key: prop.get(key) for key in old.PACK_PROPERTIES},
            'welcome': 'not_armed', 'recreation_started': False}
    for path, new in ((site, old.patch_nginx(p.read(site))), (h.ADDON, p.read(CAPTURE / 'vector-minecraft-0.1.0.jar')), (BRIDGE, bridge)):
        old.record(directory, path, new, plan)
    for name in old.ASSETS:
        old.record(directory, old.PUBLIC / name, p.read(PREPARED / 'public-assets' / name), plan, mode=0o644)
    old.atomic(directory / 'installer.py', p.read(Path(__file__)), 0, 0, 0o600)
    wrapper = '#!/bin/bash\nset -Eeuo pipefail\nexport VECTOR_FEGCRAFT_REV=' + revision + '\nexec python3 ' + shlex.quote(str(directory / 'installer.py')) + ' --rollback ' + shlex.quote(str(directory)) + '\n'
    old.atomic(directory / 'rollback.sh', wrapper.encode(), 0, 0, 0o700); old.save(directory, plan)
    print('Rollback:', directory / 'rollback.sh', flush=True)
    stopped_game = False
    try:
        phase(old, directory, plan, 'compose_preflight')
        # Validate both exact YAML edits while the old game is still online.
        original_raw = p.read(old.GAME_COMPOSE)
        before_profile = old.compose_config(old.GAME_COMPOSE, project)
        for name, raw, pack in (
                ('compose.preflight.yml', patch_loader(old.patch_compose(original_raw, service, game['Image']), service), True),
                ('rollback.preflight.yml', patch_loader(image_only(original_raw, service, game['Image']), service), False)):
            old.atomic(directory / name, raw, 0, 0, 0o600)
            validate_profile(before_profile, old.compose_config(directory / name, project), service, game['Image'], pack, old)
        # Publish and validate exact HTTPS assets while Minecraft is still online.
        phase(old, directory, plan, 'publish_logo_files')
        old.PUBLIC.mkdir(mode=0o755); old.PUBLIC.chmod(0o755)
        plan['public_directory_created'] = True
        old.save(directory, plan)
        for i, row in enumerate(plan['files']):
            path = Path(row['path'])
            if path == site or path.parent == old.PUBLIC:
                old.atomic(path, p.read(directory / ('after-' + str(i))), row['uid'], row['gid'], row['mode'])
        phase(old, directory, plan, 'nginx_config_test')
        p.run('nginx', '-t')
        phase(old, directory, plan, 'nginx_reload')
        p.run('systemctl', 'reload', 'nginx')
        phase(old, directory, plan, 'https_assets')
        verify_assets_ready(old, directory)
        old.atomic(directory / 'https-publication.json', p.read(directory / 'https-checks.json'), 0, 0, 0o600)
        check_protected(p, h, old, plan)
        # Bound the unknown input before downtime; no full-world backup or model scan.
        phase(old, directory, plan, 'root_archive_preflight')
        layer.copy_archive(original, paths[0]['path'], directory / 'root-online-preflight.tar')
        if h.snapshot() != before:
            raise RuntimeError('CHAT_IDENTITY_PRODUCTION_CHANGED_BEFORE_STOP')
        print('Stoppe Minecraft regulär; sichere nur seine private Containerschicht, keine erneute Weltkopie.', flush=True)
        phase(old, directory, plan, 'game_stop')
        stopped_game = True
        p.run('docker', 'stop', '--time', '120', original, timeout=180)
        layer.stopped(old.inspect(old.GAME))
        if auditor.unpersisted(p.run('docker', 'diff', original)) != paths:
            raise RuntimeError('CHAT_IDENTITY_WRITABLE_PATHS_CHANGED_AT_STOP')
        phase(old, directory, plan, 'root_preservation')
        plan['preservation'] = layer.preserve(original, paths, directory, secrets.token_hex(6)); old.save(directory, plan)
        image = plan['preservation']['image']
        if (old.inspect(old.GAME)['Id'] != original or old.digest(old.GAME_COMPOSE) != persistence['compose_sha256']
                or [DATA.stat().st_dev, DATA.stat().st_ino] != persistence['data_directory_identity']
                or [(DATA / 'world').stat().st_dev, (DATA / 'world').stat().st_ino] != persistence['world_directory_identity']):
            raise RuntimeError('CHAT_IDENTITY_OWNER_OR_DATA_CHANGED_BEFORE_RECREATION')
        check_protected(p, h, old, plan)
        phase(old, directory, plan, 'finalize_compose_and_files')
        original_raw = p.read(old.GAME_COMPOSE)
        candidate = patch_loader(old.patch_compose(original_raw, service, image), service)
        restore = patch_loader(image_only(original_raw, service, image), service)
        old.atomic(directory / 'compose.candidate.yml', candidate, 0, 0, 0o600)
        old.atomic(directory / 'compose.rollback.yml', restore, 0, 0, 0o600)
        before_profile = old.compose_config(old.GAME_COMPOSE, project)
        validate_profile(before_profile, old.compose_config(directory / 'compose.candidate.yml', project), service, image, True, old)
        validate_profile(before_profile, old.compose_config(directory / 'compose.rollback.yml', project), service, image, False, old)
        old.record(directory, old.GAME_COMPOSE, candidate, plan)
        plan['rollback_compose_sha256'] = p.sha(restore); old.save(directory, plan)
        old.write_records(directory, plan)
        plan['recreation_started'] = True; old.save(directory, plan)
        print('Containerschicht und geänderte Datei geprüft. Starte Minecraft mit dem neuen Addon.', flush=True)
        phase(old, directory, plan, 'game_recreation')
        old.game_up(plan); new_game = wait_game(old, image)
        after, _ = auditor.audit()
        if (after['data_directory_identity'] != persistence['data_directory_identity']
                or after['world_directory_identity'] != persistence['world_directory_identity']
                or not after['fabric_loader_pinned_to_0_19_5']):
            raise RuntimeError('CHAT_IDENTITY_WORLD_OR_LOADER_CHANGED')
        logs = old.run('docker', 'logs', '--since', new_game['State']['StartedAt'], old.GAME)
        if b'Vector bridge registered; Discord input enabled in the linked chat channel.' not in logs:
            raise RuntimeError('CHAT_IDENTITY_NEW_ADDON_REGISTRATION_MISSING')
        actual = old.properties(p.read(DATA / 'server.properties'))
        if any(actual.get(k) != v for k, v in old.PACK_PROPERTIES.items()):
            raise RuntimeError('CHAT_IDENTITY_MANDATORY_PACK_NOT_APPLIED')
        phase(old, directory, plan, 'verify_running_installation')
        check_files(old, directory, plan); check_protected(p, h, old, plan); verify_assets_ready(old, directory)
        plan['status'] = 'deployed_pending_client_test'; old.save(directory, plan)
        old.atomic(POINTER, (json.dumps({'release': str(directory), 'revision': revision}) + '\n').encode(), 0, 0, 0o600)
    except BaseException as exc:
        signal.signal(signal.SIGINT, signal.SIG_IGN); signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            record_failure(old, directory, plan, exc)
        except Exception:
            print('Private Fehlerdetails konnten nicht gespeichert werden. Stelle den vorherigen Betrieb wieder her.', flush=True)
        # Before recreation, keep and recover the original container, not a replacement.
        try:
            if not plan['recreation_started']:
                recover_original(p, old, engine, game, directory, plan, stopped_game)
            else:
                print('Installation fehlgeschlagen; starte geschützten Rollback.', flush=True)
                rollback(p, h, old, directory)
        except BaseException as recovery:
            try:
                record_failure(old, directory, plan, recovery, 'recovery')
            except Exception:
                print('Zusätzlicher Wiederherstellungsfehler: ' + safe_error(recovery), flush=True)
            raise recovery from exc
        raise
    # Welcome failure is not a reason to undo a healthy working installation.
    try:
        phase(old, directory, plan, 'owner_welcome')
        welcome = arm_welcome(p, old, new_game, directory, plan)
    except BaseException:
        welcome = False
        print('Begrüssung unbestätigt. Keine automatische Wiederholung; Marker bleiben erhalten.', flush=True)
    summary = {'deployed': True, 'only_minecraft_recreated': True, 'assistant_and_other_services_unchanged': True,
               'same_persistent_world_and_data': True, 'previous_root_layer_preserved': True,
               'required_logo_pack': True, 'discord_input_enabled': True, 'native_welcome_attempt_recorded': welcome,
               'welcome_delivery_acknowledged': False, 'real_discord_input_verified': False,
               'real_client_rendering_verified': False, 'model_calls': 0, 'cloud_calls': 0,
               'rollback': str(directory / 'rollback.sh')}
    old.atomic(directory / 'result.json', (json.dumps(summary, indent=2) + '\n').encode(), 0, 0, 0o600)
    print(json.dumps(summary, indent=2))


def main():
    os.umask(0o077); sys.dont_write_bytecode = True
    def terminate(_signal, _frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, terminate)
    revision = os.environ.get('VECTOR_FEGCRAFT_REV', '')
    if os.geteuid() != 0 or not re.fullmatch('[a-f0-9]{40}', revision):
        raise RuntimeError('CHAT_IDENTITY_ROOT_AND_PIN_REQUIRED')
    p = bootstrap()
    p.run('git', '-C', str(REPO), 'merge-base', '--is-ancestor', revision, 'origin/main')
    old = p.load(BASE, 'scripts/deploy/release-fegcraft-dialogue.py')
    h = p.load(p.HELPER, 'scripts/diagnostics/fegcraft-admission-readiness.py')
    support = p.load(p.DEPLOYED, 'scripts/deploy/release-fegcraft-reviewed-help.py')
    layer = p.load(revision, 'scripts/lib/fegcraft-root-preservation.py')
    for path in (DATA.parent / 'backups/.backup.lock', ROOT / '.chat-release.lock', POINTER):
        p.safe(path)
    with (DATA.parent / 'backups/.backup.lock').open('rb') as backup_lock, (ROOT / '.chat-release.lock').open('rb') as lock:
        fcntl.flock(backup_lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if len(sys.argv) == 3 and sys.argv[1] == '--rollback':
            rollback(p, h, old, Path(sys.argv[2]))
        elif len(sys.argv) == 1:
            install(p, h, support, old, layer, revision)
        else:
            raise RuntimeError('CHAT_IDENTITY_ARGUMENTS_INVALID')


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        code = safe_error(exc)
        print('ERROR: ' + code + '. Private Belege und Sicherungen bleiben erhalten.', file=sys.stderr)
        raise SystemExit(1)

