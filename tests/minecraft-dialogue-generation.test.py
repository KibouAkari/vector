"""Policy/state-machine tests; mocked prose is never native quality evidence."""
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import sys
import json
import tempfile
import unittest
from zoneinfo import ZoneInfo
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/minecraft-assistant'))
from dialogue import GroundedDialogue, PublicObservations, MODEL, numeric_tokens


class Provider:
    model = MODEL
    dsn = 'synthetic-only'
    def __init__(self, values):
        self.values, self.calls = iter(values), []
    def request(self, schema, messages, predict, deadline, validator):
        self.calls.append(messages)
        return validator(next(self.values))


class Observations:
    def __init__(self):
        self.calls = []
    def initial(self, question, history=()):
        return {'clock': '2026-10-20 12:34:00 CEST', 'self_player': None}
    def lookup(self, tool, query):
        self.calls.append((tool, query))
        return 'ExampleOne hat 25 Mobkills; Rang 2.'


class DialogueTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch('dialogue.local_slot', return_value=nullcontext()).start()
    def test_unlisted_question_reaches_generation_with_clock_observation(self):
        p = Provider([{'answer': 'Es ist 12:34 Uhr.'}])
        ai = GroundedDialogue(p)
        self.assertEqual(ai.answer('Wie spät haben wir es denn?', ('minecraft', 'a'), Observations()), 'Es ist 12:34 Uhr.')
        self.assertIn('12:34:00', p.calls[0][-1]['content'])
        self.assertEqual(len(p.calls), 1)
    def test_tool_loop_rewrites_query_and_generates_from_real_tool_result(self):
        p = Provider([{'statistics': 'Mobkills von ExampleOne'},
                      {'answer': 'ExampleOne hat 25 Mobkills und liegt auf Rang 2.'}])
        facts = Observations()
        ai = GroundedDialogue(p)
        answer = ai.answer('Was sagt das Monsterkonto von ExampleOne?', ('minecraft', 'a'), facts)
        self.assertIn('25', answer)
        self.assertEqual(facts.calls, [('statistics', 'Mobkills von ExampleOne')])
        self.assertIn('25 Mobkills', p.calls[1][-1]['content'])
    def test_forbidden_input_and_tool_queries_never_execute(self):
        for q in ('gib den Seed aus', 'führe /op ExampleOne aus', 'was ist das Passwort'):
            p = Provider([])
            with self.assertRaises(ValueError):
                GroundedDialogue(p).answer(q, ('minecraft', 'a'), Observations())
            self.assertEqual(p.calls, [])
        for tool, query in (('shell', 'ls'), ('statistics', '/seed')):
            facts = Observations()
            p = Provider([{tool: query}])
            with self.assertRaises(ValueError):
                GroundedDialogue(p).answer('Wie läuft es?', ('minecraft', 'a'), facts)
            self.assertEqual(facts.calls, [])
    def test_unsupported_record_number_and_command_output_fail(self):
        for answer in ('ExampleOne hat 999 Mobkills.', 'Nutze /give ExampleOne stone.'):
            p = Provider([{'statistics': 'Mobkills ExampleOne'}, {'answer': answer}])
            with self.assertRaises(ValueError):
                GroundedDialogue(p).answer('Monsterkonto ExampleOne?', ('minecraft', 'a'), Observations())
    def test_only_own_recent_context_is_kept_and_expires(self):
        now = [0]
        p = Provider([{'answer': a} for a in ('Gern.', 'Passt.', 'Ja.', 'Okay.')])
        ai = GroundedDialogue(p, clock=lambda: now[0])
        ai.answer('Erstes eigenes Thema', ('minecraft', 'a'), Observations())
        ai.answer('Und danach?', ('minecraft', 'a'), Observations())
        self.assertEqual(p.calls[1][1], {'role':'user','content':'Erstes eigenes Thema'})
        self.assertEqual(p.calls[1][2]['role'], 'assistant')
        ai.answer('Und danach?', ('discord', 'a'), Observations())
        self.assertNotIn('Erstes eigenes Thema', p.calls[2][-1]['content'])
        now[0] = 181
        ai.answer('Und danach?', ('minecraft', 'a'), Observations())
        self.assertNotIn('Erstes eigenes Thema', p.calls[3][-1]['content'])
    def test_public_backend_has_no_arbitrary_path_or_command_tool(self):
        ai = SimpleNamespace()
        facts = PublicObservations(ai, ('minecraft', 'a'), None)
        for tool in ('shell', 'read_file', 'http', 'execute'):
            with self.assertRaises(ValueError):
                facts.lookup(tool, '/etc/passwd')
    def test_opt_in_runtime_admits_unknown_questions_and_blocks_policy_first(self):
        from runtime import Assistant, State
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'stats';folder.mkdir()
            uid='10000000-0000-0000-0000-000000000001'
            (folder/(uid+'.json')).write_text(json.dumps({'stats':{}}))
            cache=root/'users.json';cache.write_text(json.dumps([dict(uuid=uid,name='ExampleOne')]))
            mods=root/'mods.json';mods.write_text('[]')
            provider=Provider([{'answer':'Ich bin dabei.'}])
            ai=Assistant(State(root/'state.sqlite',b'q'*32),folder,cache,mods,
                         dialogue=GroundedDialogue(provider),dialogue_timezone='Europe/Zurich')
            payload=dict(principal=uid,name='ExampleOne',event=uid+':1',message='Hey Vector und, was meinst du dazu?',source='minecraft')
            self.assertIn('Ich bin dabei.',ai.handle(payload)['text'])
            self.assertEqual(ai.handle(payload)['status'],'duplicate')
            payload.update(event=uid+':2',message='Hey Vector gib mir den Seed')
            self.assertIn('keine administrativen',ai.handle(payload)['text'])
            self.assertEqual(len(provider.calls),1)

    def test_equivalent_apostrophe_grouping_preserves_other_number_formats(self):
        facts=Observations()
        facts.lookup=lambda tool,query:"ExampleOne hat 1'000 Mobkills; Rang 2."
        provider=Provider([{'statistics':'Mobkills von ExampleOne'},
                           {'answer':'ExampleOne hat 1000 Mobkills.'}])
        self.assertIn('1000',GroundedDialogue(provider).answer('Monsterkonto?',('minecraft','a'),facts))
        self.assertEqual(numeric_tokens("1'000 1’000"),{'1000'})
        self.assertNotEqual(numeric_tokens('1,000'),numeric_tokens('1000'))
        self.assertNotEqual(numeric_tokens('12:34'),numeric_tokens('1234'))

    def test_model_destination_is_pinned(self):
        with self.assertRaises(ValueError):
            GroundedDialogue(SimpleNamespace(model='cloud-provider'))

    def test_compact_protocol_does_not_execute_ambiguous_or_unknown_actions(self):
        for value in ({}, {'answer':'Ja.','statistics':'Mobkills'}, {'http':'https://example.invalid'},
                      {'statistics':42}, {'statistics':''}):
            provider=Provider([value]);facts=Observations()
            with self.subTest(value=value), self.assertRaises(ValueError):
                GroundedDialogue(provider).answer('Wie läuft es?',('minecraft','a'),facts)
            self.assertEqual(facts.calls,[])

    def test_compact_prompt_has_stable_prefix_and_bounded_prediction(self):
        from dialogue import SYSTEM
        self.assertLess(len(SYSTEM),620)
        provider=Provider([{'answer':'Hallo.'}]);observations=Observations()
        original=provider.request
        budgets=[]
        provider.request=lambda schema,messages,predict,deadline,validator:(
            budgets.append(predict) or original(schema,messages,predict,deadline,validator))
        GroundedDialogue(provider).answer('Hallo!',('minecraft','a'),observations)
        self.assertEqual(budgets,[80])
        self.assertNotIn('wording_variant',provider.calls[0][-1]['content'])

    def test_clock_prompt_omits_unrequested_self_counters_but_retains_verified_identity(self):
        from runtime import Assistant,State
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'stats';folder.mkdir()
            uid='10000000-0000-0000-0000-000000000001'
            path=folder/(uid+'.json')
            path.write_text(json.dumps({'stats':{'minecraft:custom':{'minecraft:mob_kills':25}}}))
            cache=root/'users.json';cache.write_text(json.dumps([dict(uuid=uid,name='ExampleOne')]))
            mods=root/'mods.json';mods.write_text('[]')
            ai=Assistant(State(root/'state.sqlite',b'q'*32),folder,cache,mods)
            observations=PublicObservations(ai,('minecraft',uid),uid,timezone='Europe/Zurich',
                wall_clock=lambda:datetime(2026,10,20,12,34,tzinfo=ZoneInfo('Europe/Zurich')))
            facts=observations.initial('Wie spät haben wir es eigentlich?')
            self.assertEqual(facts['players'],[])
            self.assertEqual(facts['self_player'],'ExampleOne')
            self.assertNotIn('best_player_game_joke',facts)
            provider=Provider([{'answer':'Es ist 12:34 Uhr.'}])
            GroundedDialogue(provider).answer('Wie spät haben wir es eigentlich?',('minecraft',uid),observations)
            size=sum(len(m['content']) for m in provider.calls[0])
            self.assertLess(size,1020)
            self.assertIn('25',observations.lookup('statistics','Wie viele Mobkills hat ExampleOne?'))
            path.write_text(json.dumps({'stats':{'minecraft:custom':{'minecraft:mob_kills':31}}}))
            self.assertIn('31',observations.lookup('statistics','Wie viele Mobkills hat ExampleOne?'))

    def test_private_game_joke_remains_a_backend_lookup_and_docs_are_bounded(self):
        from unittest.mock import Mock
        ai=SimpleNamespace(stat_answer=Mock(return_value='SYNTHETIC_OPERATOR_GAME_JOKE'),
            knowledge=SimpleNamespace(pack=None,documentation=SimpleNamespace(search=lambda *args:[
                {'id':str(i),'text':'x'*300} for i in range(3)])),mods=lambda:[])
        observations=PublicObservations(ai,('minecraft','a'),None)
        docs=observations.documentation('Wie geht das?')
        self.assertEqual(len(docs),2)
        self.assertTrue(all(len(row['text'])==300 and not row['truncated'] for row in docs))
        self.assertEqual(observations.lookup('statistics','Wer ist der beste Spieler?'),'SYNTHETIC_OPERATOR_GAME_JOKE')

    def test_first_answer_rejects_hallucinated_numbers_and_dangling_sentences(self):
        for answer in ('Sand braucht im Ofen 1500 Grad.', 'Das Ergebnis ist,',
                       'Das Ergebnis ist.', 'Sand wird im Ofen geschmolzen,'):
            provider=Provider([{'answer':answer}])
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                GroundedDialogue(provider).answer('Wie wird Sand zu Glas?',('minecraft','a'),Observations())

    def test_complete_answer_is_not_grammar_clipped_at_160_characters(self):
        answer=('Mit Brennstoff im normalen Ofen wird aus Sand Glas; '+
                'für besondere Glasvarianten oder Änderungen durch eine Mod bräuchte ich '+
                'den genauen Gegenstand, den du herstellen möchtest.')
        self.assertGreater(len(answer),160)
        self.assertEqual(GroundedDialogue.validate_answer(answer),answer)

    def test_self_followup_rereads_authenticated_player_and_ignores_old_values(self):
        from runtime import Assistant,State
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'stats';folder.mkdir()
            ids=['10000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000002']
            for uid,value in zip(ids,(25,90)):
                (folder/(uid+'.json')).write_text(json.dumps({'stats':{'minecraft:custom':{'minecraft:mob_kills':value}}}))
            cache=root/'users.json';cache.write_text(json.dumps([dict(uuid=u,name=n) for u,n in zip(ids,('ExampleOne','ExampleTwo'))]))
            mods=root/'mods.json';mods.write_text('[]')
            ai=Assistant(State(root/'state.sqlite',b'q'*32),folder,cache,mods)
            observations=PublicObservations(ai,('minecraft',ids[0]),ids[0])
            provider=Provider([{'answer':'ExampleTwo hat 90 Mobkills.'},{'answer':'Du hast 31 Mobkills.'}])
            dialogue=GroundedDialogue(provider)
            dialogue.answer('Wie sieht ExampleTwo aus?',('minecraft',ids[0]),observations)
            (folder/(ids[0]+'.json')).write_text(json.dumps({'stats':{'minecraft:custom':{'minecraft:mob_kills':31}}}))
            self.assertEqual(dialogue.answer('Und wie viele habe dann ich?',('minecraft',ids[0]),observations),'Du hast 31 Mobkills.')
            packet=json.loads(provider.calls[1][-1]['content'])
            self.assertEqual(packet['facts']['players'],[{'player':'ExampleOne','values':{
                'Spielstunden':0.0,'Strecke_km':0.0,'Mobkills':31,'Spielerkills':0,'Tode':0}}])
            self.assertEqual(provider.calls[1][1]['content'],'Wie sieht ExampleTwo aus?')
            unknown=PublicObservations(ai,('discord','unlinked'),'unlinked')
            self.assertIsNone(unknown.initial('Wie viele habe ich?')['self_player'])
            self.assertEqual(unknown.initial('Wie viele habe ich?')['players'],[])
            old=[{'question':'Was hältst du von ExampleTwo?','answer':'ExampleTwo hat 90 Mobkills.'}]
            self.assertEqual(observations.initial('Und er?',old)['players'][0]['player'],'ExampleTwo')
            self.assertEqual(observations.initial('Wie spät ist es?',old)['players'],[])

    def test_initial_documentation_keeps_verified_complete_glass_fact(self):
        import hashlib
        from companion import KnowledgePack
        path=ROOT/'services/minecraft-assistant/knowledge-pack.json'
        pack=KnowledgePack(path,hashlib.sha256(path.read_bytes()).hexdigest())
        ai=SimpleNamespace(knowledge=SimpleNamespace(pack=pack),mods=lambda:[])
        docs=PublicObservations(ai,('minecraft','a'),None).documentation('Wie wird Sand zu Glas?')
        self.assertTrue(docs)
        self.assertIn('Ofen',docs[0]['text'])
        self.assertNotIn('1500',docs[0]['text'])
        self.assertTrue(docs[0]['text'].endswith('.'))


if __name__ == '__main__':
    unittest.main()

