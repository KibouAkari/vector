import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('pilot', Path(__file__).parents[1] / 'scripts/deploy/local-inference-pilot.py')
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class PilotTests(unittest.TestCase):
    def test_download_integrity_and_symlink_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'weights'
            file.write_bytes(b'valid')
            expected = dict(size=5, sha256=pilot.hashlib.sha256(b'valid').hexdigest())
            self.assertTrue(pilot.verified(file, expected))
            file.write_bytes(b'wrong')
            self.assertFalse(pilot.verified(file, expected))
            link = Path(directory) / 'link'
            link.symlink_to(file)
            self.assertFalse(pilot.verified(link, expected))

    def test_inference_has_no_host_access_or_published_endpoint(self):
        args = pilot.docker_args()
        self.assertNotIn('--privileged', args)
        self.assertNotIn('--network=host', args)
        self.assertNotIn('-p', args)
        self.assertFalse(any('docker.sock' in item for item in args))
        self.assertEqual(args[args.index('--cpus') + 1], '2')
        self.assertEqual(args[args.index('--memory-swap') + 1], args[args.index('--memory') + 1])
        self.assertIn('OLLAMA_NUM_PARALLEL=1', args)
        self.assertIn('OLLAMA_NO_CLOUD=1', args)
        self.assertIn('@sha256:', args[-1])

    def test_benchmark_rejects_invented_zero_and_invalid_json(self):
        for text, expected in [('not json', False), ('{"players":3,"deaths":0}', False),
                               ('{"players":3,"deaths":null}', True)]:
            with patch.object(pilot, 'api', return_value=dict(message=dict(content=text), done=True,
                    eval_duration=1000000000, eval_count=10)) as api:
                result = pilot.evaluate('http://test', 'fixture', 'warm')
                self.assertEqual(result['fixture_passed'], expected)
                self.assertEqual(result['output_tokens_per_second'], 10)
                self.assertEqual(api.call_args.args[2]['options']['num_thread'], 2)

    def test_http_does_not_inherit_proxy_environment(self):
        self.assertFalse(any(isinstance(handler, pilot.urllib.request.ProxyHandler) and handler.proxies
                             for handler in pilot.HTTP.handlers))


if __name__ == '__main__':
    unittest.main()
