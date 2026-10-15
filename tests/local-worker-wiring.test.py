import importlib.util
import json
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('wiring',Path(__file__).parents[1]/'scripts/diagnostics/local-worker-wiring.py')
wiring=importlib.util.module_from_spec(spec)
spec.loader.exec_module(wiring)


class WiringTests(unittest.TestCase):
    def test_only_allowlisted_metadata_is_reported(self):
        secret='SECRET_FIXTURE_VALUE_NEVER_PRINT'
        config=dict(name='fixture',services=dict(app=dict(image='fixture-image',networks={'default':None},
            environment={'DATABASE_URL':secret,'API_KEY':secret,'VECTOR_LOCAL_WORKERS':secret})),
            networks={'default':{'name':'fixture_default'}})
        container=dict(Image='fixture-id',Config=dict(Image='fixture-image',Env=['DATABASE_URL='+secret,
            'VECTOR_LOCAL_WORKERS='+secret]),State={'Running':True},NetworkSettings={'Networks':{'fixture_default':{}}})
        source='services:\n  app:\n    environment:\n      API_KEY: '+secret+'\n    networks:\n      - default\n'
        report=wiring.public_profile(config,{'vector-app':container},source)
        self.assertNotIn(secret,json.dumps(report))
        self.assertEqual(report['app_local_workers'],'unexpected-value-redacted')
        self.assertEqual(report['app_layout'],{'environment':'mapping','networks':'list'})
        self.assertTrue(report['read_only'])

    def test_inline_and_unexpected_layouts_are_explicit(self):
        self.assertEqual(wiring.app_layout('services:\n  app:\n    environment: {}\n'),
            {'environment':'inline','networks':'absent'})
        self.assertEqual(wiring.app_layout('services: {app: {}}'),{'style':'requires-review'})


if __name__=='__main__':
    unittest.main()
