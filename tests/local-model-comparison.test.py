import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parents[1]


def load(name, source):
    spec = importlib.util.spec_from_file_location(name, ROOT / source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ComparisonTests(unittest.TestCase):
    def test_actual_harness_keeps_failed_null_and_summary_cases_and_selects_only_a_fully_passing_candidate(self):
        comparison = load('comparison', 'scripts/deploy/compare-local-models.py')
        evaluation = load('evaluation', 'scripts/deploy/evaluate-local-workers.py')
        harness = comparison.build_harness(evaluation.HARNESS)
        stub = r'''
const fixtureValues=[{players:3,deaths:null},{dienste:7,temperatur:null},{alerts:0,latency_ms:null},
 {benutzer:12,abstuerze:2},{memory_mb:null,temperature:null},{dienste:3,status:'unbekannt'},
 {players:14,deaths:null},{players:5,deaths:0}];
const counts={};
globalThis.fetch=async(url,init)=>{
 if(url!=='http://vector-local-inference:11434/api/chat')throw Error('unexpected URL');
 const payload=JSON.parse(init.body),index=counts[payload.model]||0;
 counts[payload.model]=index+1;
 let data=fixtureValues[index];
 if(payload.model==='vector-qwen3:0.6b-q8' && index===0)data={players:3,deaths:0};
 if(payload.model==='vector-hermes3:8b-q4km' && index===5)data={dienste:['Dienst 1'],status:['unbekannt']};
 return new Response(JSON.stringify({done:true,done_reason:'stop',message:{content:JSON.stringify(data)},
  prompt_eval_count:1,eval_count:1,eval_duration:100000000,load_duration:0}));
};
'''
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / 'lib').mkdir()
            for source in evaluation.FILES:
                shutil.copyfile(ROOT / source, target / source)
            script = target / 'compare.mjs'
            script.write_text(stub + harness)
            output = subprocess.run(['node', str(script)], text=True, capture_output=True, check=True, timeout=15)
            report = json.loads(output.stdout)
        self.assertEqual(report['passing_candidates'], ['vector-qwen3:1.7b-q8'])
        self.assertEqual(report['expected_calls'], 24)
        self.assertEqual(report['accounted_calls'], 24)
        self.assertEqual(report['api_cost_chf'], 0)
        self.assertEqual(report['input_tokens'], 24)
        self.assertTrue(report['usage_complete'])
        self.assertFalse(report['vector_activated'])
        self.assertFalse(report['ledger_writes'])
        wrong = next(row for row in report['results'] if row['model']=='vector-qwen3:0.6b-q8' and row['fixture_index']==0)
        self.assertIsNone(wrong['expected']['deaths'])
        self.assertEqual(wrong['data']['deaths'], 0)
        self.assertFalse(wrong['fixture_passed'])
        hermes = next(row for row in report['results'] if row['model']=='vector-hermes3:8b-q4km' and row['fixture_index']==5)
        self.assertFalse(hermes['fixture_passed'])
        self.assertIn('field type', hermes['error'])


if __name__ == '__main__':
    unittest.main()
