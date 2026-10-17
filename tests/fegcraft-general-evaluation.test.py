"""The real general-help adapter, policy and quality gate with offline transport."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('general_eval',ROOT/'scripts/deploy/evaluate-fegcraft-general-help.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Evaluation(unittest.TestCase):
    def run_harness(self,wrong=False,diagnostic=False,variant="normal"):
        setup='''import io,json,os,urllib.request
os.environ['VECTOR_FEGCRAFT_MODEL_EVALUATION']='1'
class Opener:
 def open(self,req,**kwargs):
  value=json.loads(req.data);q=value['messages'][-1]['content'].casefold()
  if VARIANT=='timeout' and 'kolben' in q:raise TimeoutError('synthetic timeout')
  answer='Ein Kolben schiebt Blöcke.';topic='minecraft'
  if 'komparator' in q:answer='Vergleicht die Signalstärke und misst Füllstände.'
  if 'claims' in q:answer='Claims schützen Chunks und Kisten durch Zugriffsrechte.';topic='openpartiesandclaims'
  if 'partys' in q:answer='In einer Party können Mitglieder gemeinsam Claim-Rechte erhalten.';topic='openpartiesandclaims'
  if 'mitgliedern' in q:
   assert len(value['messages'])>=4
   answer='Prüfe im Claim-Menü die Rechte für Party-Mitglieder.';topic='openpartiesandclaims'
  if 'bewerbung' in q:answer='';topic='other'
  if WRONG:answer='Unpassender Text.';topic='minecraft'
  if VARIANT=='unsafe':answer='Nutze /claims.'
  return io.BytesIO(json.dumps({'model':value['model'],'done':True,'done_reason':'length' if VARIANT=='length' else 'stop','load_duration':1000000000,'prompt_eval_duration':2000000000,'eval_duration':3000000000,'prompt_eval_count':100,'eval_count':10,'message':{'content':json.dumps({'topic':topic,'answer':answer})}}).encode())
urllib.request.build_opener=lambda *args:Opener()
'''.replace('WRONG',str(wrong)).replace('VARIANT',repr(variant))
        setup+='\nos.environ["VECTOR_FEGCRAFT_GENERAL_DIAGNOSTIC"]='+repr('1' if diagnostic else '0')+'\n'
        source=m.HARNESS.replace("Path('/code/mods.json').read_text()",repr('[\"carryon\",\"openpartiesandclaims\",\"fabric-api\",\"travelersbackpack\"]')).replace("sys.path.insert(0,'/code/services/fegcraft-assistant')",'sys.path.insert(0,'+repr(str(ROOT/'services/fegcraft-assistant'))+')')
        result=subprocess.run([sys.executable,'-c',setup+source],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr);return json.loads(result.stdout)
    def test_composed_routes_context_boundaries_and_native_usage(self):
        r=self.run_harness();self.assertTrue(r['passed'],r['cases']);self.assertEqual(r['model_calls'],6)
        self.assertEqual(r['input_tokens'],600);self.assertEqual(r['output_tokens'],60)
        self.assertTrue(all(c['model_calls']==0 for c in r['cases'][6:]))
        self.assertFalse(r['production_activated']);self.assertFalse(r['dedicated_db_role_qualified']);self.assertFalse(r['universal_mod_accuracy_claimed'])
    def test_wrong_answers_cannot_pass(self):self.assertFalse(self.run_harness(True)['passed'])
    def test_successful_diagnostic_never_qualifies_activation(self):
        r=self.run_harness(diagnostic=True)
        self.assertTrue(r['quality_passed']);self.assertFalse(r['passed'])
        self.assertTrue(r['diagnostic_only']);self.assertFalse(r['eligible_for_activation'])
        self.assertEqual(r['model_calls'],4)
        native=r['cases'][0]['native'][0]
        self.assertEqual(native['load_duration_seconds'],1)
        self.assertEqual(native['prompt_eval_duration_seconds'],2)
        self.assertEqual(native['eval_duration_seconds'],3)
        self.assertIn('Kolben',native['synthetic_model_text'])
        self.assertGreater(native['prompt_characters'],0)
    def test_truncation_has_actual_rejection_reason_and_usage(self):
        r=self.run_harness(diagnostic=True,variant='length')
        self.assertFalse(r['quality_passed'])
        self.assertTrue(all(c['adapter_error']=='INCOMPLETE_MODEL_RESPONSE' for c in r['cases']))
        self.assertTrue(all(c['native'][0]['done_reason']=='length' for c in r['cases']))
        self.assertEqual(r['input_tokens'],400);self.assertEqual(r['output_tokens'],40)
    def test_timeout_does_not_discard_known_usage_from_other_calls(self):
        r=self.run_harness(diagnostic=True,variant='timeout')
        self.assertIsNone(r['input_tokens']);self.assertIsNone(r['output_tokens'])
        self.assertEqual(r['known_input_tokens'],300);self.assertEqual(r['known_output_tokens'],30)
        self.assertEqual(r['unknown_usage_calls'],1)
        self.assertEqual(r['cases'][0]['adapter_error'],'TimeoutError')
        self.assertEqual(r['cases'][0]['native'][0]['transport_error'],'TimeoutError')
    def test_unsafe_answer_is_observed_but_never_the_player_reply(self):
        r=self.run_harness(diagnostic=True,variant='unsafe')
        self.assertTrue(all(c['adapter_error']=='UNSAFE_ANSWER' for c in r['cases'] if c['id']!='off-topic'))
        self.assertTrue(all('/claims' not in c['synthetic_answer'] for c in r['cases']))
        self.assertTrue(all('/claims' in c['native'][0]['synthetic_model_text'] for c in r['cases']))

    def test_shared_coordinator_syntax(self):
        r=subprocess.run(['node','--check','--input-type=module'],input=m.COORDINATOR,text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr);self.assertIn('6194261933202610',m.COORDINATOR);self.assertIn('keep_alive:0',m.COORDINATOR)
if __name__=='__main__':unittest.main()
