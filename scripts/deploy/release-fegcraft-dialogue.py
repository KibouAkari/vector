#!/usr/bin/env python3
"""Update the owned pilot from captured evidence; never send chat or call models."""
import ast
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import stat
import subprocess
import sys
import time
import tomllib

ROOT = Path('/root/vector-workspace')
REPO = ROOT / 'github/vector'
DATA = Path('/opt/fegcraft-updated/data')
QUALIFIED = '1e9ea3da507b5483fad546426a5b9180c753c9f7'
OLD = '98bad3fba4b0f8ed9d90a845d66b4d4c3f896059'
REPORT = ROOT / 'releases/vector-fegcraft-identity-qualification-20261017T140716Z-c08e17'
CAPTURE = ROOT / 'releases/vector-fegcraft-bridge-evaluation-20261017T140716Z-ee145c'
INSTALL = ROOT / 'releases/vector-fegcraft-install-20261017T125904Z-4fdeaf'
SERVICE = 'vector-fegcraft-assistant'
GAME = 'fegcraft-updated'
GAME_COMPOSE = DATA.parent / 'docker-compose.yml'
APP_COMPOSE = Path('/opt/vector/docker-compose.yml')
SITE = Path('/etc/nginx/sites-enabled/vector.kibouakari.com')
PUBLIC = Path('/var/www/vector-fegcraft-assets')
DOMAIN = 'vector.kibouakari.com'
URL = 'https://' + DOMAIN + '/vector-fegcraft-assets/'
ASSETS = {'vector-avatar.png': 'b0861cbad964bd8600788f0892bfdad853fa7e091d3e06e62c8ba308f79d73f4',
          'vector-chat-26-2.zip': 'e43b8d1783e59ec8c717f1567a23241461f8a5d5efc3ae56ab4b9a5413445ce4'}
PACK_SHA1 = 'c3ad9bccc44029b8f907b7c7299af8bb59a7e18a'
OLD_ADDON_SHA = '0be86352e50597fc5e8e82742d87bba3ef924b8d1a8c2230c03bc89d261bc671'
ADDON_SHA = 'b09bf0e10df61ef4d758e79a183ada76be5ebc5c22ba59e7871c5dc66548db94'
NATIVE_IMAGE = 'sha256:eca0b83a886fcc9952ef13755853ef63134e5c76733d40564460398776c92dd7'
INTEGRATION_SHA = '75e039ac6c8edad3c9423c91638ffd15d7c9b95dadb60bf69349da838afbf337'
GAME_SHA = '183c0499c5f855570ee487dd38e141a53f0121f83a0b07a3bac2d8b6698823e8'
SOURCE_FILES = ('runtime.py', 'server.py', 'stats.py', 'policy.py', 'recipes.py')
OTHERS = ('vector-app', 'vector-worker', 'vector-runner', 'vector-postgres', 'vector-redis',
          'vector-local-inference', 'vector-privacy-ner')
PACK_ENV = {'RESOURCE_PACK': URL + 'vector-chat-26-2.zip', 'RESOURCE_PACK_SHA1': PACK_SHA1,
            'RESOURCE_PACK_ENFORCE': 'TRUE'}
PACK_PROPERTIES = {'resource-pack': PACK_ENV['RESOURCE_PACK'], 'resource-pack-sha1': PACK_SHA1,
                   'require-resource-pack': 'true'}


