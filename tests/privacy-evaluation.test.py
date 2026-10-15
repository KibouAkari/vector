import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('privacy_evaluation', ROOT/'scripts/deploy/evaluate-privacy-review.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

MOCK = r'''
const pg={Pool:class {
  async connect(){return {query:async sql=>({rows:[sql.includes('COUNT')?{count:0}:{locked:true}]}),release(){}}}
  async end(){}
}};
globalThis.fetch=async(url,init)=>{
  if(url.endsWith('/api/tags'))return Response.json({models:[{name:'vector-qwen3:1.7b-q8',digest:'97f1ed78571eac64f6b5b7413d9bc5f50fc95ab13ad4403cd813aebb9ba3a5b0'}]});
  if(url.endsWith('/api/ps'))return Response.json({models:[]});
  if(url.endsWith('/api/generate'))return Response.json({done:true});
  if(!url.endsWith('/api/chat'))throw Error('Unexpected endpoint');
  const body=JSON.parse(init.body);
  const text=JSON.parse(body.messages[1].content).text;
  const names=['Erika Muster','Leonhard Sample','Anna','Zoë Beispiel','Helena Musterfrau','Mia','Jean-Luc Démont'];
  const findings=names.filter(value=>text.includes(value)&&!(FAIL_CASE&&value==='Anna')).map(value=>({type:'PERSON',value}));
  if(INVALID_CASE&&text.includes('Erika Muster'))findings.push({type:'PERSON',value:'invented-value-never-print'});
  return Response.json({done:true,done_reason:'stop',prompt_eval_count:50,eval_count:10,message:{content:JSON.stringify({findings})}});
};
'''


class EvaluationTests(unittest.TestCase):
    def run_harness(self, fail, invalid=False):
        files = {name:(ROOT/name).read_text() for name in module.FILES}
        code = module.HARNESS.replace('FILES_JSON',json.dumps(files))
        code = code.replace("import pg from 'pg';",MOCK.replace('FAIL_CASE','true' if fail else 'false').replace('INVALID_CASE','true' if invalid else 'false'))
        result = subprocess.run(['node','--input-type=module'],input=code,text=True,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def test_actual_harness_preserves_expected_entities_and_native_usage(self):
        report = self.run_harness(False)
        self.assertTrue(report['passed'])
        self.assertEqual(report['calls'],9)
        self.assertEqual(report['input_tokens'],450)
        self.assertEqual(report['output_tokens'],90)
        self.assertEqual(report['api_cost_chf'],0)
        self.assertEqual(report['loaded_models_after_unload'],0)
        self.assertFalse(report['ledger_writes'])

    def test_rejected_output_has_safe_synthetic_diagnostics(self):
        report = self.run_harness(False, invalid=True)
        case = next(c for c in report['cases'] if c['id']=='german-name-email-password')
        self.assertFalse(case['passed'])
        self.assertEqual(case['error'],'DETECTOR_REJECTED')
        self.assertEqual(case['observations'][0]['findings'][-1]['value'],'[not an exact input span]')
        self.assertNotIn('invented-value-never-print',json.dumps(report))
        self.assertEqual(report['calls'],9)
        self.assertEqual(report['loaded_models_after_unload'],0)

    def test_missing_name_remains_a_quality_failure(self):
        report = self.run_harness(True)
        self.assertFalse(report['passed'])
        self.assertFalse(next(c for c in report['cases'] if c['id']=='first-name')['passed'])
        self.assertEqual(report['calls'],9)
        first=next(c for c in report['cases'] if c['id']=='first-name')
        self.assertEqual(first['missing_expected'],['Anna'])
        self.assertEqual(first['error'],'QUALITY_MISMATCH')
        self.assertEqual(first['observations'][0]['findings'],[])


if __name__ == '__main__':
    unittest.main()
