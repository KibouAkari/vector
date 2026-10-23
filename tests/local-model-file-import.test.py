"""Host download/import boundaries; no real download, Docker or inference."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
from contextlib import redirect_stdout
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
module=load('file_import','scripts/deploy/import-local-model-file.py')
guard=load('file_import_guard','scripts/deploy/update-minecraft-ranking-runtime.py')

class Response(io.BytesIO):
    def __init__(self,body):
        super().__init__(body);self.headers={'Content-Length':str(len(body))}

class FileImport(unittest.TestCase):
    def test_only_https_publisher_and_delivery_hosts_are_allowed(self):
        for url in ('https://huggingface.co/a','https://cdn-lfs.hf.co/a','https://cas-bridge.xethub.hf.co/a'):
            self.assertTrue(module.allowed_url(url))
        for url in ('http://huggingface.co/a','https://localhost/a','https://huggingface.co.evil/a',
                    'https://user:pass@huggingface.co/a','https://huggingface.co:444/a','https://[invalid'):
            self.assertFalse(module.allowed_url(url))
        with self.assertRaisesRegex(RuntimeError,'UNAPPROVED_MODEL_REDIRECT'):
            module.PublicRedirects().redirect_request(None,None,302,'',{},'http://localhost/model')

    def cache(self,body,download,*,existing=None):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'local-inference').mkdir()
            cache=root/'local-inference/model-candidates';cache.mkdir(mode=0o700)
            digest=hashlib.sha256(body).hexdigest();target=cache/(digest+'.gguf')
            if existing is not None:
                target.write_bytes(existing);target.chmod(0o600)
            with patch.object(module,'SIZE',len(body)),patch.object(module,'SHA256',digest), \
                    patch.object(module,'public_open',return_value=Response(download)) as opener,redirect_stdout(io.StringIO()):
                status={}
                if download!=body or existing is not None and existing!=body:
                    with self.assertRaises(RuntimeError):module.ensure_cached(root,guard,status)
                    self.assertEqual(target.read_bytes() if target.exists() else None,existing)
                else:
                    path=module.ensure_cached(root,guard,status)
                    self.assertEqual(path.read_bytes(),body)
                    self.assertTrue(status['host_weight_digest_verified'])
                    self.assertEqual(opener.call_count,0 if existing is not None else 1)
                self.assertEqual(list(cache.glob('.part-*')),[])

    def test_verified_download_and_existing_owned_cache_are_reused(self):
        self.cache(b'synthetic-model',b'synthetic-model')
        self.cache(b'synthetic-model',b'synthetic-model',existing=b'synthetic-model')

    def test_corrupt_or_oversized_download_and_existing_cache_fail_without_overwrite(self):
        self.cache(b'good',b'evil')
        self.cache(b'good',b'too-large')
        self.cache(b'good',b'good',existing=b'evil')

    def test_symlink_and_publicly_readable_cache_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'weight';path.write_bytes(b'x');path.chmod(0o644)
            with patch.object(module,'SIZE',1),self.assertRaisesRegex(RuntimeError,'MODEL_CACHE_FILE_INVALID'):
                module.verify_file(path)
            link=Path(temp)/'link';link.symlink_to(path)
            with self.assertRaises(OSError):module.verify_file(link)

    def test_blob_upload_precedes_create_and_never_calls_generation_or_pull(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);report=root/'report';report.mkdir()
            weight=root/'weight';weight.write_bytes(b'synthetic')
            operations=[];status={}
            def internal(container,payload,*args):
                operations.append(payload)
                return {'exists':len(operations)>1}
            with patch.object(module,'internal',side_effect=internal), \
                    patch.object(module,'ensure_cached',return_value=weight), \
                    patch.object(module.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'{}',stderr=b'')) as upload, \
                    patch.object(module,'public_open',return_value=Response(b'LFM Open License v1.0\nsynthetic')),redirect_stdout(io.StringIO()):
                module.prepare(root,'assistant',report,guard,status)
            self.assertEqual([p['operation'] for p in operations],['head','head','create'])
            body=operations[-1]['body']
            self.assertEqual(body['model'],module.MODEL)
            self.assertEqual(body['files'],{module.FILENAME:'sha256:'+module.SHA256})
            self.assertFalse(body['stream'])
            self.assertNotIn('template',body)
            self.assertNotIn('system',body)
            self.assertNotIn('pull',upload.call_args.args[0])
            self.assertNotIn('/api/generate',module.INTERNAL+module.UPLOAD)
            self.assertNotIn('/api/chat',module.INTERNAL+module.UPLOAD)
            self.assertTrue(status['host_download_internal_import'])
            self.assertEqual((report/'MODEL_LICENSE.txt').read_bytes(),b'LFM Open License v1.0\nsynthetic')

    def test_existing_verified_blob_skips_weight_download_and_upload(self):
        with tempfile.TemporaryDirectory() as temp:
            report=Path(temp);status={}
            with patch.object(module,'internal',return_value={'exists':True}) as internal, \
                    patch.object(module,'ensure_cached') as cache,patch.object(module.subprocess,'run') as upload, \
                    patch.object(module,'public_open',return_value=Response(b'LFM Open License v1.0\nsynthetic')):
                module.prepare(report,'assistant',report,guard,status)
            cache.assert_not_called();upload.assert_not_called()
            self.assertEqual(internal.call_count,2)
            self.assertTrue(status['existing_verified_blob_reused'])

    def test_upload_timeout_retains_diagnostics_and_never_creates_a_model(self):
        with tempfile.TemporaryDirectory() as temp:
            report=Path(temp);weight=report/'weight';weight.write_bytes(b'synthetic');status={}
            error=module.subprocess.TimeoutExpired('synthetic',190,output=b'partial',stderr=b'diagnostic')
            with patch.object(module,'internal',return_value={'exists':False}) as internal, \
                    patch.object(module,'ensure_cached',return_value=weight), \
                    patch.object(module.subprocess,'run',side_effect=error),redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError,'CANDIDATE_BLOB_UPLOAD_TIMEOUT'):
                    module.prepare(report,'assistant',report,guard,status)
            self.assertEqual(internal.call_count,1)
            self.assertTrue(status['import_completion_unknown'])
            self.assertEqual((report/'upload.stdout').read_bytes(),b'partial')
            self.assertEqual((report/'upload.stderr').read_bytes(),b'diagnostic')

    def test_internal_timeout_preserves_partial_private_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp:
            report=Path(temp)
            error=module.subprocess.TimeoutExpired('synthetic',70,output=b'partial',stderr=b'diagnostic')
            with patch.object(module.subprocess,'run',side_effect=error),self.assertRaises(module.subprocess.TimeoutExpired):
                module.internal('assistant',{'operation':'head'},report,guard,'probe')
            self.assertEqual((report/'probe.stdout').read_bytes(),b'partial')
            self.assertEqual((report/'probe.stderr').read_bytes(),b'diagnostic')

if __name__=='__main__':unittest.main()
