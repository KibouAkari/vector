#!/usr/bin/env python3
"""Install the qualified private NER profile; no inference or cloud requests.

Run the generated feature rollback before the separate source/image rollback.
All rollback inputs are local private files. Existing services are never removed.
"""
import ast
import copy
from datetime import datetime, timezone
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
import time

ROOT = Path('/root/vector-workspace')
REPO = ROOT / 'github/vector'
COMPOSE = Path('/opt/vector/docker-compose.yml')
MERGED = 'ba30c82f0a7b66a29272c1711858ac78ad522238'
TESTED = 'a20b9a650546e9cf8fbbba9b0fbc9f85acaf88a5'
IMAGE = 'sha256:e59160f17f47b2b8231e417bc64c25ce82a5a7320be6a0b47c6d8b226f699a80'
TAG = 'vector-app:staging-a20b9a6-20261016T084935Z-7b04eb'
NATIVE_IMAGE = 'sha256:eca0b83a886fcc9952ef13755853ef63134e5c76733d40564460398776c92dd7'
NETWORK = 'vector-privacy-ner'
SERVICE = 'privacy-ner'
DIRECTORY = Path('/opt/vector/privacy-ner')
TOKEN_TARGET = '/run/secrets/vector_privacy_ner_token'
OLD_COMPOSE_HASH = '64ac69df11b6c959e1f876a01cad32dee121705f7a510dd34650a4116fd2702d'
API_REPORT = ROOT / 'releases/vector-privacy-api-evaluation-20261016T085057Z-e2680b/result.json'
OWNER_LABEL = 'com.vector.privacy.activation'


def helpers():
    code = __import__('subprocess').check_output([
        'git', '-C', str(REPO), 'show', MERGED + ':scripts/deploy/activate-local-workers.py'], text=True)
    namespace = {'__name__': 'privacy_activation_helpers'}
    exec(compile(ast.parse(code), 'pinned-local-worker-helpers', 'exec'), namespace)
    h = namespace['helpers']()
    h['app_image_or_missing'] = lambda: namespace['app_image_or_missing'](h)
    return h


def digest(data):
    return hashlib.sha256(data).hexdigest()


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


def bind(source, target):
    return dict(type='bind', source=str(source), target=target, read_only=True,
                bind={'create_host_path': False})


def native_service(code, token, stamp):
    return dict(image=NATIVE_IMAGE, container_name=NETWORK, user='65534:65534',
                working_dir='/work', command=['python', '/work/server.py'],
                read_only=True, cap_drop=['ALL'], security_opt=['no-new-privileges:true'],
                cpus=2, mem_limit='4g', memswap_limit='4g', pids_limit=128,
                tmpfs=['/tmp:rw,nosuid,nodev,size=256m,mode=1777'],
                environment=dict(HF_HOME='/tmp/hf', HF_HUB_OFFLINE='1',
                                 TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false',
                                 VECTOR_PRIVACY_NER_IDLE_SECONDS='300'),
                volumes=[bind(code, '/work'), bind(token, TOKEN_TARGET)],
                networks=[NETWORK], restart='unless-stopped',
                labels={OWNER_LABEL: stamp})


def candidate_bytes(original, service, token):
    source = original.decode('utf8')
    if '\r' in source or not source.endswith('\n'):
        raise RuntimeError('Unexpected Compose newline format.')
    lines = source.splitlines()
    first, last = section(lines, 'app', 2)
    env, env_end = section(lines, 'environment', 4, first + 1, last)
    children = [line for line in lines[env + 1:env_end] if line.strip() and not line.lstrip().startswith('#')]
    if not children or any(not line.startswith('      ') or line.lstrip().startswith('- ') for line in children):
        raise RuntimeError('Expected environment mapping.')
    if any(re.match(r'\s*VECTOR_PRIVACY_REVIEW\s*:', line) for line in children):
        raise RuntimeError('Privacy flag already configured; requires review.')
    lines.insert(env + 1, '      VECTOR_PRIVACY_REVIEW: "1"')
    for header, item in [('networks', NETWORK), ('volumes', bind(token, TOKEN_TARGET))]:
        first, last = section(lines, 'app', 2)
        pos, end = section(lines, header, 4, first + 1, last, sequence=True)
        children = [line for line in lines[pos + 1:end] if line.strip() and not line.lstrip().startswith('#')]
        if not children or not children[0].lstrip().startswith('- '):
            raise RuntimeError('Expected Compose sequence: ' + header)
        indent = len(children[0]) - len(children[0].lstrip())
        lines.insert(pos + 1, ' ' * indent + '- ' + json.dumps(item))
    pos, end = section(lines, 'services', 0)
    lines.insert(pos + 1, '  ' + SERVICE + ': ' + json.dumps(service))
    pos, end = section(lines, 'networks', 0)
    lines.insert(pos + 1, '  ' + NETWORK + ': ' + json.dumps(dict(external=True, name=NETWORK)))
    return ('\n'.join(lines) + '\n').encode()


