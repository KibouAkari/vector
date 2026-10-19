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
from companion import CompanionKnowledge,KnowledgePack
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
        self.assertIn('Example1',self.ask('bin ich ein guter Spieler?',self.users[0]['uuid']))
        self.assertIn('Example1',self.ask('und er?'))
        self.assertIn('eindeutigen',self.ask('und er?',scope=('discord',self.users[0]['uuid'])))
        self.assertIn('Minecraft-Spielernamen',self.ask('was hältst du von mir?',scope=('discord','unlinked')))
        self.now[0]+=181;self.assertIn('eindeutigen',self.ask('und er?'))

    def test_unknown_or_partial_data_never_fabricates_portraits_or_victims(self):
        self.assertIn('eindeutigen',self.ask('bewerte UnknownName'))
        death=self.ask('bewerte Example2');self.assertNotIn('Example1',death);self.assertNotIn('zum Opfer',death)
        (self.stats/(self.users[2]['uuid']+'.json')).write_text('{bad')
        self.assertIn('unvollständig',self.ask('bewerte Example1'))

    def test_advancements_and_bow_usage_never_become_weapon_kills_or_live_events(self):
        path=self.adv/(self.users[2]['uuid']+'.json');value=json.loads(path.read_bytes())
        value['examplemod:recipes/test']={'done':True,'criteria':{}};path.write_text(json.dumps(value))
        self.assertEqual(advancement_summary(self.adv,self.users[2]['uuid'])['count'],1)
        answer=self.ask('bewerte Example3');self.assertIn('Sniper-Duell',answer);self.assertIn('30 Bogennutzungen',answer)
        self.assertNotIn('Bogenkills',answer);self.assertIn('keine Bogenkills',self.ask('wer hat die meisten Bogenkills?'))
        path=self.adv/(self.users[2]['uuid']+'.json');path.write_text('{bad')
        self.assertIsNone(advancement_summary(self.adv,self.users[2]['uuid']))
        self.assertNotIn('Sniper-Duell',self.ask('bewerte Example3'))
        path.unlink();path.symlink_to(self.cache);self.assertIsNone(advancement_summary(self.adv,self.users[2]['uuid']))




if __name__=='__main__':unittest.main()
