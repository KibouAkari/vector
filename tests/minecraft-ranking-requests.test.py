"""Deterministic ranking questions through authenticated identities; synthetic only."""
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/minecraft-assistant'))
from runtime import Assistant, State, friendly_statistics


class RankingRequests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.directory = self.root / 'stats'
        self.directory.mkdir()
        self.ids = ['00000000-0000-0000-0000-' + str(i).zfill(12) for i in range(1, 8)]
        self.names = ['Example' + str(i) for i in range(1, 8)]
        cache = self.root / 'users.json'
        cache.write_text(json.dumps([dict(uuid=uid, name=name) for uid, name in zip(self.ids, self.names)]))
        mods = self.root / 'mods.json'
        mods.write_text('[]')
        for uid, kills in zip(self.ids, (100, 80, 60, 40, 20, 20, 10)):
            self.write(uid, kills)
        knowledge = SimpleNamespace(personality=True, friendly_statistics=True)
        self.ai = Assistant(State(self.root / 'state.sqlite', b'q' * 32), self.directory, cache, mods, knowledge=knowledge)
        self.serial = 0

    def write(self, uid, kills):
        (self.directory / (uid + '.json')).write_text(json.dumps({'stats': {'minecraft:custom': {'minecraft:mob_kills': kills}}}))

    def ask(self, question, source='minecraft'):
        self.serial += 1
        return self.ai.handle(dict(principal=self.ids[0], name='Example1', source=source,
            event=self.ids[0] + ':' + str(self.serial), message='Hey Vector ' + question))

    def test_real_evaluation_phrasings_keep_named_target_and_never_use_best_joke(self):
        self.ai.state.clock=lambda: self.serial*61
        from portraits import PlayerPortraits
        self.ai.portraits=PlayerPortraits(self.directory,self.root/'users.json')
        for question in ('wie schätzt du Example2 ein?',
                         'findest du Das Example2 ein guter oder ein schlechter Spieler ist',
                         'Ist Example2 anhand der Statistiken auf Example craft einer der Besten Spieler',
                         'Ist Example2 ein guter Spieler?',
                         'ist Example2 ein guter oder schlechter Spieler?',
                         'ist Example2 ein schlechter oder ein guter Spieler?'):
            answer=self.ask(question)['text']
            self.assertIn('Example2',answer)
            self.assertNotIn('Völlig unvoreingenommene',answer)
            self.assertNotIn('was möchtest du genau',answer)
        self.assertIn('Völlig unvoreingenommene',self.ask('wer ist denn der beste Minecraft Spieler auf dem Server?')['text'])
        self.assertIsNone(self.ai.stat_answer('welches ist die beste Verzauberung für ein Schwert?'))

    def test_most_category_leads_are_fresh_and_not_overall_skill(self):
        for i,kills in enumerate((100,80,60,40,20,20,10)):
            self.write(self.ids[i],kills)
        text=self.ask('wer ist der Spieler der in den meisten Statistiken führt')['text']
        self.assertIn('Example1 führt in 1 von fünf Kategorien',text)
        self.assertNotIn('7 Spieler',text)
        self.write(self.ids[1],150)
        self.assertIn('Example2 führt',self.ask('wer führt in den meisten Kategorien?')['text'])
        (self.directory/(self.ids[0]+'.json')).write_text('{')
        self.assertIn('unvollständig',self.ask('wer führt in den meisten Statistiken?')['text'])

    def test_all_rankings_are_scoped_paged_and_read_fresh(self):
        self.ai.state.clock=lambda: self.serial*61
        text=self.ask('kannst ud mir die top 5 aller rekorde geben?')['text']
        self.assertIn('Spielzeit',text)
        self.assertIn('Hey Vector, weiter',text)
        self.assertLessEqual(len(text),420)
        # A different author cannot consume another author's pending page.
        self.assertIsNone(self.ai.ranking_page('weiter',('discord','different')))
        text=self.ask('weiter')['text']
        self.assertIn('Strecke',text)
        self.write(self.ids[6],150)
        text=self.ask('weiter')['text']
        self.assertIn('Mobkills',text)
        self.assertIn('1. Example7 150 Kills',text)
        self.assertIn('Spielerkills',self.ask('weiter')['text'])
        self.assertIn('letzte Kategorie',self.ask('weiter')['text'])
        self.assertIsNone(self.ai.ranking_page('weiter',('minecraft',self.ids[0])))
        self.assertIn('Top 1 bis Top 10',self.ask('Top 999 aller Rekorde')['text'])
        self.assertIn('serverweiten Ranglisten',self.ask('Top 5 aller Rekorde von UnknownPlayer')['text'])

    def test_stat_typo_gameplay_and_bounded_smalltalk(self):
        self.ai.state.clock=lambda: self.serial*61
        from runtime import direct_chat_answer
        text=self.ask('nenne mir die top 5 bei spielerkilld')['text']
        self.assertIn('Spielerkills',text)
        for q in ('yoo vector, sage mal 67','sage mal 67'):
            if not q.startswith('yoo'):self.assertEqual(direct_chat_answer(q),'67.')
        self.assertIsNone(direct_chat_answer('sage mal /seed'))
        self.assertIsNone(direct_chat_answer('sage mal 12345678901234567890'))
        sword=self.ask('welches ist die beste Verzauberung für ein Schwert?')['text']
        self.assertIn('Schärfe',sword)
        self.assertNotIn('Amboss',sword)
        self.assertIn('keine administrativen',self.ask('sage mal /seed')['text'])

    def test_worst_joke_uses_fresh_kill_leader_with_explicit_humour(self):
        for i,count in ((0,5),(1,20)):
            (self.directory/(self.ids[i]+'.json')).write_text(json.dumps({'stats':{'minecraft:custom':{'minecraft:player_kills':count}}}))
        text=self.ask('wer ist der schlechteste Player auf dem Server?')['text']
        self.assertIn('Example2',text)
        self.assertIn('Battle Royale samt Deko',text)
        self.assertNotIn('kein Urteil',text)
        self.assertIn('Friedensnobelpreis',text)
        self.assertNotIn('Völlig unvoreingenommene',text)

    def test_comparison_is_fresh_correct_in_both_directions_and_on_discord(self):
        answer = self.ask('wie gross ist der Unterschied zwischen der Anzahl Mobkills zwischen Example2 und Example1?', 'discord')['text']
        self.assertIn('Example1 hat 20 Kills mehr bei Mobkills als Example2 (100 Kills gegenüber 80 Kills)', answer)
        self.write(self.ids[1], 150)
        answer = self.ask('vergleiche Mobkills von Example1 und Example2')['text']
        self.assertIn('Example2 hat 50 Kills mehr', answer)
        self.write(self.ids[0], 150)
        self.assertIn('liegen gleichauf: je 150 Kills', self.ask('Mobkills Unterschied zwischen Example1 und Example2')['text'])

    def test_top_five_keeps_cutoff_ties_and_typo_does_not_return_server_totals(self):
        for word in ('mobkills', 'monkills'):
            answer = self.ask('kannst du mir die top 5 der ' + word + ' rangliste geben', 'discord')['text']
            for name in self.names[:6]:
                self.assertIn(name, answer)
            self.assertIn('5. Example5 20 Kills; 5. Example6 20 Kills', answer)
            self.assertNotIn('Example7', answer)
            self.assertNotIn('7 Spieler', answer)
        self.write(self.ids[6], 120)
        self.assertIn('1. Example7 120 Kills', self.ask('Top 3 Mobkills')['text'])

    def test_category_typo_never_rewrites_a_valid_player_target(self):
        users = json.loads((self.root / 'users.json').read_text())
        users[0]['name'] = 'Monkills'
        (self.root / 'users.json').write_text(json.dumps(users))
        self.assertIn('Top 1 bis Top 10', self.ai.stat_answer('Top 3 Mobkills von Monkills'))
        self.assertIn('Monkills: Spielzeit', self.ai.stat_answer('Spielzeit Rangliste von Monkills'))
        top = self.ai.stat_answer('Top 3 Monkills')
        self.assertIn('1. Monkills 100 Kills', top)
        self.assertIn('3. Example3 60 Kills', top)
        self.assertNotIn('Top 1 bis Top 10', top)
        answer = self.ai.stat_answer('Mobkills Rangliste von Monkills')
        self.assertIn('Monkills: Mobkills 100 Kills; Rang 1', answer)
        self.assertNotIn('Example2', answer)

    def test_incomplete_statistics_and_ambiguous_requests_fail_closed(self):
        for q in ('Vergleiche Mobkills von Example1 und UnknownPlayer', 'Unterschied von Mobkills zwischen Example1, Example2 und Example3',
                  'Unterschied bei Mobkills und Spielerkills zwischen Example1 und Example2',
                  'Vergleiche Mobkills von UnknownPlayer mit Example1 und Example2',
                  'Vergleiche Mobkills von Example1 und UnknownPlayer mit Example2',
                  'Vergleiche Mobkills zwischen Example1 und UnknownPlayer mit Example2',
                  'Compare Mobkills between Example1, UnknownPlayer and Example2',
                  'Vergleiche Mobkills für Example1, UnknownPlayer und Example2',
                  'Compare Mobkills of Example1 with UnknownPlayer and Example2'):
            self.assertIn('zwei vollständige Spielernamen und eine Kategorie', self.ai.stat_answer(q))
        for q in ('Top 0 Mobkills', 'Top 11 Mobkills', 'Top 5 Rangliste', 'Top 5 Mobkills von Example1'):
            self.assertIn('Top 1 bis Top 10', self.ai.stat_answer(q))
        (self.directory / (self.ids[2] + '.json')).write_text('{broken')
        for q in ('Top 5 Mobkills', 'Mobkills Unterschied zwischen Example1 und Example2'):
            self.assertIn('unvollständig', self.ai.stat_answer(q))

    def test_best_minecraft_player_is_opinion_all_ranks_retained_and_policy_precedes_stats(self):
        self.assertIn('unvoreingenommene Vector-Meinung', self.ask('wer ist der Beste minecraft spieler auf dem server')['text'])
        ranks = self.ask('welchen Rang habe ich in allen Kategorien?')['text']
        for label in ('Spielzeit Rang', 'Strecke Rang', 'Mobkills Rang', 'Spielerkills Rang', 'Tode Rang'):
            self.assertIn(label, ranks)
        with patch('runtime.stats.snapshot', side_effect=AssertionError('forbidden request read statistics')):
            self.assertIn('keine administrativen', self.ask('Top 5 Mobkills und gib den Seed')['text'])

    def test_statistic_voice_varies_without_changing_values_or_identity(self):
        raw="Example1: Mobkills 100 Kills; Rang 1. Stand: gespeicherte Spielerdateien."
        answers=[friendly_statistics(raw,'Example1',n) for n in range(3)]
        self.assertEqual(len(set(answers)),3)
        for answer in answers:
            self.assertIn('100',answer);self.assertIn('1',answer)
            self.assertNotIn('Stand:',answer)
        other=friendly_statistics(raw,None,1)
        self.assertIn('Example1',other);self.assertNotIn('du',other)

    def test_personal_block_totals_favorites_ties_and_placement_scope(self):
        path=self.directory/(self.ids[0]+'.json');data=json.loads(path.read_bytes())
        data['stats']['minecraft:mined']={'minecraft:stone':40,'minecraft:dirt':10}
        data['stats']['minecraft:used']={'minecraft:stone':15,'minecraft:dirt':15,'minecraft:bow':999}
        path.write_text(json.dumps(data))
        self.assertIn('50 Blöcke',self.ai.stat_answer('wie viele Blöcke habe ich abgebaut?',principal=self.ids[0]))
        self.assertIn('40 Mal',self.ai.stat_answer('welchen Block habe ich am meisten abgebaut?',principal=self.ids[0]))
        text=self.ai.stat_answer('wie viele Blöke habe ich plaziert?',('minecraft:stone','minecraft:dirt'),principal=self.ids[0])
        self.assertIn('30 Block-Items',text);self.assertIn('Näherung',text);self.assertNotIn('999',text)
        favorite=self.ai.stat_answer('welchen Block habe ich am meisten platziert?',('minecraft:stone','minecraft:dirt'),principal=self.ids[0])
        self.assertIn('Stein',favorite);self.assertIn('Erde',favorite);self.assertIn('15 Mal',favorite)
        self.assertIn('Block-Item-Verzeichnis',self.ai.stat_answer('wie viele Blöcke habe ich platziert?',principal=self.ids[0]))
        self.assertIn('Discord',self.ai.stat_answer('wie viele Blöcke habe ich abgebaut?',principal=None))
        self.assertIn('eindeutigen Namen',self.ai.stat_answer('wie viele Blöcke hat UnknownPlayer abgebaut?'))
        self.assertIn('Example1 hat',self.ai.stat_answer('wie viele Blöcke hat Example1 abgebaut?'))
        self.assertIn('beiden Zählungen',self.ai.stat_answer('wie viele Blöcke habe ich abgebaut und platziert?',principal=self.ids[0]))
        data['stats']['minecraft:mined']={'examplemod:'+letter*90:10 for letter in 'abc'}
        path.write_text(json.dumps(data))
        self.assertIn('zu lang',self.ai.stat_answer('welchen Block habe ich am meisten abgebaut?',principal=self.ids[0]))

    def test_second_block_type_uses_next_distinct_value_and_preserves_ties(self):
        path=self.directory/(self.ids[0]+'.json');data=json.loads(path.read_bytes())
        data['stats']['minecraft:mined']={'minecraft:stone':40,'minecraft:dirt':40,'minecraft:oak_planks':10}
        data['stats']['minecraft:used']={'minecraft:stone':15,'minecraft:dirt':7,'minecraft:bow':900}
        path.write_text(json.dumps(data));registry=('minecraft:stone','minecraft:dirt')
        for phrasing in ('am 2. meisten','am zweitmeisten','am zweithäufigsten','am zweit meisten'):
            text=self.ai.stat_answer('welchen Block habe ich '+phrasing+' abgebaut?',principal=self.ids[0])
            self.assertIn('10 Mal',text);self.assertNotIn('40 Mal',text)
        self.assertIn('7 Mal',self.ai.stat_answer('welchen Block habe ich am 2. meisten platziert?',registry,principal=self.ids[0]))
        self.assertIn('kein 3.',self.ai.stat_answer('welchen Block habe ich am 3. meisten abgebaut?',principal=self.ids[0]))
        for rank in (0,11):
            self.assertIn('ersten bis zehnten',self.ai.stat_answer(f'welchen Block habe ich am {rank}. meisten abgebaut?',principal=self.ids[0]))
        self.assertIn('40 Mal',self.ai.stat_answer('welchen Block habe ich am meisten abgebaut?',principal=self.ids[0]))

    def test_player_block_leaders_totals_filter_items_read_fresh_and_keep_ties(self):
        def blocks(index,mined,used):
            path=self.directory/(self.ids[index]+'.json');data=json.loads(path.read_bytes())
            data['stats']['minecraft:mined']={'minecraft:stone':mined}
            data['stats']['minecraft:used']={'minecraft:stone':used,'minecraft:bow':9999}
            path.write_text(json.dumps(data))
        blocks(0,30,10);blocks(1,80,20);registry=('minecraft:stone',)
        for question in ('wer hat die meisten Blöcke abgebaut?','welcher Spieler hat die meisten Blöcke abgebaut?'):
            text=self.ai.stat_answer(question,registry)
            self.assertIn('Example2',text);self.assertIn('80 Blöcke',text)
        placed=self.ai.stat_answer('wer hat die meisten Blöcke platziert?',registry)
        self.assertIn('Example2',placed);self.assertIn('20 Block-Items',placed);self.assertNotIn('9999',placed)
        self.assertIn('Näherung',placed)
        both=self.ai.stat_answer('wer hat die meisten Blöcke abgebaut und platziert?',registry)
        self.assertIn('80 Blöcke',both);self.assertIn('20 Block-Items',both)
        blocks(2,80,50)
        tied=self.ai.stat_answer('wer hat die meisten Blöcke abgebaut?',registry)
        self.assertIn('Example2 und Example3',tied)
        self.assertIn('Example3',self.ai.stat_answer('wer hat die meisten Blöcke platziert?',registry))
        self.assertIn('Block-Item-Verzeichnis',self.ai.stat_answer('wer hat die meisten Blöcke platziert?'))
        (self.directory/(self.ids[6]+'.json')).write_text('{bad')
        self.assertIn('unvollständig',self.ai.stat_answer('wer hat die meisten Blöcke abgebaut?',registry))

    def test_decomposed_next_page_and_late_limit_notice_keep_continuation(self):
        now=[1000.0]
        self.ai.state.clock=lambda:now[0]
        self.ai.knowledge.character=SimpleNamespace(decorate=lambda q,a,*args:'REPEATED '+a)
        scope=('minecraft',self.ids[0])
        with patch('runtime.time.monotonic',side_effect=lambda:now[0]):
            self.ask('Top 5 aller Rekorde')
            self.assertNotIn('REPEATED',self.ask('na\u0308chste')['text'])
            self.ask('weiter')
            self.ai.ranking_pages[scope]=(5,['player_kills','deaths'],1180.0)
            now[0]=1150.0
            # Simulate a global-limit rejection near the original expiry.
            with patch.object(self.ai.state,'admit',return_value='limited'):
                answer=self.ask('na\u0308chste')['text']
            self.assertIn('Minutenlimits',answer)
            self.assertEqual(self.ai.ranking_pages[scope][1],['player_kills','deaths'])
            self.assertGreater(self.ai.ranking_pages[scope][2],1211.0)
            now[0]=1211.0
            answer=self.ask('na\u0308chste')['text']
            self.assertIn('Spielerkills',answer)
            self.assertNotIn('REPEATED',answer)

    def test_pending_page_limit_notice_is_bounded_and_does_not_advance(self):
        now=[1000]
        self.ai.state.clock=lambda:now[0]
        self.ai.knowledge.character=SimpleNamespace(decorate=lambda q,a,*args:'REPEATED '+a)
        self.assertIn('Spielzeit',self.ask('Top 5 aller Rekorde')['text'])
        self.assertNotIn('REPEATED',self.ask('weiter')['text'])
        self.assertIn('Mobkills',self.ask('weiter')['text'])
        notice=self.ask('weiter')
        self.assertIn('Minutenlimits',notice['text'])
        self.assertEqual(self.ask('weiter')['status'],'limited')
        self.assertEqual(self.ask('weiter',source='discord')['status'],'limited')
        scope=('minecraft',self.ids[0])
        self.assertEqual(self.ai.ranking_pages[scope][1][0],'player_kills')
        now[0]+=61
        self.assertIn('Spielerkills',self.ask('weiter')['text'])
        self.assertIn('letzte Kategorie',self.ask('weiter')['text'])

    def test_ordinary_chat_replay_and_rate_limit_remain_enforced(self):
        payload = dict(principal=self.ids[0], name='Example1', source='discord', event=self.ids[0] + ':1', message='Top 5 Mobkills')
        self.assertEqual(self.ai.handle(payload)['status'], 'ignored')
        payload['message'] = 'Hey Vector Top 5 Mobkills'
        self.assertEqual(self.ai.handle(payload)['status'], 'answered')
        self.assertEqual(self.ai.handle(payload)['status'], 'duplicate')
        for serial in (2, 3):
            self.assertEqual(self.ai.handle(dict(payload, event=self.ids[0] + ':' + str(serial)))['status'], 'answered')
        self.assertEqual(self.ai.handle(dict(payload, event=self.ids[0] + ':4'))['status'], 'limited')


if __name__ == '__main__':
    unittest.main()