def normalized(value):
    result = copy.deepcopy(value)
    network = result.get('networks', {}).get(NETWORK, {})
    if network.get('external') is True and network.get('name') == NETWORK and network.get('ipam') == {}:
        del network['ipam']
    # Compose preserves mount insertion order on this host. Compare the full
    # app mount definitions in target order; no flags or fields are discarded.
    app = result.get('services', {}).get('app', {})
    if 'volumes' in app:
        mounts = app['volumes']
        if (not isinstance(mounts, list) or any(not isinstance(m, dict)
                or not isinstance(m.get('target'), str) for m in mounts)):
            raise RuntimeError('Unexpected canonical app mount definitions.')
        targets = [m['target'] for m in mounts]
        if len(set(targets)) != len(targets):
            raise RuntimeError('Duplicate app mount targets; requires review.')
        app['volumes'] = sorted(mounts, key=lambda m: m['target'])
    return result


def expected_config(base, profile):
    value = copy.deepcopy(base)
    app = value['services']['app']
    if app.get('image') != TAG or set(app.get('networks', {})) != {'vector-internal', 'vector-local-inference'}:
        raise RuntimeError('Qualified app image or existing networks differ.')
    if str(app.get('environment', {}).get('VECTOR_LOCAL_WORKERS')) != '1':
        raise RuntimeError('Existing local-worker feature is not enabled.')
    if str(app.get('environment', {}).get('VECTOR_PRIVACY_REVIEW', '0')).lower() not in ('0', 'false'):
        raise RuntimeError('Privacy is already enabled.')
    if SERVICE in value['services'] or NETWORK in value.get('networks', {}):
        raise RuntimeError('Private service profile already present.')
    app.setdefault('environment', {})['VECTOR_PRIVACY_REVIEW'] = '1'
    app['networks'][NETWORK] = None
    # Compose canonicalizes bind mounts independently using this minimal profile.
    token_mount = profile['services']['token-check']['volumes'][0]
    if any(v.get('target') == TOKEN_TARGET for v in app.get('volumes', [])):
        raise RuntimeError('Secret mount target already exists.')
    app.setdefault('volumes', []).append(token_mount)
    value['services'][SERVICE] = profile['services'][SERVICE]
    value.setdefault('networks', {})[NETWORK] = profile['networks'][NETWORK]
    return normalized(value)


def network_object(h):
    return json.loads(h['run']('docker', 'network', 'inspect', NETWORK))[0]


def owned_native(h, record):
    existing = h['run']('docker', 'container', 'ls', '--all', '--no-trunc',
                        '--filter', 'name=^/' + NETWORK + '$', '--format', '{{.ID}}').strip()
    if not existing:
        return None
    native = h['obj'](NETWORK)
    if native['Image'] != NATIVE_IMAGE or native['Config'].get('Labels', {}).get(OWNER_LABEL) != record['stamp']:
        raise RuntimeError('Refusing to alter a different native service.')
    return native


