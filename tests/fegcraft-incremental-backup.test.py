"""Real rsync + optional real Restic; synthetic game lifecycle and isolated files."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
m=load('incremental','scripts/maintenance/fegcraft-incremental-backup.py')
i=load('incremental_install','scripts/deploy/install-fegcraft-incremental-backup.py')

class Incremental(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);base=root/'game';data=base/'data';backups=base/'backups';state=backups/'.vector-incremental'
        for folder in ('world/playerdata','world/region','mods','config','defaultconfigs','extra-mod-data'):(data/folder).mkdir(parents=True)
        for path,raw in [('world/level.dat',b'world'),('world/playerdata/id.dat',b'player'),('mods/example.jar',b'mod'),('config/example.toml',b'config'),('extra-mod-data/state',b'extra')]:
            (data/path).write_bytes(raw)
        (data/'logs').mkdir();(data/'logs/latest.log').write_text('excluded')
        (base/'docker-compose.yml').write_text('services: {}\n');(base/'backup.log').write_text('excluded')
        state.mkdir(parents=True,mode=0o700);stage=state/'staging';stage.mkdir(mode=0o700)
        (backups/'old.tar').write_bytes(b'old');(backups/'unknown').mkdir();(backups/'unknown/keep').write_bytes(b'old')
        self.root,self.base,self.data,self.backups,self.state,self.stage=root,base,data,backups,state,stage
        self.game={'Id':'original-id','Image':'original-image','Config':{'Env':['UID=1000','GID=1000']},'HostConfig':{},
                   'Mounts':[{'Type':'bind','Source':str(data),'Destination':'/data','RW':True}],
                   'State':{'Running':True,'StartedAt':'initial','OOMKilled':False,'ExitCode':0}}
        self.events=[];self.actual=m.run
        p=patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=1024**4));p.start();self.addCleanup(p.stop)
        for name,value in dict(ROOT=root,BASE=base,DATA=data,BACKUPS=backups,STATE=state,STAGE=stage,REPOSITORY=state/'repository',PASSWORD=state/'password',CONFIG=state/'owner.json',CANCELLED=False).items():
            p=patch.object(m,name,value);p.start();self.addCleanup(p.stop)
        p=patch.object(m,'run',side_effect=self.command);p.start();self.addCleanup(p.stop)
    def command(self,args,**kw):
        if args[0]!='docker':return self.actual(args,**kw)
        if args[1]=='inspect':return json.dumps([copy.deepcopy(self.game)]).encode()
        if args[1]=='exec':return ''.join(f'{p.stat().st_dev}:{p.stat().st_ino}\n' for p in (self.data,self.data/'world')).encode()
        self.assertEqual(args[-1],'original-id')
        if args[1]=='stop':self.events.append('stop');self.game['State']['Running']=False
        elif args[1]=='start':self.events.append('start');self.game['State']['Running']=True
        else:self.fail('Unexpected docker operation')
        return b''
    def test_precopy_preserves_world_players_mod_data_and_excludes_archives(self):
        m.sync_stage(self.state/'copy.log')
        for relative in ('world/level.dat','world/playerdata/id.dat','mods/example.jar','config/example.toml','extra-mod-data/state'):
            self.assertEqual((self.stage/'data'/relative).read_bytes(),(self.data/relative).read_bytes())
        self.assertFalse((self.stage/'backups').exists());self.assertFalse((self.stage/'data/logs').exists())
        self.assertTrue(self.game['State']['Running']);self.assertEqual(self.events,[])
        self.assertEqual((self.backups/'old.tar').read_bytes(),b'old')
        (self.stage/'stale').write_text('remove stage only');m.sync_stage(self.state/'again.log')
        self.assertFalse((self.stage/'stale').exists());self.assertTrue((self.backups/'unknown/keep').is_file())
    def test_final_delta_timeout_restarts_original_without_snapshot(self):
        def sync(path,stopped=False):
            self.assertEqual(self.game['State']['Running'],not stopped)
            if stopped:raise RuntimeError('INCREMENTAL_PHASE_TIMEOUT')
        with patch.object(m,'repository_owner'),patch.object(m,'sync_stage',side_effect=sync),patch.object(m,'make_snapshot') as snapshot,patch.object(m.shutil,'which',return_value='/fixture'):
            with self.assertRaisesRegex(RuntimeError,'PHASE_TIMEOUT'):m.backup()
            snapshot.assert_not_called()
        self.assertEqual(self.events,['stop','start']);self.assertTrue(self.game['State']['Running'])
    def test_changed_repo_refused_before_stop(self):
        with patch.object(m,'repository_owner',side_effect=RuntimeError('ID_CHANGED')),patch.object(m.shutil,'which',return_value='/fixture'):
            with self.assertRaisesRegex(RuntimeError,'ID_CHANGED'):m.backup()
        self.assertEqual(self.events,[])
    def test_extra_mount_refused(self):
        self.game['Mounts'].append({'Destination':'/extra'})
        with self.assertRaisesRegex(RuntimeError,'MOUNT_CHANGED'):m.verify_bind(self.game)
        self.assertEqual(self.events,[])
    def test_external_mod_data_links_refuse_before_stop(self):
        (self.data/'external-mod').symlink_to('/outside-server-data')
        with self.assertRaisesRegex(RuntimeError,'EXTERNAL_SOURCE_LINK'):m.verify_source_links()
        self.assertEqual(self.events,[])
    @unittest.skipUnless(shutil.which('restic'),'Restic absent locally; CI installs it for real restore verification')
    def test_actual_restic_two_snapshots_deduplicate_and_restore_all_important_data(self):
        m.PASSWORD.write_text('synthetic-only\n');os.chmod(m.PASSWORD,0o600)
        subprocess.run(m.restic('init','--repository-version','2'),check=True,capture_output=True)
        config=json.loads(self.actual(m.restic('cat','config')))
        m.CONFIG.write_text(json.dumps({'schema':1,'repository_id':config['id']}));os.chmod(m.CONFIG,0o600)
        with patch.object(m,'repository_owner',return_value={'repository_id':config['id']}):
            m.backup();m.backup()
        snapshots=json.loads(self.actual(m.restic('snapshots','--json')))
        self.assertGreaterEqual(len(snapshots),1)
        latest=snapshots[-1]['id'];dest=self.root/'restore'
        self.actual(m.restic('restore',latest,'--target',str(dest)),timeout=60)
        restored=dest/str(self.stage).lstrip('/')
        for relative in ('world/level.dat','world/playerdata/id.dat','mods/example.jar','config/example.toml','extra-mod-data/state'):
            self.assertEqual((restored/'data'/relative).read_bytes(),(self.data/relative).read_bytes())
        results=[json.loads(p.read_text()) for p in self.state.glob('run-*/result.json')]
        self.assertTrue(any(x['files_unmodified']>=5 for x in results));self.assertTrue(all(x['world_restore_probe_passed'] for x in results))
        self.assertTrue((self.backups/'old.tar').is_file())

class Installation(unittest.TestCase):
    def test_cron_changes_only_matching_active_jobs(self):
        raw=b'# keep\nMAILTO=root\n0 3 * * * /opt/fegcraft-updated/backup_minecraft.sh >> /private/log 2>&1\n0 4 * * * /opt/other/backup.sh\n'
        changed,count=i.pause_lines(raw)
        self.assertEqual(count,1);self.assertIn(b'# VECTOR_INCREMENTAL_REPLACED 0 3',changed)
        self.assertTrue(changed.endswith(b'0 4 * * * /opt/other/backup.sh\n'))
        self.assertEqual(i.pause_lines(changed),(changed,0))
    def test_atomic_mode_and_symlink_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);target=folder/'file';i.atomic(target,b'private',0o600)
            self.assertEqual(target.stat().st_mode&0o777,0o600)
            link=folder/'link';link.symlink_to(target)
            with self.assertRaisesRegex(RuntimeError,'SYMLINK'):i.atomic(link,b'bad')
            self.assertEqual(target.read_bytes(),b'private')
    @unittest.skipUnless(os.geteuid()==0,'Root ownership fixture is exercised locally')
    def test_dependency_setup_failure_holds_old_entrypoint_without_game_operation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);base=root/'game';base.mkdir();backups=base/'backups';backups.mkdir();(root/'releases').mkdir()
            target=base/'backup_minecraft.py';old=b'print("old offline job")\n';target.write_bytes(old)
            shell=b'#!/bin/sh\nexec python3 backup_minecraft.py\n';(base/'backup_minecraft.sh').write_bytes(shell)
            def command(args,**kwargs):
                self.assertEqual(args[0],'git')
                if args[-1].endswith('fegcraft-incremental-backup.py'):return b'print("new job")\n'
                return shell if args[-1].endswith('.sh') else old
            with patch.multiple(i,ROOT=root,BASE=base,BACKUPS=backups,STATE=backups/'.vector-incremental',CRON=root/'cron'),patch.object(i,'run',side_effect=command),patch.object(i,'pause_cron',return_value=1),patch.object(i.shutil,'which',return_value=None),patch.dict(os.environ,{'VECTOR_BACKUP_REV':'a'*40,'VECTOR_INSTALL_BACKUP_PACKAGES':'0'}):
                with self.assertRaisesRegex(RuntimeError,'DEPENDENCIES_REQUIRE_SETUP_FLAG'):i.install()
            self.assertEqual(target.read_bytes(),i.HOLD)
            self.assertFalse((root/'cron').exists())
            release=next((root/'releases').iterdir());self.assertEqual((release/'backup.before.py').read_bytes(),old)
            self.assertTrue((release/'disable.sh').is_file())

    def test_disable_holds_job_and_keeps_archives(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);base=root/'game';base.mkdir();backups=base/'backups';backups.mkdir()
            release=root/'releases/vector-incremental-backup-fixture';release.mkdir(parents=True)
            engine=b'fixture engine';target=base/'backup_minecraft.py';target.write_bytes(engine)
            (release/'expected-engine.sha256').write_text(i.sha(engine));cron=root/'cron';cron.write_bytes(i.CRON_CONTENT)
            (backups/'old.tar').write_bytes(b'old')
            with patch.multiple(i,ROOT=root,BASE=base,BACKUPS=backups,CRON=cron),patch.object(i,'read',side_effect=lambda p:p.read_bytes()),patch.object(i.os,'geteuid',return_value=0):
                i.disable(release);i.disable(release)
            self.assertEqual(target.read_bytes(),i.HOLD);self.assertEqual((backups/'old.tar').read_bytes(),b'old')
            self.assertTrue(cron.read_bytes().startswith(b'# VECTOR_DISABLED '))

if __name__=='__main__':unittest.main()
