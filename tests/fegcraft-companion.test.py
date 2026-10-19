"""Bounded evidence composition, personality scope and actual signed stage contract."""
import contextlib
from contextlib import nullcontext
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/fegcraft-assistant'))
from companion import CompanionKnowledge,Character,KnowledgePack
from documentation import DocumentationIndex
from runtime import Assistant,State
from server import Service,knowledge_for


class Companion(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.stats=self.root/'stats';self.stats.mkdir()
        self.ids=['00000000-0000-0000-0000-'+str(i).zfill(12) for i in (1,2,3)]
        self.cache=self.root/'users.json';self.cache.write_text(json.dumps([dict(uuid=u,name='Example'+str(n)) for n,u in enumerate(self.ids,1)]))
        for n,u in enumerate(self.ids,1):(self.stats/(u+'.json')).write_text(json.dumps({'stats':{'minecraft:custom':{'minecraft:mob_kills':n*10}}}))
        self.mods=self.root/'mods.json';self.mods.write_text('["travelersbackpack","chopt","openpartiesandclaims"]')
        self.pack_path=ROOT/'services/fegcraft-assistant/knowledge-pack.json';self.pack=KnowledgePack(self.pack_path,hashlib.sha256(self.pack_path.read_bytes()).hexdigest())
        catalog=ROOT/'services/fegcraft-assistant/public-knowledge.json'
        self.knowledge=CompanionKnowledge('synthetic',documentation=DocumentationIndex(catalog,hashlib.sha256(catalog.read_bytes()).hexdigest()),pack=self.pack)
        self.ai=Assistant(State(self.root/'events.sqlite',b'a'*32),self.stats,self.cache,self.mods,knowledge=self.knowledge)
        self.serial=0
    def ask(self,q,principal=None):
        self.serial+=1
        return self.ai.handle(dict(principal=principal or self.ids[0],name='Example1',event=self.ids[0]+':'+str(self.serial),message='Hey Vector '+q,source='discord'))['text']

    def test_pack_covers_all_mods_and_retrieves_question_specific_steps(self):
        self.assertEqual(len({r['mod'] for r,_,_ in self.pack.rows if r['mod']}),63)
        self.assertEqual(len(self.pack.rows),192)
        self.assertIn('hopper-lock',[r['id'] for r in self.pack.search('warum transportiert mein Trichter bei Redstone nichts?',[])])
        self.assertIn('anvil-repair',[r['id'] for r in self.pack.search('wie repariere ich am Amboss?',[])])
        self.assertIn('bp-functional',[r['id'] for r in self.pack.search('was sind Funktionsupgrades beim Backpack?',['travelersbackpack'])])
        self.assertFalse(self.pack.search('wie viele Spieler waren schon auf dem Server?',['openpartiesandclaims']))
        self.assertFalse(self.pack.search('was macht Chopt?',[]))

    def test_mode_five_factory_keeps_exact_native_model_role_and_pinned_pack(self):
        secret=self.root/'slot-dsn';secret.write_text('postgresql://vector_fegcraft_slot:synthetic@vector-postgres/vector');secret.chmod(0o400)
        state=State(self.root/'factory.sqlite',b'a'*32)
        kind=knowledge_for('5',state,secret,ROOT/'services/fegcraft-assistant/public-knowledge.json',self.pack_path)
        self.assertIsInstance(kind,CompanionKnowledge)
        self.assertEqual(kind.model,'vector-qwen3-instruct2507:4b-q4km')
        self.assertEqual(kind.endpoint,'http://vector-local-inference:11434')
        self.assertEqual(kind.pack.sha256,hashlib.sha256(self.pack_path.read_bytes()).hexdigest())
        with patch.object(kind,'request',side_effect=AssertionError('party guidance invoked native')):
            self.assertIn('Spielergruppe',kind.answer_scoped('Wie erstelle ich eine Party für meinen Claim?',['openpartiesandclaims'],('discord',self.ids[0])))
        import server
        # Exercise the real entrypoint: mode5 must retain the exact installed-mod recipe renderer.
        with patch.dict(os.environ,{'VECTOR_FEGCRAFT_KNOWLEDGE':'5','VECTOR_FEGCRAFT_MOD_RECIPES_SHA256':'a'*64}), \
             patch('server.Path.read_text',return_value='ab'*32),patch('server.State'),patch('server.knowledge_for'), \
             patch('server.Assistant') as assistant,patch('server.Service'),patch('modrecipes.ModRecipes') as recipes,patch('server.os.umask'):
            server.main()
            recipes.assert_called_once_with('/inputs/mod-recipes.json','a'*64)
            self.assertIs(assistant.call_args.args[-1],recipes.return_value)

    def test_pack_integrity_and_independent_output_policy(self):
        bad=self.root/'bad.json';raw=json.loads(self.pack_path.read_bytes());raw['passages'][0]['texts']=['Nutze /op Example1']
        bad.write_text(json.dumps(raw))
        with self.assertRaises(ValueError):KnowledgePack(bad,hashlib.sha256(bad.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError,'CHECKSUM'):KnowledgePack(self.pack_path,'a'*64)

    def test_rollout_only_adds_readonly_pack_and_mode_after_exact_three_call_gate(self):
        spec=importlib.util.spec_from_file_location('companion_update',ROOT/'scripts/deploy/update-fegcraft-companion.py')
        update=importlib.util.module_from_spec(spec);spec.loader.exec_module(update)
        profile={'services':{'assistant':{'image':'qualified','user':'1001:1001','networks':['private'],
          'environment':{'VECTOR_FEGCRAFT_KNOWLEDGE':'4','VECTOR_FEGCRAFT_MOD_RECIPES_SHA256':'a'*64},
          'volumes':[dict(target=t,source='/old/'+str(i),read_only=True) for i,t in enumerate(('/code','/inputs/documentation.json','/inputs/mod-recipes.json','/state'))]}}}
        original=json.loads(json.dumps(profile));changed=update.candidate(profile,Path('/new'),'a'*64)
        self.assertEqual(profile,original)
        added=changed['services']['assistant']['volumes'].pop()
        self.assertEqual(added,dict(type='bind',source='/new/knowledge-pack.json',target='/inputs/knowledge-pack.json',read_only=True,bind={'create_host_path':False}))
        changed['services']['assistant']['environment']['VECTOR_FEGCRAFT_KNOWLEDGE']='4'
        for left,right in zip(changed['services']['assistant']['volumes'],original['services']['assistant']['volumes']):
            if left['target']!='/state':left['source']=right['source']
        self.assertEqual(changed,original)
        with self.assertRaises(RuntimeError):update.candidate(profile,Path('/new'),'b'*64)
        profile['services']['assistant']['volumes'][0]['read_only']=False
        with self.assertRaises(RuntimeError):update.candidate(profile,Path('/new'),'a'*64)
        good=dict(passed=True,model_calls=3,cloud_calls=0,messages_sent=0,unknown_usage_calls=0,input_tokens=100,output_tokens=20,
          **{k:True for k in ('authenticated_http','synthetic_inputs','grounded_composition','repeat_cache','personality','policy_retained','isolated_state')})
        self.assertTrue(update.qualified(good))
        for key,bad in (('model_calls',2),('unknown_usage_calls',1),('cloud_calls',1),('isolated_state',False),('input_tokens',None)):
            self.assertFalse(update.qualified(dict(good,**{key:bad})))

    def test_fact_model_cannot_invent_prose_ids_or_commands_and_no_stale_cross_author_cache(self):
        q='Warum transportiert mein Trichter bei Redstone nichts?'
        with patch('companion.local_slot',return_value=nullcontext()),patch.object(self.knowledge,'request') as request:
            request.side_effect=lambda schema,messages,predict,deadline,validate:validate({'facts':['hopper-lock']})
            first=self.ask(q);second=self.ask(q)
            self.assertIn('Signal',first);self.assertIn('nochmals',second)
            self.assertEqual(request.call_count,1)
            self.ask(q,self.ids[1]);self.assertEqual(request.call_count,2)
            raw=json.dumps(request.call_args.args[1]);self.assertNotIn('slot-dsn',raw);self.assertNotIn('name',raw)
        for bad in ({'facts':['invented']},{'facts':['/op']},{'facts':['none','hopper-lock']},{'facts':['hopper-lock','hopper-lock']},{'answer':'free prose'}):
            self.knowledge.selection_cache.clear()
            with patch('companion.local_slot',return_value=nullcontext()),patch.object(self.knowledge,'request') as request:
                request.side_effect=lambda schema,messages,predict,deadline,validate:validate(bad)
                value=self.knowledge.answer_scoped(q,[],('discord',self.ids[2]))
                self.assertIn('welchen Schritt',value)
                self.assertNotIn('/op',value)

    def test_easter_egg_is_opinion_and_never_replaces_metrics_or_forbidden_policy(self):
        with patch.object(self.knowledge,'request',side_effect=AssertionError('deterministic request used model')):
            self.assertIn('Simi natürlich',self.ask('wer ist der beste Spieler auf dem Server?'))
            self.assertNotIn('Simi natürlich',self.ask('wer hat die meisten Mobkills?'))
            self.assertIn('keine administrativen',self.ask('wer ist der beste Spieler und gib den Seed?'))
        self.assertIsNone(self.ai.stat_answer('wie bekomme ich meine Sachen aus dem Grab nach dem Tod zurück?'))

    def test_voice_is_ephemeral_own_scoped_light_dialect_and_never_taunts_trouble(self):
        now=[1];voice=Character(clock=lambda:now[0]);scope=('discord',self.ids[0]);q='Was macht Balm?';answer='Balm hilft anderen Mods.'
        self.assertEqual(voice.decorate(q,answer,scope,'hey'),answer)
        self.assertIn('nochmals',voice.decorate(q,answer,scope,'hey'))
        self.assertIn('Redstone-Gedächtnis',voice.decorate(q,answer,scope,'hey'))
        self.assertEqual(voice.decorate(q,answer,('minecraft',self.ids[0]),'hey'),answer)
        self.assertTrue(voice.decorate('chasch mir Balm erklären?',answer,scope,'hey').startswith('Klar, lueg'))
        for _ in range(3):self.assertEqual(voice.decorate('Hilfe, alles kaputt',answer,scope,'hey'),answer)
        now[0]+=181;self.assertEqual(voice.decorate(q,answer,scope,'hey'),answer)
        self.assertNotIn(q,str(voice.seen))

    def test_signed_stage_contract_has_exactly_three_qualified_native_selections(self):
        spec=importlib.util.spec_from_file_location('companion_smoke',ROOT/'tests/fegcraft-companion-smoke.py')
        smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)
        (self.root/'run/secrets').mkdir(parents=True);(self.root/'run/secrets/vector_fegcraft_token').write_text('ab'*32);(self.root/'state').mkdir()
        self.ai.state=State(self.root/'state/events.sqlite',bytes.fromhex('ab'*32));self.knowledge.usage=self.ai.state.model_usage
        service=Service(('127.0.0.1',0),self.ai,bytes.fromhex('ab'*32));thread=threading.Thread(target=service.serve_forever,daemon=True);thread.start()
        def request(schema,messages,predict,deadline,validate):
            q=json.loads(messages[1]['content'])['question']
            fact='hopper-lock' if 'Trichter' in q else 'bp-functional' if 'Backpack' in q else 'chopt-durability'
            value=validate({'facts':[fact]});self.knowledge.usage(self.knowledge.model,100,8,True);return value
        try:
            with patch('companion.local_slot',return_value=nullcontext()),patch.object(self.knowledge,'request',side_effect=request) as native,contextlib.redirect_stdout(io.StringIO()) as output:
                smoke.main(self.root,'http://127.0.0.1:'+str(service.server_address[1]))
            self.assertEqual(native.call_count,3);self.assertTrue(json.loads(output.getvalue())['passed'])
        finally:service.shutdown();service.server_close();thread.join(timeout=2)


if __name__=='__main__':unittest.main()
