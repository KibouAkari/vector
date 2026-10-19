"""Public recipe extraction, direct mod help, casing and friendly reply boundaries."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest import TestCase,main
from unittest.mock import patch
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/minecraft-assistant'))
from documentation import DocumentationIndex,ConversationKnowledge
from modrecipes import ModRecipes,export_installed
from runtime import Assistant,friendly_statistics,request_forbidden,safe_answer
from recipes import RecipeBook
from types import SimpleNamespace
from policy import addressed_question


class ModContext(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.recipe={'type':'travelersbackpack:backpack_shaped','pattern':['XBX','CDC','XSX'],
          'key':{'X':'#c:leathers','B':'#c:strings','C':'travelersbackpack:backpack_tank','D':'#c:chests/wooden','S':'#travelersbackpack:sleeping_bags'},
          'result':{'id':'travelersbackpack:standard'}}
        self.jar=self.root/'mod.jar'
        with zipfile.ZipFile(self.jar,'w') as archive:
            archive.writestr('fabric.mod.json',json.dumps({'id':'travelersbackpack','version':'11.3.2'}))
            archive.writestr('data/travelersbackpack/recipe/standard.json',json.dumps(self.recipe))
            archive.writestr('private-file.txt','never read')
        value=export_installed(self.jar);path=self.root/'recipes.json';raw=json.dumps(value).encode();path.write_bytes(raw)
        self.book=ModRecipes(path,hashlib.sha256(raw).hexdigest())
        catalog=ROOT/'services/minecraft-assistant/public-knowledge.json'
        self.index=DocumentationIndex(catalog,hashlib.sha256(catalog.read_bytes()).hexdigest())
        self.ai=ConversationKnowledge('synthetic',documentation=self.index)

    def test_case_variants_are_allowed_but_ordinary_chat_is_not(self):
        for name in ('vector','VECTOR','VeCtOr'):
            self.assertEqual(addressed_question('Yoo '+name+', wie geht es dir?')[1],'wie geht es dir?')
        self.assertIsNone(addressed_question('wer hat die meisten Mobkills?'))

    def test_installed_recipe_types_tags_aliases_and_no_unrelated_archive_data(self):
        value=export_installed(self.jar)
        self.assertEqual(set(value['recipes']),{'travelersbackpack:standard'})
        self.assertEqual(value['jar_sha256'],hashlib.sha256(self.jar.read_bytes()).hexdigest())
        for question in ('wie bekomme ich einen Backpack?','wie crafte ich einen Rucksack?','Rezept für einen standart Backpack'):
            answer=self.book.answer(question)
            self.assertIn('Standardrucksack',answer);self.assertIn('Leder, Faden, Leder',answer)
            self.assertIn('Rucksacktank, Holztruhe, Rucksacktank',answer)
            self.assertIn('Grundrezept der installierten Mod',answer);safe_answer(answer)
        self.assertIsNone(self.book.answer('wie funktioniert ein Kolben?'))
        self.assertNotIn('Leder, Faden, Leder',self.book.answer('wie crafte ich einen Diamant Backpack?'))
        self.book.value['recipes']['travelersbackpack:standard']['key']['X']='/op Synthetic'
        self.assertNotIn('/op',self.book.answer('wie bekomme ich einen Backpack?'))

    def test_recipe_version_and_digest_drift_refused(self):
        with zipfile.ZipFile(self.root/'other.jar','w') as archive:
            archive.writestr('fabric.mod.json',json.dumps({'id':'different','version':'11.3.2'}))
        with self.assertRaises(ValueError):export_installed(self.root/'other.jar')
        path=self.root/'recipes.json'
        with self.assertRaises(ValueError):ModRecipes(path,'0'*64)

    def test_all_installed_mods_have_scoped_public_cards_and_safe_text(self):
        mods={row['mod'] for row,_,_ in self.index.rows if row['id'].startswith('mod-')}
        self.assertEqual(len(mods),63)
        for row,_,_ in self.index.rows:
            safe_answer(row['text']);self.assertFalse(request_forbidden(row['text']))
        with patch.object(self.ai,'request',side_effect=AssertionError('direct help invoked model')):
            rights=self.ai.answer_scoped('wie kann ein anderer Spieler in meinem Claim bauen?',['openpartiesandclaims'],('mc','one'))
            self.assertIn('Player Groups',rights)
            self.assertIn('Haupthand',self.ai.answer_scoped('wie funktioniert diese Backpack Mod?',['travelersbackpack'],('mc','one')))
            app=Assistant(SimpleNamespace(admit=lambda *args:'accepted'),'/unused','/unused','/unused',self.ai,RecipeBook())
            app.mods=lambda:['openpartiesandclaims']
            response=app.handle(dict(principal='00000000-0000-0000-0000-000000000001',name='Synthetic',event='00000000-0000-0000-0000-000000000001:1',message='hey vector wie baue ich einen Claim?'))
            self.assertIn('beanspruche',response['text'])
            self.assertIn('Axt',self.ai.answer_scoped('wie funktioniert Chopt?',['chopt'],('mc','one')))

    def test_friendly_statistics_omit_provenance_and_repeated_name(self):
        answer=friendly_statistics('ExampleOne: Spielerkills 50 Kills; Rang 2. Stand: gespeicherte Spielerdateien.','ExampleOne')
        self.assertEqual(answer,'du hast 50 Spielerkills und bist damit auf Rang 2.')
        self.assertEqual(friendly_statistics('ExampleTwo: Mobkills 100 Kills; Rang 1. Stand: gespeicherte Spielerdateien.','ExampleOne'),
                         'ExampleTwo hat 100 Mobkills und ist damit auf Rang 1.')
        self.assertNotIn('Stand:',friendly_statistics('ExampleOne führt bei Spielzeit 20.0 h. Stand: gespeicherte Spielerdateien.','ExampleOne'))
        app=Assistant(SimpleNamespace(admit=lambda *args:'accepted'),'/unused','/unused','/unused',self.ai)
        app.stat_answer=lambda *args,**kwargs:'ExampleOne: Spielerkills 50 Kills; Rang 2. Stand: gespeicherte Spielerdateien.'
        result=app.handle(dict(principal='00000000-0000-0000-0000-000000000001',name='ExampleOne',source='discord',event='00000000-0000-0000-0000-000000000001:1',message='hey vector welchen Rang hat ExampleOne bei Spielerkills?'))
        self.assertNotIn('du hast',result['text'])
        self.assertIn('ExampleOne hat',result['text'])




if __name__=='__main__': main()
