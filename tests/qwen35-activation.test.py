"""Focused activation boundaries; no Docker, native generation or live secrets."""
import ast
import base64
import copy
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('activation',ROOT/'scripts/deploy/activate-qwen35-datafirst.py')
activation=importlib.util.module_from_spec(spec);spec.loader.exec_module(activation)


class Activation(unittest.TestCase):
    def test_error_summary_keeps_import_cause_and_redacts_credentials(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            activation.display_error(b"ImportError: missing personal_reference password=synthetic-secret postgres://user:secret@host/db")
        text=output.getvalue()
        self.assertIn('personal_reference',text)
        self.assertNotIn('synthetic-secret',text)
        self.assertNotIn('user:secret',text)

    def test_factory_preserves_private_bindings_and_changes_only_unique_import(self):
        source='''TOKEN_PATH="/run/secrets/synthetic_private_token"
def main():
    from dialogue import GroundedDialogue
    mode="6"
    dialogue=GroundedDialogue(knowledge)
'''
        result=activation.switch_factory(source).decode()
        self.assertIn('from datafirst import DataFirstDialogue as GroundedDialogue',result)
        self.assertIn('TOKEN_PATH="/run/secrets/synthetic_private_token"',result)
        a,b=ast.parse(source),ast.parse(result)
        a.body[1].body[0]=b.body[1].body[0]
        self.assertEqual(ast.dump(a),ast.dump(b))

    def test_ambiguous_or_unknown_factory_does_not_patch(self):
        for source in ('def main(): pass','def main():\n from dialogue import GroundedDialogue\n from dialogue import GroundedDialogue'):
            with self.assertRaises(RuntimeError):activation.switch_factory(source)

    def test_only_cpu_field_is_ignored_by_resource_comparison(self):
        row={'Id':'id','HostConfig':{'NanoCpus':2000000000,'Memory':24,'MemorySwap':24},'networks':['private']}
        original=copy.deepcopy(row)
        prep=SimpleNamespace(configuration=lambda guard,value:json.dumps(value,sort_keys=True))
        first=activation.fingerprint(None,prep,row)
        row['HostConfig']['NanoCpus']=4000000000
        self.assertEqual(first,activation.fingerprint(None,prep,row))
        row['HostConfig']['Memory']=12
        self.assertNotEqual(first,activation.fingerprint(None,prep,row))
        self.assertEqual(original['HostConfig']['NanoCpus'],2000000000)

    def test_cpu_restore_requires_owned_generation_and_preserves_memory(self):
        row={'Id':'id','Image':'image','State':{'StartedAt':'stamp'},'HostConfig':{'NanoCpus':4000000000,'Memory':24}}
        prep=SimpleNamespace(configuration=lambda guard,value:json.dumps(value,sort_keys=True))
        calls=[]
        def run(args):
            calls.append(args);row['HostConfig']['NanoCpus']=2000000000
        guard=SimpleNamespace(inventory=lambda:{'inference':row},identity=lambda r:(r['Id'],r['Image'],r['State']['StartedAt']),run=run)
        resources={'identity':['id','image','stamp'],'non_cpu_fingerprint':activation.fingerprint(guard,prep,row)}
        activation.restore_cpu(guard,prep,resources,'inference')
        self.assertEqual(calls,[['docker','update','--cpus','2','id']])
        self.assertEqual(row['HostConfig']['Memory'],24)
        row['Id']='other'
        with self.assertRaisesRegex(RuntimeError,'OWNERSHIP_DRIFT'):
            activation.restore_cpu(guard,prep,resources,'inference')

    def test_bootstrap_rejects_traversal_before_writing(self):
        result=subprocess.run([sys.executable,'-c',activation.BOOTSTRAP],input=json.dumps({
            'files':{'../escape':base64.b64encode(b'bad').decode()},'integration':'pass'}),
            capture_output=True,text=True,timeout=5)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('UNSAFE_CODE_PATH',result.stderr)

    def test_bootstrap_imports_whole_candidate_instead_of_old_dialogue(self):
        files={p.name:base64.b64encode(p.read_bytes()).decode()
               for p in (ROOT/'services/minecraft-assistant').glob('*.py')}
        with tempfile.TemporaryDirectory() as old:
            (Path(old)/'dialogue.py').write_text('class GroundedDialogue: pass\n')
            payload={'files':files,'integration':"import sys;sys.path.insert(0,payload['candidate_code']);import dialogue,datafirst;assert callable(dialogue.personal_reference);assert callable(datafirst.DataFirstDialogue);print('COHERENT_IMPORTS_OK')"}
            import os
            environment=dict(os.environ,PYTHONPATH=old)
            result=subprocess.run([sys.executable,'-c',activation.BOOTSTRAP],input=json.dumps(payload),
                capture_output=True,text=True,timeout=10,env=environment)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('COHERENT_IMPORTS_OK',result.stdout)


if __name__=='__main__':unittest.main()
