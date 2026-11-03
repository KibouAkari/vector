"""Pinned Qwen preparation boundaries; no Docker, model transfer or inference."""
import copy
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
m=load('q35','scripts/deploy/prepare-qwen35-cpu.py')
g=load('q35_guard','scripts/deploy/update-minecraft-ranking-runtime.py')

class Response(io.BytesIO):
    def __init__(self,body):super().__init__(body);self.headers={'Content-Length':str(len(body))}

class Preparation(unittest.TestCase):
    def test_memory_swap_plan_preserves_swap_allowance_and_cpu_configuration(self):
        self.assertEqual(m.swap_target({'Memory':12,'MemorySwap':18}),m.TARGET+6)
        self.assertEqual(m.swap_target({'Memory':12,'MemorySwap':12}),m.TARGET)
        self.assertEqual(m.swap_target({'Memory':12,'MemorySwap':0}),m.TARGET+12)
        self.assertEqual(m.swap_target({'Memory':12,'MemorySwap':-1}),-1)
        with self.assertRaises(RuntimeError):m.swap_target({'Memory':12,'MemorySwap':6})

    def test_metadata_requires_both_weights_native_renderer_and_vision(self):
        value={'candidate_exists':True,'details':{'family':'qwen35','quantization_level':'Q4_K_M'},
            'weight_digests':[m.WEIGHT,m.PROJECTOR],'template_sha256':m.TEMPLATE,
            'renderer':'qwen3.5','parser':'qwen3.5','capabilities':['completion','vision','tools','thinking']}
        m.verify_model(value)
        for changes in ({'weight_digests':[m.WEIGHT]},{'renderer':None},{'template_sha256':'a'*64},
                        {'capabilities':['completion']},{'details':{'family':'qwen3','quantization_level':'Q4_K_M'}}):
            with self.subTest(changes=changes),self.assertRaises(RuntimeError):m.verify_model({**value,**changes})

    def test_embedded_metadata_reads_two_from_layers_and_native_renderer_without_generation(self):
        value={'version':{'version':'0.40.4'},
            'tags':{'models':[{'name':m.MODEL,'digest':'a'*64}]},
            'show':{'template':'{{ .Prompt }}','modelfile':'FROM /models/sha256-'+m.WEIGHT+'\nFROM /models/sha256-'+m.PROJECTOR+'\nRENDERER qwen3.5\nPARSER qwen3.5\n',
                    'details':{'family':'qwen35','quantization_level':'Q4_K_M'},
                    'capabilities':['completion','vision','tools','thinking']}}
        routes=[]
        def open_request(req,**kwargs):
            route=req.full_url.rsplit('/',1)[-1];routes.append(route)
            return io.BytesIO(json.dumps(value[route]).encode())
        output=io.StringIO()
        with patch('urllib.request.build_opener',return_value=SimpleNamespace(open=open_request)), \
                patch.object(sys,'argv',['metadata',m.MODEL]),patch('pathlib.Path.read_bytes',return_value=b'synthetic'),redirect_stdout(output):
            exec(m.METADATA,{})
        result=json.loads(output.getvalue());m.verify_model(result)
        self.assertEqual(routes,['version','tags','show'])

    def test_public_delivery_redirects_are_limited_to_verified_registry_delivery(self):
        for url in ('https://registry.ollama.ai/a','https://cdn.ollama.com/a',
                    'https://synthetic.r2.cloudflarestorage.com/file?signature=public'):
            self.assertTrue(m.allowed_url(url))
        for url in ('http://registry.ollama.ai/a','https://localhost/a','https://evil.com/a',
                    'https://user:pass@registry.ollama.ai/a','https://registry.ollama.ai:444/a'):
            self.assertFalse(m.allowed_url(url))
        with self.assertRaises(RuntimeError):m.Redirect().redirect_request(None,None,302,'',{},'http://localhost/')

    def test_cache_checks_digest_reuses_owned_file_and_never_overwrites_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'local-inference').mkdir()
            body=b'synthetic';sha=hashlib.sha256(body).hexdigest();d={'digest':'sha256:'+sha,'size':len(body)}
            status={}
            with patch.object(m,'open_public',return_value=Response(body)) as fetch:
                path=m.cached(root,d,g,status)
                self.assertEqual(path.read_bytes(),body)
                m.cached(root,d,g,{})
                self.assertEqual(fetch.call_count,1)
            path.write_bytes(b'corrupted')
            with self.assertRaises(RuntimeError):m.cached(root,d,g,{})
            self.assertEqual(path.read_bytes(),b'corrupted')
            self.assertEqual(list(path.parent.glob('.qwen35-part-*')),[])

    def test_corrupt_download_is_not_installed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'local-inference').mkdir()
            d={'digest':'sha256:'+hashlib.sha256(b'good').hexdigest(),'size':4}
            with patch.object(m,'open_public',return_value=Response(b'evil')),self.assertRaises(RuntimeError):
                m.cached(root,d,g,{})
            self.assertEqual(list((root/'local-inference/model-candidates').iterdir()),[])

    def test_registry_never_removes_or_changes_existing_tags(self):
        old={'old':'a'}
        self.assertTrue(m.registry_retained(old,{'old':'a',m.MODEL:'b'}))
        for new in ({},{'old':'b'},{'old':'a','unrelated':'b'}):self.assertFalse(m.registry_retained(old,new))

    def execute(self,*,drift=False,update_failure=False,other_change=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'releases').mkdir();(root/'local-inference').mkdir()
            lock=root/'lock';lock.touch()
            source_hashes={n:'a'*64 for n in ('runtime.py','knowledge.py','server.py','dialogue.py')}
            op={'assistant':'assistant','inference':'vector-local-inference','protected':['game','app'],'source_hashes':source_hashes}
            operator=root/'operator.json';operator.write_text(json.dumps(op));operator.chmod(0o600)
            rows={}
            for name in ('assistant','vector-local-inference','game','app'):
                rows[name]={'Id':name+'-id','Image':'synthetic-image','State':{'StartedAt':'synthetic-start','Running':True,'Health':{'Status':'healthy'}},
                    'Config':{},'HostConfig':{'Memory':12*1073741824,'MemorySwap':24*1073741824,'NanoCpus':2000000000},
                    'Mounts':[{'Destination':'/code','RW':False}],'NetworkSettings':{'Networks':{'private':{}}}}
            count=0
            def inventory():
                nonlocal count
                count+=1
                value=copy.deepcopy(rows)
                if other_change and count>=3:value['game']['HostConfig']['NanoCpus']=999
                return value
            guard=SimpleNamespace(**{k:getattr(g,k) for k in ('checked_path','canonical','digest','identity','write_private','replace_atomic','sync_directory')},
                inventory=inventory)
            imported=False;commands=[];uploads=[]
            def metadata(container):
                value={'runtime_version':'0.40.4','sources':source_hashes if not drift else {},'registry':{'old':'a'},'candidate_exists':imported}
                if imported:value.update(registry={'old':'a',m.MODEL:'b'},manifest_digest='b'*64,
                    details={'family':'qwen35','quantization_level':'Q4_K_M'},
                    weight_digests=[m.WEIGHT,m.PROJECTOR],template_sha256=m.TEMPLATE,renderer='qwen3.5',parser='qwen3.5',
                    capabilities=['completion','vision','tools','thinking'])
                return value
            def internal(container,payload,*args):
                nonlocal imported
                self.assertEqual(payload['operation'],'create')
                body=payload['body'];self.assertEqual(body['files'],{'model.gguf':'sha256:'+m.WEIGHT,'mmproj.gguf':'sha256:'+m.PROJECTOR})
                self.assertEqual(body['renderer'],'qwen3.5');self.assertEqual(body['parameters']['num_ctx'],8192)
                self.assertEqual(body['parameters']['num_thread'],2)
                imported=True;return {'created':True}
            def command(args,**kwargs):
                commands.append(args);self.assertEqual(args[:2],['docker','update'])
                self.assertEqual(args[-1],'vector-local-inference-id')
                rows['vector-local-inference']['HostConfig'].update(Memory=m.TARGET,MemorySwap=36*1073741824)
                return SimpleNamespace(returncode=int(update_failure),stdout=b'',stderr=b'')
            transport=SimpleNamespace(internal=internal)
            suffix='application/vnd.ollama.image.'
            plan={'config':{'mediaType':'config'},'layers':[
                {'mediaType':suffix+'model','digest':'sha256:'+m.WEIGHT,'from':'model.gguf'},
                {'mediaType':suffix+'projector','digest':'sha256:'+m.PROJECTOR,'from':'mmproj.gguf'},
                *[{'mediaType':suffix+k,'digest':'sha256:'+'a'*64} for k in ('params','template','license')]]}
            def cached(root,descriptor,*args):
                path=root/(descriptor['mediaType'].replace('/','-')+'.fixture')
                values={'config':json.dumps({'model_family':'qwen35','file_type':'Q4_K_M','renderer':'qwen3.5','parser':'qwen3.5','requires':'0.30.0'}),
                    suffix+'params':'{}',suffix+'template':'{{ .Prompt }}',suffix+'license':'synthetic license'}
                path.write_text(values.get(descriptor['mediaType'],'synthetic weight'));return path
            argv=['prepare','--guard-helper',str(root/'guard.py'),'--transfer-helper',str(root/'transfer.py'),
                '--operator',str(operator),'--workspace-root',str(root),'--lock-file',str(lock),'--memory-gib','24','--download']
            spec=SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module:None))
            with patch.object(sys,'argv',argv),patch.object(m.importlib.util,'spec_from_file_location',return_value=spec), \
                    patch.object(m.importlib.util,'module_from_spec',return_value=guard),patch.object(m,'load_helper',return_value=transport), \
                    patch.object(m,'metadata',side_effect=metadata),patch.object(m,'public_plan',return_value=plan) as fetch, \
                    patch.object(m,'cached',side_effect=cached),patch.object(m,'upload',side_effect=lambda *args:uploads.append(args[1]['digest'])), \
                    patch.object(m.subprocess,'run',side_effect=command),patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1073741824)),redirect_stdout(io.StringIO()):
                if drift:
                    with self.assertRaisesRegex(RuntimeError,'OBSERVED_ASSISTANT_SOURCE_CHANGED'):m.main()
                    self.assertEqual(commands,[]);fetch.assert_not_called();return
                if update_failure or other_change:
                    with self.assertRaises(SystemExit):m.main()
                else:m.main()
            result=json.loads(next((root/'releases').glob('*/result.json')).read_text())
            self.assertEqual(len(commands),1)
            self.assertEqual(result['model_calls'],0);self.assertFalse(result['production_activated'])
            self.assertFalse(result['native_execution_tested']);self.assertFalse(result['eligible_for_activation'])
            self.assertEqual(rows['game']['HostConfig']['Memory'],12*1073741824)
            self.assertEqual(rows['vector-local-inference']['HostConfig']['NanoCpus'],2000000000)
            return result,uploads

    def test_full_preparation_changes_only_memory_and_registers_both_blobs(self):
        result,uploads=self.execute()
        self.assertTrue(result['prepared']);self.assertTrue(result['all_other_services_unchanged'])
        self.assertEqual(result['actual_memory_limit_bytes'],m.TARGET)
        self.assertEqual(set(uploads),{'sha256:'+m.WEIGHT,'sha256:'+m.PROJECTOR})
        self.execute(drift=True)

    def test_partial_resource_command_failure_is_reported_as_actual_ram_change(self):
        result,uploads=self.execute(update_failure=True)
        self.assertFalse(result['prepared']);self.assertTrue(result['memory_limit_updated'])
        self.assertEqual(result['error'],'AUTHORIZED_MEMORY_UPDATE_FAILED')
        self.assertEqual(uploads,[])

    def test_unowned_other_service_change_cannot_pass(self):
        result,uploads=self.execute(other_change=True)
        self.assertFalse(result['prepared']);self.assertFalse(result['all_other_services_unchanged'])

if __name__=='__main__':unittest.main()