def verify_private(h, record):
    native = owned_native(h, record)
    if not native or not native['State']['Running']:
        raise RuntimeError('Native service is not running.')
    host = native['HostConfig']
    if (set(native['NetworkSettings']['Networks']) != {NETWORK}
            or host.get('PortBindings') or native['Config'].get('ExposedPorts')
            or not host.get('ReadonlyRootfs') or native['Config'].get('User') != '65534:65534'
            or host.get('Memory') != 4 * 1024 ** 3 or host.get('MemorySwap') != 4 * 1024 ** 3
            or host.get('NanoCpus') != 2000000000 or host.get('PidsLimit') != 128
            or host.get('CapDrop') != ['ALL']
            or not any(v in ('no-new-privileges', 'no-new-privileges:true') for v in host.get('SecurityOpt', []))
            or host.get('RestartPolicy', {}).get('Name') != 'unless-stopped'):
        raise RuntimeError('Native runtime isolation differs from the qualified profile.')
    network = network_object(h)
    app = h['obj']('vector-app')
    if (not network['Internal'] or network.get('Labels', {}).get(OWNER_LABEL) != record['stamp']
            or set(network.get('Containers', {})) != {native['Id'], app['Id']}):
        raise RuntimeError('Unexpected private network members or ownership.')
    if (set(app['NetworkSettings']['Networks']) != {'vector-internal', 'vector-local-inference', NETWORK}
            or 'VECTOR_PRIVACY_REVIEW=1' not in app['Config']['Env']
            or 'VECTOR_LOCAL_WORKERS=1' not in app['Config']['Env']):
        raise RuntimeError('Persistent application wiring differs.')
    app_mounts = [m for m in app['Mounts'] if m['Destination'] != TOKEN_TARGET]
    stable = lambda items: sorted(items, key=lambda m: json.dumps(m, sort_keys=True))
    token_mounts = [m for m in app['Mounts'] if m['Destination'] == TOKEN_TARGET]
    if (stable(app_mounts) != stable(record['app_mounts']) or len(token_mounts) != 1
            or token_mounts[0]['Source'] != str(DIRECTORY / 'token') or token_mounts[0]['RW']):
        raise RuntimeError('Application mount preservation or private token access differs.')
    expected_mounts = {'/work': str(DIRECTORY / ('code-' + TESTED)), TOKEN_TARGET: str(DIRECTORY / 'token')}
    if (len(native['Mounts']) != 2 or any(m['RW'] or expected_mounts.get(m['Destination']) != m['Source'] for m in native['Mounts'])):
        raise RuntimeError('Native code/token mounts differ.')
    # Authenticated health is metadata only and never wakes the model.
    code = """
const fs=require('node:fs');
(async()=>{
const token=fs.readFileSync('/run/secrets/vector_privacy_ner_token','utf8').trim();
if(!/^[a-f0-9]{64}$/.test(token))throw Error('Invalid token');
const r=await fetch('http://vector-privacy-ner:8091/health',{redirect:'error',headers:{Authorization:'Bearer '+token},signal:AbortSignal.timeout(5000)});
if(!r.ok)throw Error('Private health failed'); const v=await r.json();
if(v.ok!==true||v.model!=='urchade/gliner_multi_pii-v1'||v.model_revision!=='1fcf13e85f4eef5394e1fcd406cf2ca9ea82351d'||v.state!=='sleeping')throw Error('Model metadata differs');
})().catch(()=>process.exitCode=1);
"""
    for attempt in range(20):
        try:
            h['run']('docker', 'exec', 'vector-app', 'node', '-e', code, timeout=10)
            return
        except RuntimeError:
            if attempt == 19:
                raise RuntimeError('Authenticated private model health not confirmed.') from None
            time.sleep(0.5)


