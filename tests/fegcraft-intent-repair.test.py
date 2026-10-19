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
sys.path.insert(0, str(ROOT / 'services/fegcraft-assistant'))
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
        catalog = ROOT / 'services/fegcraft-assistant/public-knowledge.json'
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

    def test_signed_http_stage_smoke_uses_only_synthetic_inputs_and_zero_native_calls(self):
        from server import Service
        spec=importlib.util.spec_from_file_location('intent_smoke',ROOT/'tests/fegcraft-intent-smoke.py')
        smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)
        (self.root/'run/secrets').mkdir(parents=True);(self.root/'run/secrets/vector_fegcraft_token').write_text(('ab'*32))
        (self.root/'state').mkdir()
        self.cache.write_text(json.dumps([dict(uuid=u,name='Example'+str(n)) for n,u in enumerate(self.ids,1)]))
        self.ai.state=State(self.root/'state/events.sqlite',bytes.fromhex('ab'*32))
        service=Service(('127.0.0.1',0),self.ai,bytes.fromhex('ab'*32))
        worker=threading.Thread(target=service.serve_forever,daemon=True);worker.start()
        try:
            with patch.object(self.knowledge,'request',side_effect=AssertionError('stage invoked model')),contextlib.redirect_stdout(io.StringIO()) as output:
                smoke.main(root=self.root,endpoint='http://127.0.0.1:'+str(service.server_address[1]))
            self.assertTrue(json.loads(output.getvalue())['passed'])
        finally:
            service.shutdown();service.server_close();worker.join(timeout=2)

    def test_update_relocates_only_owned_readonly_inputs_and_blocks_drift(self):
        spec=importlib.util.spec_from_file_location('intent_update',ROOT/'scripts/deploy/update-fegcraft-intents.py')
        update=importlib.util.module_from_spec(spec);spec.loader.exec_module(update)
        profile={'services':{'assistant':{'image':'qualified','user':'1001:1001','networks':['private'],
          'environment':{'VECTOR_FEGCRAFT_KNOWLEDGE':'4','VECTOR_FEGCRAFT_MOD_RECIPES_SHA256':'a'*64},
          'volumes':[dict(target=t,source='/old/'+str(i),read_only=True) for i,t in enumerate(('/code','/inputs/documentation.json','/inputs/mod-recipes.json','/state'))]}}}
        original=json.loads(json.dumps(profile));changed=update.candidate(profile,Path('/new'),'a'*64)
        self.assertEqual(profile,original)
        for a,b in zip(changed['services']['assistant']['volumes'],original['services']['assistant']['volumes']):
            if a['target']!='/state': a['source']=b['source']
        self.assertEqual(changed,original)
        with self.assertRaises(RuntimeError):update.candidate(profile,Path('/new'),'b'*64)
        profile['services']['assistant']['volumes'][0]['read_only']=False
        with self.assertRaises(RuntimeError):update.candidate(profile,Path('/new'),'a'*64)

    def test_pending_addon_preserves_metadata_and_refuses_a_changed_game_generation(self):
        spec=importlib.util.spec_from_file_location('intent_pending',ROOT/'scripts/deploy/update-fegcraft-intents.py')
        update=importlib.util.module_from_spec(spec);spec.loader.exec_module(update)
        addon=self.root/'addon.jar';addon.write_bytes(b'old fixture');addon.chmod(0o640)
        artifact=self.root/'vector-minecraft-0.1.0.jar';artifact.write_bytes(b'new fixture')
        sha=lambda raw:hashlib.sha256(raw).hexdigest()
        (self.root/'addon-proof.json').write_text(json.dumps(dict(offline_unit_passed=True,sha256=sha(artifact.read_bytes()))))
        game=dict(container='same-game',started_at='same-start')
        observed={'Id':'same-game','State':{'StartedAt':'same-start'}}
        writes=[]
        def atomic(path,raw,uid,gid,mode):
            writes.append((path,uid,gid,mode));path.write_bytes(raw);path.chmod(mode)
        p=SimpleNamespace(read=lambda path:path.read_bytes(),sha=sha,
            run=lambda *args:json.dumps([observed]).encode(),load=lambda *args:SimpleNamespace(atomic=atomic))
        h=SimpleNamespace(ADDON=addon)
        protected=lambda *args:{str(addon):sha(json.dumps(sha(addon.read_bytes()),sort_keys=True).encode()),'other':'unchanged'}
        support=SimpleNamespace(protected_live=protected,atomic=lambda path,raw:path.write_bytes(raw))
        record={'protected':protected()}
        update.stage_addon(p,h,support,SimpleNamespace(BASE='fixture'),self.root,record,game)
        self.assertTrue(record['addon_staged']);self.assertEqual(addon.read_bytes(),b'new fixture')
        self.assertEqual(writes[0][1:],(addon.stat().st_uid,addon.stat().st_gid,0o640))
        self.assertEqual((self.root/'addon.before.jar').read_bytes(),b'old fixture')
        update.addon_guard(p,h,support,self.root,record)
        observed['State']['StartedAt']='later-start'
        with self.assertRaisesRegex(RuntimeError,'GAME_RESTART_REQUIRES_REVIEW'):
            update.addon_guard(p,h,support,self.root,record)
        self.assertEqual(len(writes),1)

    def test_new_greetings_are_anchored_bounded_and_case_insensitive(self):
        for g in ('Eyy', 'ey', 'yooo', 'yo', 'hello', 'moin', 'servus', 'guten morgen', 'guten nachmittag', 'guten abend', 'guete morge'):
            self.assertEqual(addressed_question(g + ' VEcToR, wie geht es dir?')[1], 'wie geht es dir?')
        for text in ('heute guten Morgen Vector', 'moin VectorSuffix', 'eyyyyyyyyy Vector', 'guten Morgen zusammen', 'hey VectorExtra'):
            self.assertIsNone(addressed_question(text))


if __name__ == '__main__': unittest.main()
