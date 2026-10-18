#!/usr/bin/env python3
"""Inspect the deployed mode3 baseline and qualify an addon; never activate it."""
import ast
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import tomllib
from types import SimpleNamespace

ROOT = Path('/root/vector-workspace')
REPO = ROOT / 'github/vector'
DATA = Path('/opt/fegcraft-updated/data')
DEPLOYED = '45f3400d472603e0e55d16c31fce32bb1a8283fb'
RELEASE = ROOT / 'releases/vector-fegcraft-reviewed-help-20261018T125908Z-f15216'
INSTALL = ROOT / 'releases/vector-fegcraft-install-20261017T125904Z-4fdeaf'
HELPER = '8d80f1d3c4ecdd818be33519298333423b152e59'
BACKUP_REV = '100eb7f59f3ef4c95ddcca8c16c88f109b567355'
ASSETS = {'avatar_sha256': 'b0861cbad964bd8600788f0892bfdad853fa7e091d3e06e62c8ba308f79d73f4',
          'pack_sha256': 'e43b8d1783e59ec8c717f1567a23241461f8a5d5efc3ae56ab4b9a5413445ce4'}


def run(*args, timeout=30):
    value = subprocess.run(args, capture_output=True, timeout=timeout)
    if value.returncode or len(value.stdout) > 4_000_000:
        raise RuntimeError('CHAT_PREPARATION_COMMAND_FAILED')
    return value.stdout


def safe(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('CHAT_PREPARATION_SYMLINK')


def read(path):
    safe(path)
    value = path.stat()
    if not stat.S_ISREG(value.st_mode) or value.st_size > 2_000_000:
        raise RuntimeError('CHAT_PREPARATION_FILE_LIMIT')
    return path.read_bytes()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def error_code(exc):
    value = str(exc)
    return value if type(exc) is RuntimeError and re.fullmatch('[A-Z][A-Z0-9_]{2,100}', value) else type(exc).__name__


def source(revision, path):
    return run('git', '-C', str(REPO), 'show', revision + ':' + path)


def load(revision, path):
    raw = source(revision, path)
    ast.parse(raw)
    namespace = {'__name__': 'chat_preparation_support', '__file__': str(REPO / path)}
    exec(compile(raw, namespace['__file__'], 'exec'), namespace)
    return SimpleNamespace(**namespace)


def readonly_backup_engine(engine):
    original = engine.restic

    def metadata_only(*args):
        if not args or args[0] != 'cat' or len(args) < 2 or args[1] not in ('config', 'snapshot'):
            raise RuntimeError('CHAT_PREPARATION_BACKUP_WRITE_REFUSED')
        command = original(*args)
        return [command[0], '--no-cache', '--no-lock', *command[1:]]

    # Loaded engine functions share their isolated namespace, not the live job.
    original.__globals__['restic'] = metadata_only
    engine.restic = metadata_only
    return engine


def current_assistant(h, support):
    """Accept only the observed deployed mode3 release, never its old mode0 gate."""
    raw = read(INSTALL / 'compose.json')
    manifest = json.loads(read(INSTALL / 'manifest.json'))
    record = json.loads(read(RELEASE / 'deployment.json'))
    if (manifest.get('backend_revision') != DEPLOYED or manifest.get('backend_release') != str(RELEASE)
            or manifest.get('compose_sha256') != sha(raw)
            or record.get('status') != 'deployed' or record.get('revision') != DEPLOYED
            or record.get('new_profile_sha') != sha(raw)
            or record.get('new_manifest_sha') != sha(read(INSTALL / 'manifest.json'))
            or read(RELEASE / 'compose.candidate.json') != raw):
        raise RuntimeError('CHAT_PREPARATION_CURRENT_RELEASE_CHANGED')
    profile = json.loads(raw)
    service = profile['services']['assistant']
    if (service['environment'].get('VECTOR_FEGCRAFT_KNOWLEDGE') != '3'
            or set(service['networks']) != {'mc-net', 'vector-internal', 'vector-local-inference'}
            or service['image'] != support.IMAGE):
        raise RuntimeError('CHAT_PREPARATION_MODE3_SCOPE_CHANGED')
    support.check_runtime(support.SERVICE, service, manifest['owner'])
    mounts = {m['target']: m for m in service['volumes']}
    if len(mounts) != len(service['volumes']):
        raise RuntimeError('CHAT_PREPARATION_DUPLICATE_MOUNTS')
    code = RELEASE / 'code'
    expected = {'/code': code, '/inputs/documentation.json': code / 'public-knowledge.json',
                support.SLOT_TARGET: support.SECRET}
    for target, path in expected.items():
        mount = mounts.get(target, {})
        if mount.get('source') != str(path) or mount.get('read_only') is not True:
            raise RuntimeError('CHAT_PREPARATION_MODE3_MOUNT_CHANGED')
    for name in support.FILES:
        if read(code / name) != source(DEPLOYED, 'services/fegcraft-assistant/' + name):
            raise RuntimeError('CHAT_PREPARATION_CURRENT_CODE_CHANGED')
    uid, gid = map(int, service['user'].split(':'))
    safe(support.SECRET)
    info = support.SECRET.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_gid != gid
            or stat.S_IMODE(info.st_mode) != 0o400):
        raise RuntimeError('CHAT_PREPARATION_ROLE_SECRET_SCOPE_CHANGED')
    return {'verified': True, 'knowledge_mode': 'reviewed-local-selection',
            'current_release_retained': True, 'role_only_secret_mount_retained': True}


