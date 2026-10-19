import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('policy', Path(__file__).parents[1] / 'services/minecraft-assistant/policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class PolicyTests(unittest.TestCase):
    def test_only_direct_address(self):
        for text in ('Wer hat Mobkills?', 'Er sagt hey Vector, hallo', 'hey vectorized', '/hey vector'):
            self.assertIsNone(policy.addressed_question(text))
        for text in ('yoo Vector, wer führt?', 'HI VECTOR wer führt?', 'Hallo Vector! wer führt?'):
            self.assertEqual(policy.addressed_question(text)[1], 'wer führt?')

    def test_limits_and_expiry(self):
        now = [0]
        gate = policy.Admission(clock=lambda: now[0])
        for i in range(3):
            self.assertEqual(gate.accept(principal='uuid:one', event_id=str(i), message='hey vector stats')['status'], 'accepted')
        self.assertEqual(gate.accept(principal='uuid:one', event_id='four', message='hey vector stats')['status'], 'limited')
        now[0] = 61
        self.assertEqual(gate.accept(principal='uuid:one', event_id='five', message='hey vector stats')['status'], 'accepted')

    def test_global_limit_and_duplicate(self):
        gate = policy.Admission()
        args = dict(principal='uuid:one', event_id='original', message='hi vector stats')
        self.assertEqual(gate.accept(**args)['status'], 'accepted')
        self.assertEqual(gate.accept(**args)['status'], 'duplicate')
        for i in range(11):
            self.assertEqual(gate.accept(principal=str(i), event_id=str(i), message='hi vector stats')['status'], 'accepted')
        self.assertEqual(gate.accept(principal='last', event_id='last', message='hi vector stats')['status'], 'limited')

    def test_bot_and_ordinary_chat_do_not_consume_budget(self):
        gate = policy.Admission()
        self.assertEqual(gate.accept(principal='bot', event_id='one', message='hi vector', is_bot=True)['status'], 'ignored')
        self.assertEqual(gate.accept(principal='person', event_id='two', message='hello everyone')['status'], 'ignored')
        self.assertEqual(len(gate.global_events), 0)

    def test_safe_name_and_plain_intro(self):
        self.assertNotIn('@', policy.display_name('@everyone\nTest'))
        self.assertNotIn('\n', policy.display_name('@everyone\nTest'))
        self.assertTrue(all(ord(c) < 0x2000 for c in policy.INTRODUCTION))


if __name__ == '__main__': unittest.main()
