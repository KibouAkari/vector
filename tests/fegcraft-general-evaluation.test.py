"""Actual staged adapter and quality gate under a synthetic native transport."""
import importlib.util,json
from pathlib import Path
import subprocess,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('general_eval',ROOT/'scripts/deploy/evaluate-fegcraft-general-help.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Evaluation(unittest.TestCase):
    def run_harness(self,wrong=False,diagnostic=False,variant='normal'):
        setup='''import io,json,os,urllib.request
os.environ['VECTOR_FEGCRAFT_MODEL_EVALUATION']='1'
class Opener:
 def open(self,req,**kwargs):
  value=json.loads(req.data);data=json.loads(value['messages'][-1]['content']);q=data['question'].casefold()
  routing='route' in value['format']['properties']
  if VARIANT=='timeout' and 'kolben' in q:raise TimeoutError('synthetic timeout')
  if routing:
   body={'route':'other' if 'gedicht' in q else 'game'}
   if VARIANT=='wrong-route':body={'route':'game'}
  else:
   answer='Ein Kolben schiebt Blöcke.'
   if 'komparator' in q:answer='Vergleicht Signalstärken und misst den Füllstand einer Truhe.'
   if 'claims' in q:answer='Claims schützen Chunks und Kisten durch Zugriffsrechte.'
   if 'partys' in q:answer='Eine Party erlaubt Mitgliedern gemeinsame Claim-Rechte.'
   if 'mitgliedern' in q:
    assert len(value['messages'])>=4
    answer='Prüfe im Claim-Menü die Rechte für Party-Mitglieder.'
   if 'kühe' in q:answer='Füttere zwei Kühe mit Weizen.'
   if 'schafe' in q:answer='Füttere zwei Schafe mit Weizen.'
   if 'backpack' in q:answer='Ein tragbarer Rucksack erweitert dein Inventar.'
   if WRONG:answer='Unpassender Text.'
   if VARIANT=='unsafe':answer='Nutze /claims.'
   if VARIANT=='false-facts' and 'komparator' in q:answer='Vergleicht Signale und misst Füllstand; er invertiert Signale in beide Richtungen.'
   if VARIANT=='false-facts' and 'partys' in q:answer='Party-Mitglieder erhalten Claim-Rechte und organisieren Quests.'
   if VARIANT=='denials' and 'komparator' in q:answer='Ein Komparator vergleicht Signale und misst Füllstand; er invertiert keine Signale.'
   if VARIANT=='denials' and 'partys' in q:answer='Party-Mitglieder teilen Claim-Rechte. Die Mod bietet keine Quests.'
   if VARIANT=='mixed-claim' and 'partys' in q:answer='Party-Mitglieder teilen Claim-Rechte und bieten keine Quests, aber organisieren Spielereignisse.'
   if VARIANT=='vague-followup' and 'mitgliedern' in q:answer='Besitzer können Zugriffsrechte einstellen.'
   body={'answer':answer}
  return io.BytesIO(json.dumps({'model':value['model'],'done':True,'done_reason':'length' if VARIANT=='length' and not routing else 'stop','load_duration':1000000000,'prompt_eval_duration':2000000000,'eval_duration':3000000000,'prompt_eval_count':100,'eval_count':10,'message':{'content':json.dumps(body)}}).encode())
urllib.request.build_opener=lambda *args:Opener()
'''.replace('WRONG',str(wrong)).replace('VARIANT',repr(variant))
        setup+='\nos.environ["VECTOR_FEGCRAFT_GENERAL_DIAGNOSTIC"]='+repr('1' if diagnostic else '0')+'\n'
        source=m.HARNESS.replace("Path('/code/mods.json').read_text()",repr('["carryon","openpartiesandclaims","fabric-api","travelersbackpack"]')).replace("sys.path.insert(0,'/code/services/fegcraft-assistant')",'sys.path.insert(0,'+repr(str(ROOT/'services/fegcraft-assistant'))+')')
        result=subprocess.run([sys.executable,'-c',setup+source],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr);return json.loads(result.stdout)
    def test_full_semantic_and_security_gate_counts_every_native_stage(self):
        r=self.run_harness();self.assertTrue(r['passed'],r['cases']);self.assertEqual(r['model_calls'],10)
        self.assertEqual(r['input_tokens'],1000);self.assertEqual(r['output_tokens'],100)
        self.assertTrue(all(c['model_calls']==0 for c in r['cases'][11:]));self.assertTrue(r['latency_passed'])
        self.assertFalse(r['production_activated']);self.assertFalse(r['dedicated_db_role_qualified'])
        self.assertFalse(r['universal_mod_accuracy_claimed']);self.assertFalse(r['eligible_for_activation'])
        self.assertTrue(all(c['model_calls']==c['expected_calls'] for c in r['cases']))
    def test_factually_wrong_answers_still_fail(self):
        self.assertFalse(self.run_harness(True)['passed'])
        r=self.run_harness(variant='false-facts')
        self.assertTrue(all(not c['passed'] for c in r['cases'] if c['id'] in ('comparator','parties')))
    def test_correct_denials_pass_without_licensing_adjacent_false_claims(self):
        self.assertTrue(self.run_harness(variant='denials')['passed'])
        result=self.run_harness(variant='mixed-claim')
        self.assertFalse(next(c for c in result['cases'] if c['id']=='parties')['passed'])
    def test_followup_requires_a_step_or_specific_menu_clarification(self):
        result=self.run_harness(variant='vague-followup')
        self.assertFalse(next(c for c in result['cases'] if c['id']=='party-followup')['passed'])
    def test_unrelated_route_cannot_generate_an_answer(self):
        r=self.run_harness(variant='wrong-route');self.assertFalse(r['passed'])
        case=next(c for c in r['cases'] if c['id']=='unknown-other-topic');self.assertFalse(case['passed']);self.assertEqual(case['model_calls'],2)
    def test_successful_diagnostic_is_not_activation_qualification(self):
        r=self.run_harness(diagnostic=True);self.assertTrue(r['quality_passed']);self.assertFalse(r['passed'])
        self.assertEqual(r['model_calls'],3);self.assertFalse(r['eligible_for_activation'])
        native=r['cases'][0]['native']
        self.assertEqual([n['stage'] for n in native],['answer'])
        self.assertEqual(native[0]['load_duration_seconds'],1)
        self.assertEqual(native[0]['prompt_eval_duration_seconds'],2)
        self.assertEqual(native[0]['eval_duration_seconds'],3)
        self.assertEqual(native[0]['sampling']['temperature'],.7)
    def test_truncation_is_rejected_with_real_usage_preserved(self):
        r=self.run_harness(diagnostic=True,variant='length');self.assertFalse(r['quality_passed'])
        used=[c for c in r['cases'] if c['model_calls']]
        self.assertTrue(all(c['adapter_error']=='INCOMPLETE_MODEL_RESPONSE' for c in used))
        self.assertTrue(all(c['native'][-1]['done_reason']=='length' for c in used))
        self.assertEqual(r['input_tokens'],300);self.assertEqual(r['output_tokens'],30)
    def test_timeout_preserves_known_usage_from_other_stages(self):
        r=self.run_harness(diagnostic=True,variant='timeout')
        self.assertIsNone(r['input_tokens']);self.assertIsNone(r['output_tokens'])
        self.assertEqual(r['known_input_tokens'],200);self.assertEqual(r['known_output_tokens'],20)
        self.assertEqual(r['unknown_usage_calls'],1);self.assertEqual(r['cases'][0]['adapter_error'],'TimeoutError')
    def test_rejected_raw_command_never_becomes_player_reply(self):
        r=self.run_harness(diagnostic=True,variant='unsafe')
        used=[c for c in r['cases'] if c['model_calls']]
        self.assertTrue(all(c['adapter_error']=='UNSAFE_ANSWER' for c in used))
        self.assertTrue(all('/claims' not in c['synthetic_answer'] for c in r['cases']))
        self.assertTrue(all('/claims' in c['native'][-1]['synthetic_model_text'] for c in used))
    def test_coordinator_lease_exceeds_client_and_cleanup_budget(self):
        r=subprocess.run(['node','--check','--input-type=module'],input=m.COORDINATOR,text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr);self.assertIn('6194261933202610',m.COORDINATOR)
        self.assertIn('300000',m.COORDINATOR);self.assertIn('keep_alive:0',m.COORDINATOR)
if __name__=='__main__':unittest.main()
