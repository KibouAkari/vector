"""Resource scope and immutable private evidence checks, no Docker/model calls."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('context_update',ROOT/'scripts/deploy/update-qwen35-context.py')
update=importlib.util.module_from_spec(spec);spec.loader.exec_module(update)


class Boundaries(unittest.TestCase):
    def test_only_named_assistant_can_change(self):
        row={'Id':'id','Image':'image','State':{'StartedAt':'time'},'Config':{'User':'1000'},'HostConfig':{'NanoCpus':4000000000}}
        before={'assistant':copy.deepcopy(row),'inference':copy.deepcopy(row)}
        after=copy.deepcopy(before)
        after['assistant']['Id']='replacement'
        self.assertTrue(update.unchanged(before,after,'assistant'))
        after['inference']['HostConfig']['NanoCpus']=8000000000
        self.assertFalse(update.unchanged(before,after,'assistant'))
        self.assertFalse(update.unchanged(before,dict(after,new=row),'assistant'))

    def test_evidence_requires_private_owned_regular_file(self):
        guard=SimpleNamespace(checked_path=lambda value:Path(value))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'record.json';path.write_text(json.dumps({'deployed':True}));path.chmod(0o600)
            self.assertTrue(update.owned_json(guard,path)['deployed'])
            path.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError,'OWNED_EVIDENCE_REQUIRED'):update.owned_json(guard,path)


if __name__=='__main__':unittest.main()
