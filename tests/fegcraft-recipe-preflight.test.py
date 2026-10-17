import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('recipes', ROOT / 'scripts/diagnostics/fegcraft-recipe-preflight.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def jar(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as out:
        for name, value in entries:
            out.writestr(name, value if isinstance(value, bytes) else json.dumps(value))


def recipes(plural=False):
    # Deliberately synthetic quantities: inventory must preserve evidence, not
    # replace it with remembered vanilla ingredients or expected test answers.
    directory = 'recipes' if plural else 'recipe'
    return [(f'data/minecraft/{directory}/{name}.json', {
        'type': 'minecraft:crafting_shapeless',
        'ingredients': ['example:synthetic_input'],
        'result': {'id': 'minecraft:' + name, 'count': 7}})
        for name in ('crafting_table', 'furnace', 'hopper')]


class RecipePreflightTests(unittest.TestCase):
    def test_bundled_and_legacy_resources_keep_exact_provenance_without_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            inner = base / 'inner.jar'
            jar(inner, [('version.json', {'id': '26.2', 'ignored': 'not copied'}), *recipes()])
            raw = inner.read_bytes()
            inner.unlink()
            jar(base / 'versions/server.jar', [('META-INF/versions/26.2/server-26.2.jar', raw)])
            jar(base / 'mods/example.jar', recipes(plural=True))
            packs = base / 'world/datapacks'
            packs.mkdir(parents=True)
            (packs / 'private-pack.zip').write_bytes(b'not read')
            result = m.Inventory().run(base)
            self.assertTrue(result['candidate_inventory_complete'])
            self.assertEqual(result['recipe_documents'], 6)
            self.assertEqual(len(result['target_variants']), 3)
            self.assertEqual(result['versions'][0]['id'], '26.2')
            self.assertNotIn('ignored', result['versions'][0])
            self.assertEqual(result['datapack_entries'], 1)
            for item in result['target_variants']:
                self.assertEqual(item['document']['result']['count'], 7)
                self.assertEqual(len(item['sources']), 2)
                self.assertTrue(any('!META-INF/versions/' in source for source in item['sources']))
            self.assertFalse(result['active_pack_order_verified'])
            self.assertFalse(result['effective_recipes_qualified'])
            self.assertFalse(result['production_activated'])
            self.assertEqual(result['model_calls'], 0)
            self.assertNotIn('private-pack', json.dumps(result))

    def test_conflicting_assets_are_retained_not_silently_merged(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            jar(base / 'server.jar', recipes())
            changed = recipes()
            changed[0][1]['result']['count'] = 9
            jar(base / 'mods/override.jar', changed)
            result = m.Inventory().run(base)
            self.assertEqual(len(result['target_variants']), 4)
            counts = sorted(x['document']['result']['count'] for x in result['target_variants']
                            if x['id'] == 'minecraft:crafting_table')
            self.assertEqual(counts, [7, 9])
            self.assertFalse(result['effective_recipes_qualified'])

    def test_no_config_world_or_symlinked_archive_is_read(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            jar(base / 'server.jar', recipes())
            for location in ('config', 'world', 'logs'):
                (base / location).mkdir()
                (base / location / 'broken.jar').write_bytes(b'never open this')
            (base / 'mods').mkdir()
            (base / 'mods/linked.jar').symlink_to(base / 'config/broken.jar')
            result = m.Inventory().run(base)
            self.assertEqual(result['archives_examined'], 1)
            self.assertTrue(result['candidate_inventory_complete'])

    def test_duplicate_target_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                jar(base / 'server.jar', [recipes()[0], recipes()[0]])
            with self.assertRaisesRegex(m.Refused, 'AMBIGUOUS_RESOURCE_PATH'):
                m.Inventory().run(base)

    def test_oversized_compressed_json_is_rejected_before_inflation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            jar(base / 'server.jar', [('data/minecraft/recipe/hopper.json', b' ' * (m.MAX_JSON + 1))])
            with self.assertRaisesRegex(m.Refused, 'MEMBER_SIZE_OR_TYPE'):
                m.Inventory().run(base)

    def test_nested_depth_and_deadline_are_bounded(self):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, 'w') as out:
            out.writestr('META-INF/jars/deep.jar', b'not opened')
        with zipfile.ZipFile(io.BytesIO(raw.getvalue())) as archive:
            with self.assertRaisesRegex(m.Refused, 'NESTING_LIMIT'):
                m.Inventory().scan(archive, 'synthetic', depth=2)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            jar(base / 'server.jar', recipes())
            inventory = m.Inventory()
            inventory.deadline = 0
            with self.assertRaisesRegex(m.Refused, 'TIME_LIMIT'):
                inventory.run(base)

    def test_missing_resources_never_pass_candidate_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            result = m.Inventory().run(Path(directory))
            self.assertFalse(result['candidate_inventory_complete'])
            self.assertEqual(len(result['missing_targets']), 3)

    def test_archive_modified_during_scan_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            path = base / 'server.jar'
            jar(path, recipes())
            inventory = m.Inventory()
            original = inventory.scan

            def changing_scan(*args, **kwargs):
                result = original(*args, **kwargs)
                with path.open('ab') as handle:
                    handle.write(b'changed')
                return result

            inventory.scan = changing_scan
            with self.assertRaisesRegex(m.Refused, 'ARCHIVE_CHANGED'):
                inventory.run(base)


if __name__ == '__main__':
    unittest.main()
