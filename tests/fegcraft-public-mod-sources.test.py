"""Read only bounded public mod source candidates; never follow URLs or nested JARs."""
import importlib.util,json,os,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('public_sources',ROOT/'scripts/diagnostics/fegcraft-public-mod-sources.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Sources(unittest.TestCase):
 def test_roots_only_for_known_public_publishers(self):
  self.assertEqual(m.public_url('https://github.com/Author/Mod.git/tree/main/docs'),'https://github.com/Author/Mod')
  self.assertEqual(m.public_url('https://gitlab.com/Author/Mod/issues'),'https://gitlab.com/Author/Mod')
  self.assertEqual(m.public_url('https://modrinth.com/mod/carry-on/versions'),'https://modrinth.com/mod/carry-on')
  self.assertEqual(m.public_url('https://curseforge.com/minecraft/mc-mods/example/files'),'https://www.curseforge.com/minecraft/mc-mods/example')
 def test_credentials_queries_fragments_ports_private_and_arbitrary_hosts_withheld(self):
  for value in ('http://github.com/a/b','https://github.com/a/b?token=synthetic','https://github.com/a/b#synthetic',
   'https://user:synthetic@github.com/a/b','https://github.com:443/a/b','https://github.com.evil.invalid/a/b',
   'https://127.0.0.1/a/b','https://localhost/a/b','https://private.example.invalid/a/b','file:///etc/passwd',
   'https://github.com/a/%2e%2e/secret','https://github.com/a/../secret','https://github.com/a/b\nsecret',
   'https://github.com/a/b\\secret','https://github.com/a/bé'):
   self.assertIsNone(m.public_url(value),value)
 def test_only_expected_id_version_license_and_review_candidates_leave_metadata(self):
  value=dict(id='carryon',version='26.2-2.11.0',license=['MIT','https://private.invalid/synthetic'],
   authors=['synthetic-private-author'],description='synthetic-private-description',
   contact=dict(sources='https://github.com/example/carryon/tree/main',homepage='https://private.invalid/synthetic',email='synthetic@example.invalid'))
  result=m.public_record(value,{'carryon'})
  self.assertEqual(result,dict(id='carryon',version='26.2-2.11.0',license_ids=['MIT'],source_candidates=['https://github.com/example/carryon']))
  encoded=json.dumps(result);self.assertNotIn('synthetic',encoded);self.assertNotIn('authors',encoded)
  self.assertIsNone(m.public_record(value,{'other'}))
 def test_fixed_root_metadata_only_and_duplicate_versions_preserved(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)
   for name,version in [('first','1.0'),('second','2.0')]:
    with zipfile.ZipFile(root/(name+'.jar'),'w') as z:
     z.writestr('fabric.mod.json',json.dumps(dict(id='examplemod',version=version,contact=dict(sources='https://github.com/example/mod'))))
     z.writestr('META-INF/jars/ignored.jar',b'not executable or parsed')
     z.writestr('private-config.json',b'synthetic-not-read')
   result=m.collect(root,{'examplemod'})
   self.assertTrue(result['inventory_complete']);self.assertEqual(result['jars_seen'],2)
   self.assertEqual(result['mods'][0]['versions'],['1.0','2.0']);self.assertTrue(result['mods'][0]['multiple_metadata_entries'])
   self.assertNotIn('synthetic-not-read',json.dumps(result))
 def test_oversized_missing_and_unknown_metadata_are_reported_without_raw_contents(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)
   with zipfile.ZipFile(root/'big.jar','w') as z:z.writestr('fabric.mod.json',b'a'*65537)
   with zipfile.ZipFile(root/'missing.jar','w') as z:z.writestr('private-config.json',b'synthetic-not-read')
   with zipfile.ZipFile(root/'unknown.jar','w') as z:z.writestr('fabric.mod.json',json.dumps(dict(id='unreviewed',version='1.0')))
   result=m.collect(root,{'expected'})
   self.assertFalse(result['inventory_complete']);self.assertEqual(result['skipped_jars'],2)
   self.assertEqual(result['unmatched_jars'],1);self.assertEqual(result['missing_mod_ids'],['expected'])
   self.assertNotIn('unreviewed',json.dumps(result));self.assertNotIn('synthetic',json.dumps(result))
 def test_symlink_is_never_read_and_source_absence_is_not_documentation_coverage(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);target=root/'actual'
   with zipfile.ZipFile(target,'w') as z:z.writestr('fabric.mod.json',json.dumps(dict(id='example',version='1')))
   (root/'link.jar').symlink_to(target)
   result=m.collect(root,{'example'});self.assertEqual(result['skipped_jars'],1);self.assertFalse(result['inventory_complete'])
   (root/'link.jar').unlink();target.rename(root/'actual.jar')
   result=m.collect(root,{'example'});self.assertTrue(result['inventory_complete']);self.assertEqual(result['mods_without_source_candidates'],['example'])
 def test_no_http_model_database_or_game_action(self):
  source=(ROOT/'scripts/diagnostics/fegcraft-public-mod-sources.py').read_text()
  for operation in ("'docker','restart'","'docker','stop'","'docker','run'",'/api/chat','/api/generate','urlopen','urllib.request','pg.Client'):
   self.assertNotIn(operation,source)
  self.assertIn("archive.getinfo('fabric.mod.json')",source)
 def test_non_regular_entry_is_rejected_without_blocking(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'fifo.jar';os.mkfifo(path)
   with self.assertRaisesRegex(ValueError,'JAR_BOUND'):m.metadata(path)

if __name__=='__main__':unittest.main()
