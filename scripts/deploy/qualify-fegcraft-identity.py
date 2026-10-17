#!/usr/bin/env python3
"""Qualify player-like Vector output; prepare assets, never activate or resend."""
import ast
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
import tomllib
import zipfile

ROOT = Path('/root/vector-workspace')
REPO = ROOT / 'github/vector'
DATA = Path('/opt/fegcraft-updated/data')
BASE = '6df9a0a5420b0c754b0984aec413b2699c897b23'
GAME_SHA = '183c0499c5f855570ee487dd38e141a53f0121f83a0b07a3bac2d8b6698823e8'
PRODUCTION = ('fegcraft-updated', 'vector-fegcraft-assistant', 'vector-app', 'vector-worker',
              'vector-runner', 'vector-postgres', 'vector-redis', 'vector-local-inference', 'vector-privacy-ner')


def run(*args, timeout=30):
    result = subprocess.run(args, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('IDENTITY_CHECK_COMMAND_FAILED:' + args[0])
    return result.stdout


def read(path, limit=262144):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('UNEXPECTED_SYMLINK')
    meta = path.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_size > limit:
        raise RuntimeError('UNEXPECTED_INPUT_FILE')
    return path.read_bytes()


def digest(path):
    return hashlib.sha256(read(path)).hexdigest()


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def export(revision, source, target):
    content = run('git', '-C', str(REPO), 'show', revision + ':' + source)
    ast.parse(content)
    with target.open('xb') as handle:
        handle.write(content)
    target.chmod(0o600)


def identities():
    values = json.loads(run('docker', 'inspect', *PRODUCTION))
    if len(values) != len(PRODUCTION):
        raise RuntimeError('CONTAINER_SET_CHANGED')
    result = {}
    for value in values:
        if not value['State']['Running'] or value['State'].get('Restarting'):
            raise RuntimeError('PRODUCTION_NOT_READY')
        result[value['Name'].lstrip('/')] = (value['Id'], value['Image'], value['State']['StartedAt'])
    return result


def site_candidates(dump):
    # Diagnostics only. Never use a regex match as permission to edit Nginx.
    # The following release must use a validated server-block edit and nginx -t.
    sections = re.split(r'^# configuration file ([^\n]+):\s*$', dump, flags=re.M)
    names = []
    for i in range(1, len(sections), 2):
        path, content = sections[i], sections[i + 1]
        directives = re.findall(r'^\s*server_name\s+([^;\n]+);', content, re.M)
        if any('vector.kibouakari.com' in shlex.split(value) for value in directives):
            if not path.startswith('/etc/nginx/') or '..' in Path(path).parts:
                raise RuntimeError('UNRECOGNIZED_NGINX_SITE_PATH')
            names.append(path)
    return sorted(set(names))


def resource_version(path):
    # Verify exact installed public game JAR before using its resource format.
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 200_000_000:
        raise RuntimeError('GAME_JAR_UNAVAILABLE')
    before = path.stat()
    hashed = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            hashed.update(block)
    if hashed.hexdigest() != GAME_SHA:
        raise RuntimeError('QUALIFIED_GAME_JAR_CHANGED')
    with zipfile.ZipFile(path) as archive:
        entries = [e for e in archive.infolist() if e.filename == 'version.json']
        if len(entries) != 1 or entries[0].file_size > 65536:
            raise RuntimeError('GAME_VERSION_METADATA_INVALID')
        version = json.loads(archive.read(entries[0]))
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
        raise RuntimeError('GAME_JAR_CHANGED_DURING_READ')
    pack = version.get('pack_version', {})
    if version.get('id') != '26.2' or (pack.get('resource_major'), pack.get('resource_minor')) != (88, 0):
        raise RuntimeError('RESOURCE_FORMAT_NOT_QUALIFIED')
    return [88, 0]


def main():
    os.umask(0o077)
    sys.dont_write_bytecode = True
    revision = os.environ.get('VECTOR_FEGCRAFT_REV', '')
    if os.geteuid() != 0 or not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise RuntimeError('ROOT_OWNER_AND_PIN_REQUIRED')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
    release = ROOT / 'releases' / ('vector-fegcraft-identity-qualification-' + stamp)
    release.mkdir(mode=0o700)
    export(BASE, 'scripts/deploy/announce-fegcraft-assistant.py', release / 'installation-check.py')
    welcome = module(release / 'installation-check.py', 'identity_installation')
    marker = DATA / 'DiscordIntegration-Data/vector/introduction-v1.attempted'
    with (ROOT / '.chat-release.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        service = json.loads(run('docker', 'inspect', 'vector-fegcraft-assistant'))[0]
        installation, installed = welcome.installation(service)
        if service['State'].get('Health', {}).get('Status') != 'healthy':
            raise RuntimeError('INSTALLED_SERVICE_NOT_HEALTHY')
        before = identities()
        hashes = {p: digest(p) for p in (DATA.parent / 'docker-compose.yml', Path('/opt/vector/docker-compose.yml'), marker)}
        resource_format = resource_version(DATA / 'versions/26.2/server-26.2.jar')
        discord = tomllib.loads(read(DATA / 'config/Discord-Integration.toml').decode())
        if discord.get('webhook', {}).get('enable') is not True:
            raise RuntimeError('EXISTING_DISCORD_WEBHOOK_REQUIRED')
        # Keep configuration text private. Only structural hints leave the server.
        sites = site_candidates(run('nginx', '-T').decode(errors='replace'))
        if not sites:
            raise RuntimeError('VECTOR_HTTPS_SITE_NOT_IDENTIFIED')
    export(revision, 'scripts/deploy/evaluate-fegcraft-bridge.py', release / 'evaluate.py')
    evaluator = module(release / 'evaluate.py', 'identity_bridge_evaluation')
    previous = set((ROOT / 'releases').glob('vector-fegcraft-bridge-evaluation-*'))
    print('Qualify the new addon against the installed API and private synthetic HTTP. No restart or chat message.', flush=True)
    evaluator.main()
    created = set((ROOT / 'releases').glob('vector-fegcraft-bridge-evaluation-*')) - previous
    if len(created) != 1:
        raise RuntimeError('AMBIGUOUS_CAPTURE_RESULT')
    capture = created.pop()
    result = json.loads(read(capture / 'result.json'))
    if (result.get('passed') is not True or result.get('revision') != revision
            or result.get('discord_channel_bot_replay_and_block_registry_passed') is not True
            or result.get('statistics_dialogue_tests_passed') is not True):
        raise RuntimeError('IDENTITY_CAPTURE_FAILED')
    builder = module(capture / 'code/scripts/build-fegcraft-identity.py', 'identity_asset_builder')
    manifest = builder.write(release / 'public-assets')
    if manifest['resource_format'] != resource_format:
        raise RuntimeError('ASSET_RESOURCE_FORMAT_MISMATCH')
    with (ROOT / '.chat-release.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if identities() != before or any(digest(p) != value for p, value in hashes.items()):
            raise RuntimeError('PRODUCTION_CHANGED_DURING_QUALIFICATION')
        after_installation, after_manifest = welcome.installation(json.loads(run('docker', 'inspect', 'vector-fegcraft-assistant'))[0])
        if (after_installation, after_manifest) != (installation, installed):
            raise RuntimeError('INSTALLATION_CHANGED_DURING_QUALIFICATION')
    report = {'passed': True, 'revision': revision, 'installation': str(installation), 'capture': str(capture),
              'name_format': '<Vector>', 'minecraft_head': 'native-player-object-with-local-pack-texture',
              'discord_delivery': 'existing-webhook-with-per-message-name-and-public-png-avatar',
              'public_assets': manifest, 'nginx_site_files': sites, 'webhook_enabled': True,
              'welcome_marker_preserved': True, 'production_unchanged': True, 'production_activated': False,
              'model_calls': 0, 'cloud_calls': 0, 'messages_sent': 0,
              'real_client_rendering_verified': False, 'real_discord_avatar_verified': False}
    report['dialogue_and_discord_capture_passed'] = result.get('discord_channel_bot_replay_and_block_registry_passed') is True
    report['statistics_dialogue_tests_passed'] = result.get('statistics_dialogue_tests_passed') is True
    (release / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    print('Report: ' + str(release / 'result.json'))
    print('Assets are prepared privately, not served or activated. Keep the welcome marker. Guarded asset/pack/addon installation remains next.')


if __name__ == '__main__':
    try:
        main()
    except Exception as failure:
        print('ERROR:', str(failure) if isinstance(failure, RuntimeError) else type(failure).__name__, file=sys.stderr)
        raise SystemExit(1)
