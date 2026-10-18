import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/fegcraft-assistant'))
from runtime import Assistant, State
from recipes import label


class Dialogue(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stats = self.root / 'stats'
        self.stats.mkdir()
        self.ids = ['00000000-0000-0000-0000-' + str(i).zfill(12) for i in (1, 2, 3)]
        self.cache = self.root / 'users.json'
        self.cache.write_text(json.dumps([{'uuid': uid, 'name': name} for uid, name in zip(self.ids, ('ExampleOne', 'ExampleTwo', 'ExampleThree'))]))
        self.mods = self.root / 'mods.json'
        self.mods.write_text('[]')
        for uid, deaths in zip(self.ids, (10, 7, 7)):
            self.write(uid, deaths)
        self.ai = Assistant(State(self.root / 'state.sqlite', b'a' * 32), self.stats, self.cache, self.mods)

    def write(self, uid, deaths, stone=30):
        (self.stats / (uid + '.json')).write_text(json.dumps({'stats': {
            'minecraft:custom': {'minecraft:deaths': deaths, 'minecraft:play_time': 72000},
            'minecraft:used': {'minecraft:stone': stone, 'minecraft:dirt': 10, 'minecraft:diamond_pickaxe': 50000},
            'minecraft:mined': {'minecraft:dirt': 200}}}))

    def test_natural_deaths_and_shared_rank(self):
        value = self.ai.stat_answer('wie oft starb ExampleTwo schon und welchen Rang hat er')
        self.assertIn('Tode 7 Tode; Rang 2 nach Anzahl', value)
        self.assertNotIn('ExampleOne:', value)

    def test_general_record_holders_with_natural_plural(self):
        value = self.ai.stat_answer('kannst du mir die rekorde und rekordehalter durchgeben')
        for key in ('Spielzeit:', 'Strecke:', 'Mobkills:', 'Spielerkills:', 'Tode:'):
            self.assertIn(key, value)
        self.assertNotIn('vollständigen Spielernamen', value)

    def test_unknown_explicit_player_is_not_replaced_by_global_winner(self):
        for question in ('alle Rekordhalter von UnknownPlayer', 'Rekorde von ExampleOneSuffix',
                         'Ist UnknownPlayer Rekordhalter?', 'Ist ExampleOneSuffix Rekordhalter?',
                         'alle Rekorde von dem Spieler UnknownPlayer'):
            self.assertIn('vollständigen Spielernamen', self.ai.stat_answer(question))
        for question in ('Wer hält den Rekord für Mobkills?', 'Wer hält den Rekord für die meisten Mobkills?'):
            value = self.ai.stat_answer(question)
            self.assertIn('Mobkills:', value)
            self.assertNotIn('vollständigen Spielernamen', value)
        self.assertIn('Spielzeit:', self.ai.stat_answer('alle Rekorde von dem Server'))

    def test_blocks_use_live_item_types_and_fresh_saved_counters(self):
        question = 'welcher block wurde am meisten platziert?'
        ids = ['minecraft:stone', 'minecraft:dirt']
        first = self.ai.stat_answer(question, ids)
        self.assertIn('Stein 90 Mal', first)
        self.assertNotIn('50000', first)
        self.assertIn('keine exakte Gesamtzahl', first)
        self.write(self.ids[0], 10, stone=100)
        self.assertIn('Stein 160 Mal', self.ai.stat_answer(question, ids))
        self.assertIn('Block-Item-Verzeichnis', self.ai.stat_answer(question))
        self.assertIn('serverweit', self.ai.stat_answer('welcher Block wurde von UnknownPlayer am meisten platziert?', ids))
        self.assertIn('Erde 600 Mal', self.ai.stat_answer('welcher Block wurde am häufigsten abgebaut?'))

    def test_discord_display_name_and_input_validation(self):
        payload = {'principal': self.ids[0], 'name': 'Example Discord', 'source': 'discord',
                   'event': self.ids[0] + ':1', 'message': 'hey Vector, wie oft starb ExampleTwo?'}
        self.assertTrue(self.ai.handle(payload)['text'].startswith('Hey Example Discord,'))
        for invalid in ('@everyone', 'Example\nDiscord', 'Name<>'):
            with self.assertRaises(ValueError):
                self.ai.handle(dict(payload, name=invalid))
        with self.assertRaises(ValueError):
            self.ai.handle(dict(payload, block_items=['minecraft:stone', 'minecraft:stone']))
        self.assertEqual(label('minecraft:anvil'), 'Amboss')
        self.assertEqual(label('minecraft:iron_block'), 'Eisenblock')

    def test_party_question_cannot_reuse_previous_record_answer(self):
        previous = self.ai.stat_answer('welche Rekorde hat ExampleOne?')
        self.assertIn('ExampleOne', previous)
        with patch('runtime.stats.snapshot', side_effect=AssertionError('Party question read statistics')):
            for question in ('wie erstelle ich eine party für meinen claim?',
                             'wozu sind Partys gut?', 'und wie gebe ich Mitgliedern Zugriff?'):
                self.assertIsNone(self.ai.stat_answer(question))

    def test_discord_mobkill_rank_reads_current_values(self):
        payload = {'principal': self.ids[0], 'name': 'Example Discord', 'source': 'discord',
                   'event': self.ids[0] + ':1',
                   'message': 'Hey Vector, welchen Rang hat ExampleOne bei der Mobkills Rangliste?'}
        def kills(uid, count):
            (self.stats / (uid + '.json')).write_text(json.dumps({'stats': {
                'minecraft:custom': {'minecraft:mob_kills': count}}}))
        kills(self.ids[0], 10)
        kills(self.ids[1], 20)
        answer = self.ai.handle(payload)['text']
        self.assertTrue(answer.startswith('Hey Example Discord,'))
        self.assertIn('Mobkills 10 Kills; Rang 2', answer)
        kills(self.ids[0], 30)
        answer = self.ai.handle(dict(payload, event=self.ids[0] + ':2'))['text']
        self.assertIn('Mobkills 30 Kills; Rang 1', answer)


if __name__ == '__main__':
    unittest.main()

