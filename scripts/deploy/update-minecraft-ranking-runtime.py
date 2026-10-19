#!/usr/bin/env python3
"""Qualify an operator-pinned assistant runtime; optionally update only its code bind."""
import argparse
import ast
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import time
import uuid

JOKE_END = 'Völlig unvoreingenommene Vector-Meinung.'
FIELDS = {'schema', 'container', 'service', 'compose', 'project_directory', 'expected_image',
          'expected_runtime_sha256', 'expected_compose_sha256', 'expected_profile_sha256', 'expected_project_name'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def checked_path(value, *, directory=False):
    path = Path(value)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('UNSAFE_OPERATOR_PATH')
    if directory and not path.is_dir() or not directory and not path.is_file():
        raise RuntimeError('OPERATOR_PATH_MISSING')
    return path


def read_config(path):
    path = checked_path(path)
    meta = path.stat()
    if meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) & 0o077 or meta.st_size > 16384:
        raise RuntimeError('PRIVATE_CONFIG_REQUIRED')
    value = json.loads(path.read_bytes())
    if set(value) != FIELDS or value['schema'] != 1:
        raise RuntimeError('UNSUPPORTED_OPERATOR_CONFIG')
    if not isinstance(value['expected_project_name'], str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,62}', value['expected_project_name']):
        raise RuntimeError('INVALID_COMPOSE_PROJECT_NAME')
    for key in ('container', 'service'):
        if not isinstance(value[key], str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}', value[key]):
            raise RuntimeError('INVALID_OPERATOR_IDENTITY')
    for key in ('expected_runtime_sha256', 'expected_compose_sha256', 'expected_profile_sha256'):
        if not isinstance(value[key], str) or not re.fullmatch('[a-f0-9]{64}', value[key]):
            raise RuntimeError('INVALID_OPERATOR_PIN')
    if not re.fullmatch('sha256:[a-f0-9]{64}', value['expected_image']):
        raise RuntimeError('INVALID_IMAGE_PIN')
    checked_path(value['compose'])
    checked_path(value['project_directory'], directory=True)
    return value


def run(args, timeout=25):
    result = subprocess.run(args, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('GUARDED_COMMAND_FAILED')
    return result.stdout


def inventory():
    ids = run(['docker', 'ps', '-aq']).decode().split()
    if not ids:
        raise RuntimeError('NO_CONTAINERS')
    return {row['Name'].lstrip('/'): row for row in json.loads(run(['docker', 'inspect', *ids]))}


def identity(row):
    return (row['Id'], row['Image'], row['State']['StartedAt'])


def others(rows, target):
    return {name: identity(row) for name, row in rows.items() if name != target}


def compose_command(config, path):
    return ['docker', 'compose', '--project-name', config['expected_project_name'],
            '--project-directory', config['project_directory'], '-f', str(path)]


def compose(config, path):
    return json.loads(run(compose_command(config, path) + ['config', '--format', 'json']))


def code_source(profile, service):
    if set(profile.get('services', {})) != {service}:
        raise RuntimeError('DEDICATED_SINGLE_SERVICE_PROFILE_REQUIRED')
    mounts = [m for m in profile['services'][service].get('volumes', []) if m.get('target') == '/code']
    if len(mounts) != 1 or mounts[0].get('type') != 'bind' or mounts[0].get('read_only') is not True:
        raise RuntimeError('READ_ONLY_CODE_BIND_REQUIRED')
    return checked_path(mounts[0]['source'], directory=True)


def preserve_joke(old, new):
    def node(text):
        found = [n.value for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Return)
            and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str) and n.value.value.endswith(JOKE_END)]
        if len(found) != 1:
            raise RuntimeError('UNIQUE_PRIVATE_JOKE_REQUIRED')
        return found[0]
    old_node, new_node = node(old), node(new)
    lines = new.encode().splitlines(keepends=True)
    start = sum(map(len, lines[:new_node.lineno - 1])) + new_node.col_offset
    end = sum(map(len, lines[:new_node.end_lineno - 1])) + new_node.end_col_offset
    candidate = (new.encode()[:start] + repr(old_node.value).encode() + new.encode()[end:]).decode()
    ast.parse(candidate)
    return candidate.encode()