def backup_summary(result, snapshot, now):
    timestamp = datetime.fromisoformat(snapshot['time'].replace('Z', '+00:00'))
    age = (now - timestamp).total_seconds()
    valid = (result.get('consistent_staging_completed') is True
             and result.get('world_restore_probe_passed') is True
             and result.get('container_recreated') is False and 0 <= age <= 36 * 3600)
    return {'verified': valid, 'reason': 'RECENT_EXISTING_BACKUP' if valid else 'BACKUP_STALE_OR_INCOMPLETE',
            'age_hours': round(age / 3600, 2),
            'world_header_restore_probe_recorded': result.get('world_restore_probe_passed') is True,
            'entire_restore_tested': False, 'writable_container_layer_included': False}


def backup_evidence(engine, now):
    """Read existing owned evidence only. No backup, restore tree, prune or lock removal."""
    lock = DATA.parent / 'backups/.backup.lock'
    safe(lock)
    if not lock.is_file():
        return {'verified': False, 'reason': 'NO_BACKUP_LOCK_OR_COMPLETED_EVIDENCE'}
    with lock.open('rb') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'verified': False, 'reason': 'BACKUP_CURRENTLY_RUNNING'}
        marker = engine.STATE / 'verified-snapshot.json'
        safe(marker)
        if not marker.is_file():
            return {'verified': False, 'reason': 'NO_COMPLETED_SNAPSHOT_MARKER'}
        marker_info = marker.stat()
        if marker_info.st_uid != 0 or marker_info.st_mode & 0o077:
            raise RuntimeError('CHAT_PREPARATION_BACKUP_MARKER_PERMISSIONS')
        owner = engine.repository_owner()
        if not engine.verified_seed(owner):
            return {'verified': False, 'reason': 'NO_VERIFIED_SNAPSHOT'}
        value = json.loads(read(marker))
        found = []
        paths = sorted(engine.STATE.glob('run-*/result.json'))
        if len(paths) > 256:
            raise RuntimeError('CHAT_PREPARATION_BACKUP_REPORT_LIMIT')
        for path in paths:
            result = json.loads(read(path))
            if result.get('snapshot') == value['snapshot']:
                info = path.stat()
                if info.st_uid != 0 or info.st_mode & 0o077:
                    raise RuntimeError('CHAT_PREPARATION_BACKUP_REPORT_PERMISSIONS')
                found.append(result)
        if len(found) != 1:
            return {'verified': False, 'reason': 'MATCHING_COMPLETED_BACKUP_REPORT_REQUIRED'}
        snapshot = json.loads(run(*engine.restic('cat', 'snapshot', value['snapshot'])))
        return backup_summary(found[0], snapshot, now)


def identity_settings():
    bridge = {}
    for line in read(DATA / 'DiscordIntegration-Data/vector/bridge.properties').decode().splitlines():
        if line.strip().startswith(('#', '!')):
            continue
        key, separator, value = line.partition('=')
        if separator:
            bridge[key.strip()] = value.strip()
    discord = tomllib.loads(read(DATA / 'config/Discord-Integration.toml').decode())
    return {'discord_input_enabled': bridge.get('discordInputEnabled', 'false') == 'true',
            'avatar_configured': bool(bridge.get('avatarUrl')),
            'head_texture_configured': bool(bridge.get('logoTexture')),
            'existing_webhook_enabled': discord.get('webhook', {}).get('enable') is True}


def capture_report(result, revision):
    flags = ('passed', 'cleanup_verified', 'production_compose_unchanged',
             'production_container_identities_unchanged', 'installed_integration_unchanged',
             'discord_channel_bot_replay_and_block_registry_passed', 'statistics_dialogue_tests_passed',
             'owner_welcome_tests_passed')
    if (result.get('revision') != revision or any(result.get(k) is not True for k in flags)
            or result.get('production_activated') is not False
            or any(result.get(k) != 0 for k in ('model_calls', 'cloud_calls', 'external_messages_sent'))):
        raise RuntimeError('CHAT_PREPARATION_CAPTURE_NOT_QUALIFIED')


