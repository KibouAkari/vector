"""Real GNU archive verification, synthetic Docker lifecycle and private fixtures only."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/maintenance/fegcraft-backup.py'
spec = importlib.util.spec_from_file_location('backup_engine', SOURCE)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class Backup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.base = self.root / 'game'; self.data = self.base / 'data'
        (self.data / 'world').mkdir(parents=True); (self.data / 'world/level.dat').write_bytes(b'synthetic world')
        (self.data / 'config').mkdir(); (self.data / 'config/example.toml').write_text('example=true\n')
        (self.base / '.env').write_text('FIXTURE=synthetic\n'); (self.base / 'docker-compose.yml').write_text('services: {}\n')
        (self.base / 'backup.log').write_text('excluded synthetic log')
        self.backups = self.base / 'backups'; self.backups.mkdir()
        (self.backups / 'ziFsfR3F').mkdir(); (self.backups / 'ziFsfR3F/keep').write_text('keep')
        (self.backups / 'old.tar.gz').write_bytes(b'keep old')
        self.game = {'Id': 'synthetic-original', 'Image': 'synthetic-image', 'Config': {'Env': ['UID=1000','GID=1000']},
                     'Mounts': [{'Type': 'bind','Source': str(self.data),'Destination': '/data','RW': True}],
                     'State': {'Running': True, 'StartedAt': 'synthetic-start', 'ExitCode': 0, 'OOMKilled': False}}
        self.events = []; self.fail = None; self.actual_run = m.run
        for name, value in [('ROOT',self.root),('BASE',self.base),('DATA',self.data),('BACKUPS',self.backups)]:
            p = patch.object(m,name,value); p.start(); self.addCleanup(p.stop)
        p = patch.object(m,'run',side_effect=self.command); p.start(); self.addCleanup(p.stop)
        p = patch.object(m.shutil,'which',side_effect=lambda command: '/synthetic/' + command); p.start(); self.addCleanup(p.stop)

    def command(self, args, **kwargs):
        if args[0] == 'docker':
            if args[1] == 'inspect': return json.dumps([copy.deepcopy(self.game)]).encode()
            if args[1] == 'exec': return ''.join(f'{p.stat().st_dev}:{p.stat().st_ino}\n' for p in (self.data,self.data/'world')).encode()
            if args[1] == 'stop':
                self.events.append('stop'); self.game['State']['Running'] = False
                if self.fail == 'stop': raise subprocess.TimeoutExpired(args,180)
                return b''
            if args[1] == 'start': self.events.append('start'); self.game['State']['Running'] = True; return b''
            raise AssertionError(args)
        if '--create' in args:
            self.events.append('create'); self.assertFalse(self.game['State']['Running'])
            if self.fail == 'create': raise RuntimeError('synthetic tar failure')
            if self.fail == 'replacement': self.game['Id'] = 'synthetic-replacement'; raise RuntimeError('synthetic concurrent replacement')
        if '--compare' in args:
            self.events.append('compare'); self.assertFalse(self.game['State']['Running'])
            if self.fail == 'mutate': (self.data/'world/level.dat').write_bytes(b'changed synthetic world')
        return self.actual_run(args,**kwargs)

    def execute(self):
        with contextlib.redirect_stdout(io.StringIO()): m.backup()

    def test_consistent_archive_preserves_hidden_config_and_previous_backups(self):
        self.execute(); self.assertEqual(self.events,['stop','create','compare','start'])
        archives = list(self.backups.glob('fegcraft-updated_*.tar.gz')); self.assertEqual(len(archives),1)
        archive = archives[0]
        with tarfile.open(archive,'r:gz') as handle:
            names = handle.getnames(); self.assertIn('./.env', names); self.assertIn('./data/config/example.toml',names)
            self.assertFalse(any(name.startswith('./backups') or name=='./backup.log' for name in names))
            self.assertEqual(handle.extractfile('./data/world/level.dat').read(),b'synthetic world')
        self.assertTrue(Path(str(archive)+'.sha256').read_text().startswith(hashlib.sha256(archive.read_bytes()).hexdigest()))
        self.assertEqual((self.backups/'old.tar.gz').read_bytes(),b'keep old'); self.assertEqual((self.backups/'ziFsfR3F/keep').read_text(),'keep')
        self.assertEqual(archive.stat().st_mode & 0o077,0); self.assertTrue(self.game['State']['Running'])

    def test_failed_archive_and_compare_restart_same_container_without_publication(self):
        for failure in ('create','mutate','stop'):
            with self.subTest(failure=failure):
                self.fail=failure; self.events=[]
                with self.assertRaises((RuntimeError,subprocess.TimeoutExpired)): self.execute()
                self.assertTrue(self.game['State']['Running']); self.assertEqual(self.events[-1],'start')
                self.assertFalse(list(self.backups.glob('fegcraft-updated_*.tar.gz')))

    def test_replacement_not_started(self):
        self.fail='replacement'
        with self.assertRaisesRegex(RuntimeError,'REPLACED'): self.execute()
        self.assertNotIn('start',self.events); self.assertFalse(list(self.backups.glob('fegcraft-updated_*.tar.gz')))

    def test_initially_stopped_stays_stopped(self):
        self.game['State']['Running']=False; self.execute()
        self.assertEqual(self.events,['create','compare']); self.assertFalse(self.game['State']['Running'])

    def test_space_failure_never_stops(self):
        with patch.object(m,'required_space',return_value=10**30):
            with self.assertRaisesRegex(RuntimeError,'INSUFFICIENT_SPACE'): self.execute()
        self.assertEqual(self.events,[]); self.assertTrue(self.game['State']['Running'])

    def test_health_failure_keeps_verified_archive(self):
        with patch.object(m,'ready',side_effect=RuntimeError('synthetic health failure')):
            with self.assertRaisesRegex(RuntimeError,'health'): self.execute()
        self.assertEqual(len(list(self.backups.glob('fegcraft-updated_*.tar.gz'))),1)


if __name__=='__main__': unittest.main()
