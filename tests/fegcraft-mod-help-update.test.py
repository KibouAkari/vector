"""Synthetic service-only deployment, rollback and unchanged-game boundaries."""
import copy
import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

REPO=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mod_update',REPO/'scripts/deploy/update-fegcraft-mod-help.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class Update(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        output=contextlib.redirect_stdout(io.StringIO());output.__enter__();self.addCleanup(output.__exit__,None,None,None)
        self.root=Path(self.tmp.name);self.install=self.root/'install';self.install.mkdir()
        self.directory=self.root/'releases/vector-fegcraft-mod-help-synthetic';self.directory.mkdir(parents=True)
        self.code=self.directory/'code';self.code.mkdir()
        (self.directory/'installer.py').write_text('pass\n')
        self.profile={'services':{'assistant':{'volumes':[{'source':str(self.install/'code'),'target':'/code','read_only':True}]}}}
        self.raw=(json.dumps(self.profile)+'\n').encode()
        self.manifest={'owner':'synthetic-owner','status':'installed_pending_real_channel','compose_sha256':m.sha(self.raw)}
        self.raw_manifest=(json.dumps(self.manifest)+'\n').encode()
        (self.install/'compose.json').write_bytes(self.raw);(self.install/'manifest.json').write_bytes(self.raw_manifest)
        self.h=SimpleNamespace(HEALTH='pass\n',READ_PROBE='pass\n',compose=Mock(),existing_service=lambda:True)
        patches=[patch.object(m,'ROOT',self.root),patch.object(m,'INSTALL',self.install),
                 patch.object(m,'baseline',return_value=(self.manifest,self.profile,self.raw_manifest,self.raw)),
                 patch.object(m,'snapshots',return_value={'game':['same-id','same-image','same-start']}),
                 patch.object(m,'check_owner',return_value={}),patch.object(m,'healthy',return_value={'complete_statistics':True}),
                 patch.object(m,'helper',return_value=self.h),patch.object(m,'run',return_value=b'')]
        self.mocks=[]
        for p in patches:self.mocks.append(p.start());self.addCleanup(p.stop)

    def test_only_code_mount_changes_and_game_never_operated(self):
        result=m.candidate(self.profile,self.code)
        expected=copy.deepcopy(self.profile);expected['services']['assistant']['volumes'][0]['source']=str(self.code)
        self.assertEqual(result,expected);self.assertEqual(self.profile['services']['assistant']['volumes'][0]['source'],str(self.install/'code'))
        m.deploy(self.directory,self.h,'a'*40,self.code)
        self.h.compose.assert_called_once_with(self.install,'up','-d','--no-deps','--no-build','--pull','never','assistant')
        self.assertEqual(json.loads((self.directory/'deployment.json').read_text())['status'],'deployed')
        self.assertEqual(json.loads((self.install/'manifest.json').read_text())['backend_revision'],'a'*40)

    def test_rollback_restores_profile_manifest_and_only_vector(self):
        m.deploy(self.directory,self.h,'a'*40,self.code);m.rollback(self.directory)
        self.assertEqual((self.install/'compose.json').read_bytes(),self.raw)
        self.assertEqual((self.install/'manifest.json').read_bytes(),self.raw_manifest)
        self.assertEqual(self.h.compose.call_count,2)
        self.assertTrue(all(call.args[-1]=='assistant' for call in self.h.compose.call_args_list))

    def test_failed_service_health_automatically_restores_original(self):
        self.mocks[5].side_effect=[RuntimeError('synthetic health failure'),{'complete_statistics':True}]
        with self.assertRaisesRegex(RuntimeError,'synthetic health'):m.deploy(self.directory,self.h,'a'*40,self.code)
        self.assertEqual((self.install/'compose.json').read_bytes(),self.raw)
        self.assertEqual((self.install/'manifest.json').read_bytes(),self.raw_manifest)
        self.assertEqual(json.loads((self.directory/'deployment.json').read_text())['status'],'rolled_back')

    def test_post_publication_fsync_error_can_rollback(self):
        actual=m.atomic;once=[False]
        def fail(path,raw,mode=0o600):
            actual(path,raw,mode)
            if path==self.install/'compose.json' and not once[0]:once[0]=True;raise OSError('synthetic fsync')
        with patch.object(m,'atomic',side_effect=fail):
            with self.assertRaises(OSError):m.deploy(self.directory,self.h,'a'*40,self.code)
        self.assertEqual((self.install/'compose.json').read_bytes(),self.raw)
        self.assertEqual((self.install/'manifest.json').read_bytes(),self.raw_manifest)

    def test_later_edits_block_rollback(self):
        m.deploy(self.directory,self.h,'a'*40,self.code)
        (self.install/'compose.json').write_text('later owner edit')
        with self.assertRaisesRegex(RuntimeError,'LATER_PROFILE'):m.rollback(self.directory)
        self.assertEqual((self.install/'compose.json').read_text(),'later owner edit')
        self.assertEqual(self.h.compose.call_count,1)

    def test_game_change_blocks_activation_before_profile_write(self):
        self.mocks[3].side_effect=[{'game':'before'},{'game':'changed'}]
        with self.assertRaisesRegex(RuntimeError,'BASELINE_CHANGED'):m.deploy(self.directory,self.h,'a'*40,self.code)
        self.assertEqual((self.install/'compose.json').read_bytes(),self.raw)
        self.h.compose.assert_not_called()


class Baseline(unittest.TestCase):
    def test_public_source_permissions_survive_private_umask(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); old=os.umask(0o077)
            try:
                public,code,tests=m.prepare_public(root)
                for path in (public,code.parent,code,tests):self.assertEqual(path.stat().st_mode & 0o777,0o755)
                source=code/'synthetic.py';m.atomic(source,b'pass\n',0o644)
                self.assertEqual(source.stat().st_mode & 0o777,0o644)
                evidence=root/'private.json';m.atomic(evidence,b'{}')
                self.assertEqual(evidence.stat().st_mode & 0o777,0o600)
                self.assertEqual(root.stat().st_mode & 0o777,0o700)
            finally:os.umask(old)

    def test_default_only_qualifies_and_runner_flag_is_explicit(self):
        self.assertFalse(m.wants_deploy([],{}))
        self.assertTrue(m.wants_deploy([],{'VECTOR_FEGCRAFT_MOD_HELP_DEPLOY':'1'}))
        self.assertTrue(m.wants_deploy(['--deploy'],{}))
        with self.assertRaisesRegex(RuntimeError,'ARGUMENTS'):m.wants_deploy([],{'VECTOR_FEGCRAFT_MOD_HELP_DEPLOY':'yes'})
        with self.assertRaisesRegex(RuntimeError,'ARGUMENTS'):m.wants_deploy(['other'],{})

    def test_actual_runtime_must_match_owned_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            install=Path(temporary);(install/'code').mkdir();(install/'mods.json').write_text('["carryon"]')
            for name in m.FILES:(install/'code'/name).write_bytes(b'pass\n')
            for name in ('health.py','read-probe.py'):(install/'code'/name).write_bytes(b'pass\n')
            service={'user':'1000:1000','entrypoint':['python3','/code/server.py'],
                     'environment':{'VECTOR_FEGCRAFT_KNOWLEDGE':'0'},
                     'volumes':[{'source':str(install/'code'),'target':'/code','read_only':True}],
                     'labels':{'com.vector.installation':'owner'}}
            profile={'services':{'assistant':service}};raw=json.dumps(profile).encode()
            manifest={'owner':'owner','status':'installed_pending_real_channel','compose_sha256':m.sha(raw)}
            (install/'compose.json').write_bytes(raw);(install/'manifest.json').write_text(json.dumps(manifest))
            container={'Image':m.IMAGE,'Config':{'Labels':{'com.vector.installation':'owner','com.docker.compose.project':m.SERVICE,
                 'com.docker.compose.service':'assistant'},'User':'1000:1000','Entrypoint':['python3','/code/server.py'],
                 'Env':['VECTOR_FEGCRAFT_KNOWLEDGE=0']},'HostConfig':{'ReadonlyRootfs':True},
                 'NetworkSettings':{'Networks':{'mc-net':{}},'Ports':{}},
                 'Mounts':[{'Type':'bind','Source':str(install/'code'),'Destination':'/code','RW':False}]}
            h=SimpleNamespace(owned_files=lambda _:['one','two','three'],profile=lambda *args:copy.deepcopy(profile),
                 DATA=install,HEALTH='pass\n',READ_PROBE='pass\n',inspect=lambda _:container)
            with patch.object(m,'INSTALL',install),patch.object(m,'run',return_value=b'pass\n'):
                self.assertEqual(m.baseline(h)[0],manifest)
                container['Mounts'].append({'Type':'bind','Source':'/synthetic/extra','Destination':'/extra','RW':True})
                with self.assertRaisesRegex(RuntimeError,'RUNTIME_MOUNTS'):m.baseline(h)
                container['Mounts'].pop();container['Config']['Env']=['VECTOR_FEGCRAFT_KNOWLEDGE=1']
                with self.assertRaisesRegex(RuntimeError,'RUNTIME_ENV'):m.baseline(h)
                container['Config']['Env']=['VECTOR_FEGCRAFT_KNOWLEDGE=0']
                (install/'code/runtime.py').write_text('unknown later edit')
                with self.assertRaisesRegex(RuntimeError,'EXISTING_CODE_CHANGED'):m.baseline(h)


if __name__=='__main__':unittest.main()