def rollback(h, record_path, manual=False):
    record = json.loads(record_path.read_text())
    if (record.get('commit'), record.get('image_id')) != (MERGED, IMAGE):
        raise RuntimeError('Unexpected privacy activation rollback record.')
    original = (record_path.parent / 'compose.original.yml').read_bytes()
    candidate = (record_path.parent / 'compose.candidate.yml').read_bytes()
    if digest(original) != record['original_sha256'] or digest(candidate) != record['candidate_sha256']:
        raise RuntimeError('Activation backup changed.')
    if COMPOSE.is_symlink() or COMPOSE.read_bytes() not in (original, candidate):
        raise RuntimeError('Compose changed; refusing rollback overwrite.')
    if h['app_image_or_missing']() not in (None, IMAGE):
        raise RuntimeError('Another application release is running.')
    if h['tree_hash'](h['LIVE']) != record['source_hash']:
        raise RuntimeError('Application source changed; inspect before rollback.')
    if manual:
        h['idle']()
    native = owned_native(h, record)
    # Disconnect the app before removing the independently owned private service.
    h['atomic'](COMPOSE, original, record['mode'], record['uid'], record['gid'])
    h['compose_up']()
    if not h['healthy'](IMAGE):
        raise RuntimeError('Feature rollback app health not confirmed.')
    app = h['obj']('vector-app')
    if (set(app['NetworkSettings']['Networks']) != {'vector-internal', 'vector-local-inference'}
            or 'VECTOR_PRIVACY_REVIEW=1' in app['Config']['Env']):
        raise RuntimeError('Feature rollback wiring not confirmed.')
    if native:
        h['run']('docker', 'rm', '--force', native['Id'], timeout=30)
    if record.get('network_created'):
        network = network_object(h)
        if network.get('Labels', {}).get(OWNER_LABEL) != record['stamp'] or network.get('Containers'):
            raise RuntimeError('Private network ownership/empty check failed.')
        h['run']('docker', 'network', 'rm', network['Id'])
        record['network_created'] = False
    h['verify_others'](record['other_containers'])
    record['status'] = 'rolled-back'
    h['save_record'](record_path, record)
    print('Privacy feature rollback confirmed. Local workers and qualified app retained.')


def install_code(h, code_dir):
    hashes = {}
    for name, path in [('server.py', 'services/privacy-ner/server.py'), ('privacy-ner-core.py', 'lib/privacy-ner-core.py')]:
        # The inspected archived run() returns bytes (also used by write_bytes
        # during source release). Preserve exact Git bytes and trailing newlines.
        data = h['run']('git', '-C', str(REPO), 'show', TESTED + ':' + path)
        if not isinstance(data, bytes):
            raise RuntimeError('Archived byte-output helper contract changed.')
        ast.parse(data)
        h['atomic'](code_dir / name, data, 0o644, 0, 0)
        hashes[name] = digest(data)
    return hashes


