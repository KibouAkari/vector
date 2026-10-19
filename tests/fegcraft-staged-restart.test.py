"""No real Docker calls: same-container recovery and exact restart scope."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('staged_restart',ROOT/'scripts/deploy/restart-fegcraft-staged-addon.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)


class Restart(unittest.TestCase):
    def fixture(self,fail_stop=False,replaced=False,exit_code=0):
        game=dict(Id='original',Image='qualified',State=dict(Running=True,StartedAt='old',Health={'Status':'healthy'}))
        initial=copy.deepcopy(game);calls=[]
        def run(*args,**kwargs):
            calls.append(args)
            if args[:2]==('docker','inspect'):
                value=copy.deepcopy(game)
                if replaced:value['Id']='replacement'
                return json.dumps([value]).encode()
            if args[:2]==('docker','stop'):
                game['State']['Running']=False;game['State']['ExitCode']=exit_code
                if fail_stop:raise RuntimeError('synthetic stop CLI failure after daemon stop')
            elif args[:2]==('docker','start'):
                game['State'].update(Running=True,StartedAt='new')
            else:raise AssertionError(args)
            return b''
        return initial,game,calls,SimpleNamespace(run=run)

    def test_regular_restart_only_stops_starts_exact_original_id(self):
        initial,game,calls,p=self.fixture()
        after=r.restart(p,initial)
        self.assertTrue(after['State']['Running']);self.assertEqual(after['State']['StartedAt'],'new')
        actions=[c for c in calls if c[1]!='inspect']
        self.assertEqual(actions,[('docker','stop','--time','120','original'),('docker','start','original')])

    def test_recovery_starts_original_after_failure_but_never_touches_replacement(self):
        for code in (0,137):
            initial,game,calls,p=self.fixture(fail_stop=code==0,exit_code=code)
            with self.assertRaises(RuntimeError):r.restart(p,initial)
            self.assertTrue(game['State']['Running'])
        initial,game,calls,p=self.fixture(replaced=True)
        with self.assertRaisesRegex(RuntimeError,'REPLACED'):r.restart(p,initial)
        self.assertFalse(any(c[1] in ('stop','start') for c in calls))

    def test_only_game_started_at_may_change_in_protected_snapshot(self):
        before={'/fegcraft-updated':{'StartedAt':'old','Id':'same','Mounts':[{'source':'world'}]},'/vector-app':{'StartedAt':'unchanged'},'compose':'hash'}
        after=copy.deepcopy(before);after['/fegcraft-updated']['StartedAt']='new'
        self.assertFalse(r.differences(before,after))
        for key,field,value in (('/fegcraft-updated','Id','different'),('/vector-app','StartedAt','new')):
            changed=copy.deepcopy(after);changed[key][field]=value
            self.assertTrue(r.differences(before,changed))
        after['compose']='changed';self.assertTrue(r.differences(before,after))

    def test_loading_waits_for_fresh_boot_and_reads_registration_on_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            control=Path(directory);instance=control/'owner-welcome-v2.instance'
            instance.write_text('00000000-0000-0000-0000-000000000001\n');os.utime(instance,(0,0))
            p=SimpleNamespace(safe=lambda _:None,read=lambda x:x.read_bytes())
            game=dict(Id='same',State={'StartedAt':'1970-01-01T00:00:01Z'})
            count=[0]
            def logs(*args,**kwargs):
                count[0]+=1
                if count[0]==2:os.utime(instance,(2,2))
                return SimpleNamespace(returncode=0,stdout=b'',stderr=r.REGISTERED)
            with patch.object(r,'CONTROL',control),patch.object(r,'same'),patch.object(r.subprocess,'run',side_effect=logs),patch.object(r.time,'sleep'):
                r.loaded(p,game)
            self.assertEqual(count[0],2)


if __name__=='__main__':unittest.main()
