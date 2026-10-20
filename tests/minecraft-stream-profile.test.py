"""Streaming profile bounds, metadata privacy and one-call ceiling; no native requests."""
import importlib.util
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('evaluation',ROOT/'scripts/deploy/evaluate-minecraft-dialogue.py')
evaluation=importlib.util.module_from_spec(spec);spec.loader.exec_module(evaluation)


class Profile(unittest.TestCase):
    def run_request(self,lines,*,error=None,validator=None):
        reports=[];usage=[];sent=[];closed=[];clock=[0]
        class Socket:
            def settimeout(self,seconds):
                if not 0<seconds<=20:raise AssertionError(seconds)
        class Response:
            status=200
            def readline(self,limit):
                clock[0]+=1
                if error:raise error
                return lines.pop(0) if lines else b''
        class Connection:
            def __init__(self,host,port,timeout):
                if (host,port)!=('vector-local-inference',11434):raise AssertionError('destination')
                self.sock=Socket()
            def request(self,method,path,raw,headers):sent.append(json.loads(raw))
            def getresponse(self):return Response()
            def close(self):closed.append(True)
        provider=SimpleNamespace(endpoint='http://vector-local-inference:11434',
            model='vector-qwen3-instruct2507:4b-q4km',context_tokens=4096,
            usage=lambda *args:usage.append(args),diagnostic=reports.append)
        namespace={};exec(evaluation.STREAM_PROFILE,namespace)
        namespace['install_stream_profile'](provider)
        with patch('http.client.HTTPConnection',Connection),patch('time.monotonic',lambda:clock[0]):
            try:
                result=provider.request({'type':'object'},[{'role':'user','content':'SYNTHETIC_PRIVATE_PROMPT'}],80,24,
                                        validator or (lambda value:value['answer']))
                failure=None
            except Exception as exc:result=None;failure=exc
        self.assertTrue(closed)
        self.assertTrue(sent[0]['stream'])
        self.assertEqual(sent[0]['options']['num_thread'],2)
        return result,failure,reports,usage,provider

    def line(self,content='',**kwargs):
        return (json.dumps(dict(model='vector-qwen3-instruct2507:4b-q4km',
                                message={'content':content},done=False,**kwargs))+'\n').encode()

    def final(self,reason='stop'):
        return (json.dumps(dict(model='vector-qwen3-instruct2507:4b-q4km',message={'content':''},
                   done=True,done_reason=reason,prompt_eval_count=12,eval_count=9,
                   prompt_eval_duration=100,eval_duration=200,load_duration=300))+'\n').encode()

    def test_complete_response_records_progress_but_no_prompt_or_prose(self):
        result,error,reports,usage,provider=self.run_request([
            self.line('{"answer":"SYNTHETIC_PRIVATE_ANSWER"}'),self.final()])
        self.assertIsNone(error);self.assertEqual(result,'SYNTHETIC_PRIVATE_ANSWER')
        report=reports[0]
        self.assertEqual(report['first_content_seconds'],1)
        self.assertEqual(report['headers_seconds'],0)
        self.assertEqual(report['prompt_eval_count'],12)
        self.assertTrue(report['partial_json_complete'])
        self.assertNotIn('SYNTHETIC_PRIVATE',json.dumps(report))
        self.assertTrue(usage[0][-1])
        with self.assertRaisesRegex(ValueError,'PROFILE_ONE_CALL_LIMIT'):
            provider.request({},[],1,999,lambda value:value)

    def test_timeout_has_unknown_usage_and_never_returns_partial_answer(self):
        result,error,reports,usage,_=self.run_request([],error=TimeoutError('SYNTHETIC_PRIVATE_FAILURE'))
        self.assertIsNone(result);self.assertIsInstance(error,TimeoutError)
        self.assertIsNone(usage[0][1]);self.assertIsNone(usage[0][2]);self.assertFalse(usage[0][-1])
        self.assertEqual(reports[0]['error'],'TimeoutError')
        self.assertNotIn('SYNTHETIC_PRIVATE',json.dumps(reports))

    def test_truncated_generation_keeps_native_usage_but_rejects_answer(self):
        result,error,reports,usage,_=self.run_request([self.line('{"answer":"unfinished'),self.final('length')])
        self.assertIsNone(result);self.assertIsInstance(error,ValueError)
        self.assertEqual(usage[0][1:3],(12,9));self.assertFalse(usage[0][-1])
        self.assertFalse(reports[0]['partial_json_complete'])

    def test_response_size_and_wrong_model_fail_closed(self):
        for line in (b'x'*16385,b'{"model":"other","message":{"content":"x"}}\n'):
            with self.subTest():
                result,error,reports,usage,_=self.run_request([line])
                self.assertIsNone(result);self.assertIsInstance(error,ValueError)
                self.assertFalse(usage[0][-1])

    def test_profile_completion_does_not_qualify_a_single_successful_answer(self):
        fake={name:ModuleType(name) for name in ('runtime','portraits','dialogue','server')}
        fake['runtime'].State=lambda *args:object()
        fake['runtime'].Assistant=lambda *args,**kwargs:object()
        fake['portraits'].PlayerPortraits=lambda *args:object()
        fake['dialogue'].MODEL='synthetic-model'
        calls=[]
        def answer(*args):calls.append(1);return '12:34 Uhr'
        fake['dialogue'].GroundedDialogue=lambda *args:SimpleNamespace(answer=answer)
        fake['dialogue'].PublicObservations=lambda *args,**kwargs:object()
        fake['server'].knowledge_for=lambda *args:SimpleNamespace(model='synthetic-model')
        payload={'files':{},'profile_only':True,'stream_profile':'def install_stream_profile(provider): pass'}
        output=io.StringIO();original=Path.read_bytes;old_path=list(sys.path)
        try:
            with patch.dict(sys.modules,fake),patch.object(sys,'stdin',io.StringIO(json.dumps(payload))), \
                 patch.object(Path,'read_bytes',lambda path:b'[]' if str(path)=='/inputs/mods.json' else original(path)),redirect_stdout(output):
                exec(evaluation.INNER,{})
        finally:sys.path[:]=old_path
        result=json.loads(next(line.split('=',1)[1] for line in output.getvalue().splitlines()
                               if line.startswith('VECTOR_DIALOGUE_RESULT=')))
        self.assertEqual(calls,[1])
        self.assertTrue(result['diagnostic_completed'])
        self.assertTrue(result['cases'][0]['passed'])
        self.assertFalse(result['passed'])
        self.assertFalse(result['eligible_for_activation'])


if __name__=='__main__':unittest.main()