def run(*args, timeout=30):
    result = subprocess.run(args, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('RELEASE_COMMAND_FAILED:' + args[0])
    return result.stdout + result.stderr if args[:2] == ('docker', 'logs') else result.stdout


def safe(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('SYMLINK_REFUSED')


def read(path, limit=2_000_000):
    safe(path)
    meta = path.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_size > limit:
        raise RuntimeError('INVALID_MANAGED_FILE')
    return path.read_bytes()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(path):
    return sha(read(path))


def large_digest(path):
    safe(path)
    meta = path.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_size > 200_000_000:
        raise RuntimeError('ARCHIVE_INPUT_INVALID')
    hashed = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''): hashed.update(block)
    after = path.stat()
    if (meta.st_ino, meta.st_size, meta.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
        raise RuntimeError('ARCHIVE_CHANGED_DURING_READ')
    return hashed.hexdigest()


def atomic(path, raw, uid, gid, mode):
    safe(path)
    temporary = path.parent / ('.vector-dialogue-' + secrets.token_hex(12))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        os.chown(temporary, uid, gid); temporary.chmod(mode)
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def save(directory, plan):
    atomic(directory / 'plan.json', (json.dumps(plan, indent=2) + '\n').encode(), 0, 0, 0o600)


def inspect(name):
    return json.loads(run('docker', 'inspect', name))[0]


def identities():
    result = {}
    for name in OTHERS:
        value = inspect(name)
        if not value['State']['Running'] or value['State'].get('Restarting'):
            raise RuntimeError('OTHER_SERVICE_NOT_RUNNING')
        result[name] = [value['Id'], value['Image'], value['State']['StartedAt']]
    return result


def properties(raw):
    result = {}
    for line in raw.decode().splitlines():
        line = line.strip()
        if not line or line.startswith(('#', '!')): continue
        key, separator, value = line.partition('=')
        if separator:
            if key.strip() in result: raise RuntimeError('DUPLICATE_PROPERTY')
            result[key.strip()] = re.sub(r'\\([:= \\])', r'\1', value.strip())
    return result


def restore_properties(raw, before):
    values = properties(raw)
    for key, expected in PACK_PROPERTIES.items():
        if values.get(key) not in (expected, before.get(key)):
            raise RuntimeError('RESOURCE_PROPERTIES_CHANGED')
    lines = [line for line in raw.decode().splitlines(keepends=True)
             if line.split('=', 1)[0].strip() not in PACK_PROPERTIES]
    text = ''.join(lines)
    if text and not text.endswith('\n'): text += '\n'
    return (text + ''.join(key + '=' + value.replace('\\', '\\\\') + '\n'
                          for key, value in before.items() if value is not None)).encode()


def patch_compose(raw, service, image):
    """Edit only a simple block service/map-or-list environment; canonical diff is mandatory."""
    text = raw.decode()
    if '\t' in text or '\r' in text or not re.fullmatch(r'[A-Za-z0-9_-]+', service):
        raise RuntimeError('COMPOSE_LAYOUT_UNSUPPORTED')
    lines = text.splitlines(keepends=True)
    if sum(line.rstrip() == 'services:' for line in lines) != 1:
        raise RuntimeError('COMPOSE_SERVICES_UNSUPPORTED')
    start = next((i for i, line in enumerate(lines) if line.rstrip() == '  ' + service + ':'), None)
    if start is None: raise RuntimeError('COMPOSE_SERVICE_UNSUPPORTED')
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip() and not lines[i].lstrip().startswith('#')
                and len(lines[i]) - len(lines[i].lstrip()) <= 2), len(lines))
    block = lines[start:end]
    image_rows = [i for i, line in enumerate(block) if re.match(r'^    image\s*:', line)]
    env_rows = [i for i, line in enumerate(block) if re.match(r'^    environment\s*:', line)]
    if len(image_rows) != 1 or len(env_rows) > 1 or any(re.match(r'^    <<:', line) for line in block):
        raise RuntimeError('COMPOSE_FIELDS_UNSUPPORTED')
    block[image_rows[0]] = '    image: ' + json.dumps(image) + '\n'
    if env_rows:
        env_start = env_rows[0]
        if block[env_start].strip() != 'environment:': raise RuntimeError('INLINE_ENVIRONMENT_UNSUPPORTED')
        env_end = next((i for i in range(env_start + 1, len(block)) if block[i].strip()
                        and not block[i].lstrip().startswith('#')
                        and len(block[i]) - len(block[i].lstrip()) <= 4), len(block))
        entries = [line for line in block[env_start + 1:env_end] if line.strip() and not line.lstrip().startswith('#')]
        listing = bool(entries and re.match(r'^      - ', entries[0]))
        pattern = r'^      - [A-Za-z_][A-Za-z0-9_]*(?:=.*)?\n?$' if listing else r'^      [A-Za-z_][A-Za-z0-9_]*: .+\n?$'
        if not entries or any(not re.fullmatch(pattern, line) for line in entries):
            raise RuntimeError('ENVIRONMENT_LAYOUT_UNSUPPORTED')
        if any(any(re.match(r'^      (?:- )?' + key + r'(?:=|:|\s*$)', line) for key in PACK_ENV) for line in entries):
            raise RuntimeError('EXISTING_RESOURCE_PACK_ENVIRONMENT')
        additions = [('      - ' + key + '=' + value + '\n') if listing else
                     ('      ' + key + ': ' + json.dumps(value) + '\n') for key, value in PACK_ENV.items()]
        block[env_end:env_end] = additions
    else:
        block += ['    environment:\n'] + ['      ' + key + ': ' + json.dumps(value) + '\n' for key, value in PACK_ENV.items()]
    return ''.join(lines[:start] + block + lines[end:]).encode()


