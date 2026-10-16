#!/usr/bin/env python3
"""Build only our addon; compile-only API is not redistributed in its JAR."""
import argparse
import hashlib
import hmac
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'integrations/fegcraft-addon/build'
DEPENDENCY_URL = 'https://cdn.modrinth.com/data/rbJ7eS5V/versions/AzljeO7W/dcintegration-fabric-MC26.2-3.2.1.jar'
DEPENDENCY_SHA = '75e039ac6c8edad3c9423c91638ffd15d7c9b95dadb60bf69349da838afbf337'


def package_addon(classes, output):
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        def add(name, data):
            info = zipfile.ZipInfo(name, (2026, 10, 16, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
        add('META-INF/MANIFEST.MF', b'Manifest-Version: 1.0\nImplementation-Title: Vector Minecraft Assistant\nImplementation-Version: 0.1.0\n\n')
        for path in sorted(classes.rglob('*.class')):
            if path.name.startswith(('VectorAddonTest', 'VectorAddonFlowTest')):
                continue
            add(str(path.relative_to(classes)), path.read_bytes())
        add('DiscordIntegrationAddon.toml', (ROOT / 'integrations/fegcraft-addon/src/main/resources/DiscordIntegrationAddon.toml').read_bytes())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dependency', type=Path, help='Compile against an operator-selected installed integration JAR instead of downloading')
    parser.add_argument('--javac', default=shutil.which('javac'))
    args = parser.parse_args()
    if not args.javac:
        raise RuntimeError('JDK compiler required; no server change performed')
    compiler = Path(args.javac).resolve()
    java = compiler.with_name('java')
    BUILD.mkdir(parents=True, exist_ok=True)
    dependency = args.dependency
    if dependency is None:
        dependency = BUILD / 'dcintegration-fabric-MC26.2-3.2.1.jar'
        if not dependency.exists():
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *args):
                    return None
            opener = urllib.request.build_opener(NoRedirect())
            with opener.open(DEPENDENCY_URL, timeout=60) as response:
                data = response.read(24_000_001)
            if len(data) > 24_000_000 or hashlib.sha256(data).hexdigest() != DEPENDENCY_SHA:
                raise RuntimeError('Dependency hash mismatch')
            dependency.write_bytes(data)
        if hashlib.sha256(dependency.read_bytes()).hexdigest() != DEPENDENCY_SHA:
            raise RuntimeError('Cached dependency hash mismatch')
    with zipfile.ZipFile(dependency) as archive:
        api = 'de/erdbeerbaerlp/dcintegration/common/api/DiscordEventHandler.class'
        if api not in archive.namelist():
            # Fabric 26.2 packages the actual API as a declared nested JAR.
            nested = 'META-INF/jars/dcintegration.common-3.2.1.jar'
            if nested not in archive.namelist() or archive.getinfo(nested).file_size > 30_000_000:
                raise RuntimeError('Installed integration API missing')
            data = archive.read(nested)
            dependency = BUILD / 'installed-dcintegration.common-3.2.1.jar'
            dependency.write_bytes(data)
    with zipfile.ZipFile(dependency) as archive:
        if api not in archive.namelist():
            raise RuntimeError('Installed integration API missing')
    classes = BUILD / 'classes'
    if classes.exists():
        shutil.rmtree(classes)
    classes.mkdir()
    source = ROOT / 'integrations/fegcraft-addon/src/main/java/com/kibouakari/vector/VectorAddon.java'
    subprocess.run([str(compiler), '--release', '17', '-g:none', '-encoding', 'UTF-8', '-classpath', str(dependency), '-d', str(classes), str(source), str(ROOT / 'tests/VectorAddonTest.java'), str(ROOT / 'tests/VectorAddonFlowTest.java')], check=True)
    expected = hmac.new(bytes.fromhex('ab' * 32), b'1000000000\n{}', hashlib.sha256).hexdigest()
    subprocess.run([str(java), '-classpath', os.pathsep.join((str(classes), str(dependency))), 'com.kibouakari.vector.VectorAddonTest', expected], check=True)
    output = BUILD / 'vector-minecraft-0.1.0.jar'
    package_addon(classes, output)
    print('Addon compiled and offline checks passed.')
    print('JAR SHA256:', hashlib.sha256(output.read_bytes()).hexdigest())
    print('No addon installed, message sent or model called.')


if __name__ == '__main__':
    main()
