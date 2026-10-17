import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('recipe_evaluation', ROOT / 'scripts/deploy/evaluate-fegcraft-recipes.py')
m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sys.path.insert(0, str(ROOT / 'services/fegcraft-assistant'))
from recipes import normalise


class EvaluationTests(unittest.TestCase):
    def harness(self, wrong=False):
        # Synthetic shapeless fixtures intentionally differ from real shaped
        # game recipes; HTTP assertions must check supplied quantities only.
        records = []
        for item, ingredients in [
            ('crafting_table', ['#minecraft:planks'] * 4),
            ('furnace', ['#minecraft:stone_crafting_materials'] * 8),
            ('hopper', ['minecraft:iron_ingot'] * (4 if wrong else 5) + ['minecraft:chest'])
        ]:
            records.append(normalise('minecraft:' + item, {
                'type': 'minecraft:crafting_shapeless', 'ingredients': ingredients,
                'result': {'id': 'minecraft:' + item}}))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'recipes.json'
            path.write_text(json.dumps({'schema': 1, 'scope': 'vanilla-base', 'minecraft_version': '26.2',
                                       'source_sha256': '0' * 64, 'unsupported_count': 0, 'recipes': records}))
            source = m.HARNESS.replace("sys.path.insert(0,'/code')", 'sys.path.insert(0,' + repr(str(ROOT / 'services/fegcraft-assistant')) + ')')
            source = source.replace("'/inputs/recipes.json'", repr(str(path)))
            return subprocess.run([sys.executable, '-c', source], capture_output=True, text=True, timeout=15)

    def test_real_http_recipe_privacy_limits_and_fresh_statistics_without_models(self):
        result = self.harness()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data['passed'])
        self.assertFalse(data['effective_recipes_qualified'])
        self.assertFalse(data['production_activated'])
        self.assertEqual(data['model_calls'], 0)
        self.assertEqual(data['cloud_calls'], 0)
        self.assertEqual(len(data['answers']), 3)
        self.assertEqual(len(data['checks']), 5)

    def test_wrong_quantity_cannot_pass_the_recipe_gate(self):
        result = self.harness(wrong=True)
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
