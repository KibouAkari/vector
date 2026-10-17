import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/fegcraft-assistant'))
from recipes import RecipeBook, build_catalog, normalise
from runtime import Assistant, State, safe_answer


def synthetic(count=7):
    # Artificial quantities, not copies of installed game assets.
    return {'type': 'minecraft:crafting_shaped', 'pattern': ['AA'],
            'key': {'A': 'minecraft:iron_ingot'},
            'result': {'id': 'minecraft:crafting_table', 'count': count}}


def catalog(recipe=None):
    return {'schema': 1, 'scope': 'vanilla-base', 'minecraft_version': '26.2',
            'source_sha256': '0' * 64, 'unsupported_count': 0,
            'recipes': [normalise('minecraft:crafting_table', recipe or synthetic())]}


class RecipeTests(unittest.TestCase):
    def test_answer_uses_actual_quantities_and_explicit_vanilla_scope(self):
        book = RecipeBook(catalog())
        answer = book.answer('Wie craftet man eine Werkbank?')
        self.assertIn('7x Werkbank aus 2x Eisenbarren', answer)
        self.assertIn('Minecraft 26.2', answer)
        self.assertIn('Mod-Anpassungen sind nicht geprüft', answer)
        safe_answer('Hey ExampleOne, ' + answer)

    def test_default_output_count_and_old_item_schema(self):
        value = synthetic()
        value['result'].pop('count')
        value['key']['A'] = {'item': 'minecraft:iron_ingot'}
        recipe = normalise('minecraft:crafting_table', value)
        self.assertEqual(recipe['count'], 1)
        self.assertEqual(recipe['rows'], [[['minecraft:iron_ingot'], ['minecraft:iron_ingot']]])

    def test_alternatives_tags_and_shapeless_layout_are_preserved(self):
        value = {'type': 'minecraft:crafting_shapeless',
                 'ingredients': [['minecraft:iron_ingot', '#minecraft:planks']],
                 'result': {'id': 'minecraft:crafting_table'}}
        answer = RecipeBook(catalog(value)).answer('Rezept Werkbank')
        self.assertIn('oder', answer)
        self.assertIn('Holzbretter', answer)
        self.assertIn('Anordnung beliebig', answer)

    def test_conditions_custom_predicates_and_invalid_numbers_are_not_guessed(self):
        for change in ({'fabric:load_conditions': []}, {'type': 'example:custom'}):
            value = synthetic(); value.update(change)
            with self.assertRaises(ValueError):
                normalise('minecraft:crafting_table', value)
        for count in (True, 0, 65, 1.5):
            with self.assertRaises(ValueError):
                normalise('minecraft:crafting_table', synthetic(count))
        value = synthetic(); value['key']['A'] = {'components': {'example': True}}
        with self.assertRaises(ValueError):
            normalise('minecraft:crafting_table', value)

    def test_missing_or_ambiguous_recipe_is_explicit_and_non_recipe_is_untouched(self):
        self.assertIsNone(RecipeBook().answer('Wie funktioniert Redstone?'))
        self.assertIn('kein eindeutig', RecipeBook().answer('Rezept Trichter'))
        self.assertIn('kein eindeutig', RecipeBook(catalog()).answer('Rezept für ein unbekanntes Item'))

    def test_invalid_catalog_and_unsafe_item_ids_are_rejected(self):
        for field, value in [('scope', 'effective-server'), ('minecraft_version', '1.21.4'), ('schema', True)]:
            data = catalog(); data[field] = value
            with self.assertRaises(ValueError):
                RecipeBook(data)
        data = catalog(); data['recipes'][0]['rows'][0][0] = ['minecraft:iron_ingot\n/op anyone']
        with self.assertRaises(ValueError):
            RecipeBook(data)

    def test_pinned_game_archive_build_ignores_cache_and_skips_unsupported_types(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'server.jar'
            with zipfile.ZipFile(path, 'w') as out:
                out.writestr('version.json', json.dumps({'id': '26.2'}))
                out.writestr('data/minecraft/recipe/crafting_table.json', json.dumps(synthetic()))
                out.writestr('data/minecraft/recipe/unsupported.json', json.dumps({'type': 'example:custom'}))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result = build_catalog(path, digest)
            self.assertEqual(len(result['recipes']), 1)
            self.assertEqual(result['unsupported_count'], 1)
            self.assertEqual(result['source_sha256'], digest)
            self.assertIn('7x', RecipeBook(result).answer('Rezept Werkbank'))
            with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
                build_catalog(path, '0' * 64)

    def test_wrong_version_and_duplicate_resources_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'server.jar'
            with zipfile.ZipFile(path, 'w') as out:
                out.writestr('version.json', json.dumps({'id': '1.21.4'}))
            with self.assertRaisesRegex(ValueError, 'VERSION_MISMATCH'):
                build_catalog(path, hashlib.sha256(path.read_bytes()).hexdigest())
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                with zipfile.ZipFile(path, 'w') as out:
                    out.writestr('version.json', json.dumps({'id': '26.2'}))
                    for _ in range(2):
                        out.writestr('data/minecraft/recipe/crafting_table.json', json.dumps(synthetic()))
            with self.assertRaisesRegex(ValueError, 'PATH_OR_COUNT_LIMIT'):
                build_catalog(path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_assistant_routes_supported_and_missing_recipes_without_a_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            class ForbiddenModel:
                def answer(self, *args):
                    raise AssertionError('NO_MODEL_FOR_RECIPES')
            assistant = Assistant(State(root / 'events.sqlite', b'x' * 32), root / 'absent',
                                  root / 'absent.json', root / 'absent-mods.json',
                                  ForbiddenModel(), RecipeBook(catalog()))
            uid = str(uuid.UUID(int=1))
            def payload(message, event):
                return {'principal': uid, 'name': 'ExampleOne', 'event': uid + ':' + str(event), 'message': message}
            first = assistant.handle(payload('yoo Vector, wie craftet man eine Werkbank?', 1))
            self.assertIn('Yoo ExampleOne, Grundrezept', first['text'])
            self.assertIn('7x Werkbank', first['text'])
            self.assertIn('kein eindeutig', assistant.handle(payload('hey Vector, Rezept Trichter', 2))['text'])
            self.assertIn('keine administrativen', assistant.handle(payload('hey Vector, Rezept und seed?', 3))['text'])
            self.assertEqual(assistant.handle(payload('Rezept Werkbank', 4)), {'status': 'ignored'})


if __name__ == '__main__':
    unittest.main()
