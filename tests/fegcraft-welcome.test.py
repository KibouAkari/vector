import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('welcome',ROOT/'scripts/deploy/announce-fegcraft-assistant.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class WelcomeTests(unittest.TestCase):
    def test_fixed_message_and_single_console_submission_even_after_repeat(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(m,'run') as run:
            marker=Path(directory)/'introduction-v1.attempted'
            self.assertTrue(m.send_once(marker,os.getuid(),os.getgid()))
            self.assertFalse(m.send_once(marker,os.getuid(),os.getgid()))
            run.assert_called_once_with('docker','exec','-u',str(os.getuid())+':'+str(os.getgid()),'fegcraft-updated','mc-send-to-console','say '+m.TEXT)
            self.assertEqual(marker.stat().st_mode&0o777,0o600)
            self.assertNotIn('\n',m.TEXT)

    def test_failed_submission_keeps_marker_and_cannot_be_replayed(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(m,'run',side_effect=RuntimeError('uncertain')) as run:
            marker=Path(directory)/'introduction-v1.attempted'
            with self.assertRaises(RuntimeError):m.send_once(marker,os.getuid(),os.getgid())
            self.assertTrue(marker.exists())
            self.assertFalse(m.send_once(marker,os.getuid(),os.getgid()))
            self.assertEqual(run.call_count,1)

    def test_unrecognized_compose_path_cannot_authorize_welcome(self):
        with self.assertRaisesRegex(RuntimeError,'UNRECOGNIZED_INSTALLATION'):
            m.installation({'Config':{'Labels':{'com.docker.compose.project.config_files':'/tmp/untrusted.json'}}})

    def test_symlink_marker_is_refused_without_sending(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(m,'run') as run:
            path=Path(directory);(path/'target').touch();(path/'marker').symlink_to(path/'target')
            with self.assertRaisesRegex(RuntimeError,'SYMLINK_REFUSED'):m.send_once(path/'marker',os.getuid(),os.getgid())
            run.assert_not_called()


if __name__=='__main__':unittest.main()
