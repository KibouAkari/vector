#!/usr/bin/env python3
"""Activate the qualified release on its private network; no inference or DB writes.

Uses the owner's archived release helpers for health, idle checks and atomic files.
Run feature rollback before the separate source/image rollback.
"""
import ast
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import sys
from datetime import datetime, timezone

ROOT = Path('/root/vector-workspace')
COMPOSE = Path('/opt/vector/docker-compose.yml')
MERGED = '37130b59a6dad080076e1dea7ded563f996b1672'
IMAGE = 'sha256:d1b5b1f6c463627ba1daa20d44e9450c3862cdc4c80df245e0f94f1187f675bf'
TAG = 'vector-app:staging-b7bf796-20261015T132209Z-e0be3d'
ORIGINAL_HASH = 'ae1be307d986c7361cef9c1ee670acfa64a41a2a59f94530a59833098b90df70'
NETWORK = 'vector-local-inference'
INFERENCE_IMAGE = 'sha256:06d4cf34b8d726cc901d3cc663e36ac568b0012acf68ff2d6273fcf793e399d1'
MODELS = {
    'vector-qwen3:1.7b-q8': '97f1ed78571eac64f6b5b7413d9bc5f50fc95ab13ad4403cd813aebb9ba3a5b0',
    'vector-hermes3:8b-q4km': 'ddd98889feddbec419ccb27c2839214c100ce4ebae74f16b12fe17f5c6572a20',
}


def helpers():
    path = ROOT / 'archive/phases/vector-control-release.sh'
    source = path.read_text()
    begin, end = "<<'CONTROL_RELEASE_PYTHON'\n", '\nCONTROL_RELEASE_PYTHON\n'
    if source.count(begin) != 1 or source.count(end) != 1:
        raise RuntimeError('Archived release structure changed.')
    namespace = {'__name__': 'activation_helpers'}
    exec(compile(ast.parse(source.split(begin)[1].split(end)[0]), str(path), 'exec'), namespace)
    if namespace.get('MERGED') != 'd73f6f982db62532a80696d230dd77b01246c057':
        raise RuntimeError('Archived release baseline changed.')
    return namespace['prepare']()


def section(lines, header, indent, start=0, end=None, sequence=False):
    end = len(lines) if end is None else end
    matches = [i for i in range(start, end)
               if re.fullmatch(' ' * indent + re.escape(header) + r':\s*(?:#.*)?', lines[i])]
    if len(matches) != 1:
        raise RuntimeError('Unexpected Compose section layout: ' + header)
    first = matches[0]
    last = next((i for i in range(first + 1, end)
                 if lines[i].strip() and not lines[i].lstrip().startswith('#')
                 and not (sequence and lines[i].startswith(' ' * indent + '- '))
                 and len(lines[i]) - len(lines[i].lstrip()) <= indent), end)
    return first, last


def candidate_bytes(original):
    """Preserve raw YAML, comments and env substitutions; canonical comparison follows."""
    source = original.decode('utf-8')
    if '\r' in source or not source.endswith('\n'):
        raise RuntimeError('Unexpected Compose newline format.')
    lines = source.splitlines()
    first, last = section(lines, 'app', 2)
    env, env_end = section(lines, 'environment', 4, first + 1, last)
    children = [line for line in lines[env + 1:env_end]
                if line.strip() and not line.lstrip().startswith('#')]
    if not children or any(not line.startswith('      ') or line.lstrip().startswith('- ') for line in children):
        raise RuntimeError('Expected environment mapping.')
    if any(re.match(r'\s*VECTOR_LOCAL_WORKERS\s*:', line) for line in children):
        raise RuntimeError('Local-worker environment already configured; requires review.')
    lines.insert(env + 1, '      VECTOR_LOCAL_WORKERS: "1"')
    first, last = section(lines, 'app', 2)
    net, net_end = section(lines, 'networks', 4, first + 1, last, sequence=True)
    children = [line for line in lines[net + 1:net_end]
                if line.strip() and not line.lstrip().startswith('#')]
    if len(children) != 1 or not re.fullmatch(r'\s+- vector-internal\s*(?:#.*)?', children[0]):
        raise RuntimeError('Expected single existing internal network.')
    indent = len(children[0]) - len(children[0].lstrip())
    # Insert next to the existing item, including indentless YAML sequence style.
    lines.insert(net + 1, ' ' * indent + '- ' + NETWORK)
    first, last = section(lines, 'networks', 0)
    if any(re.match(r'\s*vector-local-inference\s*:', line) for line in lines[first + 1:last]):
        raise RuntimeError('Private network already configured.')
    lines[first + 1:first + 1] = [
        '  vector-local-inference:', '    external: true', '    name: vector-local-inference']
    return ('\n'.join(lines) + '\n').encode()


