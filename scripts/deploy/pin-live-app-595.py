#!/usr/bin/env python3
"""Pin the tested Vector application and align its Compose build source.

No container restarts. No DB migrations. Refuses unexpected environments.
"""
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/vector-workspace')
REPO = ROOT / 'github/vector'
LIVE = Path('/opt/vector/app')
COMPOSE = Path('/opt/vector/docker-compose.yml')
REVISION = '9b405f95862e14335a2693b2026e75970e9b123c'
APP_ID = 'sha256:2bc46ad8e4f0a181374873465f2208f99fa09153d00cce082cb837a8a0ac85e2'
TAG = 'vector-app:staging-9b405f9-20261014T154943Z-2943147'

def command(*args):
    return subprocess.check_output(args, text=True).strip()

def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def die(message):
    raise RuntimeError(message)

def compose_config(file):
    return json.loads(command('docker', 'compose', '-f', str(file), 'config', '--format', 'json'))

def write_candidate(path, content):
    # The Compose configuration may contain inline secrets.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(content)

print('=== VECTOR PERSISTENT RELEASE SOURCE PIN ===')
if os.geteuid() != 0:
    die('Run as root.')
for path in (REPO, LIVE, COMPOSE):
    if not path.exists() or path.is_symlink():
        die(f'Missing path or symlink: {path}')
if command('git', '-C', str(REPO), 'rev-parse', 'HEAD') != REVISION:
    die('Git commit has changed.')
if command('git', '-C', str(REPO), 'status', '--porcelain'):
    die('Git working tree is not clean.')
if command('docker', 'inspect', '--format', '{{.Image}}', 'vector-app') != APP_ID:
    die('Production app image differs from the tested image.')
if command('docker', 'image', 'inspect', '--format', '{{.Id}}', TAG) != APP_ID:
    die('Versioned image tag is missing or differs from the running image.')

base = compose_config(COMPOSE)
app = base.get('services', {}).get('app', {})
build = app.get('build') or {}
context = build.get('context') if isinstance(build, dict) else build
if context != str(LIVE) or app.get('image'):
    die('Base Compose app context or image differs from inspection.')
env = app.get('environment') or {}
if isinstance(env, dict) and str(env.get('VECTOR_PROVIDER_TELEMETRY', '0')).lower() not in ('0', 'false'):
    die('Unexpected provider telemetry setting in base Compose.')
if not isinstance(env, dict):
    die('Unexpected app environment format.')
for name, service in base['services'].items():
    if name == 'app':
        continue
    other = service.get('build') or {}
    other_context = other.get('context') if isinstance(other, dict) else other
    if other_context == str(LIVE):
        die(f'Other service shares the app build context: {name}')

original = COMPOSE.read_text()
pattern = re.compile(r'(?m)^(  app:[ \t]*(?:#[^\n]*)?)$')
matches = list(pattern.finditer(original))
if len(matches) != 1 or len(re.findall(r'(?m)^services:[ \t]*(?:#[^\n]*)?$', original)) != 1:
    die('Compose YAML layout is not the expected simple services/app format.')
match = matches[0]
candidate_text = original[:match.end()] + f'\n    image: {TAG}' + original[match.end():]

stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
release = ROOT / 'releases' / f'vector-595-persistent-{stamp}'
stage = LIVE.parent / f'.vector-app-stage-{stamp}'
backup = LIVE.parent / f'.vector-app-backup-{stamp}'
candidate = COMPOSE.parent / f'.vector-compose-candidate-{stamp}.yml'
for path in (release, stage, backup, candidate):
    if path.exists():
        die(f'Output already exists; refusing overwrite: {path}')

write_candidate(candidate, candidate_text)
try:
    proposed = compose_config(candidate)
    expected = copy.deepcopy(base)
    expected['services']['app']['image'] = TAG
    if proposed != expected:
        die('Candidate Compose changes fields other than app.image.')
finally:
    candidate.unlink(missing_ok=True)

tracked = [p for p in command('git', '-C', str(REPO), 'ls-files', '-z').split('\0') if p]
if not tracked:
    die('No tracked application source files found.')
for name in tracked:
    rel = Path(name)
    if rel.is_absolute() or '..' in rel.parts:
        die(f'Unsafe repository path: {name}')
    if any(p == '.env' or p.startswith('.env.') for p in rel.parts):
        die('Repository unexpectedly contains environment files.')
    src = REPO / rel
    dst = LIVE / rel
    if src.is_symlink() or not src.is_file() or dst.is_symlink():
        die(f'Unexpected file type in tracked source: {name}')
    parent = dst.parent
    while parent != LIVE:
        if parent.is_symlink():
            die(f'Symlinked destination directory for {name}')
        parent = parent.parent

release.mkdir(mode=0o700, parents=True)
backup_compose = release / 'docker-compose.original.yml'
shutil.copy2(COMPOSE, backup_compose)
backup_compose.chmod(0o600)
release_manifest = release / 'MANIFEST.txt'
release_manifest.write_text(
    f'Revision: {REVISION}\nImage: {APP_ID}\nTag: {TAG}\n'
    f'Original app folder: {backup}\nOriginal Compose: {backup_compose}\n'
    'Production containers were NOT restarted by this operation.\n'
)
release_manifest.chmod(0o600)

swapped_old = False
swapped_new = False
compose_pinned = False
try:
    shutil.copytree(LIVE, stage, symlinks=True)
    for name in tracked:
        destination = stage / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / name, destination)
    for name in tracked:
        if fingerprint(REPO / name) != fingerprint(stage / name):
            die(f'Checksum differs after staging: {name}')
    if fingerprint(COMPOSE) != fingerprint(backup_compose):
        die('Compose was edited during preparation.')
    if command('docker', 'inspect', '--format', '{{.Image}}', 'vector-app') != APP_ID:
        die('Running image changed during preparation.')

    LIVE.rename(backup)
    swapped_old = True
    stage.rename(LIVE)
    swapped_new = True
    write_candidate(candidate, candidate_text)
    shutil.copymode(COMPOSE, candidate)
    os.chown(candidate, COMPOSE.stat().st_uid, COMPOSE.stat().st_gid)
    candidate.replace(COMPOSE)
    compose_pinned = True

    after = compose_config(COMPOSE)
    if after != expected:
        die('Post-change Compose configuration was not as expected.')
    if any(fingerprint(REPO / name) != fingerprint(LIVE / name) for name in tracked):
        die('Production source verification failed.')
    if command('docker', 'inspect', '--format', '{{.Image}}', 'vector-app') != APP_ID:
        die('Production container changed unexpectedly.')
except Exception:
    if compose_pinned:
        shutil.copy2(backup_compose, COMPOSE)
    if swapped_new and LIVE.exists():
        LIVE.rename(stage)
    if swapped_old and backup.exists():
        backup.rename(LIVE)
    print('Operation failed; original source and Compose restored when possible.')
    raise
finally:
    candidate.unlink(missing_ok=True)

print('SUCCESS: App source synchronized to reviewed Git commit.')
print('SUCCESS: Base Compose pins the tested production image.')
print('Running containers and all mounted data remain untouched.')
print('Original source preserved at:', backup)
print('Original Compose backed up at:', backup_compose)
print('Release record:', release)
