import contextlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/minecraft-assistant'))
from datafirst import DataFirstDialogue, NativeComposer, MODEL, create_dialogue, grounded_numbers, portrait_fallback
from dialogue import PublicObservations, GroundedDialogue
from portraits import PlayerPortraits
from recipes import RecipeBook
from runtime import Assistant, State


class DialogueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'stats'
        self.path.mkdir()
        self.ids = ['00000000-0000-0000-0000-' + str(n).zfill(12) for n in (1, 2, 3)]
        self.cache = self.root / 'users.json'
        self.cache.write_text(json.dumps([{'name': name, 'uuid': uid} for name, uid in
            zip(('ExampleOne', 'ExampleTwo', 'ExampleThree'), self.ids)]))
        self.mods = self.root / 'mods.json'
        self.mods.write_text('[]')
        for uid, deaths, hours in zip(self.ids, (10, 7, 2), (300, 50, 3)):
            self.write(uid, deaths, hours)
        self.engine = DataFirstDialogue(SimpleNamespace(dsn='restricted', usage=None))
        self.ai = Assistant(State(self.root / 'events.sqlite', b'a' * 32), self.path,
            self.cache, self.mods, recipes=RecipeBook(),
            portraits=PlayerPortraits(self.path, self.cache), dialogue=self.engine)
        self.calls = []
        self.reply = 'Gönn dir eine Pause, die Blöcke laufen dir nicht weg.'

        def generate(messages, validate):
            self.calls.append(messages)
            return validate(self.reply)

        self.engine.provider.request = generate

    def write(self, uid, deaths, hours=50):
        (self.path / (uid + '.json')).write_text(json.dumps({'stats': {
            'minecraft:custom': {'minecraft:deaths': deaths, 'minecraft:play_time': hours * 72000,
                'minecraft:mob_kills': deaths * 100},
            'minecraft:used': {'minecraft:bow': 100, 'minecraft:iron_sword': 20}}}))

    def ask(self, question, principal=None, source='minecraft', block_items=()):
        principal = principal or self.ids[0]
        scope = (source, principal)
        observations = PublicObservations(self.ai, scope, principal if source == 'minecraft' else None, block_items)
        return self.engine.answer(question, scope, observations)

    def test_rankings_and_rank_followup_use_no_model(self):
        self.assertIn('ExampleOne', self.ask('wer sind die fünf mit den meisten Toden?'))
        self.assertIn('ExampleTwo', self.ask('und wer ist zweiter?'))
        self.assertEqual(self.calls, [])

    def test_fresh_own_counters(self):
        self.assertIn('10', self.ask('wie viele Tode habe ich?'))
        self.write(self.ids[0], 11)
        self.assertIn('11', self.ask('wie viele Tode habe ich?'))
        self.assertEqual(self.calls, [])

    def test_block_operation_reaches_existing_counter_engine(self):
        self.write(self.ids[0], 10)
        path = self.path / (self.ids[0] + '.json')
        value = json.loads(path.read_text())
        value['stats']['minecraft:mined'] = {'minecraft:stone': 543}
        path.write_text(json.dumps(value))
        self.assertIn('543', self.ask('wie viele Blöcke habe ich schon abgebaut?'))
        self.assertEqual(self.calls, [])

    def test_english_distance_question_uses_counter_engine(self):
        self.assertIn('Strecke', self.ask('who has traveled the most?'))
        self.assertEqual(self.calls, [])

    def test_missing_advancements_are_not_inferred_from_other_counters(self):
        self.assertIn('Fortschrittsdatei', self.ask('wie viele Fortschritte hat ExampleOne?'))
        self.assertEqual(self.calls, [])

    def test_time_qualified_counter_is_not_replaced_with_lifetime_total(self):
        self.assertIn('keine Aufteilung', self.ask('wie viele Tode habe ich seit gestern?'))
        self.assertEqual(self.calls, [])

    def test_weapon_specific_kills_are_not_total_mobkills(self):
        self.assertIn('nicht, welche Waffe', self.ask('wie viele Mobkills habe ich mit dem Schwert?'))
        self.assertEqual(self.calls, [])

    def test_focused_portrait_keeps_zero_requested_metric(self):
        self.write(self.ids[0], 0, 300)
        self.reply = 'ExampleOne hat 0 Tode, das ist ein friedlicher Zwischenstand.'
        self.ask('was hältst du von ExampleOne anhand der Tode?')
        evidence = json.loads(self.calls[-1][-2]['content'].removeprefix('Datenblock: '))
        self.assertEqual(set(evidence['records']), {'Tode'})
        self.assertEqual(evidence['records']['Tode'][0], 0)

    def test_unqualified_crafting_recipe_does_not_reach_generation(self):
        self.assertIn('Grundrezept', self.ask('wie stelle ich einen Amboss her?'))
        self.assertEqual(self.calls, [])

    def test_general_redstone_opinion_is_not_unknown_player(self):
        self.reply = 'Redstone ist für mich die schönste Art, eine Tür unnötig kompliziert zu machen.'
        self.assertEqual(self.ask('was hältst du von Redstone?'), self.reply)
        self.assertEqual(len(self.calls), 1)

    def test_portrait_is_generated_from_records_including_playtime(self):
        self.reply = 'ExampleOne hat mit 300 h Spielzeit offenbar die Stammgastkarte gelöst.'
        self.assertIn('Stammgastkarte', self.ask('was hältst du von ExampleOne?'))
        text = self.calls[0][-2]['content']
        facts = json.loads(text.removeprefix('Datenblock: '))
        self.assertEqual(facts['player'], 'ExampleOne')
        self.assertEqual(facts['records']['Spielzeit'], [300, 'h', 1])
        self.assertEqual(facts['weapon_uses'], {'Bogen': 100})
        self.assertNotIn('Stammgastkarte', text)

    def test_discord_name_is_not_authenticated_self(self):
        response = self.ask('was hältst du von mir?', source='discord')
        self.assertIn('eindeutigen aktuellen Datensatz', response)
        self.assertEqual(self.calls, [])

    def test_typo_resolves_unique_roster_player(self):
        self.reply = 'ExampleThree hat mit 3 h gerade erst angefangen.'
        self.ask('was hältst du von ExampleThre?')
        self.assertIn('ExampleThree', self.calls[0][-2]['content'])

    def test_ambiguous_player_does_not_guess(self):
        self.assertIn('eindeutigen', self.ask('was hältst du von Example?'))
        self.assertEqual(self.calls, [])

    def test_unprovided_portrait_numbers_use_fresh_facts_without_retry(self):
        self.reply = 'ExampleOne hat 99999 Mobkills.'
        text = self.ask('was hältst du von ExampleOne?')
        self.assertNotIn('99999', text)
        self.assertIn('300', text)
        self.assertEqual(len(self.calls), 1)

    def test_localized_numbers_do_not_allow_invented_values(self):
        grounded_numbers('2.345,6 km und 367,5 h', {'distance':2345.6, 'hours':367.5})
        grounded_numbers('2.345 Blöcke', {'blocks':2345})
        with self.assertRaises(ValueError): grounded_numbers('2.346 Blöcke', {'blocks':2345})
        with self.assertRaises(ValueError): grounded_numbers('2345 km', {'distance':2.345})

    def test_missing_upgrade_documentation_never_guesses_workstation(self):
        self.assertIn('geprüfte Anleitung', self.ask('wie upgrade ich meinen backpack?'))
        self.assertEqual(self.calls, [])

    def test_server_context_and_broad_top_statistics_are_grounded(self):
        self.engine.server_name = 'ExampleCraft'
        text = self.ask('kannst du mir die top 10 Statistiken zu ExampleCraft geben?')
        self.assertIn('Spielzeit', text)
        self.assertNotIn('Herobrine', text)
        self.assertEqual(self.calls, [])
        self.ask('was ist ExampleCraft?')
        self.assertIn('Servername: ExampleCraft', self.calls[-1][0]['content'])

    def test_portrait_never_infers_equipment_or_accuracy(self):
        self.reply = 'ExampleOne braucht bessere Ausrüstung und mehr Glück bei seinen Treffern.'
        text = self.ask('was hältst du von ExampleOne?')
        self.assertNotIn('Ausrüstung', text)
        self.assertIn('300', text)

    def test_portrait_does_not_invent_achievement_recency(self):
        self.reply='ExampleOne hat kürzlich einen Drachen besiegt.'
        text=self.ask('was hältst du von ExampleOne?')
        self.assertNotIn('kürzlich',text)
        self.assertIn('300',text)

    def test_fallback_blends_supported_signals_without_fixed_disclaimer(self):
        evidence={'player':'ExampleTwo','records':{'Mobkills':[9683,'Kills',6],'Strecke':[100,'km',4]},
            'signals':['more_mob_than_player_kills','travel_recorded']}
        first=portrait_fallback(evidence,0)
        second=portrait_fallback(evidence,1)
        self.assertNotEqual(first,second)
        for text in (first,second):
            self.assertIn('Rang 6',text)
            self.assertIn('Rang 4',text)
            self.assertNotIn('Gesamturteil',text)
            self.assertNotRegex(text,r'führt|viel|Elite|Spitze')
            self.assertIn('Monster',text)
            self.assertLessEqual(len(text),320)

    def test_fallback_never_invents_an_unobserved_role(self):
        evidence={'player':'Example','records':{'Mobkills':[0,'Kills',4]},'signals':[]}
        self.assertNotRegex(portrait_fallback(evidence),r'führt|Monster bekommen|Bogen|Schwert|Logout')
        evidence.update(records={'Spielzeit':[300,'h',1]},shared_leaders=['Spielzeit'])
        self.assertIn('geteilter Rang 1',portrait_fallback(evidence))

    def test_combat_metrics_do_not_hide_other_recorded_activity(self):
        self.write(self.ids[0],10,1)
        p=self.path/(self.ids[0]+'.json')
        value=json.loads(p.read_text());value['stats']['minecraft:custom'].update(
            {'minecraft:player_kills':50,'minecraft:walk_one_cm':50000000})
        p.write_text(json.dumps(value))
        self.reply='ExampleOne spielt.'
        self.ask('was hältst du von ExampleOne?')
        evidence=json.loads(self.calls[-1][-2]['content'].removeprefix('Datenblock: '))
        self.assertFalse({'Mobkills','Spielerkills'}<=set(evidence['records']))
        self.assertIn('travel_recorded',evidence['signals'])

    def test_native_failure_varies_but_rereads_current_portrait_values(self):
        def timeout(messages,validator):raise TimeoutError()
        self.engine.provider.request=timeout
        first=self.ask('was hältst du von ExampleOne?')
        self.write(self.ids[0],10,301)
        second=self.ask('was hältst du von ExampleOne?')
        self.assertNotEqual(first,second)
        self.assertIn('301',second)
        self.assertNotIn('Gesamturteil',second)

    def test_lower_ranks_do_not_get_unsupported_superlatives(self):
        users=[{'name':'Example'+str(i),'uuid':'00000000-0000-0000-0000-'+str(i).zfill(12)} for i in range(1,8)]
        self.cache.write_text(json.dumps(users))
        for i,p in enumerate(users):self.write(p['uuid'],10+i,1+i)
        self.reply='Example1 hat enorm viele Mobkills und ist absolute Elite.'
        text=self.ask('was hältst du von Example1?')
        self.assertNotRegex(text,r'enorm|Elite|viele')

    def test_portrait_timeout_uses_fresh_values_without_retry(self):
        calls=[]
        def timeout(messages, validator):
            calls.append(messages)
            raise TimeoutError('LOCAL_DEADLINE')
        self.engine.provider.request=timeout
        text=self.ask('was hältst du von ExampleOne?')
        self.assertIn('300',text)
        self.assertEqual(len(calls),1)
        self.assertEqual(self.engine.provenance(('minecraft',self.ids[0])),'tool-portrait-evidence')

    def test_five_category_pages_fit_owned_continuation_budget(self):
        import uuid
        for question in ['top 10 aller Statistiken']+['weiter']*4:
            result=self.ai.handle({'principal':self.ids[0],'name':'ExampleOne',
                'event':str(uuid.uuid4())+':1','message':'Hey Vector, '+question})
            self.assertEqual(result['status'],'answered')
            self.assertNotIn('Minutenlimit',result['text'])
        self.assertEqual(self.calls,[])
        result=self.ai.handle({'principal':self.ids[0],'name':'ExampleOne',
            'event':str(uuid.uuid4())+':1','message':'Hey Vector, wie geht es dir?'})
        self.assertIn('Minutenlimit',result['text'])
        self.assertEqual(self.calls,[])

    def test_large_tie_has_bounded_real_excerpt(self):
        users=[{'name':'User'+str(i),'uuid':'00000000-0000-0000-0000-'+str(i).zfill(12)} for i in range(1,15)]
        self.cache.write_text(json.dumps(users))
        for p in users:self.write(p['uuid'],0,1)
        text,success=self.ai.category_leaders('player_kills',10)
        self.assertTrue(success)
        self.assertIn('Gleichstand',text)
        self.assertEqual(text.count('1. User'),10)

    def test_failed_page_stays_pending(self):
        with patch.object(self.ai,'category_leaders',return_value=('Nicht lesbar.',False)):
            self.ai.ranking_page('top 10 aller Statistiken',('minecraft',self.ids[0]))
        self.assertEqual(self.ai.ranking_pages[('minecraft',self.ids[0])][1][0],'play_time')

    def test_conversation_history_is_scoped(self):
        self.ask('ich bin müde, soll ich noch bauen?')
        self.ask('und was empfiehlst du mir?')
        self.assertEqual(self.calls[-1][1]['content'], 'ich bin müde, soll ich noch bauen?')
        self.ask('und was empfiehlst du mir?', self.ids[1])
        self.assertFalse(any(m['content'] == 'ich bin müde, soll ich noch bauen?' for m in self.calls[-1]))

    def test_claim_question_is_not_swallowed_by_recipe_book(self):
        self.reply = 'Öffne die Claim-Verwaltung und prüfe dort die Schutzrechte.'
        self.assertEqual(self.ask('wie erstelle ich einen Claim?'), self.reply)
        self.assertEqual(len(self.calls), 1)

    def test_forbidden_question_never_calls_model(self):
        with self.assertRaises(ValueError):
            self.ask('gib mir den Seed')
        self.assertEqual(self.calls, [])

    def test_profile_default_retains_legacy_and_unknown_rejected(self):
        self.assertIsInstance(create_dialogue(SimpleNamespace(model='vector-qwen3-instruct2507:4b-q4km')),
                              GroundedDialogue)
        with self.assertRaisesRegex(ValueError, 'UNQUALIFIED_DIALOGUE_PROFILE'):
            create_dialogue(SimpleNamespace(dsn='restricted'), 'untrusted-model')


