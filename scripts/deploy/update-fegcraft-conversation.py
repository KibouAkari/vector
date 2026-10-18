#!/usr/bin/env python3
"""Update only the verified mode3 assistant. Never stop Minecraft or send chat."""
import ast
import copy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import sys

ROOT = Path('/root/vector-workspace')
REPO = ROOT / 'github/vector'
BASE = 'b88c1e4f4e95d94fe02e84d0d8a5b5f7b616f5cf'
RETRY = 'fc8918a9abc489fe10ab1b0e698ff672b5ead380'
POINTER = ROOT / 'fegcraft-conversation.json'
FILES = ('runtime.py', 'server.py', 'stats.py', 'policy.py', 'recipes.py', 'knowledge.py', 'documentation.py', 'public-knowledge.json')


def candidate(profile, code):
    value = copy.deepcopy(profile)
    service = value['services']['assistant']
    if service['environment'].get('VECTOR_FEGCRAFT_KNOWLEDGE') != '3':
        raise RuntimeError('CONVERSATION_CURRENT_MODE_CHANGED')
    service['environment']['VECTOR_FEGCRAFT_KNOWLEDGE'] = '4'
    for mount in service['volumes']:
        if mount['target'] == '/code':
            mount['source'] = str(code)
        elif mount['target'] == '/inputs/documentation.json':
            mount['source'] = str(code / 'public-knowledge.json')
    return value


def verify_current(p, h, support, expected_revision):
    p.safe(POINTER)
    pointer = json.loads(p.read(POINTER))
    directory = Path(pointer['release']); p.safe(directory)
    if (pointer.get('revision') != expected_revision or directory.parent != ROOT / 'releases'
            or not re.fullmatch(r'vector-fegcraft-reviewed-help-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}', directory.name)):
        raise RuntimeError('CONVERSATION_POINTER_CHANGED')
    record = json.loads(p.read(directory / 'deployment.json'))
    raw = p.read(p.INSTALL / 'compose.json'); manifest_raw = p.read(p.INSTALL / 'manifest.json')
    manifest = json.loads(manifest_raw); profile = json.loads(raw)
    if (record.get('status') != 'deployed' or record.get('revision') != expected_revision
            or p.sha(raw) != record.get('new_profile_sha') or p.sha(manifest_raw) != record.get('new_manifest_sha')
            or p.read(directory / 'compose.candidate.json') != raw
            or manifest.get('backend_revision') != expected_revision or manifest.get('backend_release') != str(directory)
            or manifest.get('compose_sha256') != p.sha(raw)):
        raise RuntimeError('CONVERSATION_DEPLOYMENT_CHANGED')
    old_profile = json.loads(p.read(directory / 'compose.before.json'))
    if p.sha(p.read(directory / 'compose.before.json')) != record['old_profile_sha']:
        raise RuntimeError('CONVERSATION_BASE_PROFILE_CHANGED')
    if profile != candidate(old_profile, directory / 'code'):
        raise RuntimeError('CONVERSATION_UNAPPROVED_PROFILE_CHANGE')
    service = profile['services']['assistant']
    support.check_runtime(support.SERVICE, service, manifest['owner'])
    for name in FILES:
        if p.read(directory / 'code' / name) != p.source(expected_revision, 'services/fegcraft-assistant/' + name):
            raise RuntimeError('CONVERSATION_CODE_CHANGED')
    if p.sha(p.read(directory / 'code/public-knowledge.json')) != h.CATALOG:
        raise RuntimeError('CONVERSATION_CATALOG_CHANGED')
    stage = json.loads(p.read(directory / 'stage-result.json'))
    if stage.get('passed') is not True or stage.get('model_calls') != 2 or stage.get('conversation_qualified') is not True:
        raise RuntimeError('CONVERSATION_NATIVE_GATE_REQUIRED')
    return directory


