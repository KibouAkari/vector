#!/usr/bin/env python3
"""Owner-run read-only inventory. Never print names, config or secret values."""
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import types
import zipfile

ROOT = Path('/root/vector-workspace')
REPO = ROOT / 'github/vector'
BASE = Path('/opt/fegcraft-updated')


def command(*args):
    result = subprocess.run(args, capture_output=True, timeout=20)
    if result.returncode:
        raise RuntimeError('Read-only inventory command failed; raw output suppressed')
    return result.stdout


def container(name):
    value = json.loads(command('docker', 'inspect', name))[0]
    return {'running': value['State'].get('Running'), 'image': value['Image'],
            'networks': sorted(value['NetworkSettings']['Networks']),
            'data_mount_matches': any(m.get('Source') == str(BASE / 'data') and m.get('Destination') == '/data' for m in value['Mounts'])}


def main():
    revision = os.environ.get('VECTOR_FEGCRAFT_REV', '')
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise RuntimeError('Pinned VECTOR_FEGCRAFT_REV required')
    with (ROOT / '.chat-release.lock').open('r') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        config_paths = [BASE / 'docker-compose.yml', Path('/opt/vector/docker-compose.yml')]
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in config_paths}
        states_before = {name: json.loads(command('docker', 'inspect', name))[0]['Id'] for name in ('fegcraft-updated', 'vector-app', 'vector-local-inference')}
        module = types.ModuleType('qualified_stats')
        code = command('git', '-C', str(REPO), 'show', revision + ':services/fegcraft-assistant/stats.py')
        exec(compile(code, 'pinned_stats.py', 'exec'), module.__dict__)
        snapshot = module.snapshot(BASE / 'data/world/players/stats', BASE / 'data/usercache.json')
        jar = BASE / 'data/mods/dcintegration-fabric-MC26.2-3.2.1.jar'
        if jar.is_symlink() or not jar.is_file() or jar.stat().st_size > 80_000_000:
            raise RuntimeError('Expected installed integration JAR unavailable')
        with zipfile.ZipFile(jar) as archive:
            if archive.getinfo('fabric.mod.json').file_size > 65536:
                raise RuntimeError('Integration metadata exceeds limit')
            info = json.loads(archive.read('fabric.mod.json'))
            nested = archive.getinfo('META-INF/jars/dcintegration.common-3.2.1.jar')
            if nested.file_size > 30_000_000:
                raise RuntimeError('Installed integration API exceeds limit')
            with zipfile.ZipFile(io.BytesIO(archive.read(nested))) as common:
                for entry in ('de/erdbeerbaerlp/dcintegration/common/api/DiscordEventHandler.class', 'de/erdbeerbaerlp/dcintegration/common/DiscordIntegration.class'):
                    if common.getinfo(entry).file_size > 1_000_000:
                        raise RuntimeError('Integration API class exceeds limit')
                api = common.read('de/erdbeerbaerlp/dcintegration/common/api/DiscordEventHandler.class')
                core = common.read('de/erdbeerbaerlp/dcintegration/common/DiscordIntegration.class')
        models = command('docker', 'exec', 'vector-local-inference', 'ollama', 'list').decode()
        mods = []
        for path in sorted((BASE / 'data/mods').glob('*.jar')):
            if path.is_symlink() or path.stat().st_size > 100_000_000:
                continue
            try:
                with zipfile.ZipFile(path) as archive:
                    item = archive.getinfo('fabric.mod.json')
                    if item.file_size > 65536:
                        continue
                    value = json.loads(archive.read(item))
                name = value.get('id')
                if isinstance(name, str) and re.fullmatch(r'[a-z0-9_.-]{1,64}', name):
                    mods.append(name)
            except (KeyError, ValueError, OSError, zipfile.BadZipFile):
                continue
        addon_dir = BASE / 'data/DiscordIntegration-Data/addons'
        report = {
            'revision': revision,
            'minecraft': container('fegcraft-updated'),
            'local_inference': container('vector-local-inference'),
            'integration_version': info.get('version'),
            'integration_jar_sha256': hashlib.sha256(jar.read_bytes()).hexdigest(),
            'minecraft_hook_present': b'onMinecraftMessage' in api,
            'addon_registration_present': b'registerEventHandler' in core,
            'saved_statistics_coverage': snapshot['coverage'],
            'definitive_rankings_available': bool(snapshot['players']) and not snapshot['coverage']['skipped'] and not snapshot['coverage']['unnamed'],
            'readable_mod_metadata_count': len(set(mods)),
            'qualified_qwen_present': 'vector-qwen3:1.7b-q8' in models,
            'host_javac_available': shutil.which('javac') is not None,
            'addon_directory_exists': addon_dir.is_dir(),
            'existing_vector_addon': addon_dir.is_dir() and any('vector' in p.name.casefold() for p in addon_dir.glob('*.jar')),
            'production_compose_unchanged': all(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p, digest in before.items()),
            'production_container_identities_unchanged': all(json.loads(command('docker', 'inspect', name))[0]['Id'] == value for name, value in states_before.items()),
            'model_calls': 0, 'messages_sent': 0, 'production_activated': False,
        }
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as failure:
        print(json.dumps({'error': type(failure).__name__, 'detail': str(failure) if isinstance(failure, RuntimeError) else 'Read-only inventory failed; private details suppressed', 'production_activated': False}))
        raise SystemExit(1)
