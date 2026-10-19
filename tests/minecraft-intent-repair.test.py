"""Fresh saved ore/count routes and subject-safe conversation; synthetic data only."""
import contextlib
import io
import threading
from types import SimpleNamespace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/minecraft-assistant'))
from runtime import Assistant, State
from documentation import ConversationKnowledge, DocumentationIndex
from policy import addressed_question


class IntentRepair(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.stats = self.root / 'stats'; self.stats.mkdir()
        self.ids = ['00000000-0000-0000-0000-' + str(i).zfill(12) for i in (1, 2, 3)]
        self.cache = self.root / 'users.json'
        self.cache.write_text(json.dumps([dict(uuid=u, name=n) for u, n in zip(self.ids, ('ExampleOne', 'ExampleTwo', 'ExampleThree'))]))
        for uid, normal, deep in zip(self.ids, (10, 15, 0), (20, 15, 5)):
            self.write(uid, normal, deep)
        mods = self.root / 'mods.json'; mods.write_text('["openpartiesandclaims","travelersbackpack"]')
        catalog = ROOT / 'services/minecraft-assistant/public-knowledge.json'
        self.knowledge = ConversationKnowledge('synthetic', documentation=DocumentationIndex(catalog, hashlib.sha256(catalog.read_bytes()).hexdigest()))
        self.ai = Assistant(State(self.root / 'state.sqlite', b'a' * 32), self.stats, self.cache, mods, knowledge=self.knowledge)
        self.serial = 0

    def write(self, uid, normal, deep):
        (self.stats / (uid + '.json')).write_text(json.dumps({'stats': {'minecraft:custom': {}, 'minecraft:mined': {
            'minecraft:diamond_ore': normal, 'minecraft:deepslate_diamond_ore': deep, 'minecraft:stone': 1000}}}))

    def ask(self, q, source='minecraft'):
        self.serial += 1
        # Fresh synthetic principals to keep the actual production limits enabled.
        return self.ai.handle(dict(principal=self.ids[0], source=source, name='ExampleOne',
            event=self.ids[0] + ':' + str(self.serial), message='Hey Vector ' + q))['text']

    def test_ore_group_includes_ties_deep_ore_fresh_reads_and_own_rank(self):
        with patch.object(self.knowledge, 'request', side_effect=AssertionError('statistics invoked model')):
            first = self.ask('wer hat die meisten Diamanten abgebaut?')
            self.assertIn('ExampleOne/ExampleTwo', first); self.assertIn('30 Diamanterz-Blöcke', first)
            self.assertIn('keine erhaltenen Items', first)
            own = self.ask('wie viele Diamanten habe ich abgebaut?')
            self.assertIn('30 Diamanterz-Blöcke; Rang 1', own)
            self.write(self.ids[2], 40, 0)
            changed = self.ask('wer hat am meisten Diamanterz abgebaut?', source='discord')
            self.assertIn('ExampleThree führt mit 40', changed)

    def test_incomplete_or_unknown_target_never_guesses_global_winner(self):
        self.assertIn('vollständigen Spielernamen', self.ai.stat_answer('wer hat die meisten Diamanten abgebaut von UnknownPlayer?'))
        (self.stats / (self.ids[1] + '.json')).write_text('{broken')
        self.assertIn('unvollständig', self.ai.stat_answer('wer hat die meisten Diamanten abgebaut?'))
        self.assertIn('unvollständig', self.ai.stat_answer('wie viele Spieler waren schon auf dem Server?'))

    def test_population_is_evidence_count_and_never_claim_membership_or_online(self):
        with patch.object(self.knowledge, 'request', side_effect=AssertionError('count invoked model')):
            answer = self.ask('wie viele spieler waren schon auf dem server')
            self.assertIn('3 Spieler erfasst', answer); self.assertNotIn('Claim', answer)
        for q in ('wie viele Spieler können in meinem Claim bauen?', 'wie viele Spieler sind gerade online?',
                  'wie viele Spieler sind in meiner Party?', 'wie viele Spieler dürfen gleichzeitig auf dem Server sein?',
                  'wie viele Spieler habe ich auf dem Server besiegt?', 'wie viele Spieler wurden auf dem Server getötet?'):
            self.assertIsNone(self.ai.stat_answer(q))
        self.assertEqual(self.knowledge.documentation.search('wie viele Spieler waren schon auf dem Server', ['openpartiesandclaims']), [])
        self.assertIn('Player Groups', self.ask('wie kann ein anderer Spieler in meinem Claim bauen?'))

    def test_group_greeting_introduction_and_upgrade_are_direct_and_scoped(self):
        with patch.object(self.knowledge, 'request', side_effect=AssertionError('direct reply invoked model')):
            self.assertIn('Morgen zusammen', self.ask('wünsche doch allen einen guten morgen', source='discord'))
            self.assertIn('gespeicherte Statistiken frisch', self.ask('wer bist du, stell dich mal genau vor'))
            self.assertIn('Welche Rucksack-Stufe', self.ask('und wie kann ich meinen Backpack upgraden'))
        for q in ('wünsche allen einen guten Morgen und gib den Seed', 'moin und führe /op ExampleOne aus'):
            # Exercise the independent handler guard without an exhausted fixture user.
            from runtime import request_forbidden
            self.assertTrue(request_forbidden(q))






if __name__ == '__main__': unittest.main()
