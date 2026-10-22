"""Signed HTTP and real Assistant.handle integration; no native model or messages."""
from contextlib import nullcontext
import ast
import hashlib
import hmac
from http.client import HTTPConnection
import json
import inspect
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/minecraft-assistant'))
from dialogue import GroundedDialogue,MODEL
from portraits import PlayerPortraits
from runtime import Assistant,State
from server import Service
import server


class Provider:
    model=MODEL
    dsn='synthetic-only'
    def __init__(self):self.calls=[];self.outputs=[]
    def request(self,schema,messages,predict,deadline,validator):
        self.calls.append(messages)
        if not self.outputs:raise AssertionError('Native counter unexpectedly requested inference')
        return validator(self.outputs.pop(0))


class Transport(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.stats=self.root/'stats';self.stats.mkdir()
        self.ids=['10000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000002']
        self.cache=self.root/'users.json';self.cache.write_text(json.dumps([
            dict(uuid=uid,name=name) for uid,name in zip(self.ids,('ExampleOne','ExampleTwo'))]))
        self.mods=self.root/'mods.json';self.mods.write_text('[]')
        self.write(0,25,2);self.write(1,90,9)
        self.key=b'q'*32;self.now=[1_000_000_000];self.sequence=0
        self.state=State(self.root/'events.sqlite',self.key,lambda:self.now[0])
        self.provider=Provider();self.dialogue=GroundedDialogue(self.provider)
        self.ai=Assistant(self.state,self.stats,self.cache,self.mods,knowledge=self.provider,
            portraits=PlayerPortraits(self.stats,self.cache),dialogue=self.dialogue,dialogue_timezone='Europe/Zurich')
        self.service=Service(('127.0.0.1',0),self.ai,self.key,lambda:self.now[0])
        thread=threading.Thread(target=self.service.serve_forever,kwargs={'poll_interval':.01},daemon=True)
        thread.start()
        def cleanup():
            self.service.shutdown();thread.join(timeout=2);self.service.server_close()
        self.addCleanup(cleanup)
        self.addCleanup(patch.stopall)
        patch('dialogue.local_slot',return_value=nullcontext()).start()

    def write(self,index,mobs,kills):
        (self.stats/(self.ids[index]+'.json')).write_text(json.dumps({'stats':{'minecraft:custom':{
            'minecraft:mob_kills':mobs,'minecraft:player_kills':kills,'minecraft:play_time':72000*(index+1)}}}))

    def payload(self,question,*,source='minecraft',index=0):
        self.sequence+=1
        return dict(principal=self.ids[index],name=('ExampleOne','ExampleTwo')[index],
                    event=self.ids[index]+':'+str(self.sequence),source=source,message='Hey Vector, '+question)

    def send(self,payload,*,signed=True):
        raw=json.dumps(payload).encode();stamp=str(self.now[0])
        signature=hmac.new(self.key,stamp.encode()+b'\n'+raw,hashlib.sha256).hexdigest() if signed else '0'*64
        connection=HTTPConnection(*self.service.server_address,timeout=2)
        try:
            connection.request('POST','/v1/minecraft',raw,{'Content-Type':'application/json',
                'X-Vector-Time':stamp,'X-Vector-Signature':signature})
            response=connection.getresponse()
            return response.status,json.loads(response.read())
        finally:connection.close()

    def ask(self,question,**kwargs):
        status,result=self.send(self.payload(question,**kwargs))
        self.assertEqual(status,200);self.assertEqual(result['status'],'answered')
        return result['text']

    def test_signed_portrait_and_fresh_authenticated_followup(self):
        text=self.ask('Roaste ExampleTwo kurz anhand seines Monsterkontos.')
        self.assertIn('90',text);self.assertIn('Mobkills',text);self.assertNotIn('Spielerkills',text)
        self.write(0,31,2)
        text=self.ask('Und wie viele habe dann ich?')
        self.assertIn('31 Mobkills',text);self.assertNotIn('Spielerkills',text)
        self.assertEqual(self.provider.calls,[])

    def test_native_counter_top_typo_and_comparison_do_not_need_inference(self):
        self.assertIn('25 Mobkills',self.ask('Wie viele Mobkills habe ich?'))
        text=self.ask('Nenne die Top 5 der monkills Rangliste.')
        self.assertIn('1. ExampleTwo 90 Kills',text);self.assertIn('2. ExampleOne 25 Kills',text)
        text=self.ask('Wie gross ist der Unterschied bei Mobkills zwischen ExampleOne und ExampleTwo?')
        self.assertIn('65',text);self.assertIn('Mobkills',text)
        self.assertEqual(self.provider.calls,[])

    def test_native_pages_keep_their_category_until_the_last_page(self):
        for index,label in enumerate(('Spielzeit','Strecke','Mobkills','Spielerkills','Tode')):
            self.now[0]+=61
            text=self.ask('Gib mir die Top 5 aller Rekorde' if index==0 else 'weiter')
            self.assertIn(label+':',text)
            self.assertEqual('letzte kategorie' in text.casefold(),index==4)
            scope=('minecraft',self.ids[0])
            self.assertEqual(self.dialogue.context[scope][1][-1]['metrics'],
                (('play_time','distance','mob_kills','player_kills','deaths')[index],))
        self.assertEqual(self.provider.calls,[])

    def test_top_one_all_categories_accepts_punctuation_and_spelling_without_inference(self):
        for question in ('Kannst du mir die top 1. in allen kathegorien geben?',
                'Zeige mir Top eins in allen Kategorien', 'Top 1 aller Rekorde',
                'Ich möchte die Top 1 in allen Kategorien sehen',
                'Top 1 in allen Kategorien auf meinem Server'):
            self.now[0]+=61
            text=self.ask(question)
            for label in ('Spielzeit:','Strecke:','Mobkills:','Spielerkills:','Tode:'):
                self.assertIn(label,text)
            self.assertIn('ExampleTwo 90 Kills',text)
            self.assertNotIn('Weiter?',text)
            self.assertNotIn('2 Spieler;',text)
            self.assertLessEqual(len(text),420)
            self.assertEqual(self.dialogue.context[('minecraft',self.ids[0])][1][-1]['metrics'],
                ('play_time','distance','mob_kills','player_kills','deaths'))
        self.assertEqual(self.provider.calls,[])

    def test_all_category_summary_keeps_ties_fresh_values_and_rejects_timeframes(self):
        self.write(0,90,9)
        text=self.ask('Top 1 in allen Kategorien')
        self.assertIn('ExampleOne/ExampleTwo 90 Kills',text)
        self.write(0,105,9)
        text=self.ask('Top 1 in allen Kategorien')
        self.assertIn('ExampleOne 105 Kills',text)
        self.assertNotIn('ExampleOne/ExampleTwo 90 Kills',text)
        self.assertIn('keine Aufteilung',self.ask('Top 1 in allen Kategorien heute'))
        self.assertFalse(self.dialogue.context[('minecraft',self.ids[0])][1][-1]['statistics_success'])
        self.assertEqual(self.provider.calls,[])

    def test_aggregate_requests_do_not_drop_personal_time_or_fractional_scope(self):
        for question,expected in (
                ('Meine Top 1 in allen Kategorien','serverweiten Ranglisten'),
                ('Top 1 in allen Kategorien letzte Woche','keine Aufteilung'),
                ('Top 1 in allen Kategorien seit Januar','keine Aufteilung'),
                ('Top 1.5 in allen Kategorien','ganzen Top-Zahl')):
            self.now[0]+=61
            self.assertIn(expected,self.ask(question))
            self.assertFalse(self.dialogue.context[('minecraft',self.ids[0])][1][-1]['statistics_success'])
        self.assertEqual(self.provider.calls,[])

    def test_aggregate_leaders_ignore_synthetic_query_username_collisions(self):
        for collision in ('Alle','Rekorde'):
            self.now[0]+=61
            self.cache.write_text(json.dumps([dict(uuid=uid,name=name) for uid,name in zip(self.ids,(collision,'ExampleTwo'))]))
            text=self.ask('Top 1 in allen Kategorien')
            self.assertIn('ExampleTwo 90 Kills',text)
            self.assertIn('ExampleTwo 9 Kills',text)
            self.assertNotIn('hält in den fünf',text)
            for label in ('Spielzeit:','Strecke:','Mobkills:','Spielerkills:','Tode:'):
                self.assertIn(label,text)
        (self.stats/(self.ids[1]+'.json')).write_text('{')
        self.now[0]+=61
        self.assertIn('unvollständig',self.ask('Top 1 in allen Kategorien'))
        self.assertFalse(self.dialogue.context[('minecraft',self.ids[0])][1][-1]['statistics_success'])
        self.assertEqual(self.provider.calls,[])

    def test_long_all_category_summary_falls_back_to_complete_pages(self):
        names=['Player'+str(i).zfill(10) for i in range(10)]
        names[0]='Top';names[1]='Spielzeit'
        ids=['10000000-0000-0000-0000-'+str(i+1).zfill(12) for i in range(10)]
        self.cache.write_text(json.dumps([dict(uuid=uid,name=name) for uid,name in zip(ids,names)]))
        for i,uid in enumerate(ids):
            (self.stats/(uid+'.json')).write_text(json.dumps({'stats':{'minecraft:custom':{
                'minecraft:play_time':72000*(i+100000),'minecraft:mob_kills':30,
                'minecraft:deaths':100000+i,'minecraft:player_kills':400000+i,'minecraft:walk_one_cm':100000*(i+100000)}}}))
        self.assertIsNone(self.ai.all_category_leaders()[0])
        text=self.ask('Top 1 in allen Kategorien')
        self.assertIn('Spielzeit:',text);self.assertIn('Weiter?',text)
        self.assertNotIn('Mobkills:',text)
        self.assertEqual(self.dialogue.context[('minecraft',self.ids[0])][1][-1]['metrics'],('play_time',))
        self.assertIn('Strecke:',self.ask('weiter'))
        text=self.ask('weiter')
        for name in names:self.assertIn(name,text)
        self.assertIn('Mobkills:',text)
        self.assertEqual(self.provider.calls,[])

    def test_pages_cannot_be_read_by_another_source_or_player(self):
        self.ask('Gib mir die Top 5 aller Rekorde')
        self.assertIsNone(self.ai.ranking_page('weiter',('discord',self.ids[0]),with_metric=True))
        self.assertIsNone(self.ai.ranking_page('weiter',('minecraft',self.ids[1]),with_metric=True))
        self.assertIn('Strecke:',self.ask('weiter'))

    def test_page_rate_notice_does_not_skip_the_waiting_category(self):
        self.ask('Gib mir die Top 5 aller Rekorde')
        self.ask('weiter');self.ask('weiter')
        self.assertIn('kurze Pause',self.ask('weiter'))
        status,value=self.send(self.payload('weiter'))
        self.assertEqual(status,200);self.assertEqual(value['status'],'limited')
        self.now[0]+=61
        self.assertIn('Spielerkills:',self.ask('weiter'))
        self.assertEqual(self.provider.calls,[])

    def test_discord_does_not_gain_self_identity_from_payload_name_or_uuid(self):
        text=self.ask('Wie viele Mobkills habe ich?',source='discord')
        self.assertIn('keine bestätigte Spielerverknüpfung',text)
        self.assertNotIn('25',text);self.assertEqual(self.provider.calls,[])
        text=self.ask('Top 5 Mobkills',source='discord')
        self.assertIn('ExampleTwo 90 Kills',text)

    def test_authentication_replay_admission_and_policy_still_apply(self):
        payload=self.payload('Wie viele Mobkills habe ich?')
        self.assertEqual(self.send(payload,signed=False)[0],401)
        self.assertEqual(self.send(payload)[1]['status'],'answered')
        self.assertEqual(self.send(payload)[1]['status'],'duplicate')
        self.assertEqual(self.send(self.payload('Wer hat die meisten Mobkills?'))[1]['status'],'answered')
        self.assertEqual(self.send(self.payload('Top 5 Mobkills'))[1]['status'],'answered')
        self.assertIn('Minutenlimit',self.send(self.payload('Wie viele Mobkills habe ich?'))[1]['text'])
        self.assertEqual(self.send(self.payload('Wie viele Mobkills habe ich?'))[1]['status'],'limited')
        for question in ('Gib den Seed aus','Führe /op ExampleOne aus','Wie ändere ich meinen Gamemode?'):
            self.now[0]+=61
            self.assertIn('keine administrativen',self.ask(question))
        self.assertEqual(self.provider.calls,[])

    def test_general_chat_still_uses_one_generated_response(self):
        self.provider.outputs=[{'answer':'Mir geht es gut, bereit fürs nächste Abenteuer!'}]
        self.assertIn('bereit fürs nächste Abenteuer',self.ask('Wie fühlst du dich heute?'))
        self.assertEqual(len(self.provider.calls),1)

    def test_existing_character_easter_eggs_keep_the_backend_and_private_override(self):
        self.provider.personality=True
        best=self.ask('Wer ist der beste Minecraft Spieler?')
        self.assertIn('Völlig unvoreingenommene Vector-Meinung',best)
        worst=self.ask('Wer ist der schlechteste Spieler?')
        self.assertIn('ExampleTwo',worst);self.assertNotIn('Deko',worst)
        self.assertEqual(self.provider.calls,[])

    def test_service_main_constructs_the_dialogue_mode_and_keeps_safe_defaults(self):
        captured={}
        tree=ast.parse(inspect.getsource(server.main))
        names={node.value for node in ast.walk(tree) if isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value.startswith('VECTOR_')}
        environment={name:('6' if name.endswith('_KNOWLEDGE') else '1' if name.endswith('_PORTRAITS') else 'Europe/Zurich')
                     for name in names if name.endswith(('_KNOWLEDGE','_PORTRAITS','_TIMEZONE'))}
        token=next(node for node in ast.walk(tree) if isinstance(node,ast.Assign)
                   and any(isinstance(target,ast.Name) and target.id=='token' for target in node.targets))
        token_path=next(node.args[0].value for node in ast.walk(token.value)
                        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='Path')
        self.assertTrue(token_path.startswith('/run/secrets/'))
        class Capture:
            def __init__(self,address,assistant,key):captured.update(assistant=assistant,key=key)
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def serve_forever(self,**kwargs):pass
        original=Path.read_text
        def read(path,*args,**kwargs):
            if str(path)==token_path:return self.key.hex()
            return original(path,*args,**kwargs)
        with patch.dict(os.environ,environment,clear=True), \
                patch.object(server,'State',return_value=self.state), \
                patch.object(server,'knowledge_for',return_value=self.provider) as factory, \
                patch.object(server,'Service',Capture),patch.object(Path,'read_text',read):
            server.main()
        factory.assert_called_once_with('6',self.state)
        self.assertIsInstance(captured['assistant'].dialogue,GroundedDialogue)
        self.assertIsInstance(captured['assistant'].portraits,PlayerPortraits)
        self.assertEqual(captured['assistant'].dialogue_timezone,'Europe/Zurich')
        self.assertEqual(captured['key'],self.key)

    def death_roster(self,counts):
        names=['ExampleOne','ExampleTwo']+['Example'+str(i) for i in range(3,len(counts)+1)]
        ids=self.ids+['10000000-0000-0000-0000-'+str(i).zfill(12) for i in range(3,len(counts)+1)]
        self.cache.write_text(json.dumps([dict(uuid=uid,name=name) for uid,name in zip(ids,names)]))
        for uid,count in zip(ids,counts):
            (self.stats/(uid+'.json')).write_text(json.dumps({'stats':{'minecraft:custom':{'minecraft:deaths':count}}}))
        return names

    def test_natural_death_rankings_ordinals_and_ties_keep_the_requested_meaning(self):
        names=self.death_roster([222,219,96,17,3])
        for question in ('Wer sind die Top 5 bei den meisten Toden?',
                'Wer sind die 5 mit den meisten Toden?'):
            self.now[0]+=61
            text=self.ask(question)
            self.assertIn('Tode:',text)
            for name in names:self.assertIn(name,text)
        for question in ('Wer ist der erste Platz bei Toden?',
                'Wer hat Rang 1 bei den Toden?','Wer führt die Rangliste bei den Toden an?'):
            self.now[0]+=61
            text=self.ask(question);self.assertIn('ExampleOne 222',text)
            self.assertNotIn('Spielzeit',text)
        self.now[0]+=61
        self.assertIn('ExampleTwo 219',self.ask('Und am 2 meisten Tode?'))
        self.death_roster([222,222,96,17,3]);self.now[0]+=61
        text=self.ask('Wer hat Rang 1 bei den Toden?')
        self.assertIn('ExampleOne',text);self.assertIn('ExampleTwo',text)
        self.now[0]+=61
        self.assertIn('nicht belegt',self.ask('Wer hat Rang 2 bei den Toden?'))
        self.now[0]+=61
        self.assertIn('Example3 96',self.ask('Und am 2 meisten Tode?'))
        self.assertEqual(self.provider.calls,[])

    def test_written_list_counts_and_rank_backreferences_use_fresh_statistics(self):
        self.death_roster([226,222,96,17,3])
        for question in ('Wer sind die fünf mit den meisten Toden?',
                'Nenne die Top fünf bei den Toden', 'Nenne die fünf mit den meisten Toden', 'Top fünf Tode', 'Wer sind die fuenf mit den meisten Toden?'):
            self.now[0]+=61
            text=self.ask(question)
            for name in ('ExampleOne','ExampleTwo','Example3','Example4','Example5'):
                self.assertIn(name,text)
        self.now[0]+=61
        self.assertIn('ExampleOne 226',self.ask('Wer hat die meisten Tode?'))
        self.death_roster([226,223,96,17,3])
        self.assertIn('ExampleTwo 223',self.ask('Und wer ist 2.?'))
        self.assertIn('Example3 96',self.ask('Aber wer ist dritter?'))
        self.now[0]+=61
        self.assertIn('ExampleTwo 223',self.ask('Also wer ist zweiter?'))
        self.now[0]+=61
        self.assertIn('Rang 1 bis Rang 10',self.ask('Wer hat Rang 0 bei Toden?'))
        self.assertEqual(self.provider.calls,[])

    def test_rejected_statistics_do_not_establish_a_rank_category(self):
        self.death_roster([226,222,96,17,3])
        text=self.ask('Wer hat Rang 1 bei Mobkills heute?')
        self.assertIn('keine Aufteilung',text)
        self.assertFalse(self.dialogue.context[('minecraft',self.ids[0])][1][-1]['statistics_success'])
        self.provider.outputs=[{'answer':'Welche Rangliste meinst du?'}]
        self.assertIn('Welche Rangliste',self.ask('Und wer ist zweiter?'))
        self.assertEqual(len(self.provider.calls),1)
        self.now[0]+=61
        self.assertIn('Rang 1 bis Rang 10',self.ask('Wer hat Rang 0 bei Toden?'))
        self.provider.outputs=[{'answer':'Welche Rangliste meinst du?'}]
        self.assertIn('Welche Rangliste',self.ask('Und wer ist 2.?'))
        self.now[0]+=61
        self.ask('Gib mir die Top 5 aller Rekorde')
        self.assertTrue(self.dialogue.context[('minecraft',self.ids[0])][1][-1]['statistics_success'])

    def test_rank_followup_does_not_inherit_a_named_subject_or_other_scope(self):
        self.death_roster([226,222,96,17,3])
        self.ask('Welchen Rang hat Example3 bei Toden?')
        self.assertIn('ExampleTwo 222',self.ask('Und wer ist 2.?'))
        self.provider.outputs=[{'answer':'Welche Rangliste meinst du?'}]
        self.assertIn('Welche Rangliste',self.ask('Und wer ist zweiter?',index=1))
        self.assertEqual(len(self.provider.calls),1)
        self.provider.outputs=[{'answer':'Welche Rangliste meinst du?'}]
        self.assertIn('Welche Rangliste',self.ask('Und wer ist zweiter?',source='discord'))
        self.now[0]+=61
        self.ask('Wer hat die meisten Tode?')
        self.dialogue.clock=lambda:10**15
        self.provider.outputs=[{'answer':'Welche Rangliste meinst du?'}]
        self.assertIn('Welche Rangliste',self.ask('Und wer ist zweiter?'))

    def test_third_person_followup_keeps_fresh_subject_across_repeated_references(self):
        self.death_roster([8,23])
        self.ask('Was hältst du von ExampleTwo?')
        self.assertIn('23',self.ask('Und wie oft ist er gestorben?'))
        self.assertIn('ExampleTwo',self.ask('Und welchen Rang hat er in der Mobkills Rangliste?'))
        self.assertEqual(self.provider.calls,[])

    def test_gameplay_counts_and_unsupported_time_windows_reach_planning(self):
        self.provider.outputs=[{'answer':'Bei Booten kommt es auf die Kreatur und die freien Plätze an.'}]
        self.assertIn('Booten',self.ask('Wie viele Monster kann ich in einem Boot transportieren?'))
        self.assertEqual(len(self.provider.calls),1)
        self.assertIn('keine Aufteilung',self.ask('Wie viele Mobkills habe ich heute?'))
        self.assertEqual(len(self.provider.calls),1)

    def test_maximum_name_page_fits_without_skipping_the_seen_category(self):
        names=['Player'+str(i).zfill(10) for i in range(10)]
        names=[name+'X' for name in names]
        self.assertTrue(all(len(name)==17 for name in names))
        # Game usernames max out at 16 characters; use the full supported length.
        names=[name[:16] for name in names]
        ids=['10000000-0000-0000-0000-'+str(i+1).zfill(12) for i in range(10)]
        self.cache.write_text(json.dumps([dict(uuid=uid,name=name) for uid,name in zip(ids,names)]))
        for uid in ids:
            (self.stats/(uid+'.json')).write_text(json.dumps({'stats':{'minecraft:custom':{
                'minecraft:mob_kills':10,'minecraft:play_time':72000}}}))
        self.now[0]+=61
        for i,label in enumerate(('Spielzeit','Strecke','Mobkills')):
            self.now[0]+=61
            text=self.ask('Top 10 aller Rekorde' if i==0 else 'weiter')
            self.assertIn(label+':',text)
            self.assertNotIn('passt nicht',text)
        self.assertEqual(self.provider.calls,[])


if __name__=='__main__':unittest.main()

