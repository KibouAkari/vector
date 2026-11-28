import importlib.util
from pathlib import Path
import unittest
import threading
import urllib.request
import urllib.error

spec=importlib.util.spec_from_file_location('collector',Path(__file__).parents[1]/'scripts/collectors/traffic.py')
collector=importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)

class Tests(unittest.TestCase):
    def test_redirect_override_replaces_default(self):
        opener=collector.make_opener()
        handlers=[handler for handler in opener.handlers if isinstance(handler,urllib.request.HTTPRedirectHandler)]
        self.assertEqual(len(handlers),1)
        self.assertIsInstance(handlers[0],collector.NoRedirect)
        request=urllib.request.Request('https://example.org/api/traffic',headers={'X-Vector-Signature':'fixture'})
        self.assertIsNone(handlers[0].redirect_request(request,None,302,'Found',{},'https://other.example/'))
    def test_collector_flushes_before_live_input_reaches_eof(self):
        gate=threading.Event()
        finished=[]
        sent=[]
        def stream():
            yield {'fixture':'observation'}
            gate.wait(timeout=1)
            finished.append(True)
        def send(batch):
            self.assertFalse(finished)
            sent.extend(batch)
            gate.set()
        collector.flush_events(stream(),send,interval=0.01)
        self.assertEqual(sent,[{'fixture':'observation'}])

if __name__=='__main__':unittest.main()