def expected_config(base):
    value = copy.deepcopy(base)
    app = value['services']['app']
    if app.get('image') != TAG or set(app.get('networks', {})) != {'vector-internal'}:
        raise RuntimeError('Source release image or networks differ.')
    if str(app.get('environment', {}).get('VECTOR_LOCAL_WORKERS', '0')).lower() not in ('0', 'false'):
        raise RuntimeError('Local workers were already enabled.')
    app.setdefault('environment', {})['VECTOR_LOCAL_WORKERS'] = '1'
    app['networks'][NETWORK] = None
    if NETWORK in value.get('networks', {}):
        raise RuntimeError('Private network already present in Compose.')
    value.setdefault('networks', {})[NETWORK] = {'name': NETWORK, 'external': True}
    return value


def activation_config(value):
    """Ignore only Compose's empty IPAM representation on this external network.

    The existing Docker network is inspected independently. Do not remove IPAM
    from other networks, or accept any supplied IPAM configuration here.
    """
    value = copy.deepcopy(value)
    network = value.get('networks', {}).get(NETWORK, {})
    if (network.get('external') is True and network.get('name') == NETWORK
            and type(network.get('ipam')) is dict and not network['ipam']):
        del network['ipam']
    return value


def rollback(h, record_path, manual=False):
    record = json.loads(record_path.read_text())
    if record.get('commit') != MERGED or record.get('image_id') != IMAGE:
        raise RuntimeError('Unexpected activation rollback record.')
    original = (record_path.parent / 'compose.original.yml').read_bytes()
    candidate = (record_path.parent / 'compose.candidate.yml').read_bytes()
    if hashlib.sha256(original).hexdigest() != record['original_sha256'] or hashlib.sha256(candidate).hexdigest() != record['candidate_sha256']:
        raise RuntimeError('Activation backup changed.')
    if COMPOSE.is_symlink() or COMPOSE.read_bytes() not in (original, candidate):
        raise RuntimeError('Compose changed; refusing rollback overwrite.')
    if h['obj']('vector-app')['Image'] != IMAGE:
        raise RuntimeError('Another application release is running.')
    if manual:
        h['idle']()
    h['atomic'](COMPOSE, original, record['mode'], record['uid'], record['gid'])
    h['compose_up']()
    if not h['healthy'](IMAGE):
        raise RuntimeError('Feature rollback health not confirmed.')
    if set(h['obj']('vector-app')['NetworkSettings']['Networks']) != {'vector-internal'}:
        raise RuntimeError('Feature rollback network not confirmed.')
    h['verify_others'](record['other_containers'])
    record['status'] = 'rolled-back'
    h['save_record'](record_path, record)
    print('Feature rollback confirmed. Qualified app retained; local workers disabled.')


