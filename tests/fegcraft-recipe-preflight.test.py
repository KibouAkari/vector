import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stdout
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
                m.Inventory().scan(archive, 'synthetic', depth=m.MAX_DEPTH)
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

    def test_realistic_deep_bundled_dependencies_can_be_scanned(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            path = base / 'server.jar'
            jar(path, recipes())
            for index in range(4):
                raw = path.read_bytes()
                jar(path, [(f'META-INF/jars/dependency-{index}.jar', raw)])
            inventory = m.Inventory()
            result = inventory.run(base)
            self.assertTrue(result['candidate_inventory_complete'])
            self.assertEqual(result['recipe_documents'], 3)
            self.assertFalse(result['effective_recipes_qualified'])
            self.assertEqual(inventory.live_nested, 0)
            self.assertEqual(inventory.progress()['location']['depth'], 4)

    def test_live_nested_budget_refuses_before_decompression_and_records_location(self):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, 'w') as out:
            out.writestr('META-INF/jars/child.jar', b'not decompressed')
        inventory = m.Inventory()
        inventory.live_nested = m.MAX_LIVE_NESTED
        with zipfile.ZipFile(io.BytesIO(raw.getvalue())) as archive:
            with self.assertRaisesRegex(m.Refused, 'LIVE_NESTED_BYTE_LIMIT'):
                inventory.scan(archive, 'synthetic.jar', depth=3)
        self.assertEqual(inventory.bytes_read, 0)
        self.assertEqual(inventory.progress()['location'], {
            'archive': 'synthetic.jar', 'member': 'META-INF/jars/child.jar', 'depth': 3})

    def test_bad_nested_archive_restores_live_budget(self):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, 'w') as out:
            out.writestr('META-INF/jars/child.jar', b'not a ZIP')
        inventory = m.Inventory()
        with zipfile.ZipFile(io.BytesIO(raw.getvalue())) as archive:
            with self.assertRaises(zipfile.BadZipFile):
                inventory.scan(archive, 'synthetic.jar')
        self.assertEqual(inventory.live_nested, 0)

    def test_identical_cached_and_nested_archives_are_scanned_once_with_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            leaf = base / 'mods/leaf.jar'
            jar(leaf, recipes())
            jar(base / 'server.jar', [('META-INF/jars/leaf.jar', leaf.read_bytes())])
            cache = base / '.fabric/cached/server.jar'
            cache.parent.mkdir(parents=True)
            cache.write_bytes((base / 'server.jar').read_bytes())
            inventory = m.Inventory()
            result = inventory.run(base)
            self.assertTrue(result['candidate_inventory_complete'])
            self.assertEqual(result['archives_examined'], 3)
            self.assertEqual(result['recipe_documents'], 3)
            self.assertEqual(inventory.entries, 4)
            self.assertEqual(len(result['identical_archive_aliases']), 2)
            self.assertEqual(inventory.progress()['unique_archives_scanned'], 2)
            self.assertEqual(inventory.progress()['identical_archives_skipped'], 2)
            self.assertTrue(all(x['sha256'] and x['same_content_as'] for x in result['identical_archive_aliases']))

    def test_per_archive_metadata_limit_remains_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            jar(base / 'server.jar', recipes())
            inventory = m.Inventory()
            with mock.patch.object(m, 'MAX_ENTRIES_PER_ARCHIVE', 2):
                with self.assertRaisesRegex(m.Refused, 'ARCHIVE_ENTRY_COUNT_LIMIT'):
                    inventory.run(base)
            self.assertEqual(inventory.progress()['location']['archive'], 'server.jar')
            self.assertFalse(inventory.result()['candidate_inventory_complete'])

    def test_recipe_limit_remains_independent_of_archive_metadata_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            jar(base / 'server.jar', recipes())
            inventory = m.Inventory()
            with mock.patch.object(m, 'MAX_RECIPES', 2):
                with self.assertRaisesRegex(m.Refused, 'RECIPE_COUNT_LIMIT'):
                    inventory.run(base)
            self.assertFalse(inventory.result()['archive_traversal_complete'])
            self.assertEqual(len(inventory.result()['target_variants']), 2)

    def test_late_global_limit_saves_found_targets_without_claiming_complete_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / 'data'
            jar(base / 'server.jar', recipes())
            different = recipes()
            different[0][1]['result']['count'] = 9
            jar(base / 'mods/different.jar', different)
            (root / 'releases').mkdir()
            (root / '.chat-release.lock').touch()
            with mock.patch.object(m, 'ROOT', root), mock.patch.object(m, 'BASE', base), \
                    mock.patch.object(m, 'MAX_ENTRIES', 5), \
                    mock.patch.object(m, 'production_state', return_value='unchanged'), \
                    mock.patch.dict(m.os.environ, {'VECTOR_FEGCRAFT_REV': '0' * 40}), \
                    redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(m.Refused, 'CANDIDATE_INVENTORY_INCOMPLETE'):
                    m.main()
            output = next((root / 'releases').glob('*/result.json'))
            result = json.loads(output.read_text())
            self.assertEqual(result['error'], 'ENTRY_COUNT_LIMIT')
            self.assertTrue(result['production_unchanged'])
            self.assertFalse(result['passed'])
            self.assertFalse(result['archive_traversal_complete'])
            self.assertFalse(result['candidate_inventory_complete'])
            self.assertFalse(result['effective_recipes_qualified'])
            self.assertEqual(len(result['target_variants']), 3)
            self.assertEqual(result['missing_targets'], [])
            self.assertEqual(result['diagnostic_progress']['location']['archive'], 'mods/different.jar')
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)

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