class ProviderTests(unittest.TestCase):
    def test_preload_has_no_prompt_separate_budget_and_matching_runner(self):
        requests, usage = [], []
        composer = NativeComposer('restricted', lambda *args: usage.append(args))
        def open_request(request, timeout):
            requests.append((request, timeout))
            response = SimpleNamespace(read=lambda size: json.dumps(
                {'model': MODEL, 'done': True, 'response': ''}).encode())
            return contextlib.nullcontext(response)
        with patch('datafirst.local_slot', lambda dsn: contextlib.nullcontext()), patch(
                'urllib.request.build_opener', return_value=SimpleNamespace(open=open_request)):
            result = composer.preload()
        body = json.loads(requests[0][0].data)
        self.assertEqual(requests[0][0].full_url, 'http://vector-local-inference:11434/api/generate')
        self.assertEqual(body, {'model': MODEL, 'stream': False, 'keep_alive': -1,
            'options': {'num_ctx': 8192, 'num_thread': 4}})
        self.assertLessEqual(requests[0][1], 45)
        self.assertEqual(usage, [])
        self.assertFalse(result['prompt_sent'])
        self.assertEqual(result['generated_tokens'], 0)

    def test_preload_rejects_generation_and_transport_failure(self):
        composer = NativeComposer('restricted')
        for value in ({'model': MODEL, 'done': True, 'response': 'unexpected'},
                      {'model': 'other', 'done': True}, {'model': MODEL, 'done': False}):
            response = SimpleNamespace(read=lambda size: json.dumps(value).encode())
            with patch('datafirst.local_slot', lambda dsn: contextlib.nullcontext()), patch(
                    'urllib.request.build_opener', return_value=SimpleNamespace(
                        open=lambda *args, **kwargs: contextlib.nullcontext(response))):
                with self.assertRaisesRegex(ValueError, 'UNEXPECTED_PRELOAD_RESPONSE'):
                    composer.preload()
        with patch('datafirst.local_slot', lambda dsn: contextlib.nullcontext()), patch(
                'urllib.request.build_opener', return_value=SimpleNamespace(
                    open=lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError()))):
            with self.assertRaises(TimeoutError): composer.preload()

    def invoke(self, value, *, release_error=False, validator=None):
        usage, requests = [], []
        @contextlib.contextmanager
        def slot(dsn):
            yield
            if release_error:
                raise RuntimeError('RELEASE_FAILED')

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return json.dumps(value).encode()

        def open_request(request, timeout):
            requests.append(request)
            return Response()

        composer = NativeComposer('restricted', lambda *args: usage.append(args))
        with patch('datafirst.local_slot', slot), patch('urllib.request.build_opener',
                return_value=SimpleNamespace(open=open_request)):
            try:
                result = composer.request([{'role': 'user', 'content': 'Hallo'}], validator or (lambda text: text))
            except Exception as exc:
                result = exc
        self.diagnostic = composer.last_error
        return result, usage, requests

    def value(self):
        return {'model': MODEL, 'done': True, 'done_reason': 'stop',
            'prompt_eval_count': 100, 'eval_count': 10,
            'message': {'role': 'assistant', 'content': 'Hallo!'}}

    def test_request_fixed_local_model_no_seed_or_native_tools(self):
        result, usage, requests = self.invoke(self.value())
        self.assertEqual(result, 'Hallo!')
        self.assertEqual(requests[0].full_url, 'http://vector-local-inference:11434/api/chat')
        body = json.loads(requests[0].data)
        self.assertFalse(body['think'])
        self.assertEqual(body['keep_alive'], -1)
        self.assertNotIn('format', body)
        self.assertNotIn('tools', body)
        self.assertNotIn('seed', body['options'])
        self.assertEqual(body['options']['num_thread'], 4)
        self.assertEqual(body['options']['num_predict'], 96)
        self.assertEqual(usage, [(MODEL, 100, 10, True)])

    def test_complete_reply_over_previous_48_token_cap_is_accepted(self):
        value = self.value()
        value['eval_count'] = 65
        result, usage, _ = self.invoke(value)
        self.assertEqual(result, 'Hallo!')
        self.assertEqual(usage, [(MODEL, 100, 65, True)])
        self.assertIsNone(self.diagnostic)

    def test_token_limit_still_rejects_partial_reply_with_safe_reason(self):
        value = self.value()
        value.update(done_reason='length', eval_count=96)
        result, usage, _ = self.invoke(value)
        self.assertIsInstance(result, ValueError)
        self.assertEqual(self.diagnostic, {'type': 'ValueError', 'request_attempted': True,
            'code': 'INCOMPLETE_MODEL_RESPONSE', 'done_reason': 'length',
            'prompt_eval_count': 100, 'eval_count': 96})
        self.assertFalse(usage[0][-1])

    def test_arbitrary_exception_text_is_never_exposed(self):
        def reject(text):
            raise ValueError('password=synthetic-secret postgres://private')
        result, usage, _ = self.invoke(self.value(), validator=reject)
        self.assertIsInstance(result, ValueError)
        self.assertNotIn('synthetic-secret', json.dumps(self.diagnostic))
        self.assertNotIn('code', self.diagnostic)
        self.assertFalse(usage[0][-1])

    def test_slot_cleanup_failure_keeps_known_usage_unaccepted(self):
        result, usage, _ = self.invoke(self.value(), release_error=True)
        self.assertIsInstance(result, RuntimeError)
        self.assertEqual(usage, [(MODEL, 100, 10, False)])

    def test_incomplete_thinking_or_tool_outputs_rejected(self):
        for mutation in ('thinking', 'tool_calls', 'incomplete'):
            value = self.value()
            if mutation == 'incomplete': value['done_reason'] = 'length'
            else: value['message'][mutation] = 'unexpected'
            result, usage, _ = self.invoke(value)
            self.assertIsInstance(result, ValueError)
            self.assertEqual(usage[0][-1], False)


