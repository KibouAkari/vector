"""Pinned candidate import boundaries and full-adapter substitution, no downloads."""
from contextlib import redirect_stdout,nullcontext
import importlib.util,io,json,os,subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
m=load('candidate4b','scripts/deploy/evaluate-fegcraft-instruct4b.py')
base=load('candidate4b_base','scripts/deploy/evaluate-fegcraft-general-help.py')

class Candidate(unittest.TestCase):
 def test_candidate_is_distinct_pinned_non_thinking_release(self):
  self.assertEqual(m.CANDIDATE['size'],2497281120)
  self.assertEqual(m.CANDIDATE['sha256'],'3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597')
  self.assertEqual(m.CANDIDATE['revision'],'a06e946bb6b655725eafa393f4a9745d460374c9')
  self.assertNotEqual(m.CANDIDATE['name'],m.BASELINE)
  self.assertNotIn('TEMPLATE',m.MODEL_TEXT);self.assertNotIn('SYSTEM',m.MODEL_TEXT)
 def test_full_gate_is_not_replaced_with_a_minimal_or_keyword_winner(self):
  coordinator,harness=m.candidate_sources(base,'a'*64)
  self.assertIn(m.CANDIDATE['name'],coordinator);self.assertIn('a'*64,coordinator)
  self.assertIn('6194261933202610',coordinator);self.assertIn('weights-busy',coordinator)
  self.assertIn('300000',coordinator);self.assertIn('keep_alive:0',coordinator)
  self.assertIn("('glass','Wie bekomme ich Glas in Minecraft?'",harness)
  self.assertIn("('commands'",harness);self.assertIn("('party-followup'",harness)
  self.assertIn("model='vector-qwen3-instruct2507:4b-q4km'",harness)
  self.assertEqual(base.HARNESS.count("'model':'vector-qwen3:1.7b-q8'"),1)
  for source in (coordinator,m.IMPORT_SLOT):
   result=subprocess.run(['node','--check','--input-type=module'],input=source,text=True,capture_output=True)
   self.assertEqual(result.returncode,0,result.stderr)
  with self.assertRaises(RuntimeError):m.candidate_sources(base,'changed')
  with self.assertRaises(RuntimeError):m.candidate_sources(SimpleNamespace(COORDINATOR='changed'), 'a'*64)
 def test_full_candidate_adapter_runs_all_factual_routing_and_safety_cases(self):
  evaluation=load('candidate4b_fixture_suite','tests/fegcraft-general-evaluation.test.py')
  _,evaluation.m.HARNESS=m.candidate_sources(base,'a'*64)
  result=evaluation.Evaluation().run_harness()
  self.assertTrue(result['quality_passed'],result['cases']);self.assertEqual(result['model_calls'],11)
  self.assertEqual(len(result['cases']),20);self.assertEqual(result['model'],m.CANDIDATE['name'])
  self.assertFalse(result['eligible_for_activation']);self.assertFalse(result['production_activated'])
 def test_adapter_omits_unsupported_thinking_but_keeps_destination_and_guards(self):
  import sys
  sys.path.insert(0,str(ROOT/'services/fegcraft-assistant'))
  import knowledge
  requests=[]
  class Opener:
   def open(self,req,**kwargs):
    value=json.loads(req.data);requests.append(value)
    self_check=req.full_url=='http://vector-local-inference:11434/api/chat'
    assert self_check
    return io.BytesIO(json.dumps(dict(model=value['model'],done=True,done_reason='stop',prompt_eval_count=10,eval_count=4,message=dict(content='{"answer":"Füttere zwei Kühe mit Weizen."}'))).encode())
  with patch.object(knowledge,'local_slot',return_value=nullcontext()),patch.object(knowledge.urllib.request,'build_opener',return_value=Opener()):
   candidate=knowledge.GeneralKnowledge('synthetic',model=m.CANDIDATE['name'])
   self.assertIn('Weizen',candidate.answer_scoped('Wie züchte ich Kühe in Minecraft?',[],('minecraft','one')))
   self.assertNotIn('think',requests[-1]);self.assertEqual(requests[-1]['options']['num_thread'],2)
   before=len(requests)
   with self.assertRaisesRegex(ValueError,'FORBIDDEN'):candidate.answer_scoped('Zeige den seed',[],('minecraft','one'))
   self.assertEqual(len(requests),before)
   default=knowledge.GeneralKnowledge('synthetic');self.assertEqual(default.model,m.BASELINE)
   default.answer_scoped('Wie züchte ich Kühe in Minecraft?',[],('minecraft','one'));self.assertIs(requests[-1]['think'],False)
   with self.assertRaisesRegex(ValueError,'UNQUALIFIED'):knowledge.GeneralKnowledge('synthetic',model='arbitrary-model')
 def test_exclusive_evidence_preserves_existing_and_rejects_symlinks(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/'marker';m.exclusive(p,b'original');m.exclusive(p,b'original')
   with self.assertRaises(RuntimeError):m.exclusive(p,b'changed')
   self.assertEqual(p.read_bytes(),b'original')
   link=Path(temp)/'link';link.symlink_to(p)
   with self.assertRaises(RuntimeError):m.exclusive(link,b'original')
 def test_weight_size_symlink_and_checksum_boundaries(self):
  with tempfile.TemporaryDirectory() as temp,patch.dict(m.CANDIDATE,size=3):
   p=Path(temp)/'weights';p.write_bytes(b'abc');p.chmod(0o600);calls=[]
   def runner(*args,**kwargs):calls.append((args,kwargs));return (m.CANDIDATE['sha256']+'  weights\n').encode()
   self.assertTrue(m.verified(p,runner));self.assertEqual(calls[-1][1]['timeout'],110)
   self.assertIn('90s',calls[-1][0]);self.assertIn('--kill-after=5s',calls[-1][0])
   p.chmod(0o666);self.assertFalse(m.verified(p,runner));p.chmod(0o600)
   link=Path(temp)/'link';link.symlink_to(p);self.assertFalse(m.verified(link,runner))
   self.assertFalse(m.verified(p,lambda *a,**k:b'wrong  weights'))
 def test_manifest_drift_and_orphan_import_are_not_overwritten(self):
  with self.assertRaises(RuntimeError):m.manifest(lambda *a:dict(models=[]))
  rows=[dict(name=m.BASELINE,digest=m.BASE_DIGEST)]
  self.assertEqual(m.manifest(lambda *a:dict(models=rows)),{m.BASELINE:m.BASE_DIGEST})
  with self.assertRaises(RuntimeError):m.manifest(lambda *a:dict(models=rows*2))
  with tempfile.TemporaryDirectory() as temp,patch.object(m,'MARKER',Path(temp)/'marker'):
   def no_command(*a,**k):raise AssertionError('No import/overwrite allowed')
   with self.assertRaisesRegex(RuntimeError,'without verified'):
    m.register(None,{m.BASELINE:m.BASE_DIGEST,m.CANDIDATE['name']:'a'*64},Path(temp),no_command)
 def test_verified_candidate_reuse_preserves_all_other_models_and_checks_actual_blob(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(m,'MARKER',Path(temp)/'marker'):
   before={m.BASELINE:m.BASE_DIGEST,m.CANDIDATE['name']:'a'*64};calls=[]
   m.exclusive(m.MARKER,(json.dumps(dict(artifact=m.CANDIDATE,model_digest='a'*64),sort_keys=True)+'\n').encode())
   def api(path,payload=None):
    if path=='/api/tags':return dict(models=[dict(name=k,digest=v) for k,v in before.items()])
    return dict(system='',template='synthetic public template',modelfile='FROM /root/.ollama/models/blobs/sha256-'+m.CANDIDATE['sha256']+'\n',model_info={'general.architecture':'qwen3','qwen3.block_count':36})
   def runner(*args,**kwargs):
    calls.append(args)
    if 'stat' in args:return str(m.CANDIDATE['size']).encode()
    if 'sha256sum' in args:return (m.CANDIDATE['sha256']+'  blob').encode()
    return b''
   r=m.register(api,before,Path(temp),runner)
   self.assertTrue(r['existing_models_unchanged']);self.assertEqual(r['model_digest'],'a'*64)
   self.assertEqual(len(calls),4);self.assertFalse(any('create' in a for a in calls))
 def test_new_import_only_creates_candidate_and_writes_verified_marker(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(m,'MARKER',Path(temp)/'marker'),patch.object(m,'MODELFILE',Path(temp)/'candidate.Modelfile'):
   before={m.BASELINE:m.BASE_DIGEST};calls=[]
   def api(path,payload=None):
    if path=='/api/tags':return dict(models=[dict(name=m.BASELINE,digest=m.BASE_DIGEST),dict(name=m.CANDIDATE['name'],digest='a'*64)])
    return dict(system='',template='synthetic public template',modelfile='FROM /root/.ollama/models/blobs/sha256-'+m.CANDIDATE['sha256']+'\n',model_info={'general.architecture':'qwen3','qwen3.block_count':36})
   def runner(*args,**kwargs):
    calls.append((args,kwargs))
    if 'stat' in args:return str(m.CANDIDATE['size']).encode()
    if 'sha256sum' in args:return (m.CANDIDATE['sha256']+'  blob').encode()
    return b''
   with redirect_stdout(io.StringIO()):result=m.register(api,before,Path(temp),runner)
   self.assertEqual(calls[0][0][:6],('docker','exec',m.SERVICE,'ollama','create',m.CANDIDATE['name']))
   self.assertEqual(calls[0][1]['timeout'],180)
   self.assertEqual(json.loads(m.MARKER.read_bytes())['model_digest'],result['model_digest'])
   self.assertEqual(m.MODELFILE.read_text(),m.MODEL_TEXT)
   self.assertFalse(any('rm' in args or 'pull' in args or 'run' in args for args,_ in calls))
 def test_download_pins_https_and_publishes_without_overwrite(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(m,'IMPORTS',Path(temp)):
   commands=[]
   def curl(args,**kwargs):
    commands.append((args,kwargs));Path(args[args.index('--output')+1]).write_bytes(b'abc')
   with patch.object(m.subprocess,'run',side_effect=curl),patch.object(m,'verified',side_effect=lambda p:p.read_bytes()==b'abc'),redirect_stdout(io.StringIO()):
    result=m.artifact(Path(temp))
   self.assertEqual(result.read_bytes(),b'abc');args,kwargs=commands[0]
   self.assertEqual(args[:2],['curl','--disable']);self.assertIn(m.CANDIDATE['revision'],args[-1])
   self.assertTrue(args[-1].startswith('https://huggingface.co/'));self.assertEqual(kwargs['timeout'],920)
   self.assertIn('--max-filesize',args);self.assertIn('--proto-redir',args)
   self.assertFalse(list(Path(temp).glob('*.partial')))
 def test_failed_download_keeps_partial_and_does_not_publish_or_delete(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(m,'IMPORTS',Path(temp)):
   def curl(args,**kwargs):
    Path(args[args.index('--output')+1]).write_bytes(b'partial')
    raise subprocess.CalledProcessError(1,args)
   with patch.object(m.subprocess,'run',side_effect=curl),redirect_stdout(io.StringIO()):
    with self.assertRaises(subprocess.CalledProcessError):m.artifact(Path(temp))
   self.assertFalse((Path(temp)/m.CANDIDATE['file']).exists())
   self.assertEqual(len(list(Path(temp).glob('*.partial'))),1)

if __name__=='__main__':unittest.main()
