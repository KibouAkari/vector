"""Offline installer boundaries. No Docker or live host changes."""
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('update',Path(__file__).parents[1]/'scripts/deploy/update-operations-web.py')
update=importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)

class Tests(unittest.TestCase):
    def test_only_app_image_build_and_binding_are_changed(self):
        original={'services':{'app':{'image':'old','build':{'context':'/example'},'environment':{'SECRET':'literal${VALUE}'},'volumes':['/private:/private:ro']},'worker':{'image':'worker'}},'networks':{'internal':{'internal':True}}}
        changed=update.candidate_profile(original,'app','sha256:fixture')
        self.assertEqual(changed['services']['worker'],original['services']['worker'])
        self.assertEqual(changed['networks'],original['networks'])
        self.assertNotIn('build',changed['services']['app'])
        self.assertEqual(changed['services']['app']['environment']['HOSTNAME'],'0.0.0.0')
        self.assertEqual(changed['services']['app']['volumes'],original['services']['app']['volumes'])
        self.assertEqual(json.loads(update.compose_bytes(changed).replace(b'$$',b'$')),changed)
        self.assertIn('build',original['services']['app'])
    def test_source_archive_rejects_symlinks_and_parent_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            for name,kind in [('../escape',tarfile.REGTYPE),('link',tarfile.SYMTYPE)]:
                buffer=io.BytesIO()
                with tarfile.open(fileobj=buffer,mode='w') as handle:
                    entry=tarfile.TarInfo(name);entry.type=kind;entry.linkname='/etc/passwd';handle.addfile(entry)
                with self.assertRaisesRegex(RuntimeError,'UNSAFE_ARCHIVE'):
                    update.extract_source(buffer.getvalue(),Path(temporary))
    def test_installer_targets_no_dependencies_and_sends_no_model_requests(self):
        source=(Path(__file__).parents[1]/'scripts/deploy/update-operations-web.py').read_text()
        self.assertIn("'--no-deps', '--no-build', '--pull', 'never', self.service",source)
        self.assertIn("'--network', 'none'",source)
        self.assertIn('self.verify_http(False)',source)
        self.assertIn('backup_created=False',source)
        self.assertNotIn('/api/chat',source)
        self.assertTrue(source.startswith('#!/usr/bin/env python3'))

if __name__=='__main__':unittest.main()
