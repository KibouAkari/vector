import hashlib
import hmac
from http.client import HTTPConnection
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'services/fegcraft-assistant'))
from runtime import Assistant, State, safe_answer, LocalKnowledge
from server import Service, Handler
from unittest.mock import patch


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stats = self.root / 'stats'
        self.stats.mkdir()
        self.uid = '00000000-0000-0000-0000-000000000001'
        self.users = self.root / 'users.json'
        self.users.write_text(json.dumps([{'uuid': self.uid, 'name': 'ExampleOne'}]))
        (self.stats / (self.uid + '.json')).write_text(json.dumps({'stats': {'minecraft:custom': {'minecraft:mob_kills': 52000, 'minecraft:play_time': 72000}}}))
        self.mods = self.root / 'mods.json'
        self.mods.write_text('["fabric-api", "travelersbackpack"]')
        self.clock = [1000]
        self.key = bytes.fromhex('ab' * 32)
        self.state = State(self.root / 'state.sqlite', self.key, lambda: self.clock[0])
        self.ai = Assistant(self.state, self.stats, self.users, self.mods)
        self.sequence = 0

    def payload(self, message):
        self.sequence += 1
        return {'principal': self.uid, 'name': 'ExampleOne', 'event': self.uid + ':' + str(self.sequence), 'message': message}

    def test_real_stats_with_author_and_no_model(self):
        result = self.ai.handle(self.payload('yoo Vector, wer hat die meisten mobkills?'))
        self.assertEqual(result['status'], 'answered')
        self.assertIn("Yoo ExampleOne, Mobkills: ExampleOne 52'000 Kills", result['text'])
        self.assertIn('gespeicherte', result['text'])

    def test_all_record_holders_are_fresh_and_cover_five_categories(self):
        first=self.ai.handle(self.payload('hey Vector, kannst du mir einfach nur alle Rekordhalter geben?'))
        for label in ('Spielzeit:','Strecke:','Mobkills:','Spielerkills:','Tode:'):
            self.assertIn(label,first['text'])
        path=self.stats/(self.uid+'.json')
        path.write_text(json.dumps({'stats':{'minecraft:custom':{'minecraft:mob_kills':53000,'minecraft:play_time':72000}}}))
        second=self.ai.handle(self.payload('hey Vector, alle Rekordhalter'))
        self.assertIn("53'000 Kills",second['text'])
        self.assertNotIn("52'000 Kills",second['text'])

    def test_private_topics_neutral_without_model(self):
        for text in ('hey Vector, was ist der seed?', 'hi Vector, kann ExampleOne gamemode creative nutzen?', 'hallo Vector, cheatet ExampleOne?'):
            self.assertIn('keine administrativen', self.ai.handle(self.payload(text))['text'])

    def test_ordinary_chat_ignored_and_unknown_player_not_leader(self):
        self.assertEqual(self.ai.handle(self.payload('wer hat die meisten mobkills?')), {'status': 'ignored'})
        answer = self.ai.handle(self.payload('hey Vector, wie viele Tode hat UnknownPlayer?'))
        self.assertIn('vollständigen Spielernamen', answer['text'])

    def test_unreadable_stats_do_not_invent_values(self):
        (self.stats / (self.uid + '.json')).write_text('{broken')
        result = self.ai.handle(self.payload('hey Vector, wer hat die meisten mobkills?'))
        self.assertIn('unvollständig', result['text'])
        self.assertNotIn('52', result['text'])

    def test_limits_and_replays_survive_restart_without_private_text(self):
        first = self.payload('hey Vector, redstone')
        self.ai.handle(first)
        self.ai.handle(self.payload('hey Vector, redstone'))
        self.ai.handle(self.payload('hey Vector, redstone'))
        restarted = State(self.root / 'state.sqlite', self.key, lambda: self.clock[0])
        self.assertEqual(restarted.admit(self.uid, first['event']), 'duplicate')
        self.assertEqual(restarted.admit(self.uid, self.uid + ':99'), 'limited')
        with sqlite3.connect(self.root / 'state.sqlite') as db:
            text = repr(db.execute('SELECT * FROM events').fetchall())
        self.assertNotIn(self.uid, text)
        self.assertNotIn('ExampleOne', text)
        self.assertNotIn('redstone', text)
        self.clock[0] += 61
        self.assertEqual(restarted.admit(self.uid, self.uid + ':100'), 'accepted')

    def test_global_budget_and_state_cap(self):
        for i in range(12):
            self.assertEqual(self.state.admit(str(i), str(i)), 'accepted')
        self.assertEqual(self.state.admit('last', 'last'), 'limited')

    def test_output_filter_blocks_commands_mentions_and_emoji(self):
        for text in ('/op ExampleOne', 'Nutze gamemode creative', 'https://example.invalid', '@everyone', 'Hallo\nWelt', '\u00a7aText', '\U0001f600', 'Text\u202eab'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                safe_answer(text)
        self.assertEqual(safe_answer('Ein Komparator kann die Füllung einer Truhe messen.'), 'Ein Komparator kann die Füllung einer Truhe messen.')

    def test_model_only_for_allowed_topic_and_filters_output(self):
        class Fixture:
            calls = 0
            def answer(inner, question, mods):
                inner.calls += 1
                return 'Ein Kolben bewegt Blöcke.'
        model = Fixture()
        self.ai.knowledge = model
        self.assertIn('Kolben', self.ai.handle(self.payload('hey Vector, wie funktioniert ein Kolben?'))['text'])
        self.ai.handle(self.payload('hey Vector, schreib mir eine Bewerbung'))
        self.assertEqual(model.calls, 1)
        with self.assertRaises(ValueError):
            LocalKnowledge('unused', endpoint='https://external.example.invalid')

    def test_immediate_next_request_during_previous_response_delivery_is_not_busy(self):
        service=Service(('127.0.0.1',0),self.ai,self.key,lambda:1_000_000_000)
        release=threading.Event();original=Handler.respond
        def delayed(handler,status,payload):
            original(handler,status,payload)
            if status==200 and payload.get('status')=='answered':release.wait(2)
        def send(raw):
            connection=HTTPConnection(*service.server_address,timeout=2)
            signature=hmac.new(self.key,b'1000000000\n'+raw,hashlib.sha256).hexdigest()
            connection.request('POST','/v1/minecraft',raw,{'X-Vector-Time':'1000000000','X-Vector-Signature':signature})
            response=connection.getresponse();result=(response.status,json.loads(response.read()));connection.close();return result
        with patch.object(Handler,'respond',delayed):
            thread=threading.Thread(target=service.serve_forever,daemon=True);thread.start()
            try:
                raw=json.dumps(self.payload('hey Vector, wer hat die meisten mobkills?')).encode()
                self.assertEqual(send(raw)[0],200)
                self.assertEqual(send(raw),(200,{'status':'duplicate'}))
            finally:
                release.set();service.shutdown();service.server_close()

    def test_authenticated_http_boundary_and_busy(self):
        service = Service(('127.0.0.1', 0), self.ai, self.key, lambda: 1000)
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(service.server_close)
        self.addCleanup(service.shutdown)
        def send(raw, signature=None, timestamp='1000', path='/v1/minecraft'):
            connection = HTTPConnection(*service.server_address, timeout=2)
            signature = signature or hmac.new(self.key, timestamp.encode() + b'\n' + raw, hashlib.sha256).hexdigest()
            connection.request('POST', path, raw, {'X-Vector-Time': timestamp, 'X-Vector-Signature': signature})
            response = connection.getresponse()
            result = response.status, json.loads(response.read())
            connection.close()
            return result
        # Transport requires a ten-digit epoch; keep the synthetic clock fixed.
        service.clock = lambda: 1_000_000_000
        raw = json.dumps(self.payload('hey Vector, wer hat die meisten mobkills?')).encode()
        self.assertEqual(send(raw, timestamp='1000000000')[0], 200)
        self.assertEqual(send(raw, timestamp='1000000000')[1]['status'], 'duplicate')
        self.assertEqual(send(raw, '0' * 64, '1000000000')[0], 401)
        self.assertEqual(send(raw, timestamp='1000000100')[0], 401)
        service.slot.acquire()
        try:
            self.assertEqual(send(raw, timestamp='1000000000')[0], 503)
        finally:
            service.slot.release()
        self.assertEqual(send(b'x' * 8193, timestamp='1000000000')[0], 413)


if __name__ == '__main__':
    unittest.main()
