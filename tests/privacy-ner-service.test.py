import concurrent.futures
import http.client
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('privacy_ner_service',ROOT/'services/privacy-ner/server.py')
service=importlib.util.module_from_spec(spec);sys.modules[spec.name]=service;spec.loader.exec_module(service)

FAKE='''import time
class LocalPersonDetector:
    def inspect(self,text):
        if text=='fail':raise ValueError(text)
        if text=='slow':time.sleep(0.4)
        return {'findings':[], 'processed_text_tokens':len(text)}
'''

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        backend=Path(self.directory.name)/'backend.py';backend.write_text(FAKE)
        self.manager=service.ModelManager(backend,idle_seconds=0.4,deadline_seconds=3)
        self.server=service.Server(('127.0.0.1',0),self.manager,'a'*64)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.manager.close();self.thread.join(3)
        self.directory.cleanup()
    def request(self,path='/scan',payload=None,auth=True,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        values={'Content-Type':'application/json'}
        if auth:values['Authorization']='Bearer '+'a'*64
        values.update(headers or {})
        conn.request('GET' if path=='/health' else 'POST',path,body=None if path=='/health' else json.dumps(payload or {'text':'hello'}),headers=values)
        response=conn.getresponse();result=(response.status,json.loads(response.read()));conn.close();return result
    def test_auth_payload_limits_and_health_do_not_load_weights(self):
        self.assertEqual(self.request(auth=False)[0],401)
        self.assertEqual(self.request(payload={'text':'hello','extra':True})[0],400)
        self.assertEqual(self.request(payload={'text':42})[0],400)
        self.assertEqual(self.request(payload={'text':'é'*80001})[0],413)
        self.assertEqual(self.request(headers={'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.request('/missing')[0],404)
        self.assertEqual(self.request('/health')[1]['state'],'sleeping')
        self.assertIsNone(self.manager.process)
    def test_cold_warm_idle_exit_and_fresh_wake(self):
        first=self.request()[1];self.assertTrue(first['cold']);self.assertEqual(first['generation'],1)
        worker=self.manager.process.pid
        second=self.request()[1];self.assertFalse(second['cold']);self.assertEqual(self.manager.process.pid,worker)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline and self.manager.state()['state']!='sleeping':time.sleep(.03)
        self.assertEqual(self.manager.state()['state'],'sleeping');self.assertIsNone(self.manager.process)
        third=self.request()[1];self.assertTrue(third['cold']);self.assertEqual(third['generation'],2)
    def test_busy_has_no_hidden_queue_and_failure_kills_worker_without_echo(self):
        with concurrent.futures.ThreadPoolExecutor() as pool:
            pending=pool.submit(self.request,payload={'text':'slow'})
            deadline=time.monotonic()+2
            while self.manager.state()['state']!='busy' and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(self.request()[0],429)
            self.assertEqual(pending.result()[0],200)
        result=self.request(payload={'text':'fail'});self.assertEqual(result,(503,{'error':'DETECTOR_UNAVAILABLE'}))
        self.assertIsNone(self.manager.process)
        self.assertTrue(self.request()[1]['cold'])
    def test_timeout_terminates_model_process_and_allows_a_new_cold_request(self):
        self.request();self.manager.deadline_seconds=.05
        self.assertEqual(self.request(payload={'text':'slow'})[0],503)
        self.assertIsNone(self.manager.process)
        self.manager.deadline_seconds=3
        self.assertTrue(self.request()[1]['cold'])

if __name__=='__main__':unittest.main()
