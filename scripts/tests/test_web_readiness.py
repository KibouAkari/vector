import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('readiness',Path(__file__).parents[1]/'diagnostics/web-release-readiness.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class Readiness(unittest.TestCase):
 def test_disappearing_configuration_invalidates_unchanged_claim(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);compose=root/'compose.yml';compose.write_text('services: {}')
   state={'vector-app':{'running':True}}
   def inspect():
    if inspect.called:compose.unlink()
    inspect.called=True
    return state
   inspect.called=False;output=io.StringIO()
   with patch.object(module,'snapshot',side_effect=inspect),patch.object(module,'run',return_value='{}'),patch('sys.argv',['readiness','--source',str(root),'--compose',str(compose)]),contextlib.redirect_stdout(output):
    with self.assertRaisesRegex(RuntimeError,'LIVE_STATE_CHANGED'):module.main()
   self.assertFalse(json.loads(output.getvalue())['production_unchanged'])
 def test_absence_and_content_are_distinct_fingerprints(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'compose.yml';self.assertIsNone(module.configuration_fingerprint(path))
   path.write_text('');first=module.configuration_fingerprint(path)
   self.assertIsNotNone(first);path.write_text('changed')
   self.assertNotEqual(first,module.configuration_fingerprint(path))
if __name__=='__main__':unittest.main()
