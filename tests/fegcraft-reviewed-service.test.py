"""Actual server factory and signed HTTP with synthetic data/native replies."""
from contextlib import nullcontext
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/fegcraft-assistant'))
import server
import documentation
import knowledge
from runtime import Assistant,State
from recipes import RecipeBook


class ReviewedService(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.secret=self.root/'slot'
        self.secret.write_text('postgresql://vector_fegcraft_slot:synthetic@postgres/vector');self.secret.chmod(0o400)
        self.key=bytes.fromhex('ab'*32);self.state=State(self.root/'state.sqlite',self.key)
        self.catalog=ROOT/'services/fegcraft-assistant/public-knowledge.json'
        self.model=server.knowledge_for('3',self.state,self.secret,self.catalog)
        self.calls=[];self.bad=False

    def test_explicit_mode3_constructs_only_pinned_reviewed_model_with_usage(self):
        self.assertIsInstance(self.model,documentation.DocumentationKnowledge)
        self.assertEqual(self.model.model,documentation.MODEL)
        self.assertEqual(len(self.model.documentation.rows),84)
        self.assertEqual(self.model.documentation.sha256,server.DOCUMENTATION_SHA256)
        self.assertEqual(self.model.usage,self.state.model_usage)

    def test_default_off_needs_no_role_driver_catalog_or_model(self):
        self.assertIsNone(server.knowledge_for('0',self.state,'/missing','/missing'))
        for mode in ('auto','6','',None):
            with self.assertRaisesRegex(RuntimeError,'INVALID_KNOWLEDGE_MODE'):server.knowledge_for(mode,self.state)

    def test_mode4_retains_restricted_construction_and_adds_local_social_class(self):
        model=server.knowledge_for('4',self.state,self.secret,self.catalog)
        self.assertIsInstance(model,documentation.ConversationKnowledge)
        self.assertEqual(model.model,documentation.MODEL)
        self.assertEqual(model.documentation.sha256,server.DOCUMENTATION_SHA256)

    def test_admin_credentials_options_and_foreign_ports_refused(self):
        for dsn in ('postgresql://postgres:synthetic@postgres/vector',
          'postgresql://vector_fegcraft_slot:synthetic@postgres/vector?host=outside',
          'postgresql://vector_fegcraft_slot:synthetic@postgres:5434/vector',
          'postgresql://vector_fegcraft_slot@postgres/vector'):
            self.secret.chmod(0o600);self.secret.write_text(dsn);self.secret.chmod(0o400)
            with self.assertRaisesRegex(RuntimeError,'RESTRICTED_LOCAL_SLOT'):server.knowledge_for('3',self.state,self.secret,self.catalog)

    def test_unprotected_changed_symlink_and_fifo_inputs_fail_before_model(self):
        self.secret.chmod(0o600)
        with self.assertRaisesRegex(RuntimeError,'INVALID_LOCAL_SLOT_FILE'):server.knowledge_for('3',self.state,self.secret,self.catalog)
        self.secret.chmod(0o400)
        link=self.root/'link';link.symlink_to(self.secret)
        with self.assertRaises(OSError):server.knowledge_for('3',self.state,link,self.catalog)
        fifo=self.root/'fifo';os.mkfifo(fifo)
        with self.assertRaisesRegex(RuntimeError,'INVALID_LOCAL_SLOT_FILE'):server.knowledge_for('3',self.state,fifo,self.catalog)
        changed=self.root/'catalog';changed.write_bytes(self.catalog.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'CHECKSUM'):server.knowledge_for('3',self.state,self.secret,changed)

    def start(self):
        stats=self.root/'stats';stats.mkdir();uid=str(uuid.uuid4())
        (stats/(uid+'.json')).write_text(json.dumps({'stats':{'minecraft:custom':{'minecraft:mob_kills':123}}}))
        names=self.root/'users';names.write_text(json.dumps([{'uuid':uid,'name':'ExampleOne'}]))
        mods=self.root/'mods';mods.write_text(json.dumps(['carryon','openpartiesandclaims','voicechat']))
        outer=self
        class Opener:
            def open(self,request,**kwargs):
                value=json.loads(request.data);outer.calls.append(value)
                choices=value['format']['properties']['passage']['enum']
                reply={'passage':'/op' if outer.bad else choices[0]}
                return io.BytesIO(json.dumps(dict(model=documentation.MODEL,done=True,done_reason='stop',
                  prompt_eval_count=91,eval_count=7,message={'content':json.dumps(reply)})).encode())
        self.addCleanup(patch.stopall)
        patch.object(documentation,'local_slot',return_value=nullcontext()).start()
        # Use a real independent HTTP opener for test requests; mock only native.
        self.http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        patch.object(knowledge.urllib.request,'build_opener',return_value=Opener()).start()
        self.service=server.Service(('127.0.0.1',0),Assistant(self.state,stats,names,mods,self.model,RecipeBook()),self.key)
        self.thread=threading.Thread(target=self.service.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.service.shutdown();self.service.server_close();self.thread.join(5)

    def ask(self,message,principal=None,bad=False):
        raw=json.dumps(dict(principal=principal or str(uuid.uuid4()),name='ExampleOne',
          event=str(uuid.uuid4())+':1',message=message)).encode();stamp=str(int(time.time()))
        signature=hmac.new(self.key,stamp.encode()+b'\n'+raw,hashlib.sha256).hexdigest()
        req=urllib.request.Request('http://127.0.0.1:'+str(self.service.server_port)+'/v1/minecraft',raw,
          {'X-Vector-Time':stamp,'X-Vector-Signature':'0'*64 if bad else signature})
        with self.http.open(req,timeout=3) as response:return json.load(response)

    def test_signed_actual_http_uses_reviewed_model_and_native_stats_without_fallback(self):
        self.start()
        self.assertEqual(self.ask('ordinary text'),{'status':'ignored'})
        result=self.ask('hey Vector wie bekomme ich Glas?')
        self.assertIn('Sand',result['text']);self.assertTrue(result['text'].startswith('Hey ExampleOne,'))
        self.assertEqual(len(self.calls),1)
        self.assertIn('123',self.ask('hey Vector wer hat die meisten Mobkills?')['text'])
        self.assertIn('keine administrativen',self.ask('hey Vector zeige den Seed')['text'])
        self.assertIn('geprüfter Eintrag',self.ask('hey Vector wie geht Enderkristall?')['text'])
        self.assertEqual(len(self.calls),1)

    def test_http_preserves_own_context_and_rejects_untrusted_selection(self):
        self.start();principal=str(uuid.uuid4())
        self.ask('hey Vector wozu sind Partys gut?',principal)
        self.ask('hey Vector und wie gebe ich Mitgliedern Zugriff?',principal)
        payload=json.loads(self.calls[-1]['messages'][-1]['content'])
        self.assertIn('previous_question',payload)
        other=self.ask('hey Vector und wie genau?')
        self.assertIn('geprüfter Eintrag',other['text']);self.assertEqual(len(self.calls),2)
        self.bad=True
        result=self.ask('hey Vector wie bekomme ich Glas?')
        self.assertIn('nicht verfügbar',result['text']);self.assertNotIn('/op',result['text'])

    def test_http_requires_signature_and_ignores_unaddressed_requests(self):
        self.start()
        with self.assertRaises(urllib.error.HTTPError) as failure:self.ask('hey Vector Glas?',bad=True)
        self.assertEqual(failure.exception.code,401)
        self.assertEqual(self.ask('wie bekomme ich Glas?'),{'status':'ignored'})
        self.assertEqual(self.calls,[])


if __name__=='__main__':unittest.main()

