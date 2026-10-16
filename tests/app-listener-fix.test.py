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
    def test_ambiguous_or_unsupported_forms_are_rejected(self):
        for raw in [b'services:\n  app:\n    environment: {}\n',
            b'services:\n  app:\n    environment:\n      - KEY=value\n',
            b'services:\n  app:\n    environment:\n      HOSTNAME: a\n      HOSTNAME: b\n',
            b'services:\n  app:\n    environment:\n  app:\n    environment:\n']:
            with self.subTest(raw=raw),self.assertRaises(RuntimeError):m.candidate(raw)

if __name__=='__main__':unittest.main()
