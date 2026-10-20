"""Own-child cancellation and release-lock boundaries; no Docker or model calls."""
import importlib.util
import ast
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/minecraft-assistant'))
spec = importlib.util.spec_from_file_location('dialogue_evaluation', ROOT/'scripts/deploy/evaluate-minecraft-dialogue.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Evaluation(unittest.TestCase):
    def test_quality_checks_reject_previous_native_regressions(self):
        import re
        tree=ast.parse(module.INNER)
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='case_checks')
        namespace={'re':re}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'case-checks','exec'),namespace)
        check=namespace['case_checks']
        rejected=(
            ('smalltalk','Was möchtest du genau wissen? Beschreibe kurz dein Ziel.'),
            ('smalltalk','Ich bin gerade nicht verfügbar, versuche es später.'),
            ('unlisted-gameplay','Sand wird im Ofen zu Glas bei 1500 Grad.'),
            ('unlisted-gameplay','Sand im Ofen schmelzen, das Ergebnis ist,'),
            ('player-opinion','ExampleTwo hat 90 Monster getötet. Keine Spielersterbe aufgezeichnet.'),
            ('player-opinion','ExampleTwo hat 90 Mobkills.'),
            ('own-context','Du hast 25 Mobkills.'),
            ('own-context','Du hast 31 Monsterkilling erzielt, aber noch keine Tode, also kein Ende der Spielzeit!'),
            ('own-context','ExampleTwo hat 90 Mobkills.'))
        for key,answer in rejected:
            with self.subTest(key=key,answer=answer):self.assertFalse(all(check(key,answer).values()))
        accepted=(
            ('smalltalk','Mir geht es gut, bereit fürs nächste Abenteuer!'),
            ('unlisted-gameplay','Sand mit Brennstoff im Ofen schmelzen, dann erhältst du Glas.'),
            ('player-opinion','ExampleTwo wirkt mit 90 Mobkills wie der Albtraum der Monster.'),
            ('own-context','Du hast inzwischen 31 Mobkills.'))
        for key,answer in accepted:
            with self.subTest(key=key,answer=answer):self.assertTrue(all(check(key,answer).values()))

    def test_rejection_capture_is_bounded_synthetic_and_never_accepts_rejected_output(self):
        import re
        from runtime import safe_answer,request_forbidden
        tree=ast.parse(module.INNER)
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('error_code','install_rejection_capture')]
        namespace={'re':re}
        exec(compile(ast.Module(body=functions,type_ignores=[]),'rejection-capture','exec'),namespace)
        self.assertIsNone(namespace['error_code'](ValueError('a private message /some/path')))
        for text,visible in (('Sand braucht 1500 Grad.',True),('Nutze /op ExampleOne.',False),
                             ('x'*321,False),('secret\nvalue',False)):
            rejected=[]
            def native(schema,messages,predict,deadline,validator):
                return validator({'answer':text})
            provider=SimpleNamespace(request=native)
            namespace['install_rejection_capture'](provider,rejected)
            def deny(value):raise ValueError('UNSUPPORTED_DIALOGUE_NUMBER')
            with self.subTest(text=text),self.assertRaisesRegex(ValueError,'UNSUPPORTED_DIALOGUE_NUMBER'):
                provider.request({},[],80,100,deny)
            self.assertEqual(rejected[0]['code'],'UNSUPPORTED_DIALOGUE_NUMBER')
            self.assertEqual('rejected_synthetic_answer' in rejected[0],visible)

    def test_rejection_diagnostic_cannot_combine_with_profile(self):
        with patch.object(sys,'argv',['evaluation','--guard-helper','unused','--baseline','unused',
                '--source-root','unused','--workspace-root','unused','--lock-file','unused',
                '--profile-only','--diagnose-rejection']),self.assertRaises(SystemExit):
            with redirect_stdout(io.StringIO()):module.main()

    def test_two_case_diagnostic_captures_rejection_but_never_qualifies(self):
        fake={name:ModuleType(name) for name in ('runtime','portraits','dialogue','server')}
        fake['runtime'].State=lambda *args:object()
        fake['runtime'].Assistant=lambda *args,**kwargs:object()
        fake['runtime'].safe_answer=lambda text:text
        fake['runtime'].request_forbidden=lambda text:False
        fake['portraits'].PlayerPortraits=lambda *args:object()
        fake['dialogue'].MODEL='synthetic-model'
        values=iter(('Es ist 12:34 Uhr.','Sand braucht 1500 Grad.'));calls=[]
        def native(schema,messages,predict,deadline,validator):
            calls.append(1);return validator({'answer':next(values)})
        provider=SimpleNamespace(model='synthetic-model',request=native)
        class Dialogue:
            def __init__(self,provider):self.provider=provider
            def answer(self,question,*args):
                def validate(value):
                    if '1500' in value['answer']:raise ValueError('UNSUPPORTED_DIALOGUE_NUMBER')
                    return value['answer']
                return self.provider.request({},[],80,100,validate)
        fake['dialogue'].GroundedDialogue=Dialogue
        fake['dialogue'].PublicObservations=lambda *args,**kwargs:object()
        fake['server'].knowledge_for=lambda *args:provider
        output=io.StringIO();original=Path.read_bytes;old_path=list(sys.path)
        try:
            with patch.dict(sys.modules,fake),patch.object(sys,'stdin',io.StringIO('{"files":{},"diagnose_rejection":true}')), \
                    patch.object(Path,'read_bytes',lambda path:b'[]' if str(path)=='/inputs/mods.json' else original(path)),redirect_stdout(output):
                exec(compile(module.INNER,'synthetic-evaluation','exec'),{})
        finally:sys.path[:]=old_path
        result=json.loads(next(line.split('=',1)[1] for line in output.getvalue().splitlines() if line.startswith('VECTOR_DIALOGUE_RESULT=')))
        self.assertEqual(len(calls),2)
        self.assertEqual(result['expected_cases'],2)
        self.assertTrue(result['diagnostic_completed'])
        self.assertFalse(result['passed'])
        self.assertFalse(result['eligible_for_activation'])
        rejected=result['cases'][1]
        self.assertEqual(rejected['error_code'],'UNSUPPORTED_DIALOGUE_NUMBER')
        self.assertEqual(rejected['rejections'][0]['rejected_synthetic_answer'],'Sand braucht 1500 Grad.')

    def test_first_native_timeout_stops_remaining_cases_without_claiming_full_pass(self):
        fake={name:ModuleType(name) for name in ('runtime','portraits','dialogue','server')}
        fake['runtime'].State=lambda *args:object()
        fake['runtime'].Assistant=lambda *args,**kwargs:object()
        fake['portraits'].PlayerPortraits=lambda *args:object()
        fake['dialogue'].MODEL='synthetic-model'
        calls=[]
        class Slow:
            def __init__(self,*args):pass
            def answer(self,*args):calls.append(1);raise TimeoutError()
        fake['dialogue'].GroundedDialogue=Slow
        fake['dialogue'].PublicObservations=lambda *args,**kwargs:object()
        fake['server'].knowledge_for=lambda *args:SimpleNamespace(model='synthetic-model')
        output=io.StringIO();original=Path.read_bytes;old_path=list(sys.path)
        def read(path):
            return b'[]' if str(path)=='/inputs/mods.json' else original(path)
        try:
            with patch.dict(sys.modules,fake),patch.object(sys,'stdin',io.StringIO('{"files":{}}')), \
                    patch.object(Path,'read_bytes',read),redirect_stdout(output):
                exec(compile(module.INNER,'synthetic-evaluation','exec'),{})
        finally:sys.path[:]=old_path
        result=json.loads(next(line.split('=',1)[1] for line in output.getvalue().splitlines()
                               if line.startswith('VECTOR_DIALOGUE_RESULT=')))
        self.assertEqual(calls,[1])
        self.assertEqual(result['expected_cases'],4)
        self.assertEqual(result['completed_cases'],1)
        self.assertFalse(result['passed'])
        self.assertFalse(result['eligible_for_activation'])

    def test_reviewed_fallback_cannot_hide_native_timeout_and_start_more_probes(self):
        fake={name:ModuleType(name) for name in ('runtime','portraits','dialogue','server')}
        fake['runtime'].State=lambda *args:object()
        fake['runtime'].Assistant=lambda *args,**kwargs:object()
        fake['portraits'].PlayerPortraits=lambda *args:object()
        fake['dialogue'].MODEL='synthetic-model'
        provider=SimpleNamespace(model='synthetic-model');calls=[]
        class Fallback:
            def __init__(self,*args):pass
            def answer(self,*args):
                calls.append(1);provider.diagnostic({'error':'TimeoutError'})
                return 'Es ist 12:34 Uhr.'
        fake['dialogue'].GroundedDialogue=Fallback
        fake['dialogue'].PublicObservations=lambda *args,**kwargs:object()
        fake['server'].knowledge_for=lambda *args:provider
        output=io.StringIO();original=Path.read_bytes;old_path=list(sys.path)
        try:
            with patch.dict(sys.modules,fake),patch.object(sys,'stdin',io.StringIO('{"files":{}}')), \
                    patch.object(Path,'read_bytes',lambda path:b'[]' if str(path)=='/inputs/mods.json' else original(path)),redirect_stdout(output):
                exec(compile(module.INNER,'synthetic-evaluation','exec'),{})
        finally:sys.path[:]=old_path
        result=json.loads(next(line.split('=',1)[1] for line in output.getvalue().splitlines() if line.startswith('VECTOR_DIALOGUE_RESULT=')))
        self.assertEqual(calls,[1])
        self.assertEqual(result['completed_cases'],1)
        self.assertFalse(result['passed'])

    def test_existing_private_slot_binding_is_retained_without_reading_secret(self):
        installed = (ROOT/'services/minecraft-assistant/server.py').read_text().replace(
            '/run/secrets/vector_minecraft_slot_dsn', '/run/secrets/operator_slot').replace(
            "value.username != 'vector_minecraft_slot'", "value.username != 'operator_slot'")
        candidate = (ROOT/'services/minecraft-assistant/server.py').read_text()
        result = module.preserve_slot_binding(installed, candidate, [
            {'Destination': '/run/secrets/operator_slot', 'RW': False}])
        self.assertEqual(result, candidate.replace(
            '/run/secrets/vector_minecraft_slot_dsn', '/run/secrets/operator_slot').replace(
            "value.username != 'vector_minecraft_slot'", "value.username != 'operator_slot'"))
        ast.parse(result)
        self.assertIn("stat.S_IMODE(meta.st_mode) != 0o400", result)
        self.assertIn("meta.st_uid != os.getuid()", result)

    def test_missing_writable_or_ambiguous_slot_mount_is_rejected(self):
        source = (ROOT/'services/minecraft-assistant/server.py').read_text()
        mount = {'Destination': '/run/secrets/vector_minecraft_slot_dsn', 'RW': False}
        for mounts in ([], [dict(mount, RW=True)], [mount, mount]):
            with self.subTest(mounts=mounts), self.assertRaisesRegex(RuntimeError, 'READ_ONLY_EXISTING_SLOT_MOUNT_REQUIRED'):
                module.preserve_slot_binding(source, source, mounts)

    def test_changed_factory_or_unsafe_binding_is_rejected(self):
        source = (ROOT/'services/minecraft-assistant/server.py').read_text()
        mounts = [{'Destination': '/run/secrets/vector_minecraft_slot_dsn', 'RW': False}]
        for invalid in (source.replace('def knowledge_for(', 'def renamed('),
                        source.replace('/run/secrets/vector_minecraft_slot_dsn', '/tmp/slot'),
                        source.replace("value.username != 'vector_minecraft_slot'", "value.username == 'vector_minecraft_slot'")):
            with self.subTest(), self.assertRaises(RuntimeError):
                module.preserve_slot_binding(invalid, source, mounts)

    def test_watchdog_reaps_only_its_own_child(self):
        foreign = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        try:
            identity = '1'*32
            code = module.WATCHDOG.replace('timeout=110', 'timeout=.05')
            result = subprocess.run([sys.executable, '-c', code], input=json.dumps({
                'program': 'import time; time.sleep(30)', 'evaluation_id': identity}).encode(),
                capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 137, result.stderr)
            self.assertIn(('VECTOR_DIALOGUE_TERMINATED='+identity).encode(), result.stdout)
            self.assertIsNone(foreign.poll())
        finally:
            foreign.terminate(); foreign.wait(timeout=5)

    def test_targeted_cancellation_leaves_unrelated_process_alive(self):
        identity = '2'*32
        foreign = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        target = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)',
                                   '--vector-dialogue-evaluation', identity], start_new_session=True)
        try:
            result = subprocess.run([sys.executable, '-c', module.CANCEL, identity],
                                    capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['terminated'])
            target.wait(timeout=5)
            self.assertIsNone(foreign.poll())
        finally:
            if target.poll() is None:target.kill(); target.wait(timeout=5)
            foreign.terminate(); foreign.wait(timeout=5)

    def test_missing_release_lock_is_never_created(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = root/'missing.lock'
            args = ['evaluation', '--guard-helper', str(ROOT/'scripts/deploy/update-minecraft-ranking-runtime.py'),
                    '--baseline', str(root), '--source-root', str(root),
                    '--workspace-root', str(root), '--lock-file', str(lock)]
            with patch.object(sys, 'argv', args), self.assertRaises(FileNotFoundError):
                module.main()
            self.assertFalse(lock.exists())


if __name__ == '__main__':
    unittest.main()