def main():
    os.umask(0o077); sys.dont_write_bytecode = True
    revision = os.environ.get('VECTOR_FEGCRAFT_REV', '')
    if os.geteuid() != 0 or not re.fullmatch('[a-f0-9]{40}', revision):
        raise RuntimeError('CONVERSATION_ROOT_AND_PIN_REQUIRED')
    import subprocess
    raw = subprocess.check_output(['git', '-C', str(REPO), 'show', BASE + ':scripts/deploy/prepare-fegcraft-chat-cutover.py'])
    ns = {'__name__': 'conversation_support', '__file__': str(REPO / 'scripts/deploy/prepare-fegcraft-chat-cutover.py')}
    exec(compile(raw, ns['__file__'], 'exec'), ns)
    from types import SimpleNamespace
    p = SimpleNamespace(**ns)
    h = p.load(p.HELPER, 'scripts/diagnostics/fegcraft-admission-readiness.py')
    support = p.load(p.DEPLOYED, 'scripts/deploy/release-fegcraft-reviewed-help.py')
    p.safe(ROOT / '.chat-release.lock')
    with (ROOT / '.chat-release.lock').open('rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        p.run('git', '-C', str(REPO), 'merge-base', '--is-ancestor', revision, 'origin/main')
        if len(sys.argv) == 3 and sys.argv[1] == '--rollback':
            directory = Path(sys.argv[2])
            p.safe(POINTER)
            if json.loads(p.read(POINTER)) != {'release': str(directory), 'revision': revision}:
                raise RuntimeError('CONVERSATION_ROLLBACK_POINTER_CHANGED')
            support.rollback(directory, h); POINTER.unlink(); return
        if sys.argv[1:]:
            raise RuntimeError('CONVERSATION_ARGUMENTS_INVALID')
        if POINTER.exists():
            verify_current(p, h, support, revision)
            print('Gesprächsmodus bereits installiert und geprüft. Kein Neustart oder Modellaufruf.'); return
        p.current_assistant(h, support)
        # Retire only the exact proven empty directory while its old protected
        # baseline is still intact, before changing the assistant container.
        retry = p.load(RETRY, 'scripts/deploy/install-fegcraft-chat-identity.py')
        old = p.load(BASE, 'scripts/deploy/release-fegcraft-dialogue.py')
        retry.retire_failed_public_directory(p, h, old, old.inspect(old.GAME))
        before = h.snapshot()
        profile_raw = p.read(p.INSTALL / 'compose.json'); manifest_raw = p.read(p.INSTALL / 'manifest.json')
        profile = json.loads(profile_raw); manifest = json.loads(manifest_raw)
        directory = ROOT / 'releases' / ('vector-fegcraft-reviewed-help-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3))
        p.safe(directory); directory.mkdir(mode=0o700)
        print('Gesprächsmodus und Rückrollbelege:', directory, flush=True)
        code = directory / 'code'; code.mkdir(mode=0o755); code.chmod(0o755)
        for name in FILES:
            data = p.source(revision, 'services/fegcraft-assistant/' + name)
            if name.endswith('.py'): ast.parse(data)
            support.atomic(code / name, data, 0o644)
        if p.sha(p.read(code / 'public-knowledge.json')) != h.CATALOG:
            raise RuntimeError('CONVERSATION_CATALOG_CHANGED')
        old_code = next(Path(m['source']) for m in profile['services']['assistant']['volumes'] if m['target'] == '/code')
        for name in ('health.py', 'read-probe.py'):
            support.atomic(code / name, p.read(old_code / name), 0o644)
        support.atomic(code / 'rollout-probe.py', p.source(revision, 'tests/fegcraft-conversation-smoke.py'), 0o644)
        value = candidate(profile, code)
        print('Kurze isolierte HTTP-Prüfung, genau zwei lokale Smalltalk-Aufrufe. Minecraft bleibt online.', flush=True)
        result = support.stage(directory, value, manifest['owner'])
        if result.get('conversation_qualified') is not True:
            raise RuntimeError('CONVERSATION_NATIVE_GATE_FAILED')
        support.atomic(directory / 'stage-result.json', (json.dumps(result, indent=2) + '\n').encode())
        if h.snapshot() != before or p.read(p.INSTALL / 'compose.json') != profile_raw or p.read(p.INSTALL / 'manifest.json') != manifest_raw:
            raise RuntimeError('CONVERSATION_BASELINE_CHANGED_DURING_STAGE')
        new_profile = (json.dumps(value, indent=2) + '\n').encode()
        next_manifest = copy.deepcopy(manifest)
        next_manifest.update(compose_sha256=p.sha(new_profile), backend_revision=revision, backend_release=str(directory))
        new_manifest = (json.dumps(next_manifest, indent=2) + '\n').encode()
        record = dict(status='prepared', revision=revision, protected=support.protected(before),
                      old_profile_sha=p.sha(profile_raw), old_manifest_sha=p.sha(manifest_raw),
                      new_profile_sha=p.sha(new_profile), new_manifest_sha=p.sha(new_manifest))
        for name, data in (('compose.before.json', profile_raw), ('manifest.before.json', manifest_raw),
                           ('compose.candidate.json', new_profile), ('deployment.json', (json.dumps(record, indent=2) + '\n').encode()),
                           ('release.py', Path(__file__).read_bytes())):
            support.atomic(directory / name, data)
        support.atomic(directory / 'rollback.sh', ('#!/bin/bash\nset -Eeuo pipefail\nexport VECTOR_FEGCRAFT_REV=' + revision + '\nexec python3 ' + shlex.quote(str(directory / 'release.py')) + ' --rollback ' + shlex.quote(str(directory)) + '\n').encode(), 0o700)
        p.run('docker', 'compose', '-p', support.SERVICE, '-f', str(directory / 'compose.candidate.json'), 'config', '--quiet')
        try:
            support.atomic(p.INSTALL / 'compose.json', new_profile); support.atomic(p.INSTALL / 'manifest.json', new_manifest)
            support.compose(); coverage = support.healthy(support.SERVICE, value['services']['assistant'], manifest['owner'])
            if support.protected_live(h) != record['protected']:
                raise RuntimeError('CONVERSATION_PROTECTED_SERVICE_CHANGED')
            record['status'] = 'deployed'; support.atomic(directory / 'deployment.json', (json.dumps(record, indent=2) + '\n').encode())
            support.atomic(POINTER, (json.dumps({'release': str(directory), 'revision': revision}) + '\n').encode())
            verify_current(p, h, support, revision)
        except BaseException:
            support.rollback(directory, h)
            if POINTER.exists() and json.loads(p.read(POINTER)) == {'release': str(directory), 'revision': revision}: POINTER.unlink()
            raise
        print(json.dumps(dict(deployed=True, only_assistant_recreated=True, minecraft_unchanged=True,
              other_services_unchanged=True, coverage=coverage, model_calls=result['model_calls'], cloud_calls=0,
              messages_sent=0, knowledge_mode='reviewed-gameplay-and-local-smalltalk', qualification=result,
              discord_input_requires_pending_addon=True, rollback=str(directory / 'rollback.sh')), indent=2))


if __name__ == '__main__':
    try: main()
    except BaseException as exc:
        value = str(exc)
        print('ERROR: ' + (value if type(exc) is RuntimeError and re.fullmatch('[A-Z][A-Z0-9_]{2,100}', value) else type(exc).__name__) + '. Minecraft wurde nicht angehalten.', file=sys.stderr)
        raise SystemExit(1)
