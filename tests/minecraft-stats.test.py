import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('stats', Path(__file__).parents[1] / 'services/minecraft-assistant/stats.py')
stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stats)


class StatsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / 'stats'
        self.data.mkdir()
        self.cache = self.root / 'users.json'
        self.ids = ['00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002']
        self.cache.write_text(json.dumps([{'uuid': uid, 'name': name} for uid, name in zip(self.ids, ['ExampleOne', 'ExampleTwo'])]))
        for uid in self.ids:
            (self.data / (uid + '.json')).write_text(json.dumps({'stats': {'minecraft:custom': {
                'minecraft:play_time': 72000, 'minecraft:mob_kills': 10, 'minecraft:walk_one_cm': 100000}}}))

    def snapshot(self):
        return stats.snapshot(self.data, self.cache)

    def test_conversions_ties_and_records(self):
        data = self.snapshot()
        self.assertEqual(len(stats.leaders(data, 'mob_kills')), 2)
        found = stats.records(data, 'exampleone')['records']
        self.assertEqual({r['metric'] for r in found}, {'play_time', 'distance', 'mob_kills'})
        self.assertTrue(all(r['shared'] for r in found))
        self.assertEqual(data['players'][0]['values']['distance'], 1)
        self.assertEqual(data['players'][0]['values']['play_time'], 1)

    def test_broken_file_blocks_false_record(self):
        (self.data / (self.ids[0] + '.json')).write_text('{broken')
        data = self.snapshot()
        self.assertEqual(data['coverage']['skipped'], 1)
        with self.assertRaises(ValueError): stats.leaders(data, 'mob_kills')

    def test_symlink_and_invalid_counter_excluded(self):
        target = self.data / (self.ids[0] + '.json')
        target.unlink()
        target.symlink_to(self.cache)
        other = self.data / (self.ids[1] + '.json')
        other.write_text(json.dumps({'stats': {'minecraft:custom': {'minecraft:mob_kills': True}}}))
        self.assertEqual(self.snapshot()['coverage']['skipped'], 2)

    def test_unknown_name_and_overflow_block_definitive_ranking(self):
        self.cache.write_text('[]')
        with self.assertRaises(ValueError): stats.leaders(self.snapshot(), 'mob_kills')
        with self.assertRaises(ValueError): stats.snapshot(self.data, self.cache, max_players=1)

    def test_missing_category_not_zero(self):
        (self.data / (self.ids[0] + '.json')).write_text('{"stats":{}}')
        self.assertEqual(self.snapshot()['coverage']['skipped'], 1)


if __name__ == '__main__': unittest.main()
