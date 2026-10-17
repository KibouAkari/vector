#!/usr/bin/env python3
"""Isolated captured addon/API qualification. Never install or contact game/Discord."""
from datetime import datetime, timezone
import fcntl
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path('/root/vector-workspace')
REPO = ROOT / 'github/vector'
JDK = 'eclipse-temurin@sha256:791193f8d46fe8afeb6360433dd057b88850a78ed440e3d57d2e6340994dd24b'
PYTHON = 'sha256:eca0b83a886fcc9952ef13755853ef63134e5c76733d40564460398776c92dd7'
INTEGRATION = Path('/opt/fegcraft-updated/data/mods/dcintegration-fabric-MC26.2-3.2.1.jar')
INTEGRATION_SHA = '75e039ac6c8edad3c9423c91638ffd15d7c9b95dadb60bf69349da838afbf337'
COMMON_DIGEST = '4b0dee9f505d30129b003eae08866be543cddc7b5bc11b7b42bae6b1fb77d0a9'
LABEL = 'com.vector.fegcraft-evaluation'
PRODUCTION = ('fegcraft-updated', 'vector-app', 'vector-privacy-ner', 'vector-local-inference', 'vector-worker', 'vector-runner', 'vector-postgres', 'vector-redis')
COMPOSE = (Path('/opt/fegcraft-updated/docker-compose.yml'), Path('/opt/vector/docker-compose.yml'))
EXPORT = ('services/fegcraft-assistant', 'integrations/fegcraft-addon/src', 'tests/VectorAddonTest.java', 'tests/VectorAddonFlowTest.java', 'tests/fegcraft-flow.test.py', 'scripts/build-fegcraft-addon.py', 'scripts/build-fegcraft-identity.py', 'public/vector-assets/brand/vector-mark.svg')


LOG_LIMIT = 128 * 1024
COMPLETION_FLAGS = ('signed_transport_passed', 'service_restart_limits_passed', 'captured_introduction_replay_passed')


def qualified(result, error, cleanup_errors, checks):
    return (error is None and not cleanup_errors
            and all(result.get(key) is True for key in (*COMPLETION_FLAGS, *checks)))


