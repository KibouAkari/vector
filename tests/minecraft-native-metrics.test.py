"""Opt-in native metadata boundaries. No network, models or database access."""
import io
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/minecraft-assistant'))
from knowledge import GeneralKnowledge

MODEL='vector-qwen3-instruct2507:4b-q4km'


class Metrics(unittest.TestCase):
    def provider(self):
        provider=GeneralKnowledge('synthetic-only',model=MODEL)
        provider.context_tokens=4096
        provider.native_timeout=20
        provider.usage=lambda *args:self.usage.append(args)
        provider.diagnostic=lambda value:self.reports.append(value)
        return provider

    def setUp(self):
        self.usage=[];self.reports=[]

    def request(self,provider,opener):
        with patch('knowledge.urllib.request.build_opener',return_value=opener):
            return provider.request({'type':'object'},[{'role':'user','content':'PRIVATE_SYNTHETIC_PROMPT'}],
                                    80,time.monotonic()+24,lambda value:value['answer'])

    def test_metrics_exclude_prompt_and_answer_and_keep_payload_settings(self):
        payload={'model':MODEL,'done':True,'done_reason':'stop',
                 'message':{'content':json.dumps({'answer':'PRIVATE_SYNTHETIC_ANSWER'})},
                 'prompt_eval_count':13,'eval_count':9,'prompt_eval_duration':123,'eval_duration':456,'load_duration':789}
        from unittest.mock import Mock
        opener=Mock();opener.open.return_value=io.BytesIO(json.dumps(payload).encode())
        self.assertEqual(self.request(self.provider(),opener),'PRIVATE_SYNTHETIC_ANSWER')
        sent=json.loads(opener.open.call_args.args[0].data)
        self.assertFalse(sent['stream'])
        self.assertEqual(sent['options']['num_thread'],2)
        self.assertEqual(sent['options']['num_ctx'],4096)
        self.assertEqual(sent['options']['num_predict'],80)
        report=self.reports[0]
        self.assertEqual(report['prompt_eval_count'],13)
        self.assertEqual(report['eval_duration'],456)
        self.assertEqual(report['prompt_characters'],len('PRIVATE_SYNTHETIC_PROMPT'))
        self.assertNotIn('PRIVATE_SYNTHETIC',json.dumps(report))
        self.assertTrue(self.usage[0][-1])

    def test_timeout_preserves_unknown_usage_and_does_not_include_error_message(self):
        from unittest.mock import Mock
        opener=Mock();opener.open.side_effect=TimeoutError('PRIVATE_SYNTHETIC_FAILURE')
        with self.assertRaises(TimeoutError):self.request(self.provider(),opener)
        self.assertEqual(self.usage,[(MODEL,None,None,False)])
        self.assertEqual(self.reports[0]['error'],'TimeoutError')
        self.assertNotIn('PRIVATE_SYNTHETIC',json.dumps(self.reports))

    def test_optional_diagnostic_failure_does_not_mask_transport_failure(self):
        from unittest.mock import Mock
        provider=self.provider()
        provider.diagnostic=lambda row:(_ for _ in ()).throw(ValueError('metric sink'))
        opener=Mock();opener.open.side_effect=TimeoutError('transport')
        with self.assertRaises(TimeoutError):self.request(provider,opener)


if __name__=='__main__':unittest.main()
