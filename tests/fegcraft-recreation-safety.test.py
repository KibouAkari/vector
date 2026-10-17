import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

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
        for key, value in (('VERSION', 'LATEST'), ('REMOVE_OLD_CONFIGS', 'true'), ('WORLD', 'remote.zip'), ('PRE_START_SCRIPT', '/data/custom-start.sh')):
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
        config = copy.deepcopy(profile); config['services']['mc']['command'] = ['custom-start']; cases.append((game, config))
        config = copy.deepcopy(profile); config['services']['mc']['environment']['UNAPPLIED_SETTING'] = 'new'; cases.append((game, config))
        for field, value in (('tmpfs', ['/data/world']), ('volumes_from', ['old']), ('secrets', [{'target': '/data/world'}]), ('configs', [{'target': '/data/world'}])):
            config = copy.deepcopy(profile); config['services']['mc'][field] = value; cases.append((game, config))
        for current, config in cases:
            with self.subTest(current=current, config=config), self.assertRaises(RuntimeError): m.validate(current, config, data)

    def test_container_layer_changes_are_not_silently_discarded(self):
        self.assertEqual(m.unpersisted(b'C /etc\nC /etc/passwd\nA /tmp/runtime\nC /run\n'), [])
        self.assertEqual(m.unpersisted(b'A /world/level.dat\nC /home/minecraft/private.txt\n'),
            [{'change': 'A', 'path': '/world/level.dat'}, {'change': 'C', 'path': '/home/minecraft/private.txt'}])
        with self.assertRaises(RuntimeError): m.unpersisted(b'not a Docker diff')

    def test_live_bind_must_match_current_host_directory(self):
        root = SimpleNamespace(st_dev=2, st_ino=10); world = SimpleNamespace(st_dev=2, st_ino=11)
        m.live_identity(b'2:10\n2:11\n', root, world)
        with self.assertRaisesRegex(RuntimeError, 'LIVE_BIND_DIFFERS'):
            m.live_identity(b'2:4\n2:5\n', root, world)
        with self.assertRaises(RuntimeError): m.live_identity(b'not stat output', root, world)

    def test_final_audit_snapshot_still_has_to_be_healthy(self):
        for case in ('success', 'stopped', 'unhealthy', 'restarting', 'renamed-bind'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                data = Path(temp) / 'game/data'
                for path in ('world/players/stats', 'mods', 'config'): (data / path).mkdir(parents=True)
                (data / 'world/level.dat').write_bytes(b'synthetic world header')
                (data / 'server.properties').write_text('level-name=world\n')
                compose = data.parent / 'docker-compose.yml'; compose.write_text('synthetic compose')
                labels = {'com.docker.compose.service': 'mc', 'com.docker.compose.project': 'game',
                    'com.docker.compose.project.config_files': str(compose), 'com.docker.compose.project.working_dir': str(data.parent)}
                game = {'Id': 'same', 'Image': 'pinned', 'Config': {'Labels': labels, 'Env': ['VERSION=26.2', 'TYPE=FABRIC']},
                    'State': {'StartedAt': 'unchanged', 'Running': True, 'Health': {'Status': 'healthy'}},
                    'Mounts': [{'Type': 'bind', 'Source': str(data), 'Destination': '/data', 'RW': True}], 'HostConfig': {}}
                profile = {'services': {'mc': {'image': 'tag', 'environment': {'VERSION': '26.2', 'TYPE': 'FABRIC'},
                    'volumes': [{'type': 'bind', 'source': str(data), 'target': '/data'}]}}}
                inspections = [0]
                def run(*args):
                    if args[:2] == ('docker', 'inspect'):
                        inspections[0] += 1; current = copy.deepcopy(game)
                        if inspections[0] > 1:
                            if case == 'stopped': current['State']['Running'] = False
                            if case == 'unhealthy': current['State']['Health']['Status'] = 'unhealthy'
                            if case == 'restarting': current['State']['Restarting'] = True
                        return json.dumps([current]).encode()
                    if args[:3] == ('docker', 'image', 'inspect'): return b'[{"Id":"pinned"}]'
                    if args[:2] == ('docker', 'compose'): return json.dumps(profile).encode()
                    if args[:2] == ('docker', 'diff'): return b''
                    if args[:2] == ('docker', 'exec'):
                        values = [data.stat(), (data / 'world').stat()]
                        return ''.join(str(meta.st_dev) + ':' + str(meta.st_ino + (1 if case == 'renamed-bind' else 0)) + '\n' for meta in values).encode()
                    raise AssertionError(args)
                with patch.multiple(m, DATA=data, COMPOSE=compose), patch.object(m, 'run', side_effect=run):
                    if case == 'success':
                        report, paths = m.audit(); self.assertTrue(report['live_container_directories_match_host']); self.assertFalse(paths)
                    else:
                        with self.assertRaises(RuntimeError): m.audit()

    def test_welcome_final_readiness_is_not_inferred_from_unchanged_id(self):
        initial = {'Id': 'same', 'Image': 'same', 'State': {'StartedAt': 'same', 'Running': True, 'Health': {'Status': 'healthy'}}}
        w.same_ready(initial, copy.deepcopy(initial))
        for case in ('stopped', 'unhealthy', 'restarting'):
            after = copy.deepcopy(initial)
            if case == 'stopped': after['State']['Running'] = False
            if case == 'unhealthy': after['State']['Health']['Status'] = 'unhealthy'
            if case == 'restarting': after['State']['Restarting'] = True
            with self.assertRaisesRegex(RuntimeError, 'NOT_READY'): w.same_ready(initial, after)

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
            (directory / 'owner-welcome-v2.attempted').unlink()
            (directory / 'owner-welcome-v2.ready').symlink_to(legacy)
            with self.assertRaises(RuntimeError): w.arm(directory, 1000, 1000, boot)
            self.assertEqual(legacy.read_text(), 'old delivery')


if __name__ == '__main__': unittest.main()
