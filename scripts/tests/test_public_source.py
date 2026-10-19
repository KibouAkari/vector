import importlib.util
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('publication',Path(__file__).parents[1]/'check_public_source.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Publication(unittest.TestCase):
 def test_private_material_fails_without_disclosing_contents(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'example.txt').write_text('/root/'+'vector-workspace/releases/private')
   self.assertEqual(module.audit(root),[('example.txt','private-operating-material')])
 def test_private_terms_are_external_and_build_output_is_excluded(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'readme.md').write_text('Synthetic community')
   (root/'node_modules').mkdir();(root/'node_modules/vendor.txt').write_text('Synthetic community')
   self.assertEqual(module.audit(root,['COMMUNITY']),[('readme.md','operator-deny-list')])
 def test_dangling_and_directory_symlinks_require_review(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'folder').mkdir()
   (root/'directory-link').symlink_to(root/'folder',target_is_directory=True)
   (root/'dangling-link').symlink_to('/private/nonexistent-example')
   self.assertEqual(module.audit(root),[('dangling-link','symlink-review'),('directory-link','symlink-review')])
if __name__=='__main__':unittest.main()