def preserve_server_literals(old, new):
    """Retain installed operator aliases only in the three existing routing guards."""
    rules = (
        ('unknown_player_target', '(?:server|', r')(?:\b|$)'),
        ('stat_answer', r'\b(?:ich|von mir|für mich|fuer mich|mein(?:e[rmns]?)?|my)\b(?!\s+(?:server|', '))'),
        ('stat_answer', r'\bserver\b|', r'|\bbisher\b'),
    )

    def find(text, function, prefix, suffix):
        functions = [n for n in ast.walk(ast.parse(text)) if isinstance(n, ast.FunctionDef) and n.name == function]
        if len(functions) != 1:
            raise RuntimeError('UNIQUE_OPERATOR_ROUTING_CONTEXT_REQUIRED')
        nodes = [n for n in ast.walk(functions[0]) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                 and n.value.startswith(prefix) and n.value.endswith(suffix)]
        if len(nodes) != 1:
            raise RuntimeError('UNIQUE_OPERATOR_ROUTING_LITERAL_REQUIRED')
        re.compile(nodes[0].value)
        return nodes[0]

    replacements = []
    lines = new.encode().splitlines(keepends=True)
    for function, prefix, suffix in rules:
        old_node = find(old, function, prefix, suffix)
        new_node = find(new, function, prefix, suffix)
        start = sum(map(len, lines[:new_node.lineno - 1])) + new_node.col_offset
        end = sum(map(len, lines[:new_node.end_lineno - 1])) + new_node.end_col_offset
        replacements.append((start, end, repr(old_node.value).encode()))
    raw = new.encode()
    for start, end, value in sorted(replacements, reverse=True):
        raw = raw[:start] + value + raw[end:]
    ast.parse(raw)
    return raw.decode()


def tree_files(root):
    files = {}
    total = 0
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if '__pycache__' in relative.parts:
            continue
        meta = path.lstat()
        if stat.S_ISDIR(meta.st_mode):
            continue
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > 2_000_000:
            raise RuntimeError('UNSUPPORTED_CODE_TREE')
        total += meta.st_size
        if total > 8_000_000:
            raise RuntimeError('CODE_TREE_LIMIT')
        files[str(relative)] = digest(path.read_bytes())
    if 'runtime.py' not in files:
        raise RuntimeError('RUNTIME_MISSING')
    return files


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_private(path, raw):
    with path.open('xb') as handle:
        os.chmod(path, 0o600)
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    sync_directory(path.parent)


def replace_atomic(path, raw):
    previous = path.stat()
    temporary = path.with_name(path.name + '.runtime-' + uuid.uuid4().hex)
    try:
        write_private(temporary, raw)
        os.chown(temporary, previous.st_uid, previous.st_gid)
        os.chmod(temporary, stat.S_IMODE(previous.st_mode))
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def validate_live(config, rows, profile):
    row = rows.get(config['container'])
    if row is None or not row['State']['Running'] or row['State'].get('Health', {}).get('Status') != 'healthy':
        raise RuntimeError('HEALTHY_ASSISTANT_REQUIRED')
    if row['Image'] != config['expected_image'] or digest(canonical(profile)) != config['expected_profile_sha256']:
        raise RuntimeError('LIVE_PROFILE_PIN_MISMATCH')
    labels = row['Config'].get('Labels') or {}
    if labels.get('com.docker.compose.service') != config['service']:
        raise RuntimeError('COMPOSE_SERVICE_MISMATCH')
    if (profile.get('name') != config['expected_project_name']
            or labels.get('com.docker.compose.project') != config['expected_project_name']
            or labels.get('com.docker.compose.project.working_dir') != config['project_directory']):
        raise RuntimeError('COMPOSE_PROJECT_IDENTITY_MISMATCH')
    paths = labels.get('com.docker.compose.project.config_files', '').split(',')
    if paths != [config['compose']]:
        raise RuntimeError('SINGLE_CURRENT_COMPOSE_FILE_REQUIRED')
    current_hash = run(compose_command(config, config['compose']) + ['config', '--hash', config['service']]).decode().split()
    if (len(current_hash) != 2 or current_hash[0] != config['service']
            or not re.fullmatch('[a-f0-9]{64}', current_hash[1])
            or current_hash[1] != labels.get('com.docker.compose.config-hash')):
        raise RuntimeError('RUNNING_SERVICE_PROFILE_DRIFT')
    source = code_source(profile, config['service'])
    mounts = [m for m in row.get('Mounts', []) if m.get('Destination') == '/code']
    if len(mounts) != 1 or mounts[0].get('RW') or mounts[0].get('Source') != str(source):
        raise RuntimeError('LIVE_CODE_BIND_MISMATCH')
    if digest((source / 'runtime.py').read_bytes()) != config['expected_runtime_sha256']:
        raise RuntimeError('ACTIVE_RUNTIME_PIN_MISMATCH')
    return source


