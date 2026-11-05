"""Resource scope and immutable private evidence checks, no Docker/model calls."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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

    def test_native_gate_rejects_failure_or_missing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'datafirst.py').write_text('MODEL="test"')
            args=SimpleNamespace(candidate_helper=root/'candidate.py',evaluation_helper=root/'evaluation.py',
                process_helper=root/'process.py',server_name='ExampleCraft',check_player=['ExampleOne'])
            writes=[]
            guard=SimpleNamespace(canonical=lambda v:json.dumps(v).encode(),write_private=lambda *v:writes.append(v))
            for body,code in ((b'',0),(b'{"portrait_report":{"passed":false}}',1)):
                candidate=SimpleNamespace(candidate_run=lambda *a:SimpleNamespace(stdout=body,returncode=code))
                with patch.object(update,'load',side_effect=[candidate,object(),object()]):
                    with self.assertRaisesRegex(RuntimeError,'GENERATED_PORTRAITS_NOT_QUALIFIED'):
                        update.check_portraits(guard,args,'assistant',root,root)
            self.assertEqual(writes,[])

    def test_native_gate_persists_success_and_full_candidate_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'server.py').write_text('PRIVATE_BINDING=True')
            args=SimpleNamespace(candidate_helper=root/'candidate.py',evaluation_helper=root/'evaluation.py',
                process_helper=root/'process.py',server_name='ExampleCraft',check_player=['ExampleOne'])
            report={'passed':True,'model_calls':1,'cases':[{'reply_origin':'generated'}]}
            calls=[];writes=[]
            def run(*values):
                calls.append(values[4])
                return SimpleNamespace(stdout=json.dumps({'portrait_report':report}).encode(),returncode=0)
            guard=SimpleNamespace(canonical=lambda v:json.dumps(v).encode(),write_private=lambda *v:writes.append(v))
            with patch.object(update,'load',side_effect=[SimpleNamespace(candidate_run=run),object(),object()]):
                self.assertEqual(update.check_portraits(guard,args,'assistant',root,root),report)
            self.assertIn('server.py',calls[0]['files'])
            self.assertEqual(calls[0]['players'],['ExampleOne'])
            self.assertEqual(len(writes),1)


class StatisticsFormatting(unittest.TestCase):
    def validate(self,text,rows,limit):
        import textwrap
        start=update.STATISTICS_CHECK.index("        body=text.removesuffix")
        end=update.STATISTICS_CHECK.index("        case=dict",start)
        code=textwrap.dedent(update.STATISTICS_CHECK[start:end])
        env=dict(text=text,ranked=rows,expected=rows[:10],limit=limit,
            data={'players':[{'values':{'player_kills':row['value']}} for row in rows]},
            number=lambda value,unit:format(int(value),',').replace(',',"'")+' '+unit)
        exec(compile(code,'<statistics-validation>','exec'),env)
        return env['valid']

    def test_actual_friendly_leader_format_matches_exact_expected_counter(self):
        rows=[{'name':'ExampleTwo','value':211}]
        for text in (
            'ExampleTwo hat mit 211 Kills die meisten Spielerkills.',
            'bei Spielerkills liegt ExampleTwo vorne: 211 Kills.',
            'die Spitze bei Spielerkills gehört ExampleTwo – mit 211 Kills.',
            'Spielerkills: ExampleTwo 211 Kills.'):
            self.assertTrue(self.validate(text,rows,1))
        self.assertFalse(self.validate('ExampleOne hat mit 211 Kills die meisten Spielerkills.',rows,1))
        self.assertFalse(self.validate('ExampleTwo hat mit 212 Kills die meisten Spielerkills.',rows,1))

    def test_friendly_sentence_cannot_hide_a_shared_leader(self):
        rows=[{'name':'ExampleOne','value':211},{'name':'ExampleTwo','value':211}]
        self.assertFalse(self.validate('ExampleOne hat mit 211 Kills die meisten Spielerkills.',rows,1))
        self.assertTrue(self.validate('Spielerkills: ExampleOne 211 Kills; ExampleTwo 211 Kills.',rows,1))

    def test_every_top_row_value_and_rank_remains_required(self):
        rows=[{'name':'ExampleOne','value':211},{'name':'ExampleTwo','value':54}]
        self.assertTrue(self.validate('Spielerkills: 1. ExampleOne 211 Kills; 2. ExampleTwo 54 Kills.',rows,10))
        self.assertFalse(self.validate('Spielerkills: 1. ExampleOne 211 Kills; 2. ExampleTwo 999 Kills.',rows,10))
        self.assertFalse(self.validate('Spielerkills: 1. ExampleOne 211 Kills; 1. ExampleTwo 54 Kills.',rows,10))


if __name__=='__main__':unittest.main()
