import copy
import json
import tempfile
from unittest.mock import patch
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('listener',ROOT/'scripts/deploy/fix-app-listener.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ListenerTests(unittest.TestCase):
    def test_only_app_mapping_changes_and_other_services_remain_exact(self):
        raw=b'''name: vector
services:
  app:
    image: fixed
    environment:
      SECRET: ${SYNTHETIC_REFERENCE}
      VECTOR_PRIVACY_REVIEW: "1"
    networks:
    - private
  worker:
    environment:
      HOSTNAME: untouched
networks:
  private:
    internal: true
'''
        expected=raw.replace(b'    environment:\n',b'    environment:\n      HOSTNAME: "0.0.0.0"\n',1)
        self.assertEqual(m.candidate(raw),expected)
        self.assertEqual(m.candidate(expected),expected)
        self.assertEqual(m.candidate(expected.replace(b'HOSTNAME: "0.0.0.0"',b'HOSTNAME: old',1)),expected)
    def test_guarded_repair_checks_ingress_and_restores_original_on_proxy_failure(self):
        for status in ('200','502'):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);(root/'releases').mkdir();base=root/'baseline';base.mkdir()
                compose=root/'compose.yml'
                raw=b'services:\n  app:\n    image: qualified-tag\n    environment:\n      VECTOR_PRIVACY_REVIEW: "1"\n'
                compose.write_bytes(raw);(base/'compose.candidate.yml').write_bytes(raw)
                (base/'release.json').write_text(json.dumps(dict(status='deployed',image_id=m.IMAGE,new_source_hash='source')))
                original=dict(services=dict(app=dict(image='qualified-tag',environment=dict(VECTOR_PRIVACY_REVIEW='1'))))
                expected=copy.deepcopy(original);expected['services']['app']['environment']['HOSTNAME']='0.0.0.0'
                calls=[]
                def config(path):return expected if b'HOSTNAME:' in path.read_bytes() else original
                def command(*args,**kw):calls.append(args);return b''
                def text(*args,**kw):return '0' if args[0]=='docker' else status
                h=dict(run=command,obj=lambda name:dict(Image=m.IMAGE),atomic=lambda p,data,*args:p.write_bytes(data),
                    LIVE=root/'app',tree_hash=lambda p:'source',identity=lambda n:dict(id=n),text=text,
                    config=config,verify_others=lambda v:calls.append(('others',)),compose_up=lambda:calls.append(('up',)))
                with patch.object(m,'ROOT',root),patch.object(m,'BASE',base),patch.object(m,'COMPOSE',compose),patch.object(m,'helpers',return_value=h),patch.object(m.os,'geteuid',return_value=0):
                    if status=='200':m.main();self.assertEqual(compose.read_bytes(),m.candidate(raw))
                    else:
                        with self.assertRaisesRegex(RuntimeError,'Nginx route'):m.main()
                        self.assertEqual(compose.read_bytes(),raw)
                self.assertIn(('systemctl','reload','nginx'),calls)
                self.assertTrue(any(args[:2]==('docker','exec') and m.PROBE in args for args in calls))
                self.assertEqual(sum(args==('up',) for args in calls),1 if status=='200' else 2)

    def test_ambiguous_or_unsupported_forms_are_rejected(self):
        for raw in [b'services:\n  app:\n    environment: {}\n',
            b'services:\n  app:\n    environment:\n      - KEY=value\n',
            b'services:\n  app:\n    environment:\n      HOSTNAME: a\n      HOSTNAME: b\n',
            b'services:\n  app:\n    environment:\n  app:\n    environment:\n']:
            with self.subTest(raw=raw),self.assertRaises(RuntimeError):m.candidate(raw)

if __name__=='__main__':unittest.main()
