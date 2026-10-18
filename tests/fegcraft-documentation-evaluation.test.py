"""Composed extraction gate with synthetic transport; never model-quality proof."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load('documentation_evaluation_base', 'scripts/deploy/evaluate-fegcraft-general-help.py')
wrapper = load('documentation_evaluation_wrapper', 'scripts/deploy/evaluate-fegcraft-documentation.py')


class Evaluation(unittest.TestCase):
    def run_harness(self, variant='normal'):
        _, source = wrapper.sources(base)
        setup = '''import io,json,os,urllib.request
os.environ['VECTOR_FEGCRAFT_MODEL_EVALUATION']='1'
class Opener:
 def open(self,req,**kwargs):
  payload=json.loads(req.data);data=json.loads(payload['messages'][-1]['content']);q=data['question'].casefold()
  choices=payload['format']['properties']['passage']['enum']
  selected=choices[0]
  if 'partys' in q:selected='party-rights'
  if any(word in q for word in ('kisten','truhe','bereich','ofen')) and 'claims-claim' in choices:selected='claims-claim'
  if 'mitgliedern' in q:selected='claims-menu'
  if 'gruppe' in q:selected='voice-groups'
  if 'lebenspunkte' in q:selected='none'
  if VARIANT=='wrong-relevance' and 'gruppe' in q:selected='voice-menu'
  if VARIANT=='wrong-kind' and 'mitgliedern' in q:selected='party-rights'
  if VARIANT=='missing-claim-step' and 'kisten' in q:selected='claims-menu'
  if VARIANT=='unknown-id':selected='not-in-evidence'
  body={'passage':selected}
  if VARIANT=='freeform':body={'answer':'Schmelze Glas aus Stein.'}
  if VARIANT=='timeout' and 'kolben' in q:raise TimeoutError('synthetic timeout')
  return io.BytesIO(json.dumps(dict(model=payload['model'],done=True,done_reason='length' if VARIANT=='length' else 'stop',prompt_eval_count=100,eval_count=10,message=dict(content=json.dumps(body)))).encode())
urllib.request.build_opener=lambda *args:Opener()
'''.replace('VARIANT', repr(variant))
        source = source.replace("Path('/code/mods.json').read_text()", repr('["carryon","openpartiesandclaims","voicechat","travelersbackpack"]'))
        source = source.replace("sys.path.insert(0,'/code/services/fegcraft-assistant')", 'sys.path.insert(0,'+repr(str(ROOT/'services/fegcraft-assistant'))+')')
        source = source.replace("'/code/services/fegcraft-assistant/public-knowledge.json'", repr(str(ROOT/'tests/fixtures/fegcraft-reviewed-catalog-v1.json')))
        result = subprocess.run([sys.executable, '-c', setup+source], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_full_original_questions_plus_heldout_topics_and_missing_evidence(self):
        result = self.run_harness()
        self.assertTrue(result['passed'], result['cases'])
        self.assertEqual(len(result['cases']), 31)
        self.assertEqual(result['model_calls'], 17)
        self.assertEqual(result['input_tokens'], 1700)
        self.assertEqual(result['output_tokens'], 170)
        self.assertEqual(result['answer_mode'], 'reviewed-extractive')
        self.assertFalse(result['production_activated'])
        self.assertFalse(result['eligible_for_activation'])
        self.assertFalse(result['full_knowledge_qualified'])
        self.assertFalse(result['dedicated_db_role_qualified'])
        self.assertFalse(result['exact_installed_mod_versions_qualified'])
        self.assertEqual(result['catalog_sha256'], wrapper.CATALOG_SHA256)
        self.assertTrue(all(c['native'][0]['stage']=='selection' for c in result['cases'] if c['native']))

    def test_valid_but_irrelevant_selection_still_fails_quality(self):
        result = self.run_harness('wrong-relevance')
        self.assertFalse(result['passed'])
        case = next(c for c in result['cases'] if c['id']=='voice-group')
        self.assertFalse(case['passed'])

    def test_owner_observed_overview_cannot_be_selected_for_action_followup(self):
        result = self.run_harness('wrong-kind')
        self.assertFalse(result['passed'])
        case = next(c for c in result['cases'] if c['id']=='party-followup')
        self.assertFalse(case['passed'])
        self.assertEqual(case['adapter_error'], 'INVALID_SOURCE_SELECTION')

    def test_opening_settings_does_not_substitute_for_claiming_the_chunk(self):
        result = self.run_harness('missing-claim-step')
        case = next(c for c in result['cases'] if c['id']=='claims')
        self.assertFalse(case['passed'])
        self.assertFalse(result['passed'])

    def test_model_cannot_smuggle_freeform_or_unknown_source_into_chat(self):
        for variant in ('freeform', 'unknown-id', 'length'):
            result = self.run_harness(variant)
            self.assertFalse(result['passed'])
            self.assertTrue(all(not c['passed'] for c in result['cases'] if c['model_calls']))
            self.assertNotIn('Glas aus Stein', str([c['synthetic_answer'] for c in result['cases']]))

    def test_timeout_keeps_known_usage_and_never_activates(self):
        result = self.run_harness('timeout')
        self.assertFalse(result['passed'])
        self.assertIsNone(result['input_tokens'])
        self.assertEqual(result['unknown_usage_calls'], 1)
        self.assertEqual(result['known_input_tokens'], 1600)
        self.assertEqual(result['known_output_tokens'], 160)

    def test_coordinator_keeps_pinned_candidate_shared_lock_lease_and_unload(self):
        coordinator, source = wrapper.sources(base)
        result = subprocess.run(['node', '--check', '--input-type=module'], input=coordinator, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for marker in (wrapper.MODEL, wrapper.DIGEST, '6194261933202610', '300000', 'keep_alive:0', 'weights-busy', 'BEGIN READ ONLY'):
            self.assertIn(marker, coordinator)
        self.assertIn('warm_median<=8', source)
        self.assertIn('25 if index==0 else 12', source)
        self.assertIn("('seed'", source)
        self.assertIn("('cheating'", source)
        with self.assertRaises(RuntimeError):
            wrapper.replace_once('changed', 'missing', 'no')


if __name__ == '__main__':
    unittest.main()
