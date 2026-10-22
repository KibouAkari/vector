"""Profile bounds and interrupted opt-in recovery; no Docker or real services."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

release=load('scripts/deploy/release-minecraft-dialogue.py','release_check')
transport=load('scripts/deploy/qualify-minecraft-dialogue-transport.py','transport_check')
guard=load('scripts/deploy/update-minecraft-ranking-runtime.py','guard_check')


class Release(unittest.TestCase):
    def test_only_code_and_bound_mode_timezone_change_in_the_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);old=root/'old';new=root/'new';old.mkdir();new.mkdir()
            source=(ROOT/'services/minecraft-assistant/server.py').read_text()
            source=source.replace('VECTOR_MINECRAFT_','VECTOR_OPERATOR_')
            (new/'server.py').write_text(source)
            profile={'services':{'assistant':{'image':'synthetic','user':'1000:1000',
                'environment':{'VECTOR_OPERATOR_KNOWLEDGE':'5','EXISTING':'keep'},
                'volumes':[{'type':'bind','source':str(old),'target':'/code','read_only':True}],
                'read_only':True,'cap_drop':['ALL']}}}
            original=copy.deepcopy(profile)
            projected=release.profile_for_dialogue(guard,transport,profile,'assistant',new,'Europe/Zurich')
            self.assertEqual(profile,original)
            self.assertEqual(projected['services']['assistant']['environment'],
                {'VECTOR_OPERATOR_KNOWLEDGE':'6','VECTOR_OPERATOR_TIMEZONE':'Europe/Zurich','EXISTING':'keep'})
            projected['services']['assistant']['environment']=original['services']['assistant']['environment']
            projected['services']['assistant']['volumes']=original['services']['assistant']['volumes']
            self.assertEqual(projected,original)
            for mode in ('0','3','6'):
                profile['services']['assistant']['environment']['VECTOR_OPERATOR_KNOWLEDGE']=mode
                with self.assertRaisesRegex(RuntimeError,'CONFIRMED_REVIEWED_MODE_REQUIRED'):
                    release.profile_for_dialogue(guard,transport,profile,'assistant',new,'Europe/Zurich')

    def test_mode6_refresh_requires_explicit_mode_and_preserves_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);code=root/'code';code.mkdir()
            (code/'server.py').write_text((ROOT/'services/minecraft-assistant/server.py').read_text())
            profile={'services':{'assistant':{'environment':{'VECTOR_MINECRAFT_KNOWLEDGE':'6',
                'VECTOR_MINECRAFT_TIMEZONE':'Europe/Zurich'},'volumes':[{'type':'bind','source':str(code),
                'target':'/code','read_only':True}]}}}
            result=release.profile_for_dialogue(guard,transport,profile,'assistant',code,'Europe/Zurich',expected_mode='6')
            self.assertEqual(result,profile)
            with self.assertRaises(RuntimeError):
                release.profile_for_dialogue(guard,transport,profile,'assistant',code,'Europe/Zurich')

    def test_previous_release_requires_success_original_capsule_and_unmodified_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);code=root/'code';code.mkdir();(code/'runtime.py').write_text('pass\n')
            raw=b'{}';record={'candidate_code':str(code),'candidate_files':guard.tree_files(code),
                'candidate_compose_sha256':guard.digest(raw),'deployed_identity':['id','image','start'],
                'transport_capsule':str(root/'capsule'),'transport_manifest_sha256':'a'*64}
            result={'deployed':True,'only_assistant_recreated':True,'other_services_unchanged':True,
                'native_model_contract_retained':True,'game_restart':False,'knowledge_mode':'grounded-conversation',
                'model_calls':0,'cloud_calls':0,'messages_sent':0,'release':str(root)}
            for name,data in (('record.json',record),('result.json',result)):
                (root/name).write_bytes(guard.canonical(data));(root/name).chmod(0o600)
            (root/'compose.candidate.json').write_bytes(raw);(root/'compose.candidate.json').chmod(0o600)
            with patch.object(guard,'read_config',return_value={'pinned':True}):
                self.assertEqual(release.previous_release(guard,transport,root,root/'capsule','a'*64)[0],{'pinned':True})
                with self.assertRaisesRegex(RuntimeError,'CAPSULE_MISMATCH'):
                    release.previous_release(guard,transport,root,root/'capsule','b'*64)
                for field,value in (('deployed',False),('game_restart',True),('model_calls',1)):
                    (root/'result.json').write_bytes(guard.canonical(dict(result,**{field:value})))
                    with self.assertRaisesRegex(RuntimeError,'SUCCESSFUL_DIALOGUE_RELEASE_REQUIRED'):
                        release.previous_release(guard,transport,root,root/'capsule','a'*64)
                (root/'result.json').write_bytes(guard.canonical(result))
                (code/'runtime.py').write_text('changed\n')
                with self.assertRaisesRegex(RuntimeError,'CODE_CHANGED'):
                    release.previous_release(guard,transport,root,root/'capsule','a'*64)

    def test_native_model_and_instruction_contracts_are_comparable_without_execution(self):
        source=(ROOT/'services/minecraft-assistant/dialogue.py').read_text()
        self.assertEqual(release.constant(source,'MODEL'),'vector-qwen3-instruct2507:4b-q4km')
        self.assertNotEqual(release.constant(source,'SYSTEM'),release.constant(source.replace('Du bist Vector.','Du bist anders.'),'SYSTEM'))
        with self.assertRaises(RuntimeError):release.constant('pass','MODEL')

    def test_start_failure_and_interrupt_restore_original_profile(self):
        for failure in (RuntimeError('synthetic-start-failure'),KeyboardInterrupt()):
            with self.subTest(kind=type(failure).__name__),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);active=root/'compose.json';active.write_bytes(b'old')
                restored=[]
                fake=SimpleNamespace(replace_atomic=lambda path,raw:path.write_bytes(raw),
                    recreate=Mock(side_effect=failure),rollback=lambda *args,**kwargs:(restored.append(True),active.write_bytes(b'old')))
                with patch.object(release.signal,'pthread_sigmask'),self.assertRaises(type(failure)):
                    release.activate(fake,{'compose':str(active)},root,{},b'new',b'old')
                self.assertEqual(active.read_bytes(),b'old');self.assertEqual(restored,[True])

    def test_success_is_recorded_only_for_the_exact_candidate_profile(self):
        for drift in (False,True):
            with self.subTest(drift=drift),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);active=root/'compose.json';active.write_bytes(b'old')
                code=root/'code';code.mkdir();(code/'runtime.py').write_text('pass\n')
                profile={'mode':'6'};files=guard.tree_files(code)
                record={'other_containers':{'game':['game','image','start']},'candidate_code':str(code),
                    'candidate_files':files,'candidate_compose_sha256':guard.digest(b'new'),
                    'candidate_profile_sha256':guard.digest(guard.canonical(profile))}
                rollback=Mock(side_effect=lambda *args,**kwargs:active.write_bytes(b'old'))
                fake=SimpleNamespace(replace_atomic=lambda path,raw:path.write_bytes(raw),recreate=Mock(),await_health=Mock(),
                    compose=lambda *args:({'mode':'0'} if drift else profile),digest=guard.digest,canonical=guard.canonical,
                    inventory=lambda:{'assistant':{'Id':'new'}},validate_live=Mock(),tree_files=guard.tree_files,
                    others=lambda *args:{'game':('game','image','start')},identity=lambda row:('new','image','start'),rollback=rollback)
                with patch.object(release.signal,'pthread_sigmask'):
                    if drift:
                        with self.assertRaisesRegex(RuntimeError,'DEPLOYED_PROFILE_CHANGED'):
                            release.activate(fake,{'compose':str(active),'container':'assistant'},root,record,b'new',b'old')
                        self.assertEqual(active.read_bytes(),b'old');rollback.assert_called_once()
                    else:
                        release.activate(fake,{'compose':str(active),'container':'assistant'},root,record,b'new',b'old')
                        self.assertEqual(json.loads((root/'record.json').read_bytes())['deployed_identity'],['new','image','start'])
                        self.assertEqual(active.read_bytes(),b'new');rollback.assert_not_called()

    def test_failed_rollback_is_explicit_and_external_profile_drift_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);active=root/'compose.json';active.write_bytes(b'old')
            def recreate(config):active.write_bytes(b'external');raise RuntimeError('failure')
            rollback=Mock()
            fake=SimpleNamespace(replace_atomic=lambda path,raw:path.write_bytes(raw),recreate=recreate,rollback=rollback)
            with patch.object(release.signal,'pthread_sigmask'),self.assertRaisesRegex(RuntimeError,'AUTOMATIC_ROLLBACK_FAILED'):
                release.activate(fake,{'compose':str(active)},root,{},b'new',b'old')
            self.assertEqual(active.read_bytes(),b'external');rollback.assert_not_called()

    def test_transport_manifest_cannot_be_replaced_or_failed_evidence_promoted(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'code').mkdir();(root/'code/runtime.py').write_text('pass\n')
            (root/'transport.test.py').write_text('pass\n')
            manifest={'candidate_sha256':guard.tree_files(root/'code'),'transport_test_sha256':guard.digest(b'pass\n'),
                'native_report':str(root),'native_manifest_sha256':'0'*64}
            pin=guard.digest(guard.canonical(manifest))
            good={'manifest_sha256':pin,'transport_qualified':True,'native_evidence_retained':True,
                'service_bindings_retained':True,'temporary_container_cleanup_verified':True,'production_unchanged':True,
                'production_activated':False,'model_calls':0,'cloud_calls':0,'messages_sent':0}
            for name,data in (('manifest.json',manifest),('result.json',good)):
                (root/name).write_bytes(guard.canonical(data));(root/name).chmod(0o600)
            verifier=Mock();fixture=SimpleNamespace(read_private=transport.read_private,verify_native=verifier)
            self.assertEqual(release.capsule(guard,fixture,root,pin)[0],manifest);verifier.assert_called_once()
            for field,value in (('transport_qualified',False),('production_activated',True),('cloud_calls',1)):
                (root/'result.json').write_bytes(guard.canonical(dict(good,**{field:value})))
                with self.subTest(field=field),self.assertRaises(RuntimeError):release.capsule(guard,fixture,root,pin)
            with self.assertRaisesRegex(RuntimeError,'TRANSPORT_MANIFEST_PIN_MISMATCH'):
                release.capsule(guard,fixture,root,'1'*64)


if __name__=='__main__':unittest.main()