def main():
    os.umask(0o077)
    if os.geteuid() != 0:
        raise RuntimeError('Run as root.')
    h = helpers()
    with (ROOT / '.chat-release.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if len(sys.argv) == 3 and sys.argv[1] == '--rollback':
            rollback(h, Path(sys.argv[2]), manual=True)
            return
        if len(sys.argv) != 1 or COMPOSE.is_symlink():
            raise RuntimeError('Unexpected arguments or Compose path.')
        original = COMPOSE.read_bytes()
        matches = []
        for path in (ROOT / 'releases').glob('vector-local-worker-release-*/release.json'):
            record = json.loads(path.read_text())
            if (record.get('commit'), record.get('image_id'), record.get('status')) == (MERGED, IMAGE, 'deployed'):
                if (path.parent / 'compose.candidate.yml').read_bytes() == original:
                    matches.append((path, record))
        if len(matches) != 1:
            raise RuntimeError('Exactly one matching completed source release is required.')
        release_path, source_record = matches[0]
        if h['sha'](release_path.parent / 'compose.original.yml') != ORIGINAL_HASH:
            raise RuntimeError('Original deployment profile differs.')
        if h['tree_hash'](h['LIVE']) != source_record['new_source_hash']:
            raise RuntimeError('Application source changed after release.')
        if h['obj']('vector-app')['Image'] != IMAGE or not h['healthy'](IMAGE, attempts=1):
            raise RuntimeError('Qualified app image is not healthy.')
        inference = h['obj'](NETWORK)
        if inference['Image'] != INFERENCE_IMAGE or not inference['State']['Running'] or inference['HostConfig'].get('PortBindings'):
            raise RuntimeError('Private inference runtime differs.')
        network = json.loads(h['run']('docker', 'network', 'inspect', NETWORK))[0]
        if not network['Internal'] or set(network.get('Containers', {})) != {inference['Id']}:
            raise RuntimeError('Expected isolated inference network.')
        base = h['config'](COMPOSE)
        expected = expected_config(base)
        candidate = candidate_bytes(original)
        others = {name: h['identity'](name) for name in (*h['OTHERS'], NETWORK)}
        before = h['identity']('vector-app')
        meta = COMPOSE.stat()
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
        release = ROOT / 'releases' / ('vector-local-worker-activation-' + stamp)
        release.mkdir(mode=0o700)
        temporary = COMPOSE.parent / ('.vector-local-worker-activation-' + stamp + '.yml')
        h['atomic'](temporary, candidate, 0o600, 0, 0)
        try:
            if activation_config(h['config'](temporary)) != expected:
                raise RuntimeError('Candidate changes more than approved flag and network.')
        finally:
            temporary.unlink(missing_ok=True)
        for name, data in (('compose.original.yml', original), ('compose.candidate.yml', candidate)):
            h['atomic'](release / name, data, 0o600, 0, 0)
        copied = release / 'activate.py'
        shutil.copy2(Path(__file__).resolve(), copied)
        copied.chmod(0o700)
        record = dict(commit=MERGED, image_id=IMAGE, source_release=str(release_path.parent),
                      mode=stat.S_IMODE(meta.st_mode), uid=meta.st_uid, gid=meta.st_gid,
                      original_sha256=hashlib.sha256(original).hexdigest(),
                      candidate_sha256=hashlib.sha256(candidate).hexdigest(),
                      other_containers=others, status='prepared')
        record_path = release / 'activation.json'
        h['save_record'](record_path, record)
        (release / 'rollback.sh').write_text('#!/usr/bin/env bash\nset -Eeuo pipefail\nexec python3 '
                                            + str(copied) + ' --rollback ' + str(record_path) + '\n')
        (release / 'rollback.sh').chmod(0o700)
        h['idle']()
        h['verify_others'](others)
        if COMPOSE.read_bytes() != original or h['identity']('vector-app') != before:
            raise RuntimeError('Production changed during activation preparation.')
        try:
            h['atomic'](COMPOSE, candidate, record['mode'], meta.st_uid, meta.st_gid)
            h['compose_up']()
            if not h['healthy'](IMAGE):
                raise RuntimeError('Activated app health not confirmed.')
            app = h['obj']('vector-app')
            if (set(app['NetworkSettings']['Networks']) != {'vector-internal', NETWORK}
                    or 'VECTOR_LOCAL_WORKERS=1' not in app['Config']['Env']
                    or app['Mounts'] != before['Mounts']
                    or activation_config(h['config'](COMPOSE)) != expected):
                raise RuntimeError('Persistent activation verification failed.')
            # Read native metadata from the actual app network; no inference, cloud or DB write.
            code = '''
const base='http://vector-local-inference:11434';
if(process.env.VECTOR_LOCAL_WORKERS!=='1') throw Error('Feature disabled');
const get=async path=>{const r=await fetch(base+path,{redirect:'error',signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error('Metadata request failed');return r.json()};
const version=await get('/api/version');
if(version.version!=='0.40.4')throw Error('Runtime version differs');
const tags=await get('/api/tags');
const expected=JSON.parse(process.argv[1]);
for(const [name,digest]of Object.entries(expected))if(!tags.models.some(m=>m.name===name&&m.digest===digest))throw Error('Model pin differs');
const loaded=await get('/api/ps');
if(loaded.models.length)throw Error('Expected idle models');
console.log('Private endpoint and model pins verified; weights unloaded.');
'''
            h['run']('docker', 'exec', 'vector-app', 'node', '--input-type=module', '-e', code,
                     json.dumps(MODELS), timeout=40)
            h['verify_others'](others)
            record['status'] = 'activated'
            h['save_record'](record_path, record)
        except BaseException:
            print('Activation failed. Restoring previous disabled feature configuration.', flush=True)
            rollback(h, record_path)
            raise
        print('LOCAL WORKERS ACTIVATED: persistent feature flag and private network verified.')
        print('Qwen 1.7B extraction; Hermes structured summaries; weights currently unloaded.')
        print('No inference/cloud calls or database writes performed by this activation.')
        print('Feature rollback:', release / 'rollback.sh')
        print('Then optional app/source rollback:', release_path.parent / 'rollback.sh')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted; inspect the private activation record before retrying.', file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print('ERROR:', str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__, file=sys.stderr)
        sys.exit(1)