def main():
    os.umask(0o077)
    sys.dont_write_bytecode = True
    revision = os.environ.get('VECTOR_FEGCRAFT_REV', '')
    if os.geteuid() != 0 or not re.fullmatch('[a-f0-9]{40}', revision) or sys.argv[1:]:
        raise RuntimeError('CHAT_PREPARATION_ROOT_AND_PIN_REQUIRED')
    run('git', '-C', str(REPO), 'merge-base', '--is-ancestor', revision, 'origin/main')
    h = load(HELPER, 'scripts/diagnostics/fegcraft-admission-readiness.py')
    support = load(DEPLOYED, 'scripts/deploy/release-fegcraft-reviewed-help.py')
    auditor = load(revision, 'scripts/diagnostics/fegcraft-recreation-safety.py')
    engine = readonly_backup_engine(load(BACKUP_REV, 'scripts/maintenance/fegcraft-incremental-backup.py'))
    evaluator = load(revision, 'scripts/deploy/evaluate-fegcraft-bridge.py')
    identity = load(revision, 'scripts/deploy/qualify-fegcraft-identity.py')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
    directory = ROOT / 'releases' / ('vector-fegcraft-chat-preparation-' + stamp)
    safe(directory)
    directory.mkdir(mode=0o700)
    print('Prüfung und private Vorbereitung:', directory, flush=True)
    report = {'revision': revision, 'audit_completed': False, 'production_activated': False,
              'restart_performed': False, 'model_calls': 0, 'cloud_calls': 0, 'messages_sent': 0}
    safe(ROOT / '.chat-release.lock')
    with (ROOT / '.chat-release.lock').open('rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        before = h.snapshot()
        report['assistant'] = current_assistant(h, support)
        report['installed_addon'] = h.addon()
        report['identity'] = identity_settings()
        protected_paths = (DATA / 'DiscordIntegration-Data/vector/bridge.properties',
                           DATA / 'config/Discord-Integration.toml')
        config_hashes = {path: sha(read(path)) for path in protected_paths}
        report['persistence'], paths = auditor.audit()
        # Exact private paths stay on the owner's server, never stdout/Git/model context.
        (directory / 'private-writable-paths.json').write_text(json.dumps(paths, indent=2) + '\n')
        report['writable_layer_review'] = [{'change': p['change'], 'path_sha256': sha(p['path'].encode())}
                                            for p in paths]
        try:
            report['backup'] = backup_evidence(engine, datetime.now(timezone.utc))
        except Exception as exc:
            report['backup'] = {'verified': False, 'reason': error_code(exc)}
        resource_format = identity.resource_version(DATA / 'versions/26.2/server-26.2.jar')
        markers = DATA / 'DiscordIntegration-Data/vector'
        marker_hashes = {p.name: sha(read(p)) for p in markers.glob('introduction-*.attempted')}
    # Evaluator owns its own lock and disposable containers; it never contacts real chats.
    previous = set((ROOT / 'releases').glob('vector-fegcraft-bridge-evaluation-*'))
    if evaluator.inspect('image', evaluator.JDK) is None:
        raise RuntimeError('CHAT_PREPARATION_PREVIOUSLY_QUALIFIED_JDK_MISSING')
    evaluator.main()
    created = set((ROOT / 'releases').glob('vector-fegcraft-bridge-evaluation-*')) - previous
    if len(created) != 1:
        raise RuntimeError('CHAT_PREPARATION_AMBIGUOUS_CAPTURE')
    capture = created.pop()
    captured = json.loads(read(capture / 'result.json'))
    capture_report(captured, revision)
    builder = evaluator.load_module(capture / 'code/scripts/build-fegcraft-identity.py', 'chat_identity_builder')
    assets = builder.write(directory / 'public-assets')
    if assets['resource_format'] != resource_format or any(assets.get(k) != v for k, v in ASSETS.items()):
        raise RuntimeError('CHAT_PREPARATION_BRAND_ASSETS_CHANGED')
    with (ROOT / '.chat-release.lock').open('rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (h.snapshot() != before or marker_hashes != {p.name: sha(read(p)) for p in markers.glob('introduction-*.attempted')}
                or any(sha(read(path)) != value for path, value in config_hashes.items())):
            raise RuntimeError('CHAT_PREPARATION_PRODUCTION_CHANGED')
        current_assistant(h, support)
    report.update(audit_completed=True, production_unchanged=True, capture=str(capture),
                  addon_sha256=captured['addon_sha256'], new_addon_qualified=True,
                  assets_prepared_privately=True, existing_welcome_markers_preserved=True,
                  eligible_for_activation=False, real_discord_input_verified=False,
                  real_client_rendering_verified=False)
    report['remaining_gates'] = []
    if paths:
        report['remaining_gates'].append('PRIVATE_WRITABLE_LAYER_REVIEW_AND_PRESERVATION')
    if not report['backup']['verified']:
        report['remaining_gates'].append('RECENT_CONSISTENT_BACKUP_EVIDENCE')
    if not report['persistence']['fabric_loader_pinned_to_0_19_5']:
        report['remaining_gates'].append('PIN_OBSERVED_FABRIC_LOADER_IN_GUARDED_CUTOVER')
    report['remaining_gates'].append('CURRENT_MODE3_AWARE_GUARDED_ASSET_PACK_ADDON_INSTALLATION')
    (directory / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    print('Minecraft bleibt online. Kein altes Installationsskript ausführen. Belege:', directory / 'result.json')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Exceptions from parsers/commands may contain private configuration values.
        print('ERROR: CHAT_PREPARATION_FAILED:' + error_code(exc) + '. Keine Aktivierung oder Nachricht.', file=sys.stderr)
        raise SystemExit(1)