def nginx_tokens(text):
    """Tokenize comments/quotes so braces inside strings never identify server boundaries."""
    tokens = []; i = 0
    while i < len(text):
        if text[i].isspace(): i += 1; continue
        if text[i] == '#':
            i = text.find('\n', i)
            if i < 0: break
            continue
        start = i
        if text[i] in '{};': tokens.append((text[i], i, i + 1)); i += 1; continue
        value = ''
        while i < len(text) and not text[i].isspace() and text[i] not in '{};#':
            if text[i] in "\"'":
                quote = text[i]; i += 1
                while i < len(text) and text[i] != quote:
                    if text[i] == '\\':
                        i += 1
                        if i >= len(text): raise RuntimeError('NGINX_QUOTE_INVALID')
                    value += text[i]; i += 1
                if i >= len(text): raise RuntimeError('NGINX_QUOTE_INVALID')
                i += 1
            elif text[i] == '\\':
                i += 1
                if i >= len(text): raise RuntimeError('NGINX_ESCAPE_INVALID')
                value += text[i]; i += 1
            else: value += text[i]; i += 1
        tokens.append((value, start, i))
    return tokens


def patch_nginx(raw):
    text = raw.decode()
    if '/vector-fegcraft-assets/' in text: raise RuntimeError('NGINX_ASSET_ROUTE_EXISTS')
    tokens = nginx_tokens(text); stack = []; pending = []; servers = []
    for value, start, end in tokens:
        if value == '{':
            node = {'header': pending, 'directives': [], 'end': None}
            if stack: stack[-1]['children'] = True
            stack.append(node); pending = []
        elif value == '}':
            if not stack or pending: raise RuntimeError('NGINX_STRUCTURE_INVALID')
            node = stack.pop(); node['end'] = start
            if node['header'] == ['server'] and not stack: servers.append(node)
        elif value == ';':
            if stack: stack[-1]['directives'].append(pending)
            pending = []
        else: pending.append(value)
    if stack or pending: raise RuntimeError('NGINX_STRUCTURE_INVALID')
    matches = []
    for node in servers:
        directives = node['directives']
        names = [d for d in directives if d and d[0] == 'server_name']
        listens = [d for d in directives if d and d[0] == 'listen']
        if any(DOMAIN in d[1:] for d in names) and any('ssl' in d and any(re.search(r'(?:^|:)443$', v) for v in d[1:]) for d in listens):
            matches.append(node)
    if len(matches) != 1: raise RuntimeError('UNIQUE_DIRECT_HTTPS_SERVER_REQUIRED')
    additions = '\n    # Vector public logo assets only; no private release directory.\n'
    for name in ASSETS:
        mime = 'image/png' if name.endswith('.png') else 'application/zip'
        additions += ('    location = /vector-fegcraft-assets/' + name + ' {\n'
                      '        alias ' + str(PUBLIC / name) + ';\n'
                      '        default_type ' + mime + ';\n'
                      '        add_header X-Content-Type-Options nosniff;\n    }\n')
    offset = matches[0]['end']
    return (text[:offset] + additions + text[offset:]).encode()


def compose_config(path, project):
    return json.loads(run('docker', 'compose', '--project-directory', str(DATA.parent), '-p', project,
                          '-f', str(path), 'config', '--format', 'json'))


def validate_candidate(before, candidate, service, image):
    expected = copy.deepcopy(before)
    target = expected['services'][service]
    if any(key in target.get('environment', {}) for key in PACK_ENV):
        raise RuntimeError('RESOURCE_ENVIRONMENT_ALREADY_CONFIGURED')
    target.setdefault('environment', {}).update(PACK_ENV); target['image'] = image
    if expected != candidate: raise RuntimeError('COMPOSE_CHANGES_EXCEED_APPROVED_SCOPE')


def nginx_site():
    site = SITE.resolve(strict=True)
    if site.parent not in (Path('/etc/nginx/sites-available'), Path('/etc/nginx/sites-enabled')):
        raise RuntimeError('NGINX_SITE_TARGET_REFUSED')
    safe(site)
    return site


def verify_assets():
    for name, expected in ASSETS.items():
        # Real host HTTPS route, exact bytes, no redirects or insecure TLS.
        for origin in (True, False):
            args = ['curl', '--silent', '--show-error', '--fail', '--noproxy', '*', '--max-time', '20']
            if origin: args += ['--resolve', DOMAIN + ':443:127.0.0.1']
            raw = run(*args, URL + name)
            if sha(raw) != expected: raise RuntimeError('ORIGIN_ASSET_MISMATCH' if origin else 'PUBLIC_ASSET_HTTPS_MISMATCH')
    run('curl', '--silent', '--show-error', '--fail', '--noproxy', '*', '--max-time', '20',
        '--resolve', DOMAIN + ':443:127.0.0.1', 'https://' + DOMAIN + '/api/health')