def run(args, *, timeout=90, log=None, check=True):
    if log is None:
        return subprocess.run(args, capture_output=True, timeout=timeout, check=check)
    # Stream output to a private temporary file, retaining a bounded diagnostic
    # tail even when a child times out. Never buffer a compiler log in memory.
    with tempfile.TemporaryFile() as output:
        failure = None
        try:
            result = subprocess.run(args, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired:
            failure = 'ISOLATED_STEP_TIMEOUT:' + log.name
        finally:
            end = output.seek(0, os.SEEK_END)
            output.seek(max(0, end - LOG_LIMIT))
            tail = output.read(LOG_LIMIT)
            log.write_bytes(tail)
            log.chmod(0o600)
        if failure:
            raise RuntimeError(failure)
        if check and result.returncode:
            raise RuntimeError('ISOLATED_STEP_FAILED:' + log.name)
        return result


def inspect(kind, name):
    result = run(['docker', kind, 'inspect', name], check=False)
    if result.returncode == 0:
        return json.loads(result.stdout)[0]
    message = result.stderr.decode(errors='replace').strip()
    missing = r'(?:Error response from daemon: |Error: )?(?:No such (?:object|image|container|network): ' + re.escape(name) + r'|network ' + re.escape(name) + r' not found)'
    if result.stdout.strip() in (b'', b'[]') and re.fullmatch(missing, message):
        return None
    raise RuntimeError('DOCKER_INSPECTION_FAILED:' + kind)


def identity(name):
    value = inspect('container', name)
    if value is None or value['State'].get('Running') is not True:
        raise RuntimeError('PRODUCTION_CONTAINER_UNAVAILABLE:' + name)
    return {'id': value['Id'], 'image': value['Image'], 'started': value['State']['StartedAt'],
            'networks': sorted(value['NetworkSettings']['Networks'])}


def remove_owned(kind, name, owner):
    value = inspect(kind, name)
    if value is None:
        return
    labels = value.get('Config', {}).get('Labels', {}) if kind == 'container' else value.get('Labels', {})
    if (labels or {}).get(LABEL) != owner:
        raise RuntimeError('CLEANUP_OWNERSHIP_MISMATCH')
    args = ['docker', kind, 'rm']
    if kind == 'container':
        args.append('-f')
    run(args + [name])


def mount(source, target, writable=False):
    if ',' in str(source) or ',' in target:
        raise RuntimeError('UNSUPPORTED_BIND_PATH')
    return ['--mount', f'type=bind,src={source},dst={target}' + ('' if writable else ',readonly')]


def container_args(name, owner, network, memory='384m'):
    return ['docker', 'run', '--rm', '--name', name, '--label', LABEL + '=' + owner,
            '--network', network, '--user', '65534:65534', '--read-only', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges:true', '--pids-limit', '128', '--cpus', '2',
            '--memory', memory, '--memory-swap', memory, '--ulimit', 'nofile=512:512',
            '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=128m,mode=1777']


def directory(path, writable=False):
    path.mkdir(parents=True, exist_ok=False)
    path.chmod(0o700 if writable else 0o755)
    if writable:
        os.chown(path, 65534, 65534)


def export_sources(revision, target):
    directory(target)
    rows = run(['git', '-C', str(REPO), 'ls-tree', '-rz', revision, '--', *EXPORT]).stdout
    count = 0
    for row in rows.split(b'\0'):
        if not row:
            continue
        metadata, raw_path = row.split(b'\t', 1)
        mode, kind, blob = metadata.decode().split()
        relative = Path(raw_path.decode())
        if mode not in ('100644', '100755') or kind != 'blob' or relative.is_absolute() or '..' in relative.parts:
            raise RuntimeError('UNSUPPORTED_EXPORTED_SOURCE')
        dest = target / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        for parent in (dest.parent, *dest.parent.parents):
            if parent == target.parent:
                break
            parent.chmod(0o755)
        dest.write_bytes(run(['git', '-C', str(REPO), 'cat-file', 'blob', blob]).stdout)
        dest.chmod(0o644)
        count += 1
    if count < 8:
        raise RuntimeError('SOURCE_EXPORT_INCOMPLETE')


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    os.umask(0o077)
    sys.dont_write_bytecode = True
    if os.geteuid() != 0:
        raise RuntimeError('ROOT_OWNER_RUNNER_REQUIRED')
    revision = os.environ.get('VECTOR_FEGCRAFT_REV', '')
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise RuntimeError('PINNED_REVISION_REQUIRED')
    with (ROOT / '.chat-release.lock').open('r') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        before = {name: identity(name) for name in PRODUCTION}
        hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in COMPOSE}
        if before['vector-privacy-ner']['image'] != PYTHON:
            raise RuntimeError('QUALIFIED_PYTHON_IMAGE_CHANGED')
        if INTEGRATION.is_symlink() or not INTEGRATION.is_file() or INTEGRATION.stat().st_size > 80_000_000:
            raise RuntimeError('INTEGRATION_INPUT_UNAVAILABLE')
        integration = INTEGRATION.read_bytes()
        if hashlib.sha256(integration).hexdigest() != INTEGRATION_SHA:
            raise RuntimeError('INSTALLED_INTEGRATION_CHANGED')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
        release = ROOT / 'releases' / ('vector-fegcraft-bridge-evaluation-' + stamp)
        release.mkdir(mode=0o700)
        owner = stamp
        network = 'vector-fegcraft-eval-' + secrets.token_hex(5)
        prefix = 'vector-fegcraft-test-' + secrets.token_hex(4)
        names = []
        network_created = False
        service_name = None
        token = None
        error = None
        cleanup_errors = []
        result = {'revision': revision, 'passed': False, 'production_activated': False,
                  'model_calls': 0, 'cloud_calls': 0, 'external_messages_sent': 0,
                  'real_minecraft_callback_tested': False, 'real_discord_delivery_tested': False}
        print('Isolated addon/API capture; synthetic inputs only. No Minecraft restart, model calls or real messages.', flush=True)
        print('Report directory:', release, flush=True)
        try:
            code, inputs, build = release / 'code', release / 'inputs', release / 'build'
            state, client = release / 'state', release / 'client'
            export_sources(revision, code)
            directory(inputs)
            directory(build, True)
            directory(state, True)
            directory(client, True)
            fixture = load_module(code / 'tests/fegcraft-flow.test.py', 'fegcraft_synthetic_fixture')
            fixture.fixtures(inputs)
            for path in inputs.rglob('*'):
                path.chmod(0o755 if path.is_dir() else 0o644)
            token = inputs / 'token'
            token.write_text(secrets.token_hex(32))
            token.chmod(0o444)
            with zipfile.ZipFile(INTEGRATION) as archive:
                item = archive.getinfo('META-INF/jars/dcintegration.common-3.2.1.jar')
                if item.file_size > 30_000_000:
                    raise RuntimeError('INTEGRATION_API_LIMIT')
                common = archive.read(item)
            if hashlib.sha256(common).hexdigest() != COMMON_DIGEST:
                raise RuntimeError('INSTALLED_COMMON_API_CHANGED')
            (inputs / 'common.jar').write_bytes(common)
            (inputs / 'common.jar').chmod(0o444)
            if inspect('image', JDK) is None:
                print('Download pinned official JDK compiler image; no host packages installed.', flush=True)
                run(['docker', 'pull', '--platform', 'linux/amd64', JDK], timeout=300, log=release / 'jdk-pull.log')
            jdk = inspect('image', JDK)
            if not jdk or jdk.get('Architecture') != 'amd64' or jdk.get('Os') != 'linux':
                raise RuntimeError('JDK_PLATFORM_MISMATCH')
            result['jdk_image'] = jdk['Id']
            result['python_image'] = PYTHON
            print('Compile against the exact installed nested API as UID 65534, network disabled.', flush=True)
            name = prefix + '-compile'; names.append(name)
            classes = '/build/classes'
            args = container_args(name, owner, 'none', '768m')
            args += mount(code, '/source') + mount(inputs, '/inputs') + mount(build, '/build', True)
            args += ['--entrypoint', 'javac', JDK, '-J-Xmx256m', '-J-XX:ActiveProcessorCount=2', '--release', '17', '-g:none', '-encoding', 'UTF-8', '-classpath', '/inputs/common.jar', '-d', classes,
                     '/source/integrations/fegcraft-addon/src/main/java/com/kibouakari/vector/VectorAddon.java',
                     '/source/tests/VectorAddonTest.java', '/source/tests/VectorAddonFlowTest.java']
            run(args, timeout=120, log=release / 'compile.log')
            name = prefix + '-unit'; names.append(name)
            args = container_args(name, owner, 'none') + mount(inputs, '/inputs') + mount(build, '/build')
            expected = hmac.new(bytes.fromhex('ab' * 32), b'1000000000\n{}', hashlib.sha256).hexdigest()
            args += ['--entrypoint', 'java', JDK, '-Xmx192m', '-XX:ActiveProcessorCount=2', '-classpath', '/build/classes:/inputs/common.jar', 'com.kibouakari.vector.VectorAddonTest', expected]
            run(args, timeout=45, log=release / 'unit.log')
            builder = load_module(code / 'scripts/build-fegcraft-addon.py', 'qualified_fegcraft_builder')
            artifact = release / 'vector-minecraft-0.1.0.jar'
            builder.package_addon(build / 'classes', artifact)
            artifact.chmod(0o600)
            result['addon_sha256'] = hashlib.sha256(artifact.read_bytes()).hexdigest()
            run(['docker', 'network', 'create', '--internal', '--label', LABEL + '=' + owner, network])
            network_created = True
            net = inspect('network', network)
            if net.get('Internal') is not True:
                raise RuntimeError('EVALUATION_NETWORK_NOT_INTERNAL')
            service_name = prefix + '-service'
            def start_service():
                names.append(service_name)
                args = container_args(service_name, owner, network, '256m')
                args.remove('--rm')  # Keep a failed service inspectable until cleanup.
                args.insert(2, '-d')
                args += ['--network-alias', 'vector-fegcraft-assistant', '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'VECTOR_FEGCRAFT_KNOWLEDGE=0']
                args += mount(code / 'services/fegcraft-assistant', '/code') + mount(inputs, '/inputs')
                args += mount(token, '/run/secrets/vector_fegcraft_token') + mount(state, '/state', True)
                args += ['--entrypoint', 'python3', PYTHON, '/code/server.py']
                run(args, log=release / 'service-start.log')
                current = inspect('container', service_name)
                if current is None or current['HostConfig'].get('ReadonlyRootfs') is not True or current['Config'].get('User') != '65534:65534' or current['HostConfig'].get('PortBindings') or set(current['NetworkSettings']['Networks']) != {network}:
                    raise RuntimeError('SERVICE_ISOLATION_MISMATCH')
            for phase in ('first', 'restart'):
                print('Signed addon/HTTP capture phase:', phase, flush=True)
                start_service()
                name = prefix + '-client-' + phase; names.append(name)
                args = container_args(name, owner, network) + mount(build, '/build') + mount(inputs, '/inputs') + mount(client, '/client', True)
                args += ['--entrypoint', 'java', JDK, '-Xmx192m', '-XX:ActiveProcessorCount=2', '-classpath', '/build/classes:/inputs/common.jar', 'com.kibouakari.vector.VectorAddonFlowTest', '/inputs/token', '/client', '/client/' + phase + '.json', phase]
                run(args, timeout=70, log=release / (phase + '.log'))
                report_path = client / (phase + '.json')
                if report_path.is_symlink() or report_path.stat().st_size > 16384:
                    raise RuntimeError('CLIENT_REPORT_INVALID')
                report = json.loads(report_path.read_text())
                if report.get('passed') is not True or report.get('phase') != phase or report.get('external_messages_sent') != 0:
                    raise RuntimeError('CAPTURE_QUALIFICATION_FAILED')
                result[phase] = report
                run(['docker', 'logs', '--tail', '80', service_name], log=release / ('service-' + phase + '.log'), check=False)
                remove_owned('container', service_name, owner)
            result['signed_transport_passed'] = True
            result['service_restart_limits_passed'] = True
            result['captured_introduction_replay_passed'] = True
        except KeyboardInterrupt:
            error = 'EVALUATION_INTERRUPTED'
        except Exception as failure:
            error = str(failure) if isinstance(failure, RuntimeError) else type(failure).__name__
        finally:
            for name in reversed(list(dict.fromkeys(names))):
                if name == service_name:
                    try:
                        current = inspect('container', name)
                        if current and (current['Config'].get('Labels') or {}).get(LABEL) == owner:
                            run(['docker', 'logs', '--tail', '80', name], log=release / 'service-final.log', check=False)
                    except Exception:
                        pass
                try:
                    remove_owned('container', name, owner)
                except Exception:
                    cleanup_errors.append('CONTAINER_CLEANUP_FAILED')
            if network_created:
                try:
                    remove_owned('network', network, owner)
                except Exception:
                    cleanup_errors.append('NETWORK_CLEANUP_FAILED')
            if token is not None:
                token.unlink(missing_ok=True)
            result['cleanup_verified'] = not cleanup_errors
            checks = {
                'production_compose_unchanged': lambda: all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in hashes.items()),
                'production_container_identities_unchanged': lambda: all(identity(name) == value for name, value in before.items()),
                'installed_integration_unchanged': lambda: hashlib.sha256(INTEGRATION.read_bytes()).hexdigest() == INTEGRATION_SHA,
            }
            for check, verify in checks.items():
                try:
                    result[check] = verify()
                except Exception:
                    result[check] = False
            result['passed'] = qualified(result, error, cleanup_errors, checks)
            result['error'] = error
            result['cleanup_errors'] = cleanup_errors
            (release / 'result.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
        if not result['passed']:
            raise RuntimeError('ISOLATED_CAPTURE_FAILED; inspect private report directory')
        print('Captured addon/API qualification passed; no production activation or real-channel delivery.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as failure:
        print('ERROR:', str(failure) if isinstance(failure, RuntimeError) else type(failure).__name__, file=sys.stderr)
        raise SystemExit(1)

