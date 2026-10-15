import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

pilot=load('ner_pilot',ROOT/'scripts/deploy/pilot-privacy-ner.py')
evaluator=load('privacy_evaluator',ROOT/'scripts/deploy/evaluate-privacy-review.py')

class NERTests(unittest.TestCase):
    def fixtures(self):
        return json.loads(subprocess.check_output(['node','--input-type=module'],
            input=pilot.fixture_expression(evaluator.HARNESS),text=True)) + pilot.HOLDOUTS

    def verify(self,change=None):
        fixtures=self.fixtures()
        cases=[dict(id=f['id'],seconds=0.1,findings=[dict(type='PERSON',value=v)
            for v in f['expected']]) for f in fixtures]
        if change:change(cases)
        payload=dict(fixtures=fixtures,inference=dict(cases=cases),original_case_count=9,additional_case_count=len(pilot.HOLDOUTS),
            core=(ROOT/'lib/privacy-review-core.mjs').read_text(),rules=(ROOT/'lib/privacy-rules.mjs').read_text())
        result=subprocess.run(['node','--input-type=module'],input=pilot.VERIFY.replace('INPUT_JSON',json.dumps(payload)),
            text=True,capture_output=True,timeout=15)
        return result

    def test_exact_original_nine_fixtures_and_roundtrip(self):
        fixtures=self.fixtures()
        self.assertEqual(len(fixtures),16)
        self.assertEqual(fixtures[2]['expected'],['Anna'])
        self.assertEqual(fixtures[3]['expected'],['Zoë Beispiel','zoe@example.invalid'])
        self.assertEqual(fixtures[5]['expected'],['Mia'])
        result=self.verify();self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(result.stdout)['passed'])
        with self.assertRaises(RuntimeError):pilot.fixture_expression('no fixtures')

    def test_missing_first_name_and_software_false_positive_fail(self):
        def missing(cases):cases[5]['findings']=[]
        report=json.loads(self.verify(missing).stdout)
        self.assertFalse(report['passed']);self.assertEqual(report['cases'][5]['missing_expected'],['Mia'])
        def extra(cases):cases[7]['findings']=[dict(type='PERSON',value='Docker')]
        report=json.loads(self.verify(extra).stdout)
        self.assertFalse(report['passed']);self.assertTrue(report['cases'][7]['unexpected_findings'])

    def test_rewritten_name_is_rejected_instead_of_repaired(self):
        def invalid(cases):cases[3]['findings'][0]['value']='Zoe Beispiel'
        self.assertNotEqual(self.verify(invalid).returncode,0)

    def test_inference_has_no_network_and_bounded_resources(self):
        args=pilot.limited_container('owned-test','sha256:test','/work/qualify.py',Path('/tmp/synthetic'),True)
        for flag,value in [('--network','none'),('--cpus','2'),('--memory','4g'),('--memory-swap','4g'),
                           ('--pids-limit','128'),('--cap-drop','ALL'),('--user','65534:65534')]:
            self.assertEqual(args[args.index(flag)+1],value)
        self.assertIn('--read-only',args)
        self.assertIn('HF_HUB_OFFLINE=1',args)
        self.assertIn('TRANSFORMERS_OFFLINE=1',args)
        self.assertTrue(any('dst=/work,readonly' in a for a in args))
        self.assertNotIn('--privileged',args)
        self.assertNotIn('/var/run/docker.sock',' '.join(args))

if __name__=='__main__':unittest.main()