def wait_ready(name, game=False):
    deadline = time.monotonic() + (240 if game else 60)
    while time.monotonic() < deadline:
        value = inspect(name)
        if value['State'].get('OOMKilled') or value['State'].get('Restarting'): raise RuntimeError('SERVICE_START_FAILED')
        if value['State']['Running'] and value['State'].get('Health', {}).get('Status') == 'healthy': return value
        time.sleep(2)
    raise RuntimeError('SERVICE_READINESS_TIMEOUT')


def assistant_identity(value):
    labels = value['Config'].get('Labels') or {}
    keys = ('com.vector.installation', 'com.docker.compose.project',
            'com.docker.compose.service', 'com.docker.compose.project.config_files')
    mounts = [{key: mount.get(key) for key in ('Type', 'Source', 'Destination', 'RW')}
              for mount in value.get('Mounts', []) if mount.get('Destination') == '/code']
    return {'id': value['Id'], 'image': value['Image'], 'user': value['Config'].get('User'),
            'labels': {key: labels.get(key) for key in keys}, 'code_mount': mounts}


def protected(plan):
    if assistant_identity(inspect(SERVICE)) != plan['assistant']:
        raise RuntimeError('ASSISTANT_CONTAINER_OWNERSHIP_CHANGED')
    if identities() != plan['others'] or digest(APP_COMPOSE) != plan['app_compose']:
        raise RuntimeError('UNRELATED_PRODUCTION_CHANGED')
    if digest(Path(plan['marker'])) != plan['marker_sha'] or digest(Path(plan['token'])) != plan['token_sha']:
        raise RuntimeError('WELCOME_MARKER_OR_TOKEN_CHANGED')
    if digest(INSTALL / 'compose.json') != plan['service_compose']:
        raise RuntimeError('PRIVATE_SERVICE_PROFILE_CHANGED')


def record(directory, path, new, plan, uid=None, gid=None, mode=None):
    safe(path)
    old = read(path) if path.exists() else None
    meta = path.stat() if old is not None else None
    index = str(len(plan['files']))
    if old is not None:
        atomic(directory / ('before-' + index), old, 0, 0, 0o600)
    entry = {'path': str(path), 'before': sha(old) if old is not None else None, 'after': sha(new),
             'backup': 'before-' + index, 'uid': meta.st_uid if meta else (uid or 0),
             'gid': meta.st_gid if meta else (gid or 0), 'mode': stat.S_IMODE(meta.st_mode) if meta else (mode or 0o644)}
    atomic(directory / ('after-' + index), new, 0, 0, 0o600)
    plan['files'].append(entry)


def validate_records(directory, plan, reverse=False):
    records = list(reversed(plan['files'])) if reverse else plan['files']
    # Preflight every file before any restoration or replacement.
    for entry in records:
        path = Path(entry['path']); safe(path)
        current = digest(path) if path.exists() else None
        if current not in (entry['before'], entry['after']): raise RuntimeError('MANAGED_FILE_CHANGED_NO_OVERWRITE')
        index = str(plan['files'].index(entry))
        source = directory / (entry['backup'] if reverse else 'after-' + index)
        expected = entry['before'] if reverse else entry['after']
        if expected is not None and digest(source) != expected: raise RuntimeError('BACKUP_OR_CANDIDATE_CHANGED')


def write_records(directory, plan, reverse=False):
    validate_records(directory, plan, reverse)
    records = list(reversed(plan['files'])) if reverse else plan['files']
    for entry in records:
        path = Path(entry['path'])
        if reverse and entry['before'] is None:
            path.unlink(missing_ok=True)
        else:
            source = directory / (entry['backup'] if reverse else 'after-' + str(plan['files'].index(entry)))
            atomic(path, read(source), entry['uid'], entry['gid'], entry['mode'])


def game_up(plan):
    run('docker', 'compose', '--project-directory', str(DATA.parent), '-p', plan['game_project'],
        '-f', str(GAME_COMPOSE), 'up', '-d', '--no-deps', '--pull', 'never', '--force-recreate',
        '--timeout', '120', plan['game_service'], timeout=180)


