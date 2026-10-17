import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result
m = load('scripts/diagnostics/fegcraft-recreation-safety.py', 'persistence')
w = load('scripts/deploy/arm-fegcraft-owner-welcome.py', 'arm_welcome')


class Persistence(unittest.TestCase):
    def test_mounts_version_startup_and_ownership(self):
        data = Path('/synthetic/game/data')
        game = {'State': {'Running': True, 'Health': {'Status': 'healthy'}},
            'HostConfig': {'AutoRemove': False}, 'Config': {'Env': ['VERSION=26.2', 'TYPE=FABRIC'], 'Labels': {
                'com.docker.compose.service': 'mc', 'com.docker.compose.project.config_files': str(data.parent / 'docker-compose.yml'),
                'com.docker.compose.project.working_dir': str(data.parent)}},
            'Mounts': [{'Type': 'bind', 'Source': str(data), 'Destination': '/data', 'RW': True}]}
        profile = {'services': {'mc': {'environment': {'VERSION': '26.2', 'TYPE': 'FABRIC'},
            'volumes': [{'type': 'bind', 'source': str(data), 'target': '/data'}]}}}
        self.assertEqual(m.validate(game, profile, data), 'mc')
        cases = []
        for key, value in (('VERSION', 'LATEST'), ('REMOVE_OLD_CONFIGS', 'true'), ('WORLD', 'remote.zip')):
            config = copy.deepcopy(profile); config['services']['mc']['environment'][key] = value; cases.append((game, config))
        for change in ('anonymous', 'source', 'readonly', 'extra', 'stopped'):
            current = copy.deepcopy(game)
            if change == 'anonymous': current['Mounts'][0]['Type'] = 'volume'
            if change == 'source': current['Mounts'][0]['Source'] = '/different/data'
            if change == 'readonly': current['Mounts'][0]['RW'] = False
            if change == 'extra': current['Mounts'].append({'Type': 'volume', 'Destination': '/other'})
            if change == 'stopped': current['State']['Running'] = False
            cases.append((current, profile))
        config = copy.deepcopy(profile); config['services']['mc']['volumes'][0]['source'] = '/different/data'; cases.append((game, config))
        for current, config in cases:
            with self.subTest(current=current, config=config), self.assertRaises(RuntimeError): m.validate(current, config, data)

    def test_container_layer_changes_are_not_silently_discarded(self):
        self.assertEqual(m.unpersisted(b'C /etc\nC /etc/passwd\nA /tmp/runtime\nC /run\n'), [])
        self.assertEqual(m.unpersisted(b'A /world/level.dat\nC /home/minecraft/private.txt\n'),
            [{'change': 'A', 'path': '/world/level.dat'}, {'change': 'C', 'path': '/home/minecraft/private.txt'}])
        with self.assertRaises(RuntimeError): m.unpersisted(b'not a Docker diff')

    def test_welcome_arm_is_distinct_durable_and_not_replayed(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(w.os, 'chown'):
            directory = Path(temp); legacy = directory / 'introduction-v1.attempted'; legacy.write_text('old delivery')
            boot = '00000000-0000-0000-0000-000000000001'
            self.assertTrue(w.arm(directory, 1000, 1000, boot)); self.assertFalse(w.arm(directory, 1000, 1000, boot))
            self.assertEqual((directory / 'owner-welcome-v2.ready').read_text(), boot + '\n')
            self.assertEqual(legacy.read_text(), 'old delivery')
            (directory / 'owner-welcome-v2.ready').unlink(); (directory / 'owner-welcome-v2.attempted').write_text('uncertain')
            self.assertFalse(w.arm(directory, 1000, 1000, boot))
            with self.assertRaises(RuntimeError): w.arm(directory, 1000, 1000, '../invalid')


if __name__ == '__main__': unittest.main()
