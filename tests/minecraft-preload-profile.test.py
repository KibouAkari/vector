"""Bound a diagnostic-only empty preload request; never generate user content."""
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType
from contextlib import contextmanager,redirect_stdout
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('evaluation',ROOT/'scripts/deploy/evaluate-minecraft-dialogue.py')
evaluation=importlib.util.module_from_spec(spec);spec.loader.exec_module(evaluation)
MODEL='vector-qwen3-instruct2507:4b-q4km'


class Preload(unittest.TestCase):
    def request(self,value=None,error=None):
        sent=[];closed=[]
        class Socket:
            def settimeout(self,seconds):
                if not 0<seconds<=45:raise AssertionError(seconds)
        class Connection:
            def __init__(self,host,port,timeout):
                if (host,port,timeout)!=('vector-local-inference',11434,45):raise AssertionError('destination')
                self.sock=Socket()
            def request(self,method,path,body,headers):sent.append(json.loads(body))
            def getresponse(self):
                if error:raise error
                return SimpleNamespace(status=200,read1=io.BytesIO(json.dumps(value).encode()).read1)
            def close(self):closed.append(True)
        namespace={};exec(evaluation.STREAM_PROFILE,namespace)
        provider=SimpleNamespace(endpoint='http://vector-local-inference:11434',model=MODEL)
        with patch('http.client.HTTPConnection',Connection):
            report=namespace['preload_profile_model'](provider)
        self.assertEqual(len(sent),1);self.assertTrue(closed)
        self.assertEqual(sent[0]['messages'],[])
        self.assertNotIn('prompt',sent[0]);self.assertNotIn('format',sent[0])
        self.assertEqual(sent[0]['options'],{'num_ctx':4096,'num_thread':2})
        self.assertEqual(sent[0]['keep_alive'],'5m')
        return report

    def test_empty_preload_keeps_load_time_separate_from_answer_budget(self):
        report=self.request(dict(model=MODEL,done=True,done_reason='load',message={'content':''},
                                 prompt_eval_count=0,eval_count=0,load_duration=123))
        self.assertTrue(report['completed'])
        self.assertEqual(report['load_duration'],123)
        self.assertEqual(report['limit_seconds'],45)

    def test_load_timeout_is_bounded_and_does_not_report_ready(self):
        report=self.request(error=TimeoutError('SYNTHETIC_PRIVATE_FAILURE'))
        self.assertFalse(report['completed']);self.assertEqual(report['error'],'TimeoutError')
        self.assertNotIn('SYNTHETIC_PRIVATE',json.dumps(report))

    def test_unexpected_model_text_or_generated_tokens_are_rejected(self):
        for value in (dict(model='other',done=True),dict(model=MODEL,done=True,message={'content':'SYNTHETIC_PRIVATE_TEXT'}),
                      dict(model=MODEL,done=True,eval_count=1)):
            with self.subTest(value=value):
                report=self.request(value)
                self.assertFalse(report['completed']);self.assertNotIn('SYNTHETIC_PRIVATE',json.dumps(report))

    def test_preload_requires_explicit_profile_mode_before_any_work(self):
        import sys
        with patch.object(sys,'argv',['evaluation','--guard-helper','/missing',
            '--baseline','/missing','--source-root','/missing','--workspace-root','/missing',
            '--lock-file','/missing','--preload']),patch('sys.stderr',io.StringIO()),self.assertRaises(SystemExit) as raised:
            evaluation.main()
        self.assertEqual(raised.exception.code,2)

    def test_failed_preload_releases_slot_and_skips_question(self):
        fake={name:ModuleType(name) for name in ('runtime','portraits','dialogue','server')}
        events=[]
        @contextmanager
        def slot(dsn):
            events.append('lock-enter')
            try:yield
            finally:events.append('lock-exit')
        fake['runtime'].local_slot=slot
        fake['runtime'].State=lambda *args:object()
        fake['runtime'].Assistant=lambda *args,**kwargs:object()
        fake['portraits'].PlayerPortraits=lambda *args:object()
        fake['dialogue'].MODEL=MODEL
        def answer(*args):events.append('question');return '12:34 Uhr'
        fake['dialogue'].GroundedDialogue=lambda *args:SimpleNamespace(answer=answer)
        fake['dialogue'].PublicObservations=lambda *args,**kwargs:object()
        provider=SimpleNamespace(model=MODEL,dsn='synthetic',events=events)
        fake['server'].knowledge_for=lambda *args:provider
        profile='def install_stream_profile(provider): pass\ndef preload_profile_model(provider):\n provider.events.append("preload")\n return {"completed":False,"request_attempted":True,"error":"TimeoutError"}'
        payload={'files':{},'profile_only':True,'preload':True,'stream_profile':profile}
        output=io.StringIO();old_path=list(sys.path);original=Path.read_bytes
        try:
            with patch.dict(sys.modules,fake),patch.object(sys,'stdin',io.StringIO(json.dumps(payload))), \
                 patch.object(Path,'read_bytes',lambda path:b'[]' if str(path)=='/inputs/mods.json' else original(path)),redirect_stdout(output):
                exec(evaluation.INNER,{})
        finally:sys.path[:]=old_path
        result=json.loads(next(line.split('=',1)[1] for line in output.getvalue().splitlines()
                               if line.startswith('VECTOR_DIALOGUE_RESULT=')))
        self.assertEqual(events,['lock-enter','preload','lock-exit'])
        self.assertEqual(result['completed_cases'],0)
        self.assertFalse(result['preload']['completed'])
        self.assertFalse(result['passed']);self.assertFalse(result['eligible_for_activation'])


if __name__=='__main__':unittest.main()
