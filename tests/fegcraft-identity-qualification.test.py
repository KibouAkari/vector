import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('identity_qualification', ROOT / 'scripts/deploy/qualify-fegcraft-identity.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Qualification(unittest.TestCase):
    def test_site_hint_exact_domain_and_no_configuration_values(self):
        dump = '''# configuration file /etc/nginx/nginx.conf:
http { include /etc/nginx/sites-enabled/*; }
# configuration file /etc/nginx/sites-enabled/vector:
server {
    server_name vector.kibouakari.com;
    ssl_certificate_key /private/synthetic.key;
}
# configuration file /etc/nginx/sites-enabled/other:
server {
    server_name vector.kibouakari.com.example.invalid;
}
'''
        self.assertEqual(module.site_candidates(dump), ['/etc/nginx/sites-enabled/vector'])
        with self.assertRaisesRegex(RuntimeError, 'SITE_PATH'):
            module.site_candidates(dump.replace('/etc/nginx/sites-enabled/vector:', '/tmp/foreign.conf:'))

    def test_exact_installed_version_and_immutable_game_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'server.jar'
            def write(version):
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr('version.json', json.dumps(version))
                return hashlib.sha256(path.read_bytes()).hexdigest()
            sha = write({'id': '26.2', 'pack_version': {'resource_major': 88, 'resource_minor': 0}})
            with patch.object(module, 'GAME_SHA', sha):
                self.assertEqual(module.resource_version(path), [88, 0])
                path.write_bytes(path.read_bytes() + b'changed')
                with self.assertRaisesRegex(RuntimeError, 'GAME_JAR_CHANGED'):
                    module.resource_version(path)
            sha = write({'id': '26.3', 'pack_version': {'resource_major': 88, 'resource_minor': 0}})
            with patch.object(module, 'GAME_SHA', sha):
                with self.assertRaisesRegex(RuntimeError, 'RESOURCE_FORMAT'):
                    module.resource_version(path)

    def test_duplicate_version_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'version.json'
            path.write_bytes(b'{}')
            link = Path(temp) / 'link'
            link.symlink_to(path)
            with self.assertRaisesRegex(RuntimeError, 'SYMLINK'):
                module.read(link)
            with self.assertRaisesRegex(RuntimeError, 'INPUT_FILE'):
                module.read(path, limit=1)


if __name__ == '__main__':
    unittest.main()