def changed_profile(profile, service, source):
    candidate = json.loads(json.dumps(profile))
    code_source(profile, service)
    for mount in candidate['services'][service]['volumes']:
        if mount.get('target') == '/code':
            mount['source'] = str(source)
    return candidate


def verify_image(config, profile):
    image = profile['services'][config['service']]['image']
    inspected = json.loads(run(['docker', 'image', 'inspect', image]))
    if len(inspected) != 1 or inspected[0]['Id'] != config['expected_image']:
        raise RuntimeError('IMAGE_TAG_DRIFT')


def recreate(config):
    verify_image(config, compose(config, Path(config['compose'])))
    run(compose_command(config, config['compose']) + ['up', '-d', '--no-deps', '--no-build', '--pull', 'never', '--force-recreate', config['service']], timeout=60)


def await_health(config, baseline, source):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        rows = inventory()
        if others(rows, config['container']) != baseline:
            raise RuntimeError('UNRELATED_CONTAINERS_CHANGED')
        row = rows.get(config['container'])
        if row and row['Image'] == config['expected_image'] and row['State']['Running'] and not row['State'].get('OOMKilled'):
            mounts = [m for m in row.get('Mounts', []) if m.get('Destination') == '/code']
            if (len(mounts) == 1 and mounts[0]['Source'] == str(source) and not mounts[0].get('RW')
                    and row['State'].get('Health', {}).get('Status') == 'healthy'):
                return
        time.sleep(2)
    raise RuntimeError('ASSISTANT_HEALTH_DEADLINE')


