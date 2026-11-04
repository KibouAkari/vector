#!/usr/bin/env python3
"""Update only composition code against an immutable successful Qwen release."""
import argparse
import ast
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import sys
import uuid


def load(path, name):
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('UNSAFE_HELPER')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def owned_json(guard, path):
    path = guard.checked_path(str(path))
    meta = path.stat()
    if meta.st_uid != os.getuid() or not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o077 or meta.st_size > 2000000:
        raise RuntimeError('OWNED_EVIDENCE_REQUIRED')
    return json.loads(path.read_bytes())


def unchanged(before, after, assistant):
    return set(before) == set(after) and all(
        (a['Id'], a['Image'], a['State']['StartedAt'], a['Config'], a['HostConfig']) ==
        (after[n]['Id'], after[n]['Image'], after[n]['State']['StartedAt'], after[n]['Config'], after[n]['HostConfig'])
        for n, a in before.items() if n != assistant)


def main():
    parser = argparse.ArgumentParser()
    for key in ('guard-helper', 'release-helper', 'baseline', 'source', 'release-root', 'lock-file'):
        parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--server-name', required=True)
    parser.add_argument('--activate', action='store_true')
    parser.add_argument('--rollback', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    sys.dont_write_bytecode = True
    guard = load(args.guard_helper, 'context_guard')
    release = load(args.release_helper, 'context_release')
    fd = os.open(guard.checked_path(str(args.lock_file)), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    meta = os.fstat(fd)
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid():
        os.close(fd)
        raise RuntimeError('OWNED_RELEASE_LOCK_REQUIRED')
    with os.fdopen(fd, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.rollback:
            guard.rollback(guard.checked_path(str(args.rollback), directory=True))
            return
        if not args.activate or not re.fullmatch(r'[\w .-]{1,64}', args.server_name):
            raise RuntimeError('EXPLICIT_ACTIVATION_AND_SERVER_NAME_REQUIRED')
        baseline = guard.checked_path(str(args.baseline), directory=True)
        proof = owned_json(guard, baseline/'result.json')
        prior = owned_json(guard, baseline/'record.json')
        config = guard.read_config(baseline/'operator.json')
        if (proof.get('deployed') is not True or proof.get('knowledge_mode') != 'qwen35-data-first'
                or proof.get('model') != 'vector-qwen35:9b-q4km-candidate'
                or proof.get('release') != str(baseline)
                or proof.get('only_assistant_recreated') is not True
                or proof.get('other_services_unchanged') is not True
                or proof.get('game_restart') is not False):
            raise RuntimeError('SUCCESSFUL_QWEN_BASELINE_REQUIRED')
        before = guard.inventory()
        assistant = config['container']
        row = before[assistant]
        active = guard.checked_path(config['compose'])
        original = active.read_bytes()
        if (list(guard.identity(row)) != prior.get('deployed_identity')
                or original != (baseline/'compose.candidate.json').read_bytes()
                or guard.digest(original) != prior['candidate_compose_sha256']):
            raise RuntimeError('LIVE_GENERATION_OR_COMPOSE_DRIFT')
        profile = guard.compose(config, active)
        config.update(expected_runtime_sha256=prior['candidate_files']['runtime.py'],
            expected_compose_sha256=prior['candidate_compose_sha256'],
            expected_profile_sha256=prior['candidate_profile_sha256'])
        installed = guard.validate_live(config, before, profile)
        if str(installed) != prior['candidate_code'] or guard.tree_files(installed) != prior['candidate_files']:
            raise RuntimeError('LIVE_CODE_DRIFT')
        directory = guard.checked_path(str(args.release_root), directory=True)/('qwen35-context-'+uuid.uuid4().hex)
        directory.mkdir(mode=0o700)
        guard.COMMAND_EVIDENCE = directory
        code = directory/'code'
        shutil.copytree(installed, code, ignore=shutil.ignore_patterns('__pycache__'))
        raw = guard.checked_path(str(args.source)).read_bytes()
        ast.parse(raw)
        if release.constant(raw, 'MODEL') != release.constant((installed/'datafirst.py').read_bytes(), 'MODEL'):
            raise RuntimeError('MODEL_CHANGE_FORBIDDEN')
        (code/'datafirst.py').write_bytes(raw)
        for path in [code, *code.rglob('*')]:
            path.chmod(0o755 if path.is_dir() else 0o644)
        candidate = guard.changed_profile(profile, config['service'], code)
        candidate['services'][config['service']].setdefault('environment', {})['VECTOR_SERVER_NAME'] = args.server_name
        candidate_raw = json.dumps(candidate, indent=2).replace('$', '$$').encode()+b'\n'
        record = dict(original_identity=guard.identity(row), original_code=str(installed), original_files=prior['candidate_files'],
            candidate_code=str(code), candidate_files=guard.tree_files(code), other_containers=guard.others(before, assistant),
            candidate_compose_sha256=guard.digest(candidate_raw), candidate_profile_sha256=guard.digest(guard.canonical(candidate)))
        guard.write_private(directory/'operator.json', guard.canonical(config))
        guard.write_private(directory/'record.json', guard.canonical(record))
        guard.write_private(directory/'compose.original', original)
        guard.write_private(directory/'compose.candidate.json', candidate_raw)
        if guard.compose(config, directory/'compose.candidate.json') != candidate:
            raise RuntimeError('CANDIDATE_RENDER_CHANGED')
        for name, path in (('guard.py', args.guard_helper), ('release.py', args.release_helper), ('deploy.py', Path(__file__))):
            guard.write_private(directory/name, path.read_bytes())
        rollback_args = [str(directory/'deploy.py'), '--guard-helper', str(directory/'guard.py'),
            '--release-helper', str(directory/'release.py'), '--baseline', str(baseline), '--source', str(args.source),
            '--release-root', str(args.release_root), '--lock-file', str(args.lock_file), '--server-name', args.server_name,
            '--rollback', str(directory)]
        guard.write_private(directory/'rollback.py', ('#!/usr/bin/env python3\nimport runpy,sys\nsys.dont_write_bytecode=True\nsys.argv='+repr(rollback_args)+'\nrunpy.run_path(sys.argv[0],run_name="__main__")\n').encode())
        print('Release und Rückrollbelege: '+str(directory), flush=True)
        print('Rollback: python3 '+str(directory/'rollback.py'), flush=True)
        def interrupted(signum, frame):
            raise InterruptedError('CONTEXT_UPDATE_INTERRUPTED')
        signal.signal(signal.SIGTERM, interrupted)
        try:
            current = guard.inventory()
            if (not unchanged(before, current, '') or active.read_bytes() != original
                    or guard.tree_files(installed) != prior['candidate_files']):
                raise RuntimeError('PRE_ACTIVATION_DRIFT')
            release.activate(guard, config, directory, record, candidate_raw, original)
            if not unchanged(before, guard.inventory(), assistant):
                raise RuntimeError('OTHER_SERVICE_CONFIGURATION_CHANGED')
            result = dict(deployed=True, knowledge_mode='qwen35-data-first', model=proof['model'],
                game_restart=False, only_assistant_recreated=True, other_services_unchanged=True,
                model_calls=0, cloud_calls=0, messages_sent=0, native_quality_retested=False,
                release=str(directory), rollback=str(directory/'rollback.py'))
            guard.write_private(directory/'result.json', guard.canonical(result))
            print(json.dumps(result, indent=2), flush=True)
        except BaseException:
            mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
            try:
                if active.read_bytes() == candidate_raw:
                    guard.rollback(directory, allow_missing=True)
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            raise


if __name__ == '__main__':
    main()
