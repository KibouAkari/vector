"""No real Docker calls: same-container recovery and exact restart scope."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

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


if __name__=='__main__':unittest.main()
