"""Public game evidence only; synthetic players and native adapter stubs."""
import contextlib
from contextlib import nullcontext
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'services/minecraft-assistant'))
from portraits import PlayerPortraits,advancement_summary,targets
from companion import CompanionKnowledge,KnowledgePack,Character
from documentation import DocumentationIndex,SOCIAL
from runtime import Assistant,State
from server import Service


class Portraits(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.stats=self.root/'stats';self.stats.mkdir();self.adv=self.root/'advancements';self.adv.mkdir()
        self.users=[dict(uuid='00000000-0000-0000-0000-'+str(n).zfill(12),name='Example'+str(n)) for n in (1,2,3)]
        self.cache=self.root/'users.json';self.cache.write_text(json.dumps(self.users))
        for n,user in enumerate(self.users,1):
            (self.stats/(user['uuid']+'.json')).write_text(json.dumps({'stats':{'minecraft:custom':{
             'minecraft:mob_kills':1000 if n==1 else n*10,'minecraft:player_kills':200 if n==1 else 0,
             'minecraft:deaths':220 if n==2 else 5,'minecraft:play_time':n*72000,'minecraft:walk_one_cm':n*100000},
             'minecraft:used':{'minecraft:bow':n*10,'minecraft:stone':n*1000}}}))
            (self.adv/(user['uuid']+'.json')).write_text(json.dumps({'minecraft:adventure/sniper_duel':{'done':True,'criteria':{'event':'2026-10-19 00:00:00 +0000'}}}))
        self.now=[1];self.portraits=PlayerPortraits(self.stats,self.cache,self.adv,clock=lambda:self.now[0])
        self.scope=('minecraft',self.users[0]['uuid'])

    def ask(self,q,principal=None,scope=None):
        return self.portraits.answer(q,principal,scope or self.scope,('minecraft:stone',))

    def test_fresh_evidence_drives_portraits_for_all_players_not_hardcoded_names(self):
        first=self.ask('was hältst du von Example1?');self.assertIn('Endgegner',first);self.assertIn("1'000",first)
        self.assertIn('Respawn',self.ask('bewerte Example2'));self.assertIn('Architekt',self.ask('wie findest du Example3?'))
        path=self.stats/(self.users[0]['uuid']+'.json');value=json.loads(path.read_bytes())
        value['stats']['minecraft:custom']['minecraft:mob_kills']=800;path.write_text(json.dumps(value))
        self.assertIn('800',self.ask('was hältst du von Example1?'));self.assertNotIn("1'000",self.ask('was hältst du von Example1?'))
        self.assertTrue(all('Example' not in str(x) for x in self.portraits.context.values()))

    def test_ambiguous_names_clarify_and_aliases_are_unique_not_guessed_accounts(self):
        people=[dict(name='Fighter123',uuid='a'),dict(name='Builder909',uuid='b')]
        self.assertEqual(targets('was hältst du von fighter?',people),[people[0]])
        self.assertEqual(targets('bewerte Buildder909',people),[people[1]])
        self.assertEqual(len(targets('bewerte fighter',people+[dict(name='Fighter456',uuid='c')])),2)
        self.assertIn('eindeutigen',self.ask('bewerte Example'))
        self.assertIn('Example2',self.ask('gib mir eine Einschätzung von Example2',self.users[0]['uuid']))

    def test_authenticated_self_own_followup_expiry_and_discord_no_impersonation(self):
        self.assertTrue(self.ask('bin ich ein guter Spieler?',self.users[0]['uuid']).startswith('Du? '))
        self.assertIn('Example1',self.ask('und er?'))
        self.assertIn('eindeutigen',self.ask('und er?',scope=('discord',self.users[0]['uuid'])))
        self.assertIn('Minecraft-Spielernamen',self.ask('was hältst du von mir?',scope=('discord','unlinked')))
        self.now[0]+=181;self.assertIn('eindeutigen',self.ask('und er?'))

    def test_attached_names_short_questions_and_varied_evidence_based_voice(self):
        first=self.ask('was hältst du vonExample1?')
        second=self.ask('hältst du von Example1?')
        self.assertIn('Example1',first);self.assertIn('Example1',second)
        self.assertNotEqual(first,second)
        for text in (first,second):
            self.assertIn("1'000",text);self.assertIn('200',text)
            self.assertNotIn('Mein Spieleindruck:',text)
            self.assertLessEqual(len(text),390)
        self.assertIn('eindeutigen',self.ask('hältst du von UnknownPlayer?'))

    def test_rank_two_pvp_does_not_dominate_a_builder_traveler_profile(self):
        path=self.stats/(self.users[2]['uuid']+'.json');data=json.loads(path.read_bytes())
        data['stats']['minecraft:custom']['minecraft:player_kills']=50
        path.write_text(json.dumps(data))
        text=self.ask('was hältst du von Example3?')
        self.assertIn('Architekt',text)
        self.assertNotIn('Spielerkills',text)
        self.assertIn("3'000",text)

    def test_style_varies_after_chat_context_expires_without_storing_old_prose(self):
        first=self.ask('was hältst du von Example1?')
        self.now[0]+=181
        second=self.ask('was hältst du von Example1?')
        self.assertNotEqual(first,second)
        for text in (first,second):
            self.assertIn("1'000",text);self.assertIn('200',text)
        self.assertTrue(all(isinstance(value[0],int) for value in self.portraits.variants.values()))

    def test_portrait_voice_is_not_wrapped_in_stock_casual_prefix(self):
        mods=self.root/'mods.json';mods.write_text('[]')
        ai=Assistant(SimpleNamespace(admit=lambda *args:'accepted'),self.stats,self.cache,mods,
            knowledge=SimpleNamespace(character=Character(),friendly_statistics=True),portraits=self.portraits)
        text=ai.handle(dict(principal=self.users[0]['uuid'],name='Example1',source='minecraft',
            event=self.users[0]['uuid']+':1',message='Yoo Vector was hältst du von Example2?',block_items=['minecraft:stone']))['text']
        self.assertNotIn('Klar:',text);self.assertIn('Respawn',text)
        self.assertLessEqual(len(text),420)

    def test_combat_style_tracks_weapon_use_fresh_and_never_claims_accuracy(self):
        for identifier,label in [('minecraft:bow','Scharfschützen'),('minecraft:diamond_sword','Samurai'),
                ('minecraft:mace','Grobe'),('examplemod:iron_spear','Speerkämpfer')]:
            path=self.stats/(self.users[0]['uuid']+'.json')
            value=json.loads(path.read_bytes());value['stats']['minecraft:used']={identifier:250}
            path.write_text(json.dumps(value))
            text=self.ask('wie ist mein fighting style?',self.users[0]['uuid'])
            self.assertIn('250',text)
            self.assertIn(label.casefold(),text.casefold())
            self.assertIn('keine Trefferquote',text)
            self.assertLessEqual(len(text),350)
        self.assertIn('Speerkämpfer',self.ask('welche Waffe benutze ich in Minecraft?',self.users[0]['uuid']))
        value['stats']['minecraft:used']={'minecraft:bow':250,'minecraft:iron_sword':250}
        path.write_text(json.dumps(value))
        self.assertIn('gleichauf',self.ask('Kampfstil von Example1'))
        value['stats']['minecraft:used']={};path.write_text(json.dumps(value))
        self.assertIn('fehlen',self.ask('Kampfstil von Example1'))
        self.assertIn('Minecraft-Spielernamen',self.ask('mein Kampfstil?',scope=('discord','unlinked')))

    def test_unique_transposition_and_common_question_typo_keep_identity(self):
        people=[dict(name='ExampleOne',uuid='a'),dict(name='DifferentTwo',uuid='b')]
        self.assertEqual(targets('was hälst du von ExampelOne?',people),[people[0]])
        self.assertIn('Example1',self.ask('was hälst du von Example1?'))
        self.assertIn('eindeutigen',self.ask('was hälst du von UnknownPlayer?'))

    def test_unknown_or_partial_data_never_fabricates_portraits_or_victims(self):
        self.assertIn('eindeutigen',self.ask('bewerte UnknownName'))
        death=self.ask('bewerte Example2');self.assertNotIn('Example1',death);self.assertNotIn('zum Opfer',death)
        (self.stats/(self.users[2]['uuid']+'.json')).write_text('{bad')
        self.assertIn('unvollständig',self.ask('bewerte Example1'))

    def test_advancements_and_bow_usage_never_become_weapon_kills_or_live_events(self):
        path=self.adv/(self.users[2]['uuid']+'.json');value=json.loads(path.read_bytes())
        value['examplemod:recipes/test']={'done':True,'criteria':{}};path.write_text(json.dumps(value))
        self.assertEqual(advancement_summary(self.adv,self.users[2]['uuid'])['count'],1)
        answer=self.ask('bewerte Example3 mit seinem Bogen');self.assertIn('30 Bogennutzungen',answer)
        self.assertIn('Sniper-Duell',self.ask('bewerte Example3 nach Fortschritten'))
        self.assertNotIn('Bogenkills',answer);self.assertIn('keine Bogenkills',self.ask('wer hat die meisten Bogenkills?'))
        path=self.adv/(self.users[2]['uuid']+'.json');path.write_text('{bad')
        self.assertIsNone(advancement_summary(self.adv,self.users[2]['uuid']))
        self.assertNotIn('Sniper-Duell',self.ask('bewerte Example3'))
        path.unlink();path.symlink_to(self.cache);self.assertIsNone(advancement_summary(self.adv,self.users[2]['uuid']))




if __name__=='__main__':unittest.main()

