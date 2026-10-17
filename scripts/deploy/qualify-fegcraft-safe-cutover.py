#!/usr/bin/env python3
"""Audit persistence and qualify changed native welcome; never deploy/arm/send."""
import ast
from datetime import datetime, timezone
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

ROOT = Path('/root/vector-workspace')
REPO = ROOT / 'github/vector'


def export(revision, source, directory, name):
    result = subprocess.run(['git', '-C', str(REPO), 'show', revision + ':' + source], capture_output=True, timeout=20)
    if result.returncode: raise RuntimeError('PINNED_QUALIFICATION_SOURCE_MISSING')
    ast.parse(result.stdout)
    path = directory / (name + '.py'); path.write_bytes(result.stdout); path.chmod(0o600)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def checked_audit(auditor, directory, phase):
    with (ROOT / '.chat-release.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        report, paths = auditor.audit()
    (directory / (phase + '-persistence.json')).write_text(json.dumps(report, indent=2) + '\n')
    (directory / (phase + '-private-writable-paths.json')).write_text(json.dumps(paths, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('persistence_checks_passed', 'same_host_data_bind',
          'same_world_directory', 'persistent_version', 'extra_writable_layer_paths', 'fabric_loader_pinned_to_0_19_5', 'production_unchanged')}, indent=2))
    if paths or report.get('persistence_checks_passed') is not True:
        raise RuntimeError('WRITABLE_LAYER_REQUIRES_REVIEW_NO_RESTART')
    return report


def main():
    os.umask(0o077); sys.dont_write_bytecode = True
    revision = os.environ.get('VECTOR_FEGCRAFT_REV', '')
    if os.geteuid() != 0 or not re.fullmatch(r'[a-f0-9]{40}', revision): raise RuntimeError('ROOT_AND_PIN_REQUIRED')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
    directory = ROOT / 'releases' / ('vector-fegcraft-safe-cutover-' + stamp); directory.mkdir(mode=0o700)
    print('Read-only readiness evidence: ' + str(directory), flush=True)
    auditor = export(revision, 'scripts/diagnostics/fegcraft-recreation-safety.py', directory, 'persistence_audit')
    qualifier = export(revision, 'scripts/deploy/qualify-fegcraft-identity.py', directory, 'identity_qualification')
    before = checked_audit(auditor, directory, 'before')
    existing = set((ROOT / 'releases').glob('vector-fegcraft-identity-qualification-*'))
    qualifier.main()
    after = checked_audit(auditor, directory, 'after')
    for key in ('game_container', 'game_image', 'compose_sha256', 'data_directory_identity', 'world_directory_identity'):
        if before[key] != after[key]: raise RuntimeError('PERSISTENCE_BASELINE_CHANGED_DURING_QUALIFICATION')
    created = set((ROOT / 'releases').glob('vector-fegcraft-identity-qualification-*')) - existing
    if len(created) != 1: raise RuntimeError('AMBIGUOUS_NATIVE_QUALIFICATION')
    identity = created.pop()
    report = json.loads((identity / 'result.json').read_bytes())
    capture = Path(report['capture']); captured = json.loads((capture / 'result.json').read_bytes())
    if (report.get('passed') is not True or report.get('revision') != revision
            or captured.get('owner_welcome_tests_passed') is not True):
        raise RuntimeError('NATIVE_OWNER_WELCOME_NOT_QUALIFIED')
    result = {'passed': True, 'revision': revision, 'persistence_checks_passed': True,
              'owner_welcome_tests_passed': True, 'identity_qualification': str(identity),
              'capture': str(capture), 'addon_sha256': captured['addon_sha256'],
              'production_activated': False, 'restart_performed': False, 'messages_sent': 0,
              'model_calls': 0, 'cloud_calls': 0, 'backup_verified': False,
              'real_native_welcome_delivered': False, 'data_loss_guarantee': False, 'fabric_loader_pin_requires_review': not after['fabric_loader_pinned_to_0_19_5']}
    (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2)); print('Report: ' + str(directory / 'result.json'))
    print('Do not run the old release command. Guarded deployment must bind this new evidence; welcome remains unarmed.')


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print('ERROR: ' + (str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__) + '. No production activation or welcome.', file=sys.stderr)
        raise SystemExit(1)
