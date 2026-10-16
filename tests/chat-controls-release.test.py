import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SHELL=ROOT/'scripts/deploy/release-chat-controls.sh'
EMBEDDED=SHELL.read_text().split("<<'CHAT_CONTROLS_RELEASE_PYTHON'\n")[1].split('\nCHAT_CONTROLS_RELEASE_PYTHON\n')[0]
N={'__name__':'test_release'}
exec(compile(EMBEDDED,str(SHELL),'exec'),N)

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

P=load('scripts/deploy/qualify-and-release-chat-controls.py','chat_controls_pipeline')
E=load('scripts/deploy/evaluate-privacy-api.py','chat_controls_evaluator')

class ReleaseTests(unittest.TestCase):
    def reports(self):
        return dict(previous=dict(status='deployed',commit=N['CURRENT'],image_id=N['CURRENT_IMAGE']),
            read=dict(passed=True,snapshot_available=True,statistics_complete=True,production_unchanged=True,
                revision=N['TESTED'],files=50,cloud_calls=0,model_calls=0),
            api=dict(passed=True,isolated_database=True,production_unchanged=True,cleanup_verified=True,
                production_activated=False,cloud_calls=0,revision='a'*40,app_runtime_revision=N['TESTED'],
                app_image=N['TESTED_IMAGE'],native_image='sha256:eca0b83a886fcc9952ef13755853ef63134e5c76733d40564460398776c92dd7',
                normal=dict(passed=True,phase='normal',cloud_calls=0,executed_jobs=0,checks=[
                    'explicit-off-preserves-original-and-skips-detector-normal',
                    'off-restores-owned-historical-placeholders-without-rescan','privacy-off-cannot-override-local-only-project']),
                outage=dict(passed=True,phase='outage',cloud_calls=0,executed_jobs=0,checks=[
                    'native-service-outage-blocks-cloud-send-before-writes',
                    'explicit-off-preserves-original-and-skips-detector-outage',
                    'local-request-remains-quiet-during-detector-outage'])))
    def gate(self,reports,path='/root/vector-workspace/releases/vector-privacy-api-evaluation-20261017T000000Z-aabbcc/result.json'):
        def report(p):
            if p.name=='release.json':return reports['previous']
            return reports['read'] if 'server-read' in str(p) else reports['api']
        with patch.dict(N,private_json=report),patch.object(Path,'read_bytes',return_value=b'same'),patch.dict(os.environ,
            VECTOR_CHAT_RELEASE_REV='a'*40,VECTOR_CHAT_API_REPORT=path):
            N['qualification_gate']()
    def test_exact_completed_reports_allow_release_and_changed_gates_block(self):
        self.gate(self.reports())
        for group,key,value in [('previous','status','prepared'),('previous','image_id','later'),
            ('read','files',0),('read','files',True),('read','statistics_complete',False),
            ('api','cleanup_verified',False),('api','app_image','wrong'),('api','revision','b'*40),
            ('api','production_unchanged',False),('api','cloud_calls',1),('api','production_activated',True)]:
            r=self.reports();r[group][key]=value
            with self.subTest(group=group,key=key),self.assertRaises(RuntimeError):self.gate(r)
        for phase in ['normal','outage']:
            for key,value in [('passed',False),('executed_jobs',1),('checks',[]),('phase','wrong')]:
                r=self.reports();r['api'][phase][key]=value
                with self.subTest(phase=phase,key=key),self.assertRaises(RuntimeError):self.gate(r)
        with self.assertRaises(RuntimeError):self.gate(self.reports(),'/tmp/result.json')
    def test_active_profile_change_blocks_before_report_handoff(self):
        with patch.dict(N,private_json=lambda p:self.reports()['previous']),patch.object(Path,'read_bytes',side_effect=[b'active',b'old']):
            with self.assertRaisesRegex(RuntimeError,'Active profile'):N['qualification_gate']()
    def test_factory_retains_checkout_source_and_other_container_guards(self):
        # Small synthetic archived factory exercises preparation, not production.
        factory="""TESTED='1f742366856a17ff7ab3ab01542d1eb7aca0a4a7'
MERGED='d73f6f982db62532a80696d230dd77b01246c057'
def prepare():
    return {'OLD_REV':CURRENT,'REV':MERGED,'NEW_ID':TESTED_IMAGE,'OTHERS':('vector-worker','vector-runner','vector-postgres','vector-redis'),'idle':lambda:None}
"""
        with tempfile.TemporaryDirectory() as directory:
            script=Path(directory)/'control.sh';script.write_text("<<'CONTROL_RELEASE_PYTHON'\n"+factory+'\nCONTROL_RELEASE_PYTHON\n')
            with patch.dict(N,SCRIPT=script),patch.object(sys,'argv',['release']):
                wrapper=N['prepare']();runtime=wrapper['prepare']()
                self.assertEqual(runtime['OLD_REV'],N['CURRENT']);self.assertEqual(runtime['REV'],N['MERGED'])
                self.assertEqual(runtime['NEW_ID'],N['TESTED_IMAGE']);self.assertEqual(len(runtime['OTHERS']),7)
                calls=[]
                with patch.dict(N,qualification_gate=lambda:calls.append('gate')):
                    runtime['idle']();runtime['idle']()
                self.assertEqual(calls,['gate'])
            with patch.dict(N,SCRIPT=script),patch.object(sys,'argv',['release','--rollback','record']):
                runtime=N['prepare']()['prepare']()
                with patch.dict(N,qualification_gate=lambda:self.fail('Rollback must retain its own guards')):runtime['idle']()
    def test_release_file_is_idempotent_without_overwriting_or_following_links(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(P,'ROOT',Path(directory)):
            (Path(directory)/'current').mkdir();source=b'#!/bin/bash\nset -eu\n'
            path=P.release_file(source);self.assertEqual(path.read_bytes(),source)
            self.assertEqual(P.release_file(source),path)
            with self.assertRaises(RuntimeError):P.release_file(source+b'# changed\n')
            path.unlink();path.symlink_to(Path(directory)/'missing')
            with self.assertRaises(RuntimeError):P.release_file(source)
    def test_failed_qualification_never_invokes_release(self):
        source=b"def main():\n    raise RuntimeError('QUALIFICATION_FAILED')\n"
        with patch.object(P,'git',side_effect=[b'',source,b'#!/bin/bash\n']),patch.object(P,'release_file',return_value=Path('/synthetic/release.sh')),patch.dict(os.environ,VECTOR_CHAT_RELEASE_REV='a'*40),patch.object(P.os,'geteuid',return_value=0),patch.object(P.subprocess,'run') as run:
            with self.assertRaisesRegex(RuntimeError,'QUALIFICATION_FAILED'):P.main()
            run.assert_not_called()
    def test_evaluator_publishes_success_only_after_cleanup(self):
        tree=ast.parse((ROOT/'scripts/deploy/evaluate-privacy-api.py').read_text())
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        tries=[n for n in ast.walk(main) if isinstance(n,ast.Try)]
        self.assertTrue(any(n.finalbody for n in tries))
        lines=(ROOT/'scripts/deploy/evaluate-privacy-api.py').read_text()
        self.assertLess(lines.index("if errors:raise"),lines.index("result['cleanup_verified']=True"))
        self.assertLess(lines.index("result['cleanup_verified']=True"),lines.index("(release/'result.json').write_text"))
    def test_production_fingerprint_requires_all_eight_services(self):
        names=['vector-app','vector-worker','vector-runner','vector-postgres','vector-redis','vector-local-inference','vector-privacy-ner','fegcraft-updated']
        values=[dict(Name='/'+name,Id=name,Image='image',State=dict(Running=True,StartedAt='time'),NetworkSettings=dict(Networks={'private':{}}),Mounts=[]) for name in names]
        with patch.object(E,'run',return_value=json.dumps(values).encode()),patch.object(Path,'read_bytes',return_value=b'compose'):
            result=E.production_fingerprint();self.assertEqual(len(result),10)
        with patch.object(E,'run',return_value=json.dumps(values[:-1]).encode()):
            with self.assertRaises(RuntimeError):E.production_fingerprint()

if __name__=='__main__':unittest.main()
