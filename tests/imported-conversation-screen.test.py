"""Native candidate screen contracts with synthetic metadata/responses only."""
from contextlib import contextmanager,redirect_stdout,redirect_stderr
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
screen=load('candidate_screen','scripts/deploy/screen-imported-conversation.py')
guard=load('candidate_guard','scripts/deploy/update-minecraft-ranking-runtime.py')
TEMPLATE='synthetic template'
PINS={'model':screen.MODEL,'manifest_digest':'a'*64,'template_sha256':hashlib.sha256(TEMPLATE.encode()).hexdigest()}

class Screen(unittest.TestCase):
    def test_preparation_must_be_private_owned_and_verified_for_separate_alias(self):
        record={**PINS,'prepared':True,'expected_weight_sha256':screen.WEIGHT,
            'weight_digest_matches_source':True,'service_configuration_and_identities_unchanged':True,
            'production_activated':False}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'result.json';path.write_text(json.dumps(record));path.chmod(0o600)
            self.assertEqual(screen.preparation(path,guard),PINS)
            for key,value in [('model','active-model'),('prepared',False),('manifest_digest','short'),
                              ('expected_weight_sha256','b'*64),('production_activated',True)]:
                with self.subTest(key=key):
                    path.write_text(json.dumps({**record,key:value}))
                    with self.assertRaises(RuntimeError):screen.preparation(path,guard)
            path.write_text(json.dumps(record));path.chmod(0o644)
            with self.assertRaises(RuntimeError):screen.preparation(path,guard)

    def probe(self,*,timeout=False,slot_busy=False,bad_manifest=False,incomplete=False):
        requests=[];slots=[]
        runtime=ModuleType('runtime')
        runtime.State=lambda *args:None
        @contextmanager
        def slot(dsn):
            slots.append(dsn)
            if slot_busy:raise RuntimeError('SYNTHETIC_BUSY')
            yield
        runtime.local_slot=slot;runtime.request_forbidden=lambda q:False;runtime.safe_answer=lambda q:q
        server=ModuleType('server');server.knowledge_for=lambda *args:SimpleNamespace(dsn='synthetic-restricted-role')
        dialogue=ModuleType('dialogue');dialogue.SYSTEM='synthetic system'
        dialogue.require_grounded_numbers=lambda *args:None
        dialogue.GroundedDialogue=SimpleNamespace(validate_answer=lambda value:value)
        def open_request(req,**kwargs):
            route=req.full_url.rsplit('/',1)[-1]
            if route=='tags':value={'models':[{'name':screen.MODEL,'digest':('b' if bad_manifest else 'a')*64}]}
            elif route=='show':value={'template':TEMPLATE,'modelfile':'FROM /models/sha256-'+screen.WEIGHT,
                                      'details':{'family':'lfm2'}}
            else:
                self.assertEqual(route,'chat')
                body=json.loads(req.data);requests.append(body)
                if timeout:raise TimeoutError()
                text='Gönn dir eine Pause und ruh dich auf dem Sofa aus.'
                value={'model':screen.MODEL,'done':True,'done_reason':'length' if incomplete else 'stop',
                    'message':{'content':json.dumps({'answer':text})},
                    'prompt_eval_count':100,'eval_count':20,'load_duration':10,'eval_duration':30}
            return io.BytesIO(json.dumps(value).encode())
        payload={'candidate_screen':PINS,'files':{name:'# synthetic' for name in
            ('runtime.py','server.py','knowledge.py','dialogue.py','portraits.py')}}
        output=io.StringIO()
        with patch.dict(sys.modules,{'runtime':runtime,'server':server,'dialogue':dialogue}), \
                patch('urllib.request.build_opener',return_value=SimpleNamespace(open=open_request)), \
                patch.object(sys,'stdin',io.StringIO(json.dumps(payload))),redirect_stdout(output),redirect_stderr(io.StringIO()):
            if bad_manifest:
                with self.assertRaisesRegex(RuntimeError,'CANDIDATE_MANIFEST_CHANGED'):exec(screen.INNER,{})
                self.assertEqual(requests,[]);return None
            exec(screen.INNER,{})
        result=json.loads(next(s.split('=',1)[1] for s in output.getvalue().splitlines() if s.startswith('VECTOR_DIALOGUE_RESULT=')))
        return result,requests,slots

    def test_two_chat_calls_use_pinned_model_shared_slot_and_real_history_without_promotion(self):
        result,requests,slots=self.probe()
        self.assertTrue(result['passed']);self.assertEqual(result['model_calls'],2)
        self.assertEqual(len(slots),2);self.assertEqual(result['unknown_usage_calls'],0)
        self.assertEqual(result['known_input_tokens'],200)
        self.assertEqual([m['role'] for m in requests[1]['messages']],['system','user','assistant','user'])
        self.assertIn('Pause',requests[1]['messages'][2]['content'])
        self.assertEqual(requests[0]['model'],screen.MODEL)
        self.assertEqual(requests[0]['options']['temperature'],0.1)
        self.assertEqual(requests[0]['options']['num_ctx'],4096)
        self.assertNotIn('think',requests[0])
        self.assertEqual(set(requests[0]['format']['properties']),{'answer','statistics','portrait','documentation','recipe','mods'})
        self.assertFalse(result['production_activated']);self.assertFalse(result['eligible_for_activation'])
        self.assertFalse(result['production_request_contract_tested'])
        self.assertTrue(result['humor_requires_manual_review'])

    def test_timeout_stops_after_one_request_and_retains_unknown_usage(self):
        result,requests,slots=self.probe(timeout=True)
        self.assertFalse(result['passed']);self.assertEqual(len(requests),1)
        self.assertEqual(result['unknown_usage_calls'],1)
        self.assertTrue(result['cases'][0]['server_completion_unknown'])

    def test_slot_contention_prevents_native_request_and_is_not_counted_as_unknown_usage(self):
        result,requests,slots=self.probe(slot_busy=True)
        self.assertFalse(result['passed']);self.assertEqual(requests,[])
        self.assertEqual(result['model_calls'],0);self.assertEqual(result['unknown_usage_calls'],0)

    def test_incomplete_response_keeps_known_token_counts_and_cannot_pass(self):
        result,requests,slots=self.probe(incomplete=True)
        self.assertFalse(result['passed']);self.assertEqual(len(requests),1)
        self.assertEqual(result['known_input_tokens'],100);self.assertEqual(result['unknown_usage_calls'],0)

    def test_manifest_drift_stops_before_any_native_request(self):
        self.probe(bad_manifest=True)

if __name__=='__main__':unittest.main()
