import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import tempfile
import contextlib
import io

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
  if(url.endsWith('/api/tags'))return Response.json({models:[candidate] .map(m=>({name:m.name,digest:m.digest}))});
  if(url.endsWith('/api/ps'))return Response.json({models:[]});
  if(url.endsWith('/api/generate')){if(JSON.parse(init.body).model!==candidate.name)throw Error('Wrong model unload');return Response.json({done:true});}
  if(!url.endsWith('/api/chat'))throw Error('Unexpected endpoint');
  const body=JSON.parse(init.body);
  if(body.model!==candidate.name)throw Error('Wrong candidate request');
  const text=JSON.parse(body.messages[1].content).text;
  const names=['Erika Muster','Leonhard Sample','Anna','Zoë Beispiel','Helena Musterfrau','Mia','Jean-Luc Démont'];
  const findings=names.filter(value=>text.includes(value)&&!(FAIL_CASE&&value==='Anna')).map(value=>({type:'PERSON',value}));
  if(INVALID_CASE&&text.includes('Erika Muster'))findings.push({type:'PERSON',value:'invented-value-never-print'});
  return Response.json({done:true,done_reason:'stop',prompt_eval_count:50,eval_count:10,message:{content:JSON.stringify({findings})}});
};
'''


class EvaluationTests(unittest.TestCase):
    def run_harness(self, fail, invalid=False, candidate=None):
        files = {name:(ROOT/name).read_text() for name in module.FILES}
        code = module.render_harness(files,candidate or module.CANDIDATES[0])
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

    def test_both_pinned_candidates_use_identical_fixtures_and_native_usage(self):
        baseline = self.run_harness(False)
        other = self.run_harness(False,candidate=module.CANDIDATES[1])
        self.assertTrue(other['passed'])
        self.assertEqual(other['model'],'vector-hermes3:8b-q4km')
        self.assertEqual(other['calls'],9)
        self.assertEqual(other['input_tokens'],450)
        self.assertEqual(other['loaded_models_after_unload'],0)
        self.assertEqual([c['id'] for c in baseline['cases']],[c['id'] for c in other['cases']])
        failing = self.run_harness(True,candidate=module.CANDIDATES[1])
        self.assertFalse(failing['passed'])
        with self.assertRaises(RuntimeError):
            module.render_harness({}, {'name':'unapproved'})

    def test_rejected_output_has_safe_synthetic_diagnostics(self):
        report = self.run_harness(False, invalid=True)
        case = next(c for c in report['cases'] if c['id']=='german-name-email-password')
        self.assertFalse(case['passed'])
        self.assertEqual(case['error'],'DETECTOR_REJECTED')
        self.assertEqual(case['observations'][0]['findings'][-1]['value'],'[not an exact input span]')
        self.assertNotIn('invented-value-never-print',json.dumps(report))
        self.assertEqual(report['calls'],9)
        self.assertEqual(report['loaded_models_after_unload'],0)

    def test_comparison_records_both_models_and_never_activates(self):
        for passes in ([False, True], [False, False]):
            calls=[]
            def command(*args, **kwargs):
                if args[0]=='git':
                    return b''
                self.assertEqual(args[:4],('docker','exec','-i','vector-app'))
                index=len(calls)
                calls.append(kwargs['data'].decode())
                return json.dumps(dict(model=module.CANDIDATES[index]['name'],
                    passed=passes[index],api_cost_chf=0,loaded_models_after_unload=0)).encode()
            fingerprint={'/vector-app':{'image':module.IMAGE},
                '/vector-local-inference':{'networks':['vector-local-inference']}}
            with tempfile.TemporaryDirectory() as directory:
                def safe_path(value):
                    self.assertEqual(value,'/root/vector-workspace/releases')
                    return Path(directory)
                with patch.dict(module.os.environ,{'VECTOR_PRIVACY_REV':'a'*40,'VECTOR_PRIVACY_COMPARE_MODELS':'1'}), \
                     patch.object(module.os,'geteuid',return_value=0), \
                     patch.object(module,'run',side_effect=command), \
                     patch.object(module,'fingerprint',return_value=fingerprint), \
                     patch.object(module,'Path',side_effect=safe_path), \
                     contextlib.redirect_stdout(io.StringIO()):
                    if any(passes):
                        module.main()
                    else:
                        with self.assertRaises(RuntimeError):
                            module.main()
                report=json.loads(next(Path(directory).glob('*/result.json')).read_text())
                self.assertEqual(len(calls),2)
                self.assertEqual(report['passed'],any(passes))
                self.assertFalse(report['production_activated'])
                self.assertFalse(report['ledger_writes'])
                self.assertTrue(report['production_unchanged'])
                expected=['vector-hermes3:8b-q4km'] if any(passes) else []
                self.assertEqual(report['qualified_models'],expected)

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
