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
    def run_harness(self,wrong=False):
        setup='''import io,json,os,urllib.request
os.environ['VECTOR_FEGCRAFT_MODEL_EVALUATION']='1'
class Opener:
 def open(self,req,**kwargs):
  value=json.loads(req.data);q=value['messages'][-1]['content'].casefold()
  answer='Ein Kolben schiebt Blöcke.';topic='minecraft'
  if 'komparator' in q:answer='Vergleicht die Signalstärke und misst Füllstände.'
  if 'claims' in q:answer='Claims schützen Chunks und Kisten durch Zugriffsrechte.';topic='openpartiesandclaims'
  if 'partys' in q:answer='In einer Party können Mitglieder gemeinsam Claim-Rechte erhalten.';topic='openpartiesandclaims'
  if 'mitgliedern' in q:
   assert len(value['messages'])>=4
   answer='Prüfe im Claim-Menü die Rechte für Party-Mitglieder.';topic='openpartiesandclaims'
  if 'bewerbung' in q:answer='';topic='other'
  if WRONG:answer='Unpassender Text.';topic='minecraft'
  return io.BytesIO(json.dumps({'model':value['model'],'done':True,'done_reason':'stop','prompt_eval_count':100,'eval_count':10,'message':{'content':json.dumps({'topic':topic,'answer':answer})}}).encode())
urllib.request.build_opener=lambda *args:Opener()
'''.replace('WRONG',str(wrong))
        source=m.HARNESS.replace("Path('/code/mods.json').read_text()",repr('[\"carryon\",\"openpartiesandclaims\",\"fabric-api\",\"travelersbackpack\"]')).replace("sys.path.insert(0,'/code/services/fegcraft-assistant')",'sys.path.insert(0,'+repr(str(ROOT/'services/fegcraft-assistant'))+')')
        result=subprocess.run([sys.executable,'-c',setup+source],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr);return json.loads(result.stdout)
    def test_composed_routes_context_boundaries_and_native_usage(self):
        r=self.run_harness();self.assertTrue(r['passed'],r['cases']);self.assertEqual(r['model_calls'],6)
        self.assertEqual(r['input_tokens'],600);self.assertEqual(r['output_tokens'],60)
        self.assertTrue(all(c['model_calls']==0 for c in r['cases'][6:]))
        self.assertFalse(r['production_activated']);self.assertFalse(r['dedicated_db_role_qualified']);self.assertFalse(r['universal_mod_accuracy_claimed'])
    def test_wrong_answers_cannot_pass(self):self.assertFalse(self.run_harness(True)['passed'])
    def test_shared_coordinator_syntax(self):
        r=subprocess.run(['node','--check','--input-type=module'],input=m.COORDINATOR,text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr);self.assertIn('6194261933202610',m.COORDINATOR);self.assertIn('keep_alive:0',m.COORDINATOR)
if __name__=='__main__':unittest.main()
