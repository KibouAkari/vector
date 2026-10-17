"""Synthetic model/format observations never qualify production gameplay."""
import ast,importlib.util,io,json
from pathlib import Path
import subprocess,sys,tempfile,unittest
from types import SimpleNamespace
from contextlib import redirect_stdout
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
m=load('format_diagnostic','scripts/deploy/diagnose-fegcraft-model-format.py')
base=load('format_base','scripts/deploy/evaluate-fegcraft-general-help.py')
class Format(unittest.TestCase):
 def harness(self,model='vector-qwen3:1.7b-q8',fmt='schema',variant='normal'):
  setup=r'''
import io,json,urllib.request
calls=[]
class HTTP:
 def open(self,request,**kwargs):
  data=json.loads(request.data);calls.append(request.full_url)
  if request.full_url.endswith('/api/show'):return io.BytesIO(json.dumps({'template':'<|im_start|>system<|im_end|>','system':''}).encode())
  assert request.full_url=='http://vector-local-inference:11434/api/chat'
  assert kwargs['timeout']==25
  if VARIANT=='timeout':raise TimeoutError('synthetic')
  q=json.loads(data['messages'][-1]['content'])['question']
  answer='Füttere zwei Tiere mit Weizen.'
  if 'Zugriff' in q:answer='Welches Menü der Mod hast du geöffnet?'
  if 'Glas' in q:answer='Schmelze Sand im Ofen.'
  if VARIANT=='unsafe':answer='Nutze /claims.'
  if VARIANT=='false':answer='In Minecraft kann man Schafe nicht vermehren.'
  if VARIANT=='length':answer='a'*201
  assert ('think' in data)==(data['model']=='vector-qwen3:1.7b-q8')
  text=json.dumps({'answer':answer}) if 'format' in data else answer
  return io.BytesIO(json.dumps({'model':data['model'],'done':True,'done_reason':'length' if VARIANT=='truncated' else 'stop','prompt_eval_count':100,'eval_count':10,'load_duration':1000000000,'message':{'content':text}}).encode())
urllib.request.build_opener=lambda *args:HTTP()
'''.replace('VARIANT',repr(variant))
  source=m.harness(model,fmt).replace("sys.path.insert(0,'/code/services/fegcraft-assistant')",'sys.path.insert(0,'+repr(str(ROOT/'services/fegcraft-assistant'))+')')
  result=subprocess.run([sys.executable,'-c',setup+source],capture_output=True,text=True,timeout=10)
  self.assertEqual(result.returncode,0,result.stderr);return json.loads(result.stdout)
 def test_all_four_model_format_combinations_keep_usage_and_fail_activation(self):
  for model in m.MODELS:
   for fmt in ('schema','plain'):
    r=self.harness(model,fmt)
    self.assertEqual(r['model_calls'],4);self.assertEqual(r['input_tokens'],400);self.assertEqual(r['output_tokens'],40)
    self.assertTrue(all(c['factual_fixture_passed'] and c['complete'] and c['display_safe'] for c in r['cases']))
    self.assertFalse(r['passed']);self.assertFalse(r['quality_passed']);self.assertFalse(r['eligible_for_activation'])
    self.assertEqual(r['cloud_calls'],0);self.assertTrue(r['metadata']['template_chatml_start'])
 def test_guards_distinguish_false_unsafe_and_incomplete_content(self):
  for variant in ('false','unsafe','length','truncated'):
   r=self.harness(fmt='plain',variant=variant)
   if variant=='false':self.assertTrue(all(not c['factual_fixture_passed'] for c in r['cases']))
   if variant in ('unsafe','length'):self.assertTrue(all(not c['display_safe'] for c in r['cases']))
   if variant=='truncated':self.assertTrue(all(not c['complete'] for c in r['cases']))
   self.assertEqual(r['output_tokens'],40)
 def test_timeout_is_unknown_not_zero_and_has_no_output(self):
  r=self.harness(variant='timeout');self.assertIsNone(r['input_tokens']);self.assertIsNone(r['output_tokens'])
  self.assertEqual(r['known_input_tokens'],0);self.assertEqual(r['unknown_usage_calls'],4)
  self.assertTrue(all(c['error']=='TimeoutError' and not c['synthetic_answer'] for c in r['cases']))
 def test_manifest_model_identity_and_missing_optional_model(self):
  qwen=next(iter(m.MODELS));self.assertEqual(m.select_models([dict(name=qwen,digest=m.MODELS[qwen])]),[qwen])
  for value in ([],[dict(name=qwen,digest='changed')],[dict(name='unknown',digest='abc')],[dict(name=qwen,digest=m.MODELS[qwen])]*2):
   with self.assertRaises(RuntimeError):m.select_models(value)
  with self.assertRaises(ValueError):m.harness('unknown','plain')
  with self.assertRaises(ValueError):m.harness(qwen,'unbounded')
 def test_native_coordinator_keeps_lock_digest_idle_and_unload_checks(self):
  for model,digest in m.MODELS.items():
   source=m.coordinator(base.COORDINATOR,model)
   self.assertIn(digest,source);self.assertIn('6194261933202610',source)
   self.assertIn('weights-busy',source);self.assertIn('keep_alive:0',source)
   result=subprocess.run(['node','--check','--input-type=module'],input=source,text=True,capture_output=True)
   self.assertEqual(result.returncode,0,result.stderr)
  with self.assertRaises(RuntimeError):m.coordinator('changed',next(iter(m.MODELS)))
 def test_prompt_matches_candidate_except_explicit_output_format(self):
  tree=ast.parse((ROOT/'services/fegcraft-assistant/knowledge.py').read_text())
  self.assertIn(m.PROMPT,[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)])
 def test_compare_releases_each_phase_and_preserves_missing_models(self):
  phases=[];calls=[]
  def command(*args,**kwargs):calls.append((args,kwargs));return b''
  def evaluate():
   fake.command('docker','run')
   phases.append((fake.COORDINATOR,fake.HARNESS))
   model='vector-qwen3:1.7b-q8';fmt='schema' if "'format': 'schema'" in fake.HARNESS else 'plain'
   return dict(model=model,format=fmt,cases=[dict(factual_fixture_passed=True,display_safe=True,complete=True)],production_unchanged=True,cleanup_verified=True,weights_unloaded=True,model_calls=1,input_tokens=2,output_tokens=3,known_input_tokens=2,known_output_tokens=3,unknown_usage_calls=0)
  fake=SimpleNamespace(command=command,COORDINATOR=base.COORDINATOR,HARNESS='',evaluate=evaluate)
  model=next(iter(m.MODELS))
  with tempfile.TemporaryDirectory() as temp,redirect_stdout(io.StringIO()):
   result=m.compare(fake,Path(temp),[dict(name=model,digest=m.MODELS[model])])
  self.assertEqual(len(phases),2);self.assertEqual(result['model_calls'],2)
  self.assertEqual(result['skipped_models'],['vector-hermes3:8b-q4km']);self.assertFalse(result['passed'])
  self.assertEqual(calls[0][1]['timeout'],150);self.assertIs(fake.command,command)
 def test_unverified_cleanup_aborts_remaining_phases(self):
  count=[]
  def evaluate():count.append(1);return dict(production_unchanged=True,cleanup_verified=False,weights_unloaded=False)
  fake=SimpleNamespace(command=lambda *a,**k:None,COORDINATOR=base.COORDINATOR,HARNESS='',evaluate=evaluate)
  model=next(iter(m.MODELS))
  with tempfile.TemporaryDirectory() as temp,redirect_stdout(io.StringIO()):
   with self.assertRaises(RuntimeError):m.compare(fake,Path(temp),[dict(name=model,digest=m.MODELS[model])])
  self.assertEqual(len(count),1)
if __name__=='__main__':unittest.main()
