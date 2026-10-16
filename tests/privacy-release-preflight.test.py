import ast
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('privacy_release_inventory',ROOT/'scripts/deploy/preflight-privacy-release.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class InventoryTests(unittest.TestCase):
    def test_only_requested_function_definitions_are_returned_not_resolved_globals(self):
        source="private_global='synthetic-private-global'\ndef main():\n    return private_global\ndef config(path):\n    return path\ndef unrelated():\n    return 1\n"
        filename='synthetic-archived-helper';namespace={}
        exec(compile(source,filename,'exec'),namespace)
        functions=module.helper_inventory(namespace,[(filename,ast.parse(source))])
        self.assertEqual(set(functions),{'main','config'})
        self.assertNotIn('synthetic-private-global','\n'.join(functions.values()))
        self.assertNotIn('unrelated',functions)
    def test_active_filename_and_function_name_select_the_matching_definition(self):
        source='def compose_up():\n    return 2\n';namespace={}
        exec(compile(source,'active-helper','exec'),namespace)
        result=module.helper_inventory(namespace,[('old-helper','def compose_up():\n    return 1\n'),('active-helper',source)])
        self.assertIn('return 2',result['compose_up'])
        self.assertNotIn('return 1',result['compose_up'])

if __name__=='__main__':unittest.main()