class SignedCandidateProbeTests(unittest.TestCase):
    def test_signed_http_full_assistant_route_with_mocked_native_only(self):
        import io
        import server
        spec = importlib.util.spec_from_file_location('native_probe',
            ROOT / 'scripts/deploy/evaluate-qwen35-native.py')
        probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe)
        source = (ROOT / 'services/minecraft-assistant/datafirst.py').read_text()
        source += '''
def synthetic_request(self,messages,validator):
    text=('ExampleOne hat mit 300 h Spielzeit wohl ein zweites Zuhause gefunden.'
        if 'ExampleOne' in messages[-1]['content'] else 'Gönn dir eine Pause, die Blöcke laufen dir nicht weg.')
    result=validator(text)
    self.usage(MODEL,100,20,True)
    return result
NativeComposer.request=synthetic_request
NativeComposer.preload=lambda self:dict(completed=True,seconds=0,prompt_sent=False,generated_tokens=0,keep_alive=-1)
'''
        payload = {'module_source': source, 'pins': {}}
        output = io.StringIO()
        with patch('server.knowledge_for', return_value=SimpleNamespace(dsn='restricted', usage=None)), \
                patch('sys.stdin', io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(output):
            exec(compile(probe.INTEGRATION, '<synthetic-signed-candidate>', 'exec'), {})
        line = next(line for line in output.getvalue().splitlines() if line.startswith('VECTOR_QWEN35_RESULT='))
        result = json.loads(line.split('=', 1)[1])
        self.assertTrue(result['diagnostic_completed'])
        self.assertTrue(result['passed'])
        self.assertEqual(result['model_calls'], 2)
        self.assertTrue(result['preload']['completed'])
        self.assertFalse(result['cold_start_latency_tested'])
        self.assertEqual(result['cases'][0]['model_calls'], 0)
        self.assertTrue(result['signed_candidate_http_tested'])
        self.assertFalse(result['production_activated'])
        self.assertFalse(result['production_request_contract_tested'])


if __name__ == '__main__':
    unittest.main()
