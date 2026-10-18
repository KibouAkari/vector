"""Private stopped-container preservation. Never publish images or read mounted data."""
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import tarfile
import time

LABEL = 'com.vector.fegcraft-root-preservation'
LIMIT = 32 * 1024 * 1024


def run(*args, timeout=30):
    value = subprocess.run(args, capture_output=True, timeout=timeout)
    if value.returncode or len(value.stdout) > 2_000_000:
        raise RuntimeError('ROOT_PRESERVATION_COMMAND_FAILED')
    return value.stdout


def inspect(kind, name):
    return json.loads(run('docker', kind, 'inspect', name))[0]


def evidence(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump(value, handle, indent=2); handle.write('\n'); handle.flush(); os.fsync(handle.fileno())


def stopped(container):
    state = container['State']
    if state['Running'] or state.get('Restarting') or state.get('OOMKilled') or state.get('ExitCode') not in (0, 143):
        raise RuntimeError('ROOT_PRESERVATION_CLEAN_STOP_REQUIRED')


def allowed_path(value):
    if not isinstance(value, str):
        raise RuntimeError('ROOT_PRESERVATION_PATH_REFUSED')
    path = Path(value)
    if (not path.is_absolute() or str(path) != value or '..' in path.parts
            or value == '/' or value == '/data' or value.startswith('/data/') or any(ord(c) < 32 for c in value)):
        raise RuntimeError('ROOT_PRESERVATION_PATH_REFUSED')


def copy_archive(container, path, target):
    """Bound time and bytes before parsing; retain a partial only in private evidence."""
    allowed_path(path)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    process = None
    try:
        with os.fdopen(fd, 'wb') as output:
            process = subprocess.Popen(['docker', 'cp', container + ':' + path, '-'],
                                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                end, total = time.monotonic() + 20, 0
                while selector.get_map():
                    if time.monotonic() > end:
                        raise RuntimeError('ROOT_PRESERVATION_COPY_TIMEOUT')
                    for key, _ in selector.select(.2):
                        block = os.read(key.fd, 65536)
                        if not block:
                            selector.unregister(key.fileobj)
                            continue
                        total += len(block)
                        if total > LIMIT:
                            raise RuntimeError('ROOT_PRESERVATION_COPY_LIMIT')
                        output.write(block)
            if process.wait(timeout=3):
                raise RuntimeError('ROOT_PRESERVATION_COPY_FAILED')
            output.flush()
            os.fsync(output.fileno())
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            process.stdout.close()


def archive_fingerprint(path):
    """Compare contents and all archived metadata; never extract a private archive."""
    entries, total = {}, 0
    with tarfile.open(path, 'r:') as archive:
        for member in archive:
            name = member.name.rstrip('/')
            relative = Path(name)
            if (relative.is_absolute() or '..' in relative.parts or name in entries or len(entries) >= 10000
                    or not (member.isfile() or member.isdir() or member.issym() or member.islnk())):
                raise RuntimeError('ROOT_PRESERVATION_ARCHIVE_REFUSED')
            total += member.size
            if member.size < 0 or total > LIMIT:
                raise RuntimeError('ROOT_PRESERVATION_ARCHIVE_LIMIT')
            checksum = None
            if member.isfile():
                digest = hashlib.sha256()
                with archive.extractfile(member) as stream:
                    for block in iter(lambda: stream.read(65536), b''):
                        digest.update(block)
                checksum = digest.hexdigest()
            entries[name] = [member.type.decode(), member.size, member.mode, member.uid, member.gid,
                             member.mtime, member.linkname, member.pax_headers, checksum]
    if not entries:
        raise RuntimeError('ROOT_PRESERVATION_EMPTY_ARCHIVE')
    return hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()


def unspecified_user(value):
    # OCI ImageConfig.User is an optional string with json omitempty. Docker
    # container inspection retains "" while committed image inspection can omit
    # it (get -> None). Only these two spellings mean no user override.
    # https://github.com/opencontainers/image-spec/blob/main/specs-go/v1/config.go
    return '' if value is None else value


def validate_image(container, parent, image, owner):
    expected = container['Config']
    actual = image['Config']
    keys = ('Entrypoint', 'Cmd', 'Env', 'WorkingDir', 'Volumes', 'ExposedPorts',
            'Healthcheck', 'StopSignal', 'Shell', 'OnBuild')
    if (any(expected.get(k) != actual.get(k) for k in keys)
            or unspecified_user(expected.get('User')) != unspecified_user(actual.get('User'))
            or actual.get('Labels') != dict(expected.get('Labels') or {}, **{LABEL: owner})
            or image.get('Os') != parent.get('Os') or image.get('Architecture') != parent.get('Architecture')):
        raise RuntimeError('ROOT_PRESERVATION_IMAGE_CONFIG_CHANGED')
    layers = parent['RootFS']['Layers']
    current = image['RootFS']['Layers']
    if (current[:len(layers)] != layers or len(current) not in (len(layers), len(layers) + 1)
            or image['Size'] - parent['Size'] > 64 * 1024 * 1024
            or set(actual.get('Volumes') or {}) - {'/data'}):
        raise RuntimeError('ROOT_PRESERVATION_IMAGE_SCOPE_CHANGED')


def preserve(container_id, paths, directory, owner):
    if not re.fullmatch('[a-f0-9]{64}', container_id) or not re.fullmatch('[a-f0-9]{12}', owner):
        raise RuntimeError('ROOT_PRESERVATION_OWNER_INVALID')
    if len(paths) > 8 or len({p['path'] for p in paths}) != len(paths):
        raise RuntimeError('ROOT_PRESERVATION_PATH_COUNT_LIMIT')
    game = inspect('container', container_id)
    stopped(game)
    parent = inspect('image', game['Image'])
    for index, row in enumerate(paths):
        if row['change'] not in ('A', 'C'):
            raise RuntimeError('ROOT_PRESERVATION_DELETED_PATH_REQUIRES_REVIEW')
        copy_archive(container_id, row['path'], directory / ('root-before-' + str(index) + '.tar'))
    tag = 'vector-fegcraft-private-root:' + owner
    evidence(directory / 'root-preservation-intent.json', {'owner': owner, 'tag': tag,
             'container': container_id, 'parent_image': game['Image'], 'never_push_image': True})
    # The game is already stopped. No pause of any live service and no world copy.
    print('Sichere private Docker-Schicht. Zeitlimit für diesen Schritt: 45 Sekunden.', flush=True)
    raw = run('docker', 'commit', '--change', 'LABEL ' + LABEL + '=' + owner,
              container_id, tag, timeout=45).decode().strip()
    if not re.fullmatch('sha256:[a-f0-9]{64}', raw):
        raise RuntimeError('ROOT_PRESERVATION_IMAGE_ID_INVALID')
    evidence(directory / 'root-preservation-image.json', {'owner': owner, 'image': raw, 'tag': tag})
    image = inspect('image', raw)
    validate_image(game, parent, image, owner)
    name = 'vector-root-proof-' + owner
    probe = None
    try:
        probe = run('docker', 'create', '--name', name, '--network', 'none', '--read-only',
                    '--label', LABEL + '=' + owner, '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                    '--label', 'com.docker.compose.project=' + name, '--label', 'com.docker.compose.service=root-proof',
                    '--mount', 'type=tmpfs,destination=/data', '--entrypoint', '/bin/true', raw).decode().strip()
        value = inspect('container', probe)
        if (value['State']['Running'] or value['Image'] != raw
                or unspecified_user(value['Config'].get('User')) != unspecified_user(game['Config'].get('User'))):
            raise RuntimeError('ROOT_PRESERVATION_REFERENCE_NOT_ISOLATED')
        fingerprints = []
        print('Vergleiche die geänderten Dateien mit der gesicherten Containerschicht.', flush=True)
        for index, row in enumerate(paths):
            restored = directory / ('root-image-' + str(index) + '.tar')
            copy_archive(probe, row['path'], restored)
            before = archive_fingerprint(directory / ('root-before-' + str(index) + '.tar'))
            if archive_fingerprint(restored) != before:
                raise RuntimeError('ROOT_PRESERVATION_IMAGE_CONTENT_MISMATCH')
            fingerprints.append(before)
        stopped(inspect('container', container_id))
        return {'image': raw, 'tag': tag, 'owner': owner, 'path_count': len(paths),
                'archived_metadata_and_content_verified': True, 'private_archive_fingerprints': fingerprints,
                'mounted_world_included': False, 'never_push_image': True}
    finally:
        if probe is not None:
            value = inspect('container', probe)
            if value['State']['Running'] or value['Config'].get('Labels', {}).get(LABEL) != owner:
                raise RuntimeError('ROOT_PRESERVATION_REFERENCE_OWNER_CHANGED')
            run('docker', 'rm', probe)

