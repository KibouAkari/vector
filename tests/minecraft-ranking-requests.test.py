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
from runtime import Assistant, State


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
        answer = self.ai.stat_answer('Mobkills Rangliste von Monkills')
        self.assertIn('Monkills: Mobkills 100 Kills; Rang 1', answer)
        self.assertNotIn('Example2', answer)

    def test_incomplete_statistics_and_ambiguous_requests_fail_closed(self):
        for q in ('Vergleiche Mobkills von Example1 und UnknownPlayer', 'Unterschied von Mobkills zwischen Example1, Example2 und Example3',
                  'Unterschied bei Mobkills und Spielerkills zwischen Example1 und Example2',
                  'Vergleiche Mobkills von UnknownPlayer mit Example1 und Example2'):
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
