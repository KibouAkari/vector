"""Completed advancement rankings use whole saved datasets, never model prose."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/minecraft-assistant'))
import advancements


class Rankings(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.s=self.root/'stats';self.a=self.root/'advancements'
        self.s.mkdir();self.a.mkdir()
        self.players=[dict(name='Example'+str(i),uuid='00000000-0000-0000-0000-'+str(i).zfill(12)) for i in range(1,4)]
        cache=self.root/'users.json';cache.write_text(json.dumps(self.players))
        for p in self.players:
            (self.s/(p['uuid']+'.json')).write_text(json.dumps({'stats':{'minecraft:custom':{}}}))
        self.write(0,['minecraft:story/root','minecraft:adventure/sniper_duel'])
        self.write(1,['minecraft:story/root','minecraft:nether/root','minecraft:end/kill_dragon'])
        self.write(2,['minecraft:story/root'])
        self.obs=SimpleNamespace(principal=self.players[0]['uuid'],assistant=SimpleNamespace(
            stats_dir=self.s,usercache=cache,portraits=SimpleNamespace(advancements=self.a)))

    def write(self,index,done,unfinished=()):
        value={key:{'done':True} for key in done}
        value.update({key:{'done':False} for key in unfinished})
        value['DataVersion']=1
        (self.a/(self.players[index]['uuid']+'.json')).write_text(json.dumps(value))

    def ask(self,q):return advancements.answer(q,self.obs)

    def test_total_leader_category_leader_and_competition_rank(self):
        self.assertIn('1. Example2 3',self.ask('wer hat die meisten Fortschritte?'))
        self.assertIn('1. Example1 1',self.ask('wer hat die meisten Abenteuer-Fortschritte?'))
        self.assertIn('Rang 2',self.ask('welchen Rang habe ich bei Fortschritten?'))
        self.assertIn('1. Example2 1',self.ask('wer hat den Fortschritt Drachensieg?'))

    def test_ordinal_followup_preserves_category_but_reads_new_values(self):
        previous=self.ask('wer hat die meisten Nether-Fortschritte?')
        self.write(0,['minecraft:nether/root','minecraft:nether/explore_nether'])
        history=[{'origin':'tool-advancements','answer':previous}]
        text=advancements.answer('und wer ist zweiter?',self.obs,history)
        self.assertIn('Fortschritte (Nether)',text)
        self.assertIn('2. Example2 1',text)

    def test_recipes_and_unfinished_entries_are_not_completions(self):
        self.write(0,['minecraft:story/root','minecraft:recipes/tools/axe'],['minecraft:adventure/sniper_duel'])
        self.assertIn('1 abgeschlossen',self.ask('wie viele Fortschritte habe ich?'))
        self.assertIn('noch kein Abschluss',self.ask('wer hat den Fortschritt minecraft:adventure/sniper_duel?'))

    def test_mod_category_is_discovered_even_if_not_yet_completed(self):
        self.write(0,['example:exploration/first'],['example:industry/first'])
        self.assertIn('example:industry',self.ask('welche Fortschrittskategorien gibt es?'))
        self.assertIn('1. Example1 1',self.ask('wer hat die meisten Fortschritte bei example:exploration?'))
        self.assertIn('noch kein Abschluss',self.ask('wer hat Fortschritt example:industry/first?'))

    def test_missing_or_malformed_files_never_become_zero_players(self):
        (self.a/(self.players[1]['uuid']+'.json')).unlink()
        self.assertIn('fehlen lesbare',self.ask('wer hat die meisten Fortschritte?'))
        self.assertIn('2 abgeschlossen',self.ask('wie viele Fortschritte habe ich?'))
        self.assertIn('kein belegter Nullwert',self.ask('wie viele Fortschritte hat Example2?'))

    def test_invalid_done_type_and_symlink_are_rejected(self):
        p=self.a/(self.players[1]['uuid']+'.json');p.write_text('{"minecraft:story/root":{"done":1}}')
        self.assertIn('fehlen lesbare',self.ask('top 5 Fortschritte'))
        p.unlink();p.symlink_to(self.a/(self.players[0]['uuid']+'.json'))
        self.assertIn('fehlen lesbare',self.ask('top 5 Fortschritte'))

    def test_ties_rank_gaps_and_shared_records(self):
        self.write(0,['minecraft:story/root']*1)
        self.write(1,['minecraft:story/root'])
        text=self.ask('top 2 Fortschritte')
        self.assertIn('1. Example1 1',text);self.assertIn('1. Example2 1',text)
        self.assertIn('nicht belegt',self.ask('wer ist Rang 2 bei Fortschritten?'))
        self.assertIn('(geteilt)',self.ask('welche Fortschrittsrekorde hat Example1?'))

    def test_no_discord_self_guess_and_no_period_guess(self):
        self.obs.principal=None
        self.assertIn('Spielerverknüpfung',self.ask('wie viele Fortschritte habe ich?'))
        self.assertIn('nicht neu erreichte',self.ask('wer hat heute die meisten Fortschritte?'))
        self.assertIn('nur vom aktuellen',self.ask('wer hat die meisten Fortschritte auf server-2?'))
        self.assertIn('Einschränkung',self.ask('wer hat die meisten Fortschritte ohne End?'))

    def test_unknown_category_or_identifier_does_not_become_total(self):
        self.assertIn('Welche Fortschrittskategorie',self.ask('top 5 Fortschritte Kategorie PVP'))
        self.assertIn('nicht in den gespeicherten',self.ask('wer hat Fortschritt example:unknown/foo?'))
        self.assertIsNone(self.ask('wer hat die meisten playerkills?'))
        self.assertIsNone(self.ask('wie bekomme ich den Fortschritt Sniper-Duell?'))

    def test_operator_gate_runs_both_live_input_categories_without_generation(self):
        import contextlib,io,os
        from unittest.mock import patch
        spec=importlib.util.spec_from_file_location('advance_update',ROOT/'scripts/deploy/update-qwen35-context.py')
        update=importlib.util.module_from_spec(spec);spec.loader.exec_module(update)
        mods=self.root/'mods.json';mods.write_text('[]')
        program=update.STATISTICS_CHECK
        for name,path in [('stats',self.s),('usercache.json',self.obs.assistant.usercache),
                          ('mods.json',mods),('advancements',self.a)]:
            program=program.replace("'/inputs/"+name+"'",repr(str(path)))
        output=io.StringIO()
        payload={'candidate_code':str(ROOT/'services/minecraft-assistant'),'server_name':'ExampleCraft','check_advancements':True}
        with patch.dict(os.environ),patch('sys.stdin',io.StringIO(json.dumps(payload))),contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as stopped:exec(compile(program,'<advancement-gate>','exec'),{})
        self.assertEqual(stopped.exception.code,0)
        report=json.loads(output.getvalue().splitlines()[-1])['statistics_report']
        self.assertTrue(report['passed']);self.assertEqual(len(report['cases']),4)
        self.assertEqual(report['model_calls'],0)
        self.assertEqual(report['advancements_coverage']['missing_or_unreadable'],0)


if __name__=='__main__':unittest.main()
