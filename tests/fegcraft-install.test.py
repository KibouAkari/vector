import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('install',ROOT/'scripts/deploy/install-fegcraft-assistant.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class InstallTests(unittest.TestCase):
    def test_profile_is_private_bounded_and_has_only_scoped_read_inputs(self):
        value=m.profile(Path('/release'),1000,1000,Path('/game/vector/token'))
        self.assertEqual(set(value['services']),{'assistant'})
        service=value['services']['assistant']
        self.assertEqual(service['image'],m.IMAGE)
        self.assertEqual(service['user'],'1000:1000')
        self.assertNotIn('ports',service);self.assertNotIn('privileged',service)
        self.assertEqual(service['networks'],['mc-net'])
        self.assertEqual(service['environment']['VECTOR_FEGCRAFT_KNOWLEDGE'],'0')
        self.assertEqual(service['cap_drop'],['ALL'])
        self.assertEqual(service['mem_limit'],'256m')
        self.assertEqual(service['cpus'],1)
        mounts={x['target']:x for x in service['volumes']}
        self.assertEqual({t for t,v in mounts.items() if not v['read_only']},{'/state'})
        self.assertEqual(set(mounts),{'/code','/state','/inputs/stats','/inputs/usercache.json','/inputs/mods.json','/inputs/recipes.json','/run/secrets/vector_fegcraft_token'})
        self.assertTrue(all(x['bind']['create_host_path'] is False for x in mounts.values()))

    def test_atomic_publication_never_overwrites_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'token'
            m.publish_file(path,b'synthetic',os.getuid(),os.getgid(),0o400)
            self.assertEqual(path.stat().st_mode&0o777,0o400)
            with self.assertRaises(FileExistsError):m.publish_file(path,b'changed',os.getuid(),os.getgid(),0o400)
            self.assertEqual(path.read_bytes(),b'synthetic')
            self.assertEqual(list(path.parent.glob('.vector-write-*')),[])

    def test_partial_owned_files_can_be_checked_but_unknown_or_changed_paths_cannot(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(m,'DATA',Path(directory)):
            path=m.DATA/'DiscordIntegration-Data/vector/token';path.parent.mkdir(parents=True);path.write_text('synthetic')
            manifest={'files':{str(path):m.digest(path)}}
            self.assertEqual(m.owned_files(manifest),[path])
            path.write_text('changed')
            with self.assertRaisesRegex(RuntimeError,'MANAGED_FILE_CHANGED'):m.owned_files(manifest)
            with self.assertRaisesRegex(RuntimeError,'ROLLBACK_PATH_MISMATCH'):m.owned_files({'files':{'/etc/passwd':'anything'}})

    def rollback_case(self,started=False,foreign=False):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);data=root/'data';release=root/'releases/vector-fegcraft-install-test';release.mkdir(parents=True)
        token=data/'DiscordIntegration-Data/vector/token';token.parent.mkdir(parents=True);token.write_text('synthetic')
        (release/'compose.json').write_text('{}')
        manifest={'files':{str(token):m.digest(token)},'owner':'ours','minecraft_image':'image',
                  'compose_sha256':m.digest(release/'compose.json'),'minecraft_restart_started':started}
        (release/'manifest.json').write_text(json.dumps(manifest))
        def inspect(name):
            return {'Image':'image'} if name=='fegcraft-updated' else {'Config':{'Labels':{'com.vector.installation':'foreign' if foreign else 'ours'}}}
        with patch.object(m,'ROOT',root),patch.object(m,'DATA',data),patch.object(m,'inspect',side_effect=inspect),\
             patch.object(m,'existing_service',return_value=foreign),patch.object(m,'compose') as compose,patch.object(m,'run') as run,contextlib.redirect_stdout(io.StringIO()):
            if foreign:
                with self.assertRaisesRegex(RuntimeError,'UNEXPECTED_SERVICE'):m.rollback(release)
                compose.assert_not_called();run.assert_not_called();self.assertTrue(token.exists())
            else:
                m.rollback(release);self.assertFalse(token.exists())
                self.assertEqual(json.loads((release/'manifest.json').read_text())['status'],'rolled_back')
                if started:run.assert_called_once_with('docker','restart','--time','120','fegcraft-updated',timeout=180)
                else:run.assert_not_called()

    def test_pre_cutover_failure_does_not_restart_minecraft(self):self.rollback_case()
    def test_post_cutover_rollback_restarts_only_minecraft(self):self.rollback_case(started=True)
    def test_foreign_service_is_not_removed(self):self.rollback_case(foreign=True)

    def test_persistent_health_probe_uses_signed_ignored_requests_without_rate_events(self):
        sys.path.insert(0,str(ROOT/'services/fegcraft-assistant'))
        from runtime import Assistant,State
        from server import Service
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);token=path/'token';token.write_text('ab'*32)
            state=State(path/'state.sqlite',bytes.fromhex('ab'*32))
            assistant=Assistant(state,None,None,None)
            service=Service(('127.0.0.1',0),assistant,bytes.fromhex('ab'*32))
            worker=threading.Thread(target=service.serve_forever,daemon=True);worker.start()
            try:
                code=m.HEALTH.replace('/run/secrets/vector_fegcraft_token',str(token)).replace('127.0.0.1:8090','127.0.0.1:'+str(service.server_port))
                result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=5)
                self.assertEqual(result.returncode,0,result.stderr)
                with sqlite3.connect(path/'state.sqlite') as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],0)
            finally:service.shutdown();service.server_close();worker.join(timeout=2)


if __name__=='__main__':unittest.main()