def check_private_path(path, mode, *, directory=False, owner=0):
    metadata = path.lstat()
    expected_kind = stat.S_ISDIR if directory else stat.S_ISREG
    if (not expected_kind(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != mode
            or metadata.st_uid != owner or metadata.st_gid != (0 if owner == 0 else os.getgid())
            or (not directory and metadata.st_nlink != 1)):
        raise RuntimeError('Prepared privacy file type, ownership or permissions differ.')


def prepare_private_files(h, directory, *, owner=0):
    code_dir = directory / ('code-' + TESTED)
    token = directory / 'token'
    if not directory.exists() and not directory.is_symlink():
        directory.mkdir(mode=0o700)
        code_dir.mkdir(mode=0o755)
        code_dir.chmod(0o755)  # explicit bind-root access under root's 0077 umask
        hashes = install_code(h, code_dir)
        h['atomic'](token, (secrets.token_hex(32) + '\n').encode(), 0o444, 0, 0)
        return code_dir, token, hashes
    # An earlier canonical comparison stopped before any live wiring changed.
    # Reuse exact trusted bytes and token without changing or deleting files.
    check_private_path(directory, 0o700, directory=True, owner=owner)
    if {p.name for p in directory.iterdir()} != {code_dir.name, token.name}:
        raise RuntimeError('Unexpected prepared privacy directory contents.')
    check_private_path(code_dir, 0o755, directory=True, owner=owner)
    if {p.name for p in code_dir.iterdir()} != {'server.py', 'privacy-ner-core.py'}:
        raise RuntimeError('Unexpected prepared privacy code files.')
    hashes = {}
    for name, source in [('server.py', 'services/privacy-ner/server.py'), ('privacy-ner-core.py', 'lib/privacy-ner-core.py')]:
        path = code_dir / name
        check_private_path(path, 0o644, owner=owner)
        expected = h['run']('git', '-C', str(REPO), 'show', TESTED + ':' + source)
        if not isinstance(expected, bytes) or path.read_bytes() != expected:
            raise RuntimeError('Prepared privacy code differs from the qualified Git revision.')
        hashes[name] = digest(expected)
    check_private_path(token, 0o444, owner=owner)
    if token.stat().st_size != 65 or not re.fullmatch(b'[a-f0-9]{64}\n', token.read_bytes()):
        raise RuntimeError('Prepared private token format differs.')
    print('Verified prepared code, permissions and private token; reusing without overwrite.')
    return code_dir, token, hashes


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
        qualification = json.loads(API_REPORT.read_text())
        if (qualification.get('passed') is not True or qualification.get('revision') != TESTED
                or qualification.get('app_image') != IMAGE or qualification.get('native_image') != NATIVE_IMAGE
                or qualification.get('production_unchanged') is not True):
            raise RuntimeError('Observed enabled API qualification differs.')
        original = COMPOSE.read_bytes()
        matches = []
        for path in (ROOT / 'releases').glob('vector-privacy-release-*/release.json'):
            record = json.loads(path.read_text())
            if (record.get('commit'), record.get('image_id'), record.get('status')) == (MERGED, IMAGE, 'deployed'):
                if (path.parent / 'compose.candidate.yml').read_bytes() == original:
                    matches.append((path, record))
        if len(matches) != 1:
            raise RuntimeError('Exactly one matching completed privacy app release is required.')
        source_path, source_record = matches[0]
        if digest((source_path.parent / 'compose.original.yml').read_bytes()) != OLD_COMPOSE_HASH:
            raise RuntimeError('Original deployment profile differs.')
        if h['tree_hash'](h['LIVE']) != source_record['new_source_hash']:
            raise RuntimeError('Application source changed after release.')
        if h['obj']('vector-app')['Image'] != IMAGE or not h['healthy'](IMAGE, attempts=1):
            raise RuntimeError('Qualified app is not healthy.')
        if h['run']('docker', 'network', 'ls', '--filter', 'name=^' + NETWORK + '$', '--format', '{{.ID}}').strip():
            raise RuntimeError('Private network already exists.')
        if h['run']('docker', 'container', 'ls', '--all', '--filter', 'name=^/' + NETWORK + '$', '--format', '{{.ID}}').strip():
            raise RuntimeError('Private container already exists.')
        if json.loads(h['run']('docker', 'image', 'inspect', NATIVE_IMAGE))[0]['Id'] != NATIVE_IMAGE:
            raise RuntimeError('Qualified native image is unavailable.')
        base = h['config'](COMPOSE)
        others = {name: h['identity'](name) for name in (*h['OTHERS'], 'vector-local-inference')}
        before = h['identity']('vector-app')
        meta = COMPOSE.stat()
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
        release = ROOT / 'releases' / ('vector-privacy-activation-' + stamp)
        release.mkdir(mode=0o700)
        code_dir, token, code_hashes = prepare_private_files(h, DIRECTORY)
        service = native_service(code_dir, token, stamp)
        candidate = candidate_bytes(original, service, token)
        temporary = COMPOSE.parent / ('.vector-privacy-activation-' + stamp + '.yml')
        profile_path = COMPOSE.parent / ('.vector-privacy-profile-' + stamp + '.json')
        try:
            profile = dict(services={SERVICE: service, 'token-check': dict(image=IMAGE, volumes=[bind(token, TOKEN_TARGET)])},
                           networks={NETWORK: dict(external=True, name=NETWORK)})
            h['atomic'](profile_path, json.dumps(profile).encode(), 0o600, 0, 0)
            expected = expected_config(base, normalized(h['config'](profile_path)))
            h['atomic'](temporary, candidate, 0o600, 0, 0)
            if normalized(h['config'](temporary)) != expected:
                raise RuntimeError('Candidate changes more than the approved private service, flag, network and token mount.')
        finally:
            temporary.unlink(missing_ok=True)
            profile_path.unlink(missing_ok=True)
        for name, data in [('compose.original.yml', original), ('compose.candidate.yml', candidate)]:
            h['atomic'](release / name, data, 0o600, 0, 0)
        copied = release / 'activate.py'
        shutil.copy2(Path(__file__).resolve(), copied)
        copied.chmod(0o700)
        record = dict(commit=MERGED, image_id=IMAGE, native_image=NATIVE_IMAGE, stamp=stamp,
                      source_release=str(source_path.parent), source_hash=source_record['new_source_hash'],
                      mode=stat.S_IMODE(meta.st_mode), uid=meta.st_uid, gid=meta.st_gid,
                      original_sha256=digest(original), candidate_sha256=digest(candidate),
                      code_sha256=code_hashes, token_sha256=digest(token.read_bytes()),
                      other_containers=others, app_mounts=h['obj']('vector-app')['Mounts'],
                      network_created=False, status='prepared')
        record_path = release / 'activation.json'
        h['save_record'](record_path, record)
        rollback_script = '#!/usr/bin/env bash\nset -Eeuo pipefail\nexec python3 ' + str(copied) + ' --rollback ' + str(record_path) + '\n'
        h['atomic'](release / 'rollback.sh', rollback_script.encode(), 0o700, 0, 0)
        # Exact unprivileged read checks before changing the running app/profile.
        h['run']('docker', 'run', '--rm', '--pull', 'never', '--network', 'none', '--user', '65534:65534',
                 '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                 '--mount', f'type=bind,src={code_dir},dst=/work,readonly',
                 '--mount', f'type=bind,src={token},dst={TOKEN_TARGET},readonly', NATIVE_IMAGE,
                 'python', '-c', "from pathlib import Path; [Path(p).read_bytes() for p in ['/work/server.py','/work/privacy-ner-core.py','/run/secrets/vector_privacy_ner_token']]; assert Path('/models/entity/model.safetensors').is_file()")
        h['run']('docker', 'run', '--rm', '--pull', 'never', '--network', 'none', '--user', '1001:1001',
                 '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                 '--mount', f'type=bind,src={token},dst={TOKEN_TARGET},readonly', '--entrypoint', 'node', IMAGE,
                 '-e', "require('node:fs').readFileSync('/run/secrets/vector_privacy_ner_token')")
        h['idle']()
        h['verify_others'](others)
        if COMPOSE.read_bytes() != original or h['identity']('vector-app') != before:
            raise RuntimeError('Production changed during activation preparation.')
        try:
            h['run']('docker', 'network', 'create', '--internal', '--label', OWNER_LABEL + '=' + stamp, NETWORK)
            record['network_created'] = True
            h['save_record'](record_path, record)
            h['atomic'](COMPOSE, candidate, record['mode'], record['uid'], record['gid'])
            h['run']('docker', 'compose', '--project-directory', str(COMPOSE.parent), '-f', str(COMPOSE),
                     'up', '-d', '--no-deps', '--no-build', '--pull', 'never', SERVICE, timeout=180)
            h['compose_up']()
            if not h['healthy'](IMAGE):
                raise RuntimeError('Activated app health not confirmed.')
            if normalized(h['config'](COMPOSE)) != expected:
                raise RuntimeError('Persistent Compose verification failed.')
            verify_private(h, record)
            h['verify_others'](others)
            if h['tree_hash'](h['LIVE']) != record['source_hash']:
                raise RuntimeError('Source changed during activation.')
            record['status'] = 'activated'
            h['save_record'](record_path, record)
        except BaseException:
            print('Activation failed. Attempting guarded feature rollback.', flush=True)
            try:
                rollback(h, record_path)
            except BaseException:
                print('CRITICAL: Automatic rollback was not confirmed. Inspect:', release / 'rollback.sh', flush=True)
            raise
        print('PRIVACY REVIEW ACTIVATED: qualified app, authenticated private service and persistent flag verified.')
        print('Model sleeps until needed and unloads after 300 idle seconds. Local workers retained.')
        print('No inference/cloud requests or database writes performed by this activation.')
        print('Feature rollback:', release / 'rollback.sh')
        print('Then optional app/source rollback:', source_path.parent / 'rollback.sh')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted. Inspect activation status before retrying.', file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print('ERROR:', str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__, file=sys.stderr)
        sys.exit(1)