def rollback(release, *, allow_missing=False):
    release = checked_path(release, directory=True)
    config = read_config(release / 'operator.json')
    record = json.loads((release / 'record.json').read_bytes())
    active = Path(config['compose'])
    original_compose = (release / 'compose.original').read_bytes()
    if digest(original_compose) != config['expected_compose_sha256']:
        raise RuntimeError('ROLLBACK_ORIGINAL_COMPOSE_DRIFT')
    # Saved bytes can resolve differently after env_file/interpolation changes.
    original_profile = compose(config, release / 'compose.original')
    if digest(canonical(original_profile)) != config['expected_profile_sha256']:
        raise RuntimeError('ROLLBACK_ORIGINAL_RESOLVED_PROFILE_DRIFT')
    verify_image(config, original_profile)
    expected_others = {k: tuple(v) for k, v in record['other_containers'].items()}
    if tree_files(Path(record['candidate_code'])) != record['candidate_files']:
        raise RuntimeError('ROLLBACK_CANDIDATE_CODE_DRIFT')
    if tree_files(Path(record['original_code'])) != record['original_files']:
        raise RuntimeError('ROLLBACK_ORIGINAL_CODE_DRIFT')

    marker = release / 'rollback.progress.json'
    progress = None
    if marker.exists() or marker.is_symlink():
        checked_path(marker)
        meta = marker.stat()
        if meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o600 or meta.st_size > 16384:
            raise RuntimeError('ROLLBACK_PRIVATE_PROGRESS_REQUIRED')
        progress = json.loads(marker.read_bytes())
        if (set(progress) != {'schema', 'record_sha256', 'phase', 'generation'} or progress['schema'] != 1
                or progress['record_sha256'] != digest(canonical(record))
                or progress['phase'] not in ('prepared', 'compose_restored', 'recreating', 'recreated', 'failed', 'verified')):
            raise RuntimeError('ROLLBACK_PROGRESS_INVALID')
    rows = inventory()
    if others(rows, config['container']) != expected_others:
        raise RuntimeError('ROLLBACK_UNRELATED_CONTAINER_DRIFT')
    row = rows.get(config['container'])
    current_generation = list(identity(row)) if row is not None else None
    active_hash = digest(active.read_bytes())
    if progress is not None:
        # Only an owned interrupted rollback permits original Compose on resume.
        permitted = {config['expected_compose_sha256']}
        if progress['phase'] == 'prepared':
            permitted.add(record['candidate_compose_sha256'])
        if active_hash not in permitted or current_generation != progress['generation']:
            raise RuntimeError('ROLLBACK_RESUME_GENERATION_OR_COMPOSE_DRIFT')
    else:
        if active_hash != record['candidate_compose_sha256']:
            raise RuntimeError('ROLLBACK_COMPOSE_DRIFT')
        if row is None and not allow_missing:
            raise RuntimeError('ROLLBACK_ASSISTANT_MISSING')
        if row is not None and record.get('deployed_identity') and identity(row) != tuple(record['deployed_identity']):
            raise RuntimeError('ROLLBACK_DEPLOYMENT_GENERATION_DRIFT')
    if row is not None:
        mounts = [m for m in row.get('Mounts', []) if m.get('Destination') == '/code']
        if (row['Image'] != config['expected_image'] or len(mounts) != 1 or mounts[0].get('RW')
                or mounts[0]['Source'] not in (record['candidate_code'], record['original_code'])):
            raise RuntimeError('ROLLBACK_ASSISTANT_DRIFT')
        if (progress is None and mounts[0]['Source'] == record['original_code']
                and identity(row) != tuple(record['original_identity'])):
            raise RuntimeError('ROLLBACK_ASSISTANT_DRIFT')
    if progress is None:
        progress = dict(schema=1, record_sha256=digest(canonical(record)), phase='prepared', generation=current_generation)
        write_private(marker, canonical(progress))

    def save(phase):
        progress['phase'] = phase
        replace_atomic(marker, canonical(progress))

    if progress['phase'] == 'verified':
        await_health(config, expected_others, Path(record['original_code']))
    else:
        if active_hash == record['candidate_compose_sha256']:
            replace_atomic(active, original_compose)
        save('compose_restored')
        try:
            save('recreating')
            recreate(config)
            after = inventory()
            if others(after, config['container']) != expected_others:
                raise RuntimeError('ROLLBACK_UNRELATED_CONTAINER_DRIFT')
            observed = after.get(config['container'])
            if observed is None:
                raise RuntimeError('ROLLBACK_RECREATED_ASSISTANT_MISSING')
            mounts = [m for m in observed.get('Mounts', []) if m.get('Destination') == '/code']
            if (observed['Image'] != config['expected_image'] or len(mounts) != 1
                    or mounts[0].get('RW') or mounts[0]['Source'] != record['original_code']):
                raise RuntimeError('ROLLBACK_RECREATED_ASSISTANT_DRIFT')
            progress['generation'] = list(identity(observed))
            save('recreated')
            await_health(config, expected_others, Path(record['original_code']))
            save('verified')
        except Exception:
            # Keep the exact last known generation. Uncertain/new generations
            # cannot be adopted by a later retry merely because paths match.
            save('failed')
            raise
    print(json.dumps({'rolled_back': True, 'only_assistant_recreated': True, 'messages_sent': 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--release-root', type=Path, required=True)
    parser.add_argument('--lock-file', type=Path, required=True)
    parser.add_argument('--activate', action='store_true')
    parser.add_argument('--rollback', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    checked_path(args.release_root, directory=True)
    checked_path(args.lock_file.parent, directory=True)
    if args.lock_file.is_symlink():
        raise RuntimeError('UNSAFE_LOCK')
    descriptor = os.open(args.lock_file, os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid():
        os.close(descriptor)
        raise RuntimeError('EXISTING_OWNED_RELEASE_LOCK_REQUIRED')
    with os.fdopen(descriptor, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.rollback:
            return rollback(args.rollback)
        if args.config is None or args.source_root is None:
            raise RuntimeError('OPERATOR_CONFIG_AND_SOURCE_REQUIRED')
        config = read_config(args.config)
        source = checked_path(args.source_root, directory=True)
        compose_path = Path(config['compose'])
        original = compose_path.read_bytes()
        if digest(original) != config['expected_compose_sha256']:
            raise RuntimeError('COMPOSE_PIN_MISMATCH')
        before = inventory()
        profile = compose(config, compose_path)
        old_code = validate_live(config, before, profile)
        original_files = tree_files(old_code)
        checked_path(source / 'services/minecraft-assistant/runtime.py')
        checked_path(source / 'tests/minecraft-ranking-requests.test.py')
        installed_runtime = (old_code / 'runtime.py').read_text()
        candidate_runtime = preserve_joke(installed_runtime, preserve_server_literals(installed_runtime,
            (source / 'services/minecraft-assistant/runtime.py').read_text()))
        release = args.release_root / ('minecraft-ranking-runtime-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-' + uuid.uuid4().hex[:6])
        release.mkdir(mode=0o700)
        candidate_code = release / 'code'
        candidate_code.mkdir()
        for relative in original_files:
            old, new = old_code / relative, candidate_code / relative
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old, new)
            meta = old.stat()
            os.chown(new, meta.st_uid, meta.st_gid)
        for folder in [candidate_code, *[p for p in candidate_code.rglob('*') if p.is_dir()]]:
            meta = (old_code / folder.relative_to(candidate_code)).stat()
            os.chown(folder, meta.st_uid, meta.st_gid)
            os.chmod(folder, stat.S_IMODE(meta.st_mode))
        (candidate_code / 'runtime.py').write_bytes(candidate_runtime)
        candidate_files = tree_files(candidate_code)
        if {k: v for k, v in candidate_files.items() if k != 'runtime.py'} != {k: v for k, v in original_files.items() if k != 'runtime.py'}:
            raise RuntimeError('NON_RUNTIME_CODE_CHANGED')
        test = source / 'tests/minecraft-ranking-requests.test.py'
        qualification_code = release / 'qualification-code'
        shutil.copytree(candidate_code, qualification_code)
        for entry in [qualification_code, *qualification_code.rglob('*')]:
            os.chmod(entry, 0o755 if entry.is_dir() else 0o644)
        qualifier = 'vector-ranking-check-' + uuid.uuid4().hex
        try:
            run(['docker', 'run', '--name', qualifier, '--rm', '--network', 'none', '--read-only', '--user', '65534:65534',
                 '--cpus', '1', '--memory', '256m', '--memory-swap', '256m', '--pids-limit', '64', '--cap-drop', 'ALL',
                 '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp:rw,nosuid,nodev,size=16m,mode=1777',
                 '-e', 'PYTHONDONTWRITEBYTECODE=1', '--mount', 'type=bind,src=' + str(qualification_code) + ',dst=/qualification/services/minecraft-assistant,readonly',
                 '--mount', 'type=bind,src=' + str(test) + ',dst=/qualification/tests/check.py,readonly',
                 '--entrypoint', 'python3', config['expected_image'], '/qualification/tests/check.py'], timeout=30)
        finally:
            # Only the unique temporary container created above can be removed.
            subprocess.run(['docker', 'rm', '-f', qualifier], capture_output=True, timeout=15)
        candidate = changed_profile(profile, config['service'], candidate_code)
        candidate_raw = json.dumps(candidate, indent=2).replace('$', '$$').encode() + b'\n'
        candidate_path = release / 'compose.candidate.json'
        write_private(candidate_path, candidate_raw)
        if compose(config, candidate_path) != candidate:
            raise RuntimeError('CANDIDATE_COMPOSE_RENDERS_DIFFERENTLY')
        if ({k: identity(v) for k, v in inventory().items()} != {k: identity(v) for k, v in before.items()}
                or compose_path.read_bytes() != original or tree_files(old_code) != original_files
                or tree_files(candidate_code) != candidate_files):
            raise RuntimeError('PRODUCTION_CHANGED_DURING_QUALIFICATION')
        write_private(release / 'operator.json', canonical(config))
        write_private(release / 'compose.original', original)
        record = {'candidate_compose_sha256': digest(candidate_raw), 'original_code': str(old_code),
            'candidate_code': str(candidate_code), 'original_files': original_files, 'candidate_files': candidate_files,
            'other_containers': others(before, config['container']), 'original_identity': identity(before[config['container']])}
        write_private(release / 'record.json', canonical(record))
        if not args.activate:
            print(json.dumps({'qualified': True, 'production_activated': False, 'release': str(release), 'model_calls': 0, 'messages_sent': 0}))
            return
        replace_atomic(compose_path, candidate_raw)
        try:
            recreate(config)
            await_health(config, others(before, config['container']), candidate_code)
            record['deployed_identity'] = identity(inventory()[config['container']])
            replace_atomic(release / 'record.json', canonical(record))
        except Exception:
            rollback(release, allow_missing=True)
            raise
        print(json.dumps({'deployed': True, 'only_assistant_recreated': True, 'game_restart': False,
            'private_character_retained': True, 'release': str(release), 'model_calls': 0, 'cloud_calls': 0, 'messages_sent': 0}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit('Assistant runtime update failed: ' + str(exc) if isinstance(exc, RuntimeError) else 'Assistant runtime update failed: ' + type(exc).__name__)

