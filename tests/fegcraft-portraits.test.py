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

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'services/fegcraft-assistant'))
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
        answer=self.ask('bewerte Example3');self.assertIn('Sniper-Duell',answer);self.assertIn('30 Bogennutzungen',answer)
        self.assertNotIn('Bogenkills',answer);self.assertIn('keine Bogenkills',self.ask('wer hat die meisten Bogenkills?'))
        path=self.adv/(self.users[2]['uuid']+'.json');path.write_text('{bad')
        self.assertIsNone(advancement_summary(self.adv,self.users[2]['uuid']))
        self.assertNotIn('Sniper-Duell',self.ask('bewerte Example3'))
        path.unlink();path.symlink_to(self.cache);self.assertIsNone(advancement_summary(self.adv,self.users[2]['uuid']))

    def test_feelings_route_and_real_signed_stage_with_one_native_call(self):
        self.assertTrue(SOCIAL.search('wie fühlst du dich heute?'))
        self.assertTrue(SOCIAL.search('wie fuehlst du dich heute?'))
        catalog=ROOT/'services/fegcraft-assistant/public-knowledge.json';pack=ROOT/'services/fegcraft-assistant/knowledge-pack.json'
        knowledge=CompanionKnowledge('synthetic',documentation=DocumentationIndex(catalog,hashlib.sha256(catalog.read_bytes()).hexdigest()),pack=KnowledgePack(pack,hashlib.sha256(pack.read_bytes()).hexdigest()))
        (self.root/'run/secrets').mkdir(parents=True);(self.root/'run/secrets/vector_fegcraft_token').write_text('ab'*32);(self.root/'state').mkdir()
        state=State(self.root/'state/events.sqlite',bytes.fromhex('ab'*32));knowledge.usage=state.model_usage
        mods=self.root/'mods.json';mods.write_text('["travelersbackpack"]')
        ai=Assistant(state,self.stats,self.cache,mods,knowledge,portraits=self.portraits)
        service=Service(('127.0.0.1',0),ai,bytes.fromhex('ab'*32));thread=threading.Thread(target=service.serve_forever,daemon=True);thread.start()
        spec=importlib.util.spec_from_file_location('portrait_smoke',ROOT/'tests/fegcraft-portraits-smoke.py');smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)
        def native(schema,messages,predict,deadline,validate):
            value=validate({'answer':'Mein Redstone-Puls läuft rund. Und wie geht es dir?'});knowledge.usage(knowledge.model,100,18,True);return value
        try:
            with patch('documentation.local_slot',return_value=nullcontext()),patch.object(knowledge,'request',side_effect=native) as call,patch.dict(os.environ,{'VECTOR_FEGCRAFT_ADVANCEMENTS':'1'}),contextlib.redirect_stdout(io.StringIO()) as output:
                smoke.main(self.root,'http://127.0.0.1:'+str(service.server_address[1]))
            self.assertTrue(json.loads(output.getvalue())['passed']);self.assertEqual(call.call_count,1)
        finally:service.shutdown();service.server_close();thread.join(timeout=2)

    def test_rollout_only_relocates_owned_inputs_adds_readonly_advancements_and_flags(self):
        spec=importlib.util.spec_from_file_location('portrait_update',ROOT/'scripts/deploy/update-fegcraft-portraits.py');update=importlib.util.module_from_spec(spec);spec.loader.exec_module(update)
        profile={'services':{'assistant':{'image':'qualified','environment':{'VECTOR_FEGCRAFT_KNOWLEDGE':'5','VECTOR_FEGCRAFT_MOD_RECIPES_SHA256':'a'*64},
          'volumes':[dict(target=t,source='/old/'+str(i),read_only=True) for i,t in enumerate(('/code','/inputs/documentation.json','/inputs/mod-recipes.json','/inputs/knowledge-pack.json','/state'))]}}}
        original=copy.deepcopy(profile);adv='/opt/fegcraft-updated/data/world/players/advancements'
        changed=update.candidate(profile,Path('/new'),'a'*64,adv);self.assertEqual(original,profile)
        mount=changed['services']['assistant']['volumes'].pop();self.assertTrue(mount['read_only']);self.assertEqual(mount['source'],adv)
        for a,b in zip(changed['services']['assistant']['volumes'],profile['services']['assistant']['volumes']):
            if a['target']!='/state':a['source']=b['source']
        env=changed['services']['assistant']['environment'];self.assertEqual(env.pop('VECTOR_FEGCRAFT_PORTRAITS'),'1');self.assertEqual(env.pop('VECTOR_FEGCRAFT_ADVANCEMENTS'),'1')
        self.assertEqual(changed,original)
        with self.assertRaises(RuntimeError):update.candidate(profile,Path('/new'),'a'*64,'/private/logs')
        profile['services']['assistant']['volumes'][0]['read_only']=False
        with self.assertRaises(RuntimeError):update.candidate(profile,Path('/new'),'a'*64,None)


if __name__=='__main__':unittest.main()
