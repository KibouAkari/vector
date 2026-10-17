"""Synthetic repair and guarded rollback; no Docker or private server files."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('repair',REPO/'scripts/deploy/repair-fegcraft-backup.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class Repair(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.base=self.root/'game'; self.base.mkdir()
        self.directory=self.root/'releases/vector-fegcraft-backup-repair-synthetic'; self.directory.mkdir(parents=True)
        self.original=b"#!/bin/bash\necho 'synthetic truncated\n"; self.shell=self.base/'backup_minecraft.sh'
        self.shell.write_bytes(self.original); self.shell.chmod(0o700)
        self.sources={name:(REPO/source).read_bytes() for name,source in m.SOURCES.items()}
        for name,value in [('ROOT',self.root),('BASE',self.base)]:
            p=patch.object(m,name,value); p.start(); self.addCleanup(p.stop)
        # CI is unprivileged; permission validation is separately tested below.
        p=patch.object(m,'checked',side_effect=lambda path:path.read_bytes()); p.start(); self.addCleanup(p.stop)
        self.output=contextlib.redirect_stdout(io.StringIO()); self.output.__enter__(); self.addCleanup(self.output.__exit__,None,None,None)

    def test_install_idempotence_and_guarded_rollback(self):
        self.assertTrue(m.install(self.directory,self.sources))
        self.assertEqual(self.shell.read_bytes(),self.sources[self.shell.name])
        self.assertEqual((self.directory/'original.sh').read_bytes(),self.original)
        self.assertFalse(m.install(self.directory,self.sources))
        m.rollback(self.directory)
        self.assertEqual(self.shell.read_bytes(),self.original); self.assertFalse((self.base/'backup_minecraft.py').exists())

    def test_do_not_overwrite_valid_script_or_unknown_engine(self):
        self.shell.write_bytes(b'#!/bin/bash\ntrue\n')
        with self.assertRaisesRegex(RuntimeError,'CURRENT_SCRIPT_VALID'): m.install(self.directory,self.sources)
        self.assertFalse((self.base/'backup_minecraft.py').exists())
        self.shell.write_bytes(self.original); (self.base/'backup_minecraft.py').write_text('unrelated fixture')
        with self.assertRaisesRegex(RuntimeError,'ENGINE_ALREADY_EXISTS'): m.install(self.directory,self.sources)
        self.assertEqual(self.shell.read_bytes(),self.original)

    def test_invalid_source_is_rejected_before_writes(self):
        self.sources['backup_minecraft.py']=b'broken ( '
        with self.assertRaises(SyntaxError): m.install(self.directory,self.sources)
        self.assertEqual(self.shell.read_bytes(),self.original); self.assertFalse((self.base/'backup_minecraft.py').exists())

    def test_rollback_retains_later_edits(self):
        m.install(self.directory,self.sources); self.shell.write_text('later owner edit')
        with self.assertRaisesRegex(RuntimeError,'LATER_EDIT'): m.rollback(self.directory)
        self.assertEqual(self.shell.read_text(),'later owner edit'); self.assertTrue((self.base/'backup_minecraft.py').exists())

    def test_symlink_and_private_name_boundaries(self):
        symlink=self.base/'synthetic-link'; symlink.symlink_to(self.shell)
        with self.assertRaisesRegex(RuntimeError,'SYMLINK'): m.safe(symlink)
        result=m.classify([{'path':'/root/synthetic-private-filename','change':'A'},{'path':'/etc/hostname','change':'C'}])
        self.assertNotIn('synthetic-private-filename',str(result)); self.assertEqual(result[0]['category'],'owner-local-review-required')
        self.assertEqual(result[1]['category'],'docker-hostname')


if __name__=='__main__':unittest.main()
