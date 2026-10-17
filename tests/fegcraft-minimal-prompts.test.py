"""Synthetic native transport controls and cleanup; never model qualification."""
import importlib.util,io,json,subprocess,sys,tempfile,unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('minimal',ROOT/'scripts/deploy/diagnose-fegcraft-minimal-prompts.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Minimal(unittest.TestCase):
 def run_harness(self,variant='normal'):
  setup=r'''
import hashlib,io,json,urllib.request
variant=VARIANT
template='synthetic audited template'
real_hash=hashlib.sha256
class Hash:
 def hexdigest(self):return '57f1fd00f0013a2be96aa79b857391f27e23df5b5f847072b524c897e24d0361'
hashlib.sha256=lambda data:Hash() if data==template.encode() else real_hash(data)
calls=[];controls={}
class HTTP:
 def open(self,request,**kwargs):
  path=request.full_url.removeprefix('http://vector-local-inference:11434')
  if path=='/api/version':return io.BytesIO(json.dumps({'version':'changed' if variant=='version' else '0.40.4'}).encode())
  data=json.loads(request.data)
  if path=='/api/show':
   return io.BytesIO(json.dumps({'template':template,'system':'private' if variant=='system' else '',
    'model_info':{'general.architecture':'qwen3','tokenizer.ggml.add_bos_token':variant=='bos','tokenizer.ggml.eos_token_id':151645}}).encode())
  assert kwargs['timeout']==25
  assert 'format' not in data and data['stream'] is False
  assert data['options']['num_predict']==96 and data['options']['temperature']==.7
  assert data['options']['stop']==['<|im_end|>','<|im_start|>']
  if path=='/api/chat':
   assert data['think'] is False and 'raw' not in data
   assert len(data['messages'])==2
   controls['system']=data['messages'][0]['content'];controls['question']=data['messages'][1]['content']
  else:
   assert path=='/api/generate' and data['raw'] is True
   assert 'messages' not in data and 'think' not in data
   assert data['prompt']=='<|im_start|>system\n'+controls['system']+'<|im_end|>\n<|im_start|>user\n'+controls['question']+'<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
  calls.append(path)
  if variant=='timeout' and len(calls)==2:raise TimeoutError('synthetic')
  if variant=='list' and len(calls)==2:return io.BytesIO(b'[]')
  result={'model':data['model'],'done':True,'done_reason':'length' if variant=='length' else 'stop',
   'prompt_eval_count':10,'eval_count':5,'load_duration':1000000000,'prompt_eval_duration':200000000,'eval_duration':500000000,
   'message':{'content':'synthetic chat answer'},'response':'synthetic raw answer'}
  if variant=='text' and len(calls)==2:result['response']=None
  if variant=='counts' and len(calls)==2:result.update(prompt_eval_count=True,eval_count=-1)
  return io.BytesIO(json.dumps(result).encode())
urllib.request.build_opener=lambda *a:HTTP()
'''.replace('VARIANT',repr(variant))
  return subprocess.run([sys.executable,'-c',setup+m.HARNESS],capture_output=True,text=True,timeout=10)
 def test_paired_native_and_raw_language_controls_and_usage(self):
  r=self.run_harness();self.assertEqual(r.returncode,0,r.stderr);v=json.loads(r.stdout)
  self.assertEqual(v['model_calls'],8);self.assertEqual(v['metadata_reads'],2)
  self.assertEqual((v['input_tokens'],v['output_tokens']),(80,40))
  self.assertTrue(all(row['complete'] for row in v['cases']))
  self.assertEqual({(r['id'],r['language'],r['transport']) for r in v['cases']},
   {(i,l,t) for i in ('cow','glass') for l in ('en','de') for t in ('chat','raw-chatml')})
  self.assertTrue(all(row['synthetic_answer']==('synthetic chat answer' if row['transport']=='chat' else 'synthetic raw answer') for row in v['cases']))
  self.assertFalse(v['quality_passed']);self.assertFalse(v['passed']);self.assertFalse(v['eligible_for_activation'])
  self.assertEqual(v['cloud_calls'],0);self.assertNotIn('factual_fixture_passed',v['cases'][0])
 def test_unknown_usage_not_zero_and_no_retry(self):
  for variant in ('timeout','counts','list'):
   r=self.run_harness(variant);self.assertEqual(r.returncode,0,r.stderr);v=json.loads(r.stdout)
   self.assertIsNone(v['input_tokens']);self.assertIsNone(v['output_tokens'])
   self.assertEqual(v['unknown_usage_calls'],1);self.assertEqual(v['model_calls'],8)
   self.assertEqual(v['known_input_tokens'],70)
 def test_complete_native_counts_retained_for_truncation_or_bad_text(self):
  for variant in ('length','text'):
   r=self.run_harness(variant);self.assertEqual(r.returncode,0,r.stderr);v=json.loads(r.stdout)
   self.assertEqual(v['output_tokens'],40)
   if variant=='length':self.assertTrue(all(not row['complete'] for row in v['cases']))
   else:self.assertEqual(v['cases'][1]['error'],'NATIVE_TEXT_SHAPE')
 def test_metadata_drift_stops_before_inference(self):
  for variant in ('version','system','bos'):
   r=self.run_harness(variant);self.assertNotEqual(r.returncode,0)
   self.assertIn('AUDITED_NATIVE_METADATA_CHANGED',r.stderr);self.assertNotIn('private',r.stdout)
 def test_reuses_evaluator_and_rejects_unverified_cleanup(self):
  for bad in (None,'cleanup_verified','production_unchanged','weights_unloaded'):
   result=dict(model_calls=8,cleanup_verified=True,production_unchanged=True,weights_unloaded=True)
   if bad:result[bad]=False
   calls=[]
   def evaluate():calls.append(fake.HARNESS);return result
   fake=SimpleNamespace(HARNESS='original',evaluate=evaluate)
   with tempfile.TemporaryDirectory() as folder,redirect_stdout(io.StringIO()):
    if bad:
     with self.assertRaises(RuntimeError):m.diagnose(fake,Path(folder))
    else:self.assertIs(m.diagnose(fake,Path(folder)),result)
   self.assertEqual(calls,[m.HARNESS]);self.assertEqual(fake.HARNESS,'original')

if __name__=='__main__':unittest.main()
