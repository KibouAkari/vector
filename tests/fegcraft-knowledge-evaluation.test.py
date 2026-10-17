import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('knowledge_evaluation',ROOT/'scripts/deploy/evaluate-fegcraft-knowledge.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class KnowledgeEvaluationTests(unittest.TestCase):
    def harness(self,wrong=False,scope="full"):
        self.scope=scope
        # An offline transport fixture exercises the real adapter/parser/policy.
        setup='''import io,json,os,urllib.request
os.environ['VECTOR_FEGCRAFT_MODEL_EVALUATION']='1'
class Opener:
 def open(self,request,**kwargs):
  assert request.full_url=='http://vector-local-inference:11434/api/chat'
  payload=json.loads(request.data)
  assert payload['model']=='vector-qwen3:1.7b-q8' and payload['think'] is False
  assert payload['options']['num_predict']==160
  question=payload['messages'][-1]['content'].casefold()
  answer='Ein Kolben bewegt Blöcke.'
  for key,value in [('werkbank','Vier Holzbretter.'),('ofen','Acht Bruchsteine.'),('trichter','Fünf Eisenbarren und eine Truhe.'),('komparator','Vergleicht Signalstärken.'),('repeater','Verstärkt und verzögert ein Signal.')]:
   if key in question:answer=value
  if WRONG:answer='Unzutreffende Antwort.'
  return io.BytesIO(json.dumps({'done':True,'done_reason':'stop','model':payload['model'],'message':{'content':json.dumps({'answer':answer})},'prompt_eval_count':100,'eval_count':10}).encode())
urllib.request.build_opener=lambda *args:Opener()
'''.replace('WRONG',str(wrong))
        setup+='\nos.environ["VECTOR_FEGCRAFT_EVALUATION_SCOPE"]='+repr(scope)+'\n'
        source=m.HARNESS.replace("sys.path.insert(0,'/code/services/fegcraft-assistant')",'sys.path.insert(0,'+repr(str(ROOT/'services/fegcraft-assistant'))+')')
        result=subprocess.run([sys.executable,'-c',setup+source],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)
    def test_real_adapter_policy_and_metrics_are_exercised_without_external_calls(self):
        result=self.harness()
        self.assertTrue(result['passed']);self.assertEqual(result['model_calls'],6)
        self.assertEqual(result['input_tokens'],600);self.assertEqual(result['output_tokens'],60)
        self.assertEqual(result['cloud_calls'],0);self.assertFalse(result['dedicated_db_role_qualified'])
        self.assertFalse(result['production_activated']);self.assertEqual(result['messages_sent'],0)
        self.assertTrue(all(case['model_calls']==0 for case in result['cases'][6:]))
    def test_incorrect_model_answers_fail_quality_instead_of_enabling_knowledge(self):
        result=self.harness(True);self.assertFalse(result['passed'])
        self.assertTrue(all(not case['passed'] for case in result['cases'][:6]))
        self.assertTrue(all(case['passed'] for case in result['cases'][6:]))
    def test_recipe_diagnostic_is_bounded_and_cannot_qualify_full_knowledge(self):
        result=self.harness(scope='recipe-diagnostic')
        self.assertEqual(result['evaluation_scope'],'recipe-diagnostic');self.assertEqual(result['model_calls'],3)
        self.assertTrue(result['passed']);self.assertFalse(result['full_knowledge_qualified'])
        self.assertEqual([case['id'] for case in result['cases']],['crafting-table','furnace','hopper'])
        self.assertTrue(all(case['synthetic_model_text'] and case['synthetic_answer'] for case in result['cases']))
        self.assertTrue(all(len(case['synthetic_model_text'][0])<=2048 for case in result['cases']))

    def test_coordinator_is_syntax_valid_and_releases_the_real_shared_slot(self):
        result=subprocess.run(['node','--check','--input-type=module'],input=m.COORDINATOR,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('BEGIN READ ONLY',m.COORDINATOR);self.assertIn('6194261933202610',m.COORDINATOR)
        self.assertIn('pg_advisory_unlock',m.COORDINATOR);self.assertIn('keep_alive:0',m.COORDINATOR)
        self.assertNotIn('OPENAI',m.COORDINATOR)

if __name__=='__main__':unittest.main()

