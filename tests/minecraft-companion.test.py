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
sys.path.insert(0,str(ROOT/'services/minecraft-assistant'))
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
        self.pack_path=ROOT/'services/minecraft-assistant/knowledge-pack.json';self.pack=KnowledgePack(self.pack_path,hashlib.sha256(self.pack_path.read_bytes()).hexdigest())
        catalog=ROOT/'services/minecraft-assistant/public-knowledge.json'
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
        secret=self.root/'slot-dsn';secret.write_text('postgresql://vector_minecraft_slot:synthetic@vector-postgres/vector');secret.chmod(0o400)
        state=State(self.root/'factory.sqlite',b'a'*32)
        kind=knowledge_for('5',state,secret,ROOT/'services/minecraft-assistant/public-knowledge.json',self.pack_path)
        self.assertIsInstance(kind,CompanionKnowledge)
        self.assertEqual(kind.model,'vector-qwen3-instruct2507:4b-q4km')
        self.assertEqual(kind.endpoint,'http://vector-local-inference:11434')
        self.assertEqual(kind.pack.sha256,hashlib.sha256(self.pack_path.read_bytes()).hexdigest())
        with patch.object(kind,'request',side_effect=AssertionError('party guidance invoked native')):
            self.assertIn('Spielergruppe',kind.answer_scoped('Wie erstelle ich eine Party für meinen Claim?',['openpartiesandclaims'],('discord',self.ids[0])))
        import server
        # Exercise the real entrypoint: mode5 must retain the exact installed-mod recipe renderer.
        with patch.dict(os.environ,{'VECTOR_MINECRAFT_KNOWLEDGE':'5','VECTOR_MINECRAFT_MOD_RECIPES_SHA256':'a'*64}), \
             patch('server.Path.read_text',return_value='ab'*32),patch('server.State'),patch('server.knowledge_for'), \
             patch('server.Assistant') as assistant,patch('server.Service'),patch('modrecipes.ModRecipes') as recipes,patch('server.os.umask'):
            server.main()
            recipes.assert_called_once_with('/inputs/mod-recipes.json','a'*64)
            self.assertIs(assistant.call_args.args[-2],recipes.return_value)

    def test_mode_six_is_explicit_and_keeps_local_role_catalog_and_usage(self):
        from dialogue import GroundedDialogue
        secret=self.root/'dialogue-slot';secret.write_text('postgresql://vector_minecraft_slot:synthetic@vector-postgres/vector');secret.chmod(0o400)
        state=State(self.root/'dialogue-factory.sqlite',b'a'*32)
        kind=knowledge_for('6',state,secret,ROOT/'services/minecraft-assistant/public-knowledge.json',self.pack_path)
        self.assertIsInstance(kind,CompanionKnowledge)
        dialogue=GroundedDialogue(kind)
        self.assertIs(dialogue.provider,kind)
        self.assertEqual(kind.context_tokens,4096)
        self.assertEqual(kind.usage,state.model_usage)
        import server
        with patch.dict(os.environ,{'VECTOR_MINECRAFT_KNOWLEDGE':'6','VECTOR_MINECRAFT_TIMEZONE':'Europe/Zurich'}), \
             patch('server.Path.read_text',return_value='ab'*32),patch('server.State'),patch('server.knowledge_for',return_value=kind), \
             patch('server.Assistant') as assistant,patch('server.Service'),patch('server.os.umask'):
            server.main()
            self.assertIsInstance(assistant.call_args.kwargs['dialogue'],GroundedDialogue)
            self.assertEqual(assistant.call_args.kwargs['dialogue_timezone'],'Europe/Zurich')

    def test_pack_integrity_and_independent_output_policy(self):
        bad=self.root/'bad.json';raw=json.loads(self.pack_path.read_bytes());raw['passages'][0]['texts']=['Nutze /op Example1']
        bad.write_text(json.dumps(raw))
        with self.assertRaises(ValueError):KnowledgePack(bad,hashlib.sha256(bad.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError,'CHECKSUM'):KnowledgePack(self.pack_path,'a'*64)


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
            self.assertIn('Du natürlich',self.ask('wer ist der beste Spieler auf dem Server?'))
            self.assertNotIn('Du natürlich',self.ask('wer hat die meisten Mobkills?'))
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



if __name__=='__main__':unittest.main()

