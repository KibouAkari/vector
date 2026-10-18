"""Run the shared actual driver harness only against the disposable CI service."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlsplit

if os.environ.get('CI') != 'true': raise SystemExit('DISPOSABLE_CI_REQUIRED')
dsn=os.environ.get('VECTOR_ADMISSION_FIXTURE_DSN','')
value=urlsplit(dsn)
if value.hostname!='127.0.0.1' or value.port!=5433 or value.path!='/vector_admission_fixture':
    raise SystemExit('DISPOSABLE_CI_DESTINATION_REQUIRED')
with tempfile.TemporaryDirectory() as folder:
    config=Path(folder)/'fixture.json'
    config.write_text(json.dumps({'disposable':True,'dsn':dsn}));config.chmod(0o600)
    subprocess.run(['/tmp/vector-admission-driver-ci/bin/python',
      'tests/fegcraft-admission-driver.integration.py',str(config)],check=True)
