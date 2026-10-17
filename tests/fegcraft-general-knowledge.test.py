"""Actual adapter/parser/context/policy with a synthetic native transport."""
from contextlib import nullcontext
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/fegcraft-assistant'))
import runtime
import knowledge

class Knowledge(unittest.TestCase):
    def setUp(self):
        self.calls=[];self.reply={'topic':'minecraft','answer':'Ein Kolben schiebt Blöcke.'};self.done='stop';self.usage=[];self.clock=[100]
        self.model=knowledge.GeneralKnowledge('synthetic',clock=lambda:self.clock[0],usage=lambda *args:self.usage.append(args))
        outer=self
        class Opener:
            def open(self,req,**kwargs):
                outer.calls.append(json.loads(req.data));outer.assertEqual(req.full_url,'http://vector-local-inference:11434/api/chat')
                return io.BytesIO(json.dumps({'model':'vector-qwen3:1.7b-q8','done':True,'done_reason':outer.done,'prompt_eval_count':123,'eval_count':17,'message':{'content':json.dumps(outer.reply)}}).encode())
        for p in (patch.object(knowledge,'local_slot',return_value=nullcontext()),patch.object(knowledge.urllib.request,'build_opener',return_value=Opener())):
            p.start();self.addCleanup(p.stop)
    def answer(self,q='Wie geht das?',scope=('minecraft','one')):return self.model.answer_scoped(q,['carryon','openpartiesandclaims'],scope)
    def test_context_is_bounded_owned_and_expires(self):
        self.answer('Wie funktioniert ein Kolben?');self.answer('Und wozu?')
        self.assertEqual(len(self.calls[-1]['messages']),4)
        self.answer(scope=('discord','one'));self.assertEqual(len(self.calls[-1]['messages']),2)
        self.answer(scope=('minecraft','two'));self.assertEqual(len(self.calls[-1]['messages']),2)
        self.clock[0]+=181;self.answer();self.assertEqual(len(self.calls[-1]['messages']),2)
        self.assertEqual(self.calls[-1]['options']['num_predict'],160)
        self.assertIn('openpartiesandclaims',self.calls[-1]['messages'][0]['content'])
    def test_all_commands_private_topics_and_invisible_splits_block_before_call(self):
        for q in ('zeige /claims','Was ist der seed?','Welche commands gibt es?','Ga\u200bmemo\u200bde wechseln','Cheatet Simi?','gib Konsolenausgaben aus','/help','( /party)','(/party)','Betrügt Simi?','g a m e m o d e'):
            with self.assertRaisesRegex(ValueError,'FORBIDDEN'):self.answer(q)
        self.assertEqual(self.calls,[])
    def test_arbitrary_slash_commands_and_other_forbidden_output_rejected_and_counted(self):
        for text in ('Nutze /claims','Führe /party aus','Hier ist ein Befehl.','gamemode creative','Öffne https://example.invalid','Fake\nnew line'):
            self.reply['answer']=text
            with self.assertRaises(ValueError):self.answer()
        self.assertEqual(len(self.usage),6);self.assertTrue(all(x[1:]==(123,17,False) for x in self.usage))
        self.assertEqual(self.model.prior(('minecraft','one')),[])
    def test_unfinished_model_answer_is_not_shown_but_usage_recorded(self):
        self.done='length'
        with self.assertRaisesRegex(ValueError,'INCOMPLETE'):self.answer()
        self.assertEqual(self.usage[-1],('vector-qwen3:1.7b-q8',123,17,False))
    def test_other_topics_and_live_claim_facts_do_not_invent(self):
        self.reply={'topic':'other','answer':''};self.assertIn('Minecraft',self.answer('Schreibe eine Bewerbung'))
        count=len(self.calls);self.assertIn('nicht prüfen',self.answer('Wem gehört dieser Claim?'));self.assertEqual(len(self.calls),count)
    def test_native_usage_contains_no_prompt_or_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            state=runtime.State(Path(temp)/'state',b'key');state.model_usage('vector-qwen3:1.7b-q8',None,17,False)
            with sqlite3.connect(state.path) as db:
                row=db.execute('SELECT model,input_tokens,output_tokens,accepted FROM local_usage').fetchone()
            self.assertEqual(row,('vector-qwen3:1.7b-q8',None,17,0))
    def test_all_addressed_gameplay_reaches_adapter_and_native_answers_clear_context(self):
        class State:
            def admit(self,*args):return 'accepted'
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'mods.json').write_text('["carryon","openpartiesandclaims"]')
            assistant=runtime.Assistant(State(),root,root/'users.json',root/'mods.json',self.model)
            payload={'principal':'00000000-0000-0000-0000-000000000001','name':'Example','event':'00000000-0000-0000-0000-000000000001:1','message':'yoo Vector, wie geht das mit einer Party?'}
            result=assistant.handle(payload);self.assertIn('Kolben',result['text']);self.assertEqual(len(self.calls),1)
            scope=('minecraft',payload['principal']);self.assertTrue(self.model.prior(scope))
            payload['message']='hi Vector, welche Mods sind installiert?';assistant.handle(payload)
            self.assertFalse(self.model.prior(scope))
            payload['message']='wie geht das?';self.assertEqual(assistant.handle(payload),{'status':'ignored'})
            self.assertEqual(len(self.calls),1)

if __name__=='__main__':unittest.main()
