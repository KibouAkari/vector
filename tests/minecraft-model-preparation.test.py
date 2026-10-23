"""Candidate preparation boundaries without Docker, downloads or inference."""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('model_preparation',ROOT/'scripts/deploy/prepare-minecraft-model-candidate.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
guard_spec=importlib.util.spec_from_file_location('preparation_real_guard',ROOT/'scripts/deploy/update-minecraft-ranking-runtime.py')
real_guard=importlib.util.module_from_spec(guard_spec);guard_spec.loader.exec_module(real_guard)


class Preparation(unittest.TestCase):
    def metadata(self,*,weight=None,family='lfm2',size=731000000):
        model=module.MODEL.lower()
        data={'tags':{'models':[{'name':model,'digest':'a'*64,'size':size}]},
              'show':{'modelfile':'FROM /models/blobs/sha256-'+(weight or module.WEIGHT_SHA256)+'\n',
                      'details':{'family':family,'quantization_level':'Q4_K_M'},
                      'template':'{{ .Prompt }}'}}
        class Opener:
            def open(self,request,**kwargs):
                return io.BytesIO(json.dumps(data[request.full_url.rsplit('/',1)[-1]]).encode())
        with patch('urllib.request.build_opener',return_value=Opener()):
            namespace={};exec(module.METADATA,namespace)
            return namespace['metadata'](module.MODEL,module.WEIGHT_SHA256)

    def test_metadata_verifies_weight_architecture_and_bounded_size_without_generation(self):
        result=self.metadata()
        self.assertTrue(result['weight_digest_matches_source'])
        self.assertEqual(result['model_calls'],0)
        self.assertEqual(result['manifest_digest'],'a'*64)
        self.assertEqual(result['template_sha256'],hashlib.sha256(b'{{ .Prompt }}').hexdigest())
        self.assertTrue(result['template_uses_prompt'])
        self.assertFalse(result['template_uses_messages'])
        for values in ({'weight':'b'*64},{'family':'qwen3'},{'size':1000},{'size':2000000000}):
            with self.subTest(values=values),self.assertRaises(RuntimeError):self.metadata(**values)

    def test_existing_model_tags_cannot_be_removed_overwritten_or_added_unrelated(self):
        before={'registered_models':{'existing':'a'}}
        for roster in ({},{'existing':'b'},{'existing':'a','unrelated':'c'}):
            self.assertFalse(module.registered_models_retained(before,{'registered_models':roster}))
        self.assertTrue(module.registered_models_retained(before,{'registered_models':{'existing':'a',module.MODEL.lower():'b'}}))

    def test_observation_ignores_mount_order_but_detects_resources_and_service_changes(self):
        guard=SimpleNamespace(identity=lambda row:(row['Id'],),canonical=lambda value:json.dumps(value,sort_keys=True).encode(),
            digest=lambda raw:hashlib.sha256(raw).hexdigest())
        row={'Id':'a','State':{'Running':True},'Config':{},'HostConfig':{'NanoCpus':2},'Mounts':[{'b':2},{'a':1}]}
        original=module.observed(guard,{'service':row})
        row['Mounts'].reverse()
        self.assertEqual(module.observed(guard,{'service':row}),original)
        row['NetworkSettings']={'Networks':{'private':{'NetworkID':'changed'}}}
        self.assertNotEqual(module.observed(guard,{'service':row}),original)
        del row['NetworkSettings']
        row['HostConfig']['NanoCpus']=4
        self.assertNotEqual(module.observed(guard,{'service':row}),original)

    def run_preparation(self,exists,*,profile_drift=False,metadata_error=False,pull_timeout=False,verification_error=False,host_download=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'releases').mkdir();baseline=root/'baseline';baseline.mkdir()
            profile=root/'compose';profile.write_bytes(b'profile')
            (baseline/'compose.candidate.json').write_bytes(b'wrong' if profile_drift else b'profile')
            code=root/'code';code.mkdir()
            lock=root/'lock';lock.touch()
            record={'candidate_compose_sha256':hashlib.sha256(b'profile').hexdigest(),
                'candidate_code':str(code),'candidate_files':{},'deployed_identity':['id']}
            (baseline/'record.json').write_text(json.dumps(record))
            guard=SimpleNamespace(checked_path=lambda path,**kwargs:Path(path),
                read_config=lambda path:{'compose':str(profile),'service':'assistant','container':'assistant'},
                digest=lambda raw:hashlib.sha256(raw).hexdigest(),canonical=lambda value:json.dumps(value,sort_keys=True).encode(),
                compose=lambda *args:{},code_source=lambda *args:code,tree_files=lambda path:{},identity=lambda row:(row['Id'],),
                write_private=real_guard.write_private,replace_atomic=real_guard.replace_atomic)
            row={'Id':'id','State':{'Running':True,'Health':{'Status':'healthy'}},'Config':{},'HostConfig':{},'Mounts':[]}
            calls=[]
            def inventory():
                calls.append(1)
                if verification_error and len(calls)>1:raise PermissionError('synthetic verification failure')
                return {'assistant':row,'vector-local-inference':row}
            guard.inventory=inventory
            selected='vector-lfm25:1.2b-q4km-candidate' if host_download else module.MODEL
            importer=SimpleNamespace(SHA256=module.WEIGHT_SHA256,SIZE=module.WEIGHT_BYTES,MODEL=selected)
            imports=[]
            def prepare(*values):
                imports.append(1);values[-1].update(download_attempted=True,import_attempted=True)
            importer.prepare=prepare
            old={'registered_models':{'existing':'a'},'candidate_exists':exists}
            new={'registered_models':{'existing':'a',selected:'b'},'candidate_exists':True,'manifest_digest':'b'}
            args=['prep','--guard-helper',str(root/'guard.py'),'--baseline',str(baseline),
                '--workspace-root',str(root),'--lock-file',str(lock),'--download']
            if host_download:args+=['--host-download','--import-helper',str(root/'import.py')];(root/'import.py').write_bytes(b'# synthetic')
            fake_spec=SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module:None))
            with patch.object(sys,'argv',args),patch.object(module.importlib.util,'spec_from_file_location',return_value=fake_spec), \
                    patch.object(module.importlib.util,'module_from_spec',side_effect=[guard,importer] if host_download else [guard]), \
                    patch.object(module,'inspect_metadata',side_effect=[RuntimeError('CANDIDATE_METADATA_CHECK_FAILED') if metadata_error else new if exists else old,new]) as metadata, \
                    patch.object(module.subprocess,'run',side_effect=module.subprocess.TimeoutExpired('synthetic-pull',300) if pull_timeout else None,return_value=SimpleNamespace(returncode=0)) as command, \
                    redirect_stdout(io.StringIO()):
                if profile_drift:
                    with self.assertRaisesRegex(RuntimeError,'CONFIRMED_BASELINE_PROFILE_CHANGED'):module.main()
                    self.assertEqual(metadata.call_count,0);command.assert_not_called()
                    return None
                if metadata_error or pull_timeout or verification_error:
                    with self.assertRaises(SystemExit):module.main()
                    result=json.loads(next((root/'releases').glob('*/result.json')).read_text())
                    self.assertFalse(result['prepared'])
                    self.assertEqual(command.call_count,0 if metadata_error else 1)
                    return result
                module.main()
                result=json.loads(next((root/'releases').glob('*/result.json')).read_text())
                self.assertEqual(command.call_count,0 if exists or host_download else 1)
                self.assertEqual(len(imports),int(host_download and not exists))
                if not exists and not host_download:self.assertEqual(command.call_args.args[0],['docker','exec','vector-local-inference','ollama','pull',module.MODEL])
                return result

    def test_only_explicit_candidate_is_downloaded_without_activation_or_native_claim(self):
        result=self.run_preparation(False)
        self.assertTrue(result['prepared'])
        self.assertTrue(result['download_attempted'])
        self.assertTrue(result['service_configuration_and_identities_unchanged'])
        self.assertFalse(result['production_activated'])
        self.assertFalse(result['native_execution_tested'])
        self.assertFalse(result['eligible_for_activation'])
        self.assertEqual(result['model_calls'],0)

    def test_existing_valid_candidate_is_reused_and_profile_drift_stops_before_download(self):
        result=self.run_preparation(True)
        self.assertTrue(result['prepared'])
        self.assertFalse(result['download_attempted'])
        self.run_preparation(False,profile_drift=True)

    def test_host_mode_imports_only_distinct_candidate_and_never_invokes_registry_pull(self):
        result=self.run_preparation(False,host_download=True)
        self.assertTrue(result['prepared'])
        self.assertTrue(result['import_attempted'])
        self.assertEqual(result['model'],'vector-lfm25:1.2b-q4km-candidate')
        self.assertEqual(result['download_route'],'host-verified-internal-import')
        self.assertTrue(result['model_cache_may_have_changed'])
        self.assertEqual(result['model_calls'],0)

    def test_download_requires_explicit_flag(self):
        args=['prep','--guard-helper','unused','--baseline','unused','--workspace-root','unused','--lock-file','unused']
        with patch.object(sys,'argv',args),redirect_stdout(io.StringIO()),self.assertRaises(SystemExit):module.main()

    def test_rejected_metadata_cannot_trigger_pull_and_download_timeout_remains_uncertain(self):
        rejected=self.run_preparation(True,metadata_error=True)
        self.assertFalse(rejected['download_attempted'])
        timed_out=self.run_preparation(False,pull_timeout=True)
        self.assertTrue(timed_out['download_completion_unknown'])
        self.assertTrue(timed_out['model_cache_may_have_changed'])
        self.assertFalse(timed_out['prepared'])

    def test_verification_outage_preserves_download_timeout_evidence_and_never_reports_success(self):
        result=self.run_preparation(False,pull_timeout=True,verification_error=True)
        self.assertEqual(result['error'],'CANDIDATE_DOWNLOAD_TIMEOUT')
        self.assertEqual(result['verification_error'],'PermissionError')
        self.assertIsNone(result['service_configuration_and_identities_unchanged'])
        self.assertTrue(result['download_completion_unknown'])
        self.assertTrue(result['download_attempted'])
        self.assertFalse(result['prepared'])


if __name__=='__main__':unittest.main()

