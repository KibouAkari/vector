"""Actual addon/HTTP flow; all channel delivery is captured in the fixture."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'services/fegcraft-assistant'))
from runtime import Assistant, State
from server import Service


def fixtures(directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'stats').mkdir(exist_ok=True)
    for number, name, kills in ((1, 'ExampleOne', 40), (2, 'ExampleTwo', 52000)):
        uid = f'00000000-0000-0000-0000-{number:012d}'
        (directory / 'stats' / (uid + '.json')).write_text(json.dumps({'stats': {'minecraft:custom': {'minecraft:mob_kills': kills, 'minecraft:play_time': 72000}}}))
    (directory / 'usercache.json').write_text(json.dumps([{'uuid': f'00000000-0000-0000-0000-{n:012d}', 'name': name} for n, name in ((1, 'ExampleOne'), (2, 'ExampleTwo'))]))
    (directory / 'mods.json').write_text('["fabric-api","travelersbackpack"]')


def main():
    build = ROOT / 'integrations/fegcraft-addon/build'
    java = os.environ.get('VECTOR_TEST_JAVA') or shutil.which('java')
    if not java:
        raise RuntimeError('Java runtime required')
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        inputs, client = base / 'inputs', base / 'client'
        fixtures(inputs)
        client.mkdir()
        key = secrets.token_bytes(32)
        (inputs / 'token').write_text(key.hex())
        (base / 'hosts').write_text('127.0.0.1 localhost vector-fegcraft-assistant\n')
        state = State(base / 'events.sqlite', key)
        assistant = Assistant(state, inputs / 'stats', inputs / 'usercache.json', inputs / 'mods.json')
        for phase in ('first', 'restart'):
            # Fresh server/Assistant/SQLite connection, same durable state.
            if phase == 'restart':
                assistant = Assistant(State(base / 'events.sqlite', key), inputs / 'stats', inputs / 'usercache.json', inputs / 'mods.json')
            service = Service(('127.0.0.1', 8090), assistant, key)
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            try:
                report = base / (phase + '.json')
                subprocess.run([java, '-Djdk.net.hosts.file=' + str(base / 'hosts'), '-classpath', os.pathsep.join((str(build / 'classes'), str(build / 'installed-dcintegration.common-3.2.1.jar'))), 'com.kibouakari.vector.VectorAddonFlowTest', str(inputs / 'token'), str(client), str(report), phase], check=True, timeout=55)
                assert json.loads(report.read_text())['passed'] is True
            finally:
                service.shutdown()
                service.server_close()
                thread.join(timeout=2)
        print('Signed addon/HTTP capture, service restart limits and introduction replay checks passed')


if __name__ == '__main__':
    main()