def rollback(directory):
    safe(directory)
    if directory.parent != ROOT / 'releases' or not re.fullmatch(r'vector-fegcraft-dialogue-release-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}', directory.name):
        raise RuntimeError('ROLLBACK_DIRECTORY_REFUSED')
    plan = json.loads(read(directory / 'plan.json'))
    if plan['status'] == 'rolled_back': print('Already rolled back. No restart.'); return
    expected = {str(GAME_COMPOSE), str(nginx_site()), str(INSTALL / 'manifest.json'),
                str(DATA / 'DiscordIntegration-Data/addons/vector-minecraft-0.1.0.jar'),
                str(DATA / 'DiscordIntegration-Data/vector/bridge.properties')}
    expected.update(str(INSTALL / 'code' / name) for name in SOURCE_FILES)
    expected.update(str(PUBLIC / name) for name in ASSETS)
    if (len(plan['files']) != len(expected) or {entry['path'] for entry in plan['files']} != expected
            or any(entry['backup'] != 'before-' + str(i) for i, entry in enumerate(plan['files']))):
        raise RuntimeError('ROLLBACK_SCOPE_CHANGED')
    protected(plan)
    present = bool(run('docker', 'ps', '-aq', '--filter', 'name=^/' + GAME + '$').strip())
    if present:
        game = inspect(GAME)
        labels = game['Config'].get('Labels') or {}
        if (game['Image'] != plan['game_image'] or labels.get('com.docker.compose.project') != plan['game_project']
                or labels.get('com.docker.compose.service') != plan['game_service']):
            raise RuntimeError('GAME_OWNERSHIP_CHANGED')
    elif not plan.get('cutover'): raise RuntimeError('GAME_MISSING_BEFORE_CUTOVER')
    validate_records(directory, plan, reverse=True)
    old_compose = next(entry for entry in plan['files'] if entry['path'] == str(GAME_COMPOSE))
    original_profile = compose_config(directory / old_compose['backup'], plan['game_project'])
    original_image = original_profile['services'][plan['game_service']]['image']
    if json.loads(run('docker', 'image', 'inspect', original_image))[0]['Id'] != plan['game_image']:
        raise RuntimeError('ORIGINAL_LOCAL_IMAGE_TAG_CHANGED')
    # Validate file guards before stopping anything.
    for entry in plan['files']:
        path = Path(entry['path']); safe(path)
        if (digest(path) if path.exists() else None) not in (entry['before'], entry['after']):
            raise RuntimeError('MANAGED_FILE_CHANGED_NO_ROLLBACK')
    if plan.get('cutover'):
        raw = read(DATA / 'server.properties')
        restored = restore_properties(raw, plan['properties_before'])
        if present: run('docker', 'stop', '--time', '120', GAME, timeout=180)
        run('docker', 'stop', '--time', '15', SERVICE, timeout=40)
        # Properties may have been re-saved at graceful stop: revalidate only the owned keys.
        raw = read(DATA / 'server.properties'); restored = restore_properties(raw, plan['properties_before'])
    write_records(directory, plan, reverse=True)
    if plan.get('cutover'):
        path = DATA / 'server.properties'; meta = path.stat()
        atomic(path, restored, meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode))
    run('nginx', '-t'); run('systemctl', 'reload', 'nginx')
    if plan.get('cutover'):
        run('docker', 'start', SERVICE); wait_ready(SERVICE)
        game_up(plan); wait_ready(GAME, True)
    protected(plan)
    if PUBLIC.is_dir() and not any(PUBLIC.iterdir()): PUBLIC.rmdir()
    plan['status'] = 'rolled_back'; save(directory, plan)
    print('Previous pilot, logo settings and manifest restored. Welcome marker retained.')


def completed_release(manifest):
    directory = Path(manifest['dialogue_release'])
    safe(directory)
    if directory.parent != ROOT / 'releases' or not re.fullmatch(r'vector-fegcraft-dialogue-release-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}', directory.name):
        raise RuntimeError('RECORDED_RELEASE_PATH_INVALID')
    plan = json.loads(read(directory / 'plan.json'))
    if plan.get('status') != 'deployed_pending_client_test' or manifest.get('dialogue_revision') != QUALIFIED:
        raise RuntimeError('RECORDED_RELEASE_INCOMPLETE_CHECK_ROLLBACK')
    protected(plan); validate_records(directory, plan)
    if any(digest(Path(entry['path'])) != entry['after'] for entry in plan['files']):
        raise RuntimeError('RECORDED_RELEASE_CHANGED')
    game = inspect(GAME)
    if game['Image'] != plan['game_image'] or game['State'].get('Health', {}).get('Status') != 'healthy':
        raise RuntimeError('RECORDED_GAME_NOT_READY')
    actual = properties(read(DATA / 'server.properties'))
    if any(actual.get(key) != value for key, value in PACK_PROPERTIES.items()): raise RuntimeError('RECORDED_PACK_CHANGED')
    verify_assets()
    print('Already deployed; verified owned files and HTTPS. No restart or welcome. Client tests remain pending.')


