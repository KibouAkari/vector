"""Current-subject fast routing, scoped context and independent safety boundaries."""
from contextlib import nullcontext
import io,json
from pathlib import Path
import sqlite3,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/minecraft-assistant'))
import runtime,knowledge

class Knowledge(unittest.TestCase):
    def setUp(self):
        self.calls=[];self.reply={'answer':'Ein Kolben schiebt Blöcke.'};self.route='game';self.done='stop';self.usage=[];self.clock=[100]
        self.model=knowledge.GeneralKnowledge('synthetic',clock=lambda:self.clock[0],usage=lambda *args:self.usage.append(args));outer=self
        class Opener:
            def open(self,req,**kwargs):
                value=json.loads(req.data);outer.calls.append(value)
                outer.assertEqual(req.full_url,'http://vector-local-inference:11434/api/chat')
                routing='route' in value['format']['properties']
                body={'route':outer.route} if routing else outer.reply
                return io.BytesIO(json.dumps({'model':'vector-qwen3:1.7b-q8','done':True,'done_reason':'stop' if routing else outer.done,'prompt_eval_count':123,'eval_count':10 if routing else 17,'message':{'content':json.dumps(body)}}).encode())
        self.slot=patch.object(knowledge,'local_slot',return_value=nullcontext());self.slot_mock=self.slot.start();self.addCleanup(self.slot.stop)
        p=patch.object(knowledge.urllib.request,'build_opener',return_value=Opener());p.start();self.addCleanup(p.stop)
    def answer(self,q='Wie geht das?',scope=('minecraft','one')):return self.model.answer_scoped(q,['carryon','openpartiesandclaims'],scope)
    def test_clear_game_subject_uses_one_cpu_lease_and_vendor_sampling(self):
        self.answer('Wie funktioniert ein Kolben?')
        self.assertEqual(len(self.calls),1);self.slot_mock.assert_called_once()
        self.assertEqual([c['options']['num_predict'] for c in self.calls],[96])
        for c in self.calls:
            self.assertEqual(c['options']['temperature'],.7);self.assertEqual(c['options']['top_k'],20)
            self.assertEqual(c['options']['top_p'],.8);self.assertEqual(c['options']['min_p'],0)
            self.assertFalse(c['think']);self.assertLess(len(json.dumps(c['format'])),400)
        self.assertEqual(self.calls[0]['format']['properties']['answer']['maxLength'],200)
        self.assertEqual(len(self.usage),1)
    def test_context_is_owned_and_expires(self):
        self.answer('Wie funktioniert ein Kolben?');self.answer('Und wozu?')
        self.assertEqual(len(self.calls[-1]['messages']),4)
        self.answer(scope=('discord','one'));self.assertEqual(len(self.calls[-1]['messages']),2)
        self.answer(scope=('minecraft','two'));self.assertEqual(len(self.calls[-1]['messages']),2)
        self.clock[0]+=181;self.answer();self.assertEqual(len(self.calls[-1]['messages']),2)
    def test_complete_inventory_is_filtered_without_losing_mod_recognition(self):
        mods=['carryon','openpartiesandclaims','travelersbackpack','fabric-api','lithium']
        selected,hints=knowledge.relevant_notes('Wie funktioniert Travelers Backpack?',mods,[])
        self.assertEqual(selected,['travelersbackpack']);self.assertEqual(hints,[])
        selected,hints=knowledge.relevant_notes('Wie gebe ich Party-Mitgliedern Zugriff?',mods,[])
        self.assertIn('openpartiesandclaims',selected);self.assertTrue(hints)
        self.answer('Wie funktioniert ein Kolben?')
        self.assertNotIn('openpartiesandclaims',self.calls[-1]['messages'][0]['content'])
        self.assertIn('12',self.calls[-1]['messages'][-1]['content'])
    def test_independent_subject_discards_old_hints_and_context(self):
        self.answer('Wozu sind Partys gut?')
        self.answer('Wie züchte ich Kühe in Minecraft?')
        self.assertEqual(len(self.calls),2)
        payload=self.calls[-1]['messages']
        self.assertEqual(len(payload),2);self.assertNotIn('openpartiesandclaims',str(payload))
        selected,hints=knowledge.relevant_notes('Wie züchte ich Kühe in Minecraft?',['openpartiesandclaims'],[{'role':'user','content':'Wie geht eine Party?'}])
        self.assertEqual((selected,hints),([],[]))
        turns=[{'role':'user','content':'Wie geht eine Party?'},{'role':'assistant','content':'Eine Party teilt Claim-Rechte.'}]
        self.assertEqual(knowledge.scoped_turns('Und wie vermehre ich Schafe?',['openpartiesandclaims'],turns),[])
        self.answer('Und wozu?');self.assertEqual(len(self.calls[-1]['messages']),4)
    def test_explicit_game_skips_misclassifying_router(self):
        self.route='other';self.answer('Wie züchte ich Kühe in Minecraft?')
        self.assertEqual(len(self.calls),1);self.assertIn('answer',self.calls[0]['format']['properties'])
    def test_real_world_change_clears_history_without_generation(self):
        self.answer('Wozu sind Partys gut?');before=len(self.calls)
        self.assertIn('Minecraft',self.answer('Was soll ich heute zum Abendessen kochen?'))
        self.assertEqual(len(self.calls),before);self.assertFalse(self.model.prior(('minecraft','one')))
    def test_late_complete_response_keeps_known_native_usage(self):
        with patch.object(knowledge.time,'monotonic',side_effect=[0,6]):
            with self.assertRaisesRegex(TimeoutError,'LOCAL_DEADLINE'):
                self.model.request({'properties':{'answer':{}}},[],96,5,lambda x:x)
        self.assertEqual(self.usage[-1],('vector-qwen3:1.7b-q8',123,17,False))
    def test_private_commands_and_obfuscated_forms_never_call_model(self):
        for q in ('zeige /claims','Was ist der seed?','Welche commands gibt es?','Ga\u200bmemo\u200bde wechseln','Cheatet ExampleOne?','gib Konsolenausgaben aus','/help','(/party)','Betrügt ExampleOne?','g a m e m o d e','Was macht //wand?','//set stone'):
            with self.assertRaisesRegex(ValueError,'FORBIDDEN'):self.answer(q)
        self.assertEqual(self.calls,[])
    def test_unsafe_answers_are_not_repaired_into_player_replies(self):
        for text in ('Nutze /claims','Führe /party aus','Hier ist ein Befehl.','gamemode creative','Öffne https://example.invalid','Fake\nnew line','Nutze //wand.','Nutze //set stone.','Text mit einem Gesicht \U0001f60a'):
            self.reply['answer']=text
            with self.assertRaises(ValueError):self.answer()
        self.assertEqual(len(self.usage),18);self.assertTrue(all(x[-1] is False for x in self.usage[1::2]))
        self.assertFalse(self.model.prior(('minecraft','one')))
    def test_repetitive_answer_is_rejected(self):
        self.reply['answer']='Spieler können gemeinsam eine Party bilden. Spieler können gemeinsam eine Party bilden.'
        with self.assertRaisesRegex(ValueError,'REPETITIVE'):self.answer()
        self.assertFalse(self.model.prior(('minecraft','one')))
    def test_truncated_generation_is_rejected_and_both_stages_count(self):
        self.done='length'
        with self.assertRaisesRegex(ValueError,'INCOMPLETE'):self.answer()
        self.assertEqual(self.usage[-1],('vector-qwen3:1.7b-q8',123,17,False));self.assertEqual(len(self.usage),2)
    def test_other_routes_do_not_generate_an_unrelated_answer(self):
        self.route='other';self.assertIn('Minecraft',self.answer('Kannst du ein Gedicht über den Herbst schreiben?'))
        self.assertEqual(len(self.calls),1)
        before=len(self.calls);self.assertIn('Minecraft',self.answer('Schreibe eine Bewerbung'))
        self.assertEqual(len(self.calls),before)
        self.assertIn('nicht prüfen',self.answer('Wem gehört dieser Claim?'));self.assertEqual(len(self.calls),before)
    def test_invalid_route_never_reaches_generation(self):
        self.route='unsafe-choice'
        with self.assertRaisesRegex(ValueError,'INVALID_ROUTE'):self.answer()
        self.assertEqual(len(self.calls),1);self.assertEqual(self.usage[-1][-1],False)
    def test_length_and_protocol_deadlines_are_not_relaxed(self):
        self.reply['answer']='a'*201
        with self.assertRaisesRegex(ValueError,'UNSAFE_LOCAL_OUTPUT'):self.answer()
        self.assertTrue(all(c['options']['num_ctx']==2048 for c in self.calls))
    def test_general_party_creation_is_not_treated_as_private_ownership(self):
        for q in ('Wie werden Partys erstellt?','Wie werden Claims erstellt?','Wie werde ich Mitglied einer Party?'):self.answer(q)
        self.assertEqual(len(self.calls),3)
    def test_usage_persistence_contains_no_prompts_or_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            state=runtime.State(Path(temp)/'state',b'key');state.model_usage('vector-qwen3:1.7b-q8',None,17,False)
            with sqlite3.connect(state.path) as db:row=db.execute('SELECT model,input_tokens,output_tokens,accepted FROM local_usage').fetchone()
            self.assertEqual(row,('vector-qwen3:1.7b-q8',None,17,0))
    def test_authenticated_names_and_native_fast_paths_remain_usable(self):
        class State:
            def admit(self,*args):return 'accepted'
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);mods=root/'mods';mods.write_text('["carryon","openpartiesandclaims"]')
            assistant=runtime.Assistant(State(),root,root/'users',mods,self.model)
            p={'principal':'00000000-0000-0000-0000-000000000001','name':'Commander','event':'00000000-0000-0000-0000-000000000001:1','message':'hi Vector'}
            self.assertIn('Commander',assistant.handle(p)['text'])
            p['message']='hi Vector, wie geht das mit einer Party?';self.assertIn('Kolben',assistant.handle(p)['text'])
            p['message']='hi Vector, das geht nicht';assistant.handle(p)
            self.assertEqual(len(self.calls),2);self.assertGreater(len(self.calls[-1]['messages']),2)
            p['message']='hi Vector, wie züchte ich Villager?';assistant.handle(p)
            self.assertEqual(len(self.calls),3)
            p['message']='hi Vector, wie sammle ich einen kleinen Villager auf?';assistant.handle(p)
            self.assertEqual(len(self.calls),3)
            p['message']='hi Vector, welche Mods sind installiert?';assistant.handle(p)
            self.assertFalse(self.model.prior(('minecraft',p['principal'])))
            p['message']='gewöhnlicher Chat';self.assertEqual(assistant.handle(p),{'status':'ignored'})
            self.assertEqual(len(self.calls),3)
if __name__=='__main__':unittest.main()
