"""Read-only, fixed-scope artifact verification with no model generation."""
import importlib.util,json,re,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('artifact_audit',ROOT/'scripts/diagnostics/audit-local-model-artifacts.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Audit(unittest.TestCase):
 def test_hashes_exact_registered_blobs_and_internal_timeout(self):
  for model,expected in m.MODELS.items():
   calls=[]
   def command(*args,**kwargs):
    calls.append((args,kwargs))
    if 'stat' in args:return str(expected['size'])+'\n'
    if 'sha256sum' in args:return expected['blob']+'  '+args[-1]+'\n'
    return ''
   result=m.verify_blob(model,dict(registration_matches=True,registered_blob=expected['blob']),command)
   self.assertTrue(result['verified']);self.assertEqual(len(calls),4)
   self.assertEqual(calls[-1][0][:8],('docker','exec',m.SERVICE,'timeout','--signal=TERM','--kill-after=5s','90s','sha256sum'))
   self.assertEqual(calls[-1][1]['timeout'],110)
   self.assertTrue(all(call[0][-1]=='/root/.ollama/models/blobs/sha256-'+expected['blob'] for call in calls))
 def test_identity_size_and_checksum_drift_fail_without_repair(self):
  model,expected=next(iter(m.MODELS.items()));calls=[]
  def wrong_size(*args,**kwargs):calls.append(args);return '1\n' if 'stat' in args else ''
  self.assertFalse(m.verify_blob(model,dict(registration_matches=False),wrong_size)['verified']);self.assertEqual(calls,[])
  self.assertFalse(m.verify_blob(model,dict(registration_matches=True,registered_blob='a'*64),wrong_size)['verified']);self.assertEqual(calls,[])
  self.assertFalse(m.verify_blob(model,dict(registration_matches=True,registered_blob=expected['blob']),wrong_size)['verified'])
  self.assertFalse(any('sha256sum' in call for call in calls))
  def wrong_hash(*args,**kwargs):return str(expected['size']) if 'stat' in args else 'a'*64+'  '+args[-1]+'\n' if 'sha256sum' in args else ''
  self.assertFalse(m.verify_blob(model,dict(registration_matches=True,registered_blob=expected['blob']),wrong_hash)['verified'])
 def test_native_metadata_is_bounded_and_does_not_return_system_text(self):
  prefix=r'''
const blobs=__MODELS__;
globalThis.fetch=async(url,options)=>{
 if(url.endsWith('/api/version'))return new Response(JSON.stringify({version:'0.40.4'}));
 if(url.endsWith('/api/tags'))return new Response(JSON.stringify({models:Object.entries(blobs).map(([name,m])=>({name,digest:m.digest}))}));
 if(!url.endsWith('/api/show'))throw Error('unexpected endpoint');
 const model=JSON.parse(options.body).model;
 return new Response(JSON.stringify({template:'unexpected private template',system:'synthetic private system',modelfile:'FROM /root/.ollama/models/blobs/sha256-'+blobs[model].blob,
  parameters:'num_ctx 2048\nowner_secret hidden',model_info:{'general.architecture':'test','private.parameter':'hidden','tokenizer.ggml.tokens':['hidden']}}));
};
'''.replace('__MODELS__',json.dumps(m.MODELS))
  source=prefix+m.METADATA_JS.replace('__MODELS__',json.dumps(m.MODELS))
  result=subprocess.run(['node','--input-type=module'],input=source,text=True,capture_output=True,timeout=10)
  self.assertEqual(result.returncode,0,result.stderr);self.assertNotIn('synthetic private system',result.stdout);self.assertNotIn('unexpected private template',result.stdout)
  self.assertNotIn('hidden',result.stdout);report=json.loads(result.stdout)
  self.assertTrue(all(row['template_withheld'] and row['public_template'] is None for row in report['models']))
  self.assertTrue(all(row['parameters']==['num_ctx 2048'] for row in report['models']))
 def test_no_inference_or_service_mutation_and_production_drift_is_reported(self):
  models=[dict(model=name,registration_matches=True,registered_blob=value['blob']) for name,value in m.MODELS.items()]
  calls=[];states=[{'/'+m.SERVICE:{'image':'synthetic'}},{'/'+m.SERVICE:{'image':'changed'}}]
  def command(*args,**kwargs):
   calls.append(args)
   if 'node' in args:return json.dumps(dict(runtime_version='0.40.4',models=models))
   expected=next(v for v in m.MODELS.values() if args[-1].endswith(v['blob']))
   if 'stat' in args:return str(expected['size'])
   if 'sha256sum' in args:return expected['blob']+'  '+args[-1]+'\n'
   return ''
  report=m.audit(command,lambda:states.pop(0),lambda *a,**k:None)
  self.assertTrue(report['integrity_verified']);self.assertFalse(report['passed']);self.assertFalse(report['production_unchanged'])
  self.assertEqual(report['model_calls'],0);self.assertFalse(report['quality_passed']);self.assertFalse(report['eligible_for_activation'])
  self.assertFalse(any(x in args for args in calls for x in ('start','stop','restart','create','rm','pull','build')))
  self.assertNotIn('/api/chat',m.METADATA_JS);self.assertNotIn('/api/generate',m.METADATA_JS)
 def test_read_failure_is_not_reported_as_verified(self):
  models=[dict(model=name,registration_matches=True,registered_blob=value['blob']) for name,value in m.MODELS.items()]
  def command(*args,**kwargs):
   if 'node' in args:return json.dumps(dict(runtime_version='0.40.4',models=models))
   raise subprocess.TimeoutExpired(args,110)
  state={'/'+m.SERVICE:{'image':'synthetic'}}
  report=m.audit(command,lambda:state,lambda *a,**k:None)
  self.assertFalse(report['integrity_verified']);self.assertTrue(all(r['weight_integrity']['reason']=='WEIGHT_READ_NOT_VERIFIED' for r in report['models']))
if __name__=='__main__':unittest.main()