def release():
    if os.environ.get('VECTOR_REQUIRE_LOGO_PACK') != '1': raise RuntimeError('OWNER_REQUIRED_PACK_CHOICE_MISSING')
    report = json.loads(read(REPORT / 'result.json')); capture = json.loads(read(CAPTURE / 'result.json'))
    if (report.get('revision') != QUALIFIED or report.get('passed') is not True
            or report.get('installation') != str(INSTALL) or report.get('capture') != str(CAPTURE)
            or report.get('dialogue_and_discord_capture_passed') is not True
            or report.get('statistics_dialogue_tests_passed') is not True
            or capture.get('revision') != QUALIFIED or capture.get('passed') is not True
            or capture.get('cleanup_verified') is not True or capture.get('addon_sha256') != ADDON_SHA
            or digest(CAPTURE / 'vector-minecraft-0.1.0.jar') != ADDON_SHA):
        raise RuntimeError('QUALIFIED_CAPTURE_REQUIRED')
    for name, expected in ASSETS.items():
        if digest(REPORT / 'public-assets' / name) != expected: raise RuntimeError('QUALIFIED_ASSET_CHANGED')
    # Load only the pinned local helper, not a mutable current/ script.
    helper_raw = run('git', '-C', str(REPO), 'show', QUALIFIED + ':scripts/deploy/announce-fegcraft-assistant.py')
    namespace = {'__name__': 'release_installation', '__file__': str(INSTALL / 'installation-check.py')}
    exec(compile(helper_raw, '<pinned-installation-check>', 'exec'), namespace)
    service = inspect(SERVICE); game = inspect(GAME)
    directory, manifest = namespace['installation'](service)
    if directory != INSTALL or game['Image'] != manifest['minecraft_image']: raise RuntimeError('BASELINE_CHANGED')
    if (service.get('Image') != NATIVE_IMAGE
            or not any(m.get('Source') == str(INSTALL / 'code') and m.get('Destination') == '/code' and m.get('RW') is False for m in service.get('Mounts', []))):
        raise RuntimeError('PRIVATE_SERVICE_RUNTIME_CHANGED')
    if (large_digest(DATA / 'mods/dcintegration-fabric-MC26.2-3.2.1.jar') != INTEGRATION_SHA
            or large_digest(DATA / 'versions/26.2/server-26.2.jar') != GAME_SHA):
        raise RuntimeError('QUALIFIED_GAME_OR_API_CHANGED')
    if (not service['State'].get('Running') or not game['State'].get('Running')
            or service['State'].get('Restarting') or game['State'].get('Restarting')
            or service['State'].get('Health', {}).get('Status') != 'healthy' or game['State'].get('Health', {}).get('Status') != 'healthy'):
        raise RuntimeError('PILOT_NOT_HEALTHY')
    if manifest.get('dialogue_release'):
        completed_release(manifest)
        return
    if digest(DATA / 'DiscordIntegration-Data/addons/vector-minecraft-0.1.0.jar') != OLD_ADDON_SHA:
        raise RuntimeError('ORIGINAL_ADDON_CHANGED')
    env = dict(value.split('=', 1) for value in game['Config']['Env'] if '=' in value)
    if env.get('VERSION') != '26.2' or any(env.get(key) for key in PACK_ENV): raise RuntimeError('GAME_ENVIRONMENT_CHANGED')
    labels = game['Config'].get('Labels') or {}
    project = labels.get('com.docker.compose.project', ''); game_service = labels.get('com.docker.compose.service', '')
    if (not re.fullmatch(r'[a-zA-Z0-9_-]+', project) or not re.fullmatch(r'[a-zA-Z0-9_-]+', game_service)
            or labels.get('com.docker.compose.project.config_files') != str(GAME_COMPOSE)
            or labels.get('com.docker.compose.project.working_dir') != str(DATA.parent)):
        raise RuntimeError('GAME_COMPOSE_OWNERSHIP_UNSUPPORTED')
    if not any(m.get('Source') == str(DATA) and m.get('Destination') == '/data' and m.get('RW') is True for m in game['Mounts']):
        raise RuntimeError('GAME_MOUNT_CHANGED')
    discord = tomllib.loads(read(DATA / 'config/Discord-Integration.toml').decode())
    if discord.get('webhook', {}).get('enable') is not True: raise RuntimeError('WEBHOOK_REQUIRED')
    site = nginx_site()
    if PUBLIC.exists(): raise RuntimeError('PUBLIC_DIRECTORY_ALREADY_EXISTS')
    safe(PUBLIC)
    prop = properties(read(DATA / 'server.properties'))
    if prop.get('resource-pack') or prop.get('resource-pack-sha1') or prop.get('require-resource-pack', 'false').lower() != 'false':
        raise RuntimeError('EXISTING_RESOURCE_PACK_REFUSED')
    probe_source = ast.parse(run('git', '-C', str(REPO), 'show', QUALIFIED + ':scripts/deploy/install-fegcraft-assistant.py'))
    probes = {node.targets[0].id: ast.literal_eval(node.value) for node in probe_source.body
              if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
              and node.targets[0].id in ('HEALTH', 'READ_PROBE')}
    if (set(probes) != {'HEALTH', 'READ_PROBE'} or read(INSTALL / 'code/health.py') != probes['HEALTH'].encode()
            or read(INSTALL / 'code/read-probe.py') != probes['READ_PROBE'].encode()):
        raise RuntimeError('INSTALLED_PROBES_CHANGED')
    for name in SOURCE_FILES:
        if read(INSTALL / 'code' / name) != run('git', '-C', str(REPO), 'show', OLD + ':services/fegcraft-assistant/' + name):
            raise RuntimeError('PRIVATE_SERVICE_CODE_CHANGED')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
    release_dir = ROOT / 'releases' / ('vector-fegcraft-dialogue-release-' + stamp)
    release_dir.mkdir(mode=0o700)
    print('Update evidence: ' + str(release_dir), flush=True)
    marker = DATA / 'DiscordIntegration-Data/vector/introduction-v1.attempted'
    token = DATA / 'DiscordIntegration-Data/vector/token'
    plan = {'status': 'prepared', 'files': [], 'others': identities(), 'assistant': assistant_identity(service), 'app_compose': digest(APP_COMPOSE),
            'marker': str(marker), 'marker_sha': digest(marker), 'token': str(token), 'token_sha': digest(token),
            'service_compose': digest(INSTALL / 'compose.json'), 'game_image': game['Image'],
            'game_project': project, 'game_service': game_service,
            'properties_before': {key: prop.get(key) for key in PACK_PROPERTIES}, 'cutover': False}
    candidate = release_dir / 'compose.candidate.yml'
    atomic(candidate, patch_compose(read(GAME_COMPOSE), game_service, game['Image']), 0, 0, 0o600)
    before_compose = compose_config(GAME_COMPOSE, project)
    if before_compose['services'][game_service].get('environment', {}).get('VERSION') != '26.2':
        raise RuntimeError('PERSISTENT_GAME_VERSION_MUST_BE_26_2')
    if json.loads(run('docker', 'image', 'inspect', before_compose['services'][game_service]['image']))[0]['Id'] != game['Image']:
        raise RuntimeError('CURRENT_LOCAL_IMAGE_TAG_CHANGED')
    validate_candidate(before_compose, compose_config(candidate, project), game_service, game['Image'])
    record(release_dir, GAME_COMPOSE, read(candidate), plan)
    record(release_dir, site, patch_nginx(read(site)), plan)
    for name in SOURCE_FILES:
        raw = run('git', '-C', str(REPO), 'show', QUALIFIED + ':services/fegcraft-assistant/' + name)
        ast.parse(raw); record(release_dir, INSTALL / 'code' / name, raw, plan)
    addon = DATA / 'DiscordIntegration-Data/addons/vector-minecraft-0.1.0.jar'
    bridge = DATA / 'DiscordIntegration-Data/vector/bridge.properties'
    settings = properties(read(bridge))
    if settings.get('enabled') != 'true' or settings.get('introductionEnabled') != 'false' or settings.get('avatarUrl'):
        raise RuntimeError('BRIDGE_BASELINE_CHANGED')
    if set(settings) != {'enabled', 'introductionEnabled', 'tokenFile', 'avatarUrl'} or settings['tokenFile'] != '/data/DiscordIntegration-Data/vector/token':
        raise RuntimeError('BRIDGE_FIELDS_CHANGED')
    settings.update({'avatarUrl': URL + 'vector-avatar.png', 'logoTexture': 'vector:entity/vector', 'discordInputEnabled': 'true'})
    bridge_new = ''.join(key + '=' + value + '\n' for key, value in settings.items()).encode()
    record(release_dir, addon, read(CAPTURE / 'vector-minecraft-0.1.0.jar'), plan)
    record(release_dir, bridge, bridge_new, plan)
    updated = copy.deepcopy(manifest)
    updated['files'][str(addon)] = ADDON_SHA; updated['files'][str(bridge)] = sha(bridge_new)
    updated['dialogue_release'] = str(release_dir); updated['dialogue_revision'] = QUALIFIED
    record(release_dir, INSTALL / 'manifest.json', (json.dumps(updated, indent=2) + '\n').encode(), plan)
    for name in ASSETS:
        record(release_dir, PUBLIC / name, read(REPORT / 'public-assets' / name), plan, mode=0o644)
    atomic(release_dir / 'release.py', read(Path(__file__)), 0, 0, 0o600)
    script = '#!/bin/sh\nset -eu\nexec python3 ' + shlex.quote(str(release_dir / 'release.py')) + ' --rollback ' + shlex.quote(str(release_dir)) + '\n'
    atomic(release_dir / 'rollback.sh', script.encode(), 0, 0, 0o700)
    save(release_dir, plan)
    print('Rollback: ' + str(release_dir / 'rollback.sh'), flush=True)
    try:
        protected(plan)
        # Publish/validate HTTPS before any game downtime or enabling the head.
        PUBLIC.mkdir(mode=0o755); PUBLIC.chmod(0o755)
        for entry in plan['files']:
            if Path(entry['path']).parent == PUBLIC or Path(entry['path']) == site:
                index = str(plan['files'].index(entry))
                if (digest(Path(entry['path'])) if Path(entry['path']).exists() else None) != entry['before']:
                    raise RuntimeError('PUBLICATION_BASELINE_CHANGED')
                atomic(Path(entry['path']), read(release_dir / ('after-' + index)), entry['uid'], entry['gid'], entry['mode'])
        run('nginx', '-t'); run('systemctl', 'reload', 'nginx'); verify_assets()
        protected(plan); validate_records(release_dir, plan)
        plan['cutover'] = True; plan['status'] = 'cutover'; save(release_dir, plan)
        run('docker', 'stop', '--time', '120', GAME, timeout=180)
        run('docker', 'stop', '--time', '15', SERVICE, timeout=40)
        write_records(release_dir, plan)
        run('docker', 'start', SERVICE); wait_ready(SERVICE)
        run('docker', 'exec', SERVICE, 'python3', '/code/health.py')
        coverage = json.loads(run('docker', 'exec', SERVICE, 'python3', '/code/read-probe.py'))
        game_up(plan); new_game = wait_ready(GAME, True)
        if new_game['Image'] != plan['game_image']: raise RuntimeError('GAME_IMAGE_CHANGED')
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            logs = run('docker', 'logs', '--since', new_game['State']['StartedAt'], GAME)
            if b'Vector bridge registered; Discord input enabled in the linked chat channel.' in logs: break
            time.sleep(2)
        else: raise RuntimeError('NEW_ADDON_REGISTRATION_NOT_OBSERVED')
        actual = properties(read(DATA / 'server.properties'))
        if any(actual.get(key) != value for key, value in PACK_PROPERTIES.items()): raise RuntimeError('CLIENT_PACK_SETTINGS_NOT_APPLIED')
        protected(plan); verify_assets()
        plan['status'] = 'deployed_pending_client_test'; save(release_dir, plan)
        print(json.dumps({'deployed': True, 'required_logo_pack': True, 'discord_input_enabled': True,
                          'saved_data_coverage': coverage, 'welcome_marker_preserved': True,
                          'other_containers_unchanged': True, 'model_calls': 0, 'cloud_calls': 0,
                          'messages_sent': 0, 'real_client_rendering_verified': False,
                          'real_discord_input_verified': False, 'rollback': str(release_dir / 'rollback.sh')}, indent=2))
    except Exception:
        print('Update failed. Attempt guarded restoration; evidence retained.', flush=True)
        try: rollback(release_dir)
        except Exception as recovery:
            reason = str(recovery) if isinstance(recovery, RuntimeError) else type(recovery).__name__
            print('Automatic rollback stopped: ' + reason + '. Rollback: ' + str(release_dir / 'rollback.sh'), file=sys.stderr)
        raise


def main():
    if os.geteuid() != 0: raise RuntimeError('ROOT_OWNER_REQUIRED')
    os.umask(0o077); sys.dont_write_bytecode = True
    with (ROOT / '.chat-release.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if len(sys.argv) == 3 and sys.argv[1] == '--rollback': rollback(Path(sys.argv[2]))
        elif len(sys.argv) == 1: release()
        else: raise RuntimeError('INVALID_ARGUMENTS')


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print('ERROR: ' + (str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__), file=sys.stderr)
        raise SystemExit(1)
