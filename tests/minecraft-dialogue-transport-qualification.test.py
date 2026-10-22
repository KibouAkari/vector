"""Private service binding and immutable native evidence boundaries; no Docker."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('transport_qualification',ROOT/'scripts/deploy/qualify-minecraft-dialogue-transport.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class Qualification(unittest.TestCase):
    def test_existing_service_token_and_environment_bindings_are_retained_narrowly(self):
        candidate=(ROOT/'services/minecraft-assistant/server.py').read_text()
        installed=candidate.replace('VECTOR_MINECRAFT_','VECTOR_OPERATOR_').replace(
            '/run/secrets/vector_minecraft_token','/run/secrets/operator_token')
        mounted=[dict(Destination='/run/secrets/operator_token',RW=False)]
        result=module.preserve_service_bindings(installed,candidate,mounted)
        self.assertEqual(result,installed.replace("'/run/secrets/operator_token'",repr('/run/secrets/operator_token')))
        self.assertIn("value.username != 'vector_minecraft_slot'",result)
        self.assertIn("stat.S_IMODE(meta.st_mode) != 0o400",result)

    def test_unmounted_writable_ambiguous_or_arbitrary_service_tokens_are_rejected(self):
        source=(ROOT/'services/minecraft-assistant/server.py').read_text()
        mount=dict(Destination='/run/secrets/vector_minecraft_token',RW=False)
        for mounts in ([],[dict(mount,RW=True)],[mount,mount]):
            with self.subTest(mounts=mounts),self.assertRaises(RuntimeError):
                module.preserve_service_bindings(source,source,mounts)
        for path in ('/tmp/token','/run/secrets/nested/token'):
            with self.subTest(path=path),self.assertRaises(RuntimeError):
                module.preserve_service_bindings(source.replace('/run/secrets/vector_minecraft_token',path),source,[mount])

    def test_unknown_or_nonliteral_environment_contract_is_rejected(self):
        source=(ROOT/'services/minecraft-assistant/server.py').read_text()
        for changed in (source.replace("'VECTOR_MINECRAFT_KNOWLEDGE'","'VECTOR_UNREVIEWED'"),
                        source.replace("os.environ.get('VECTOR_MINECRAFT_KNOWLEDGE',",'os.environ.get(variable,')):
            with self.subTest(),self.assertRaises(RuntimeError):module.service_bindings(changed)

    def test_native_manifest_and_sources_must_match_complete_unchanged_qualification(self):
        canonical=lambda v:json.dumps(v,sort_keys=True,separators=(',',':')).encode()
        digest=lambda raw:hashlib.sha256(raw).hexdigest()
        guard=SimpleNamespace(canonical=canonical,digest=digest,checked_path=lambda p:Path(p))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'candidate').mkdir()
            def write(name,value):
                p=root/name;p.write_bytes(value);p.chmod(0o600)
            sources={name:b'pass\n' for name in module.FILES}
            for name,raw in sources.items():write('candidate/'+name,raw)
            manifest={'candidate_sha256':{name:digest(raw) for name,raw in sources.items()}}
            pin=digest(canonical(manifest));write('manifest.json',canonical(manifest))
            result={'passed':True,'production_activated':False,'production_containers_and_profiles_unchanged':True,
                'native_process_termination_verified':True,'expected_cases':4,'completed_cases':4,
                'model_calls':1,'cloud_calls':0,'messages_sent':0,'manifest_sha256':pin,
                'cases':[dict(id=key,passed=True) for key in ('smalltalk','unlisted-gameplay','player-opinion','own-context')]}
            write('result.json',canonical(result))
            self.assertEqual(module.verify_native(guard,root,pin)[1],sources)
            for field,value in (('passed',False),('production_activated',True),('messages_sent',1),
                                ('cloud_calls',1),('completed_cases',3),('native_process_termination_verified',False)):
                write('result.json',canonical(dict(result,**{field:value})))
                with self.subTest(field=field),self.assertRaises(RuntimeError):module.verify_native(guard,root,pin)
            write('result.json',canonical(result));write('candidate/dialogue.py',b'changed\n')
            with self.assertRaisesRegex(RuntimeError,'NATIVE_CANDIDATE_CHANGED'):module.verify_native(guard,root,pin)


if __name__=='__main__':unittest.main()
