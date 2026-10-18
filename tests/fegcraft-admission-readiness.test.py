import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('readiness', ROOT/'scripts/diagnostics/fegcraft-admission-readiness.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def report():
    rows = []
    # Case IDs alone are not evidence: all per-call completion/usage must agree.
    for i, name in enumerate(sorted(m.CASES)):
        n = int(i < 17)
        rows.append({'id': name, 'passed': True, 'seconds': 2 if n else .001,
          'model_calls': n, 'native': [{'model': m.MODEL, 'done': True, 'done_reason': 'stop',
          'prompt_eval_count': 100, 'eval_count': 10}] if n else []})
    return dict(passed=True, quality_passed=True, latency_passed=True, production_unchanged=True,
      cleanup_verified=True, weights_unloaded=True, revision=m.TESTED, catalog_sha256=m.CATALOG,
      model=m.MODEL, evaluation_scope='offline-reviewed-passage-selection', answer_mode='reviewed-extractive',
      production_activated=False, eligible_for_activation=False, ledger_writes=False, diagnostic_only=False,
      full_knowledge_qualified=False, universal_mod_accuracy_claimed=False, exact_installed_mod_versions_qualified=False,
      cloud_calls=0, api_cost_chf=0, messages_sent=0, unknown_usage_calls=0, cases=rows, model_calls=17,
      input_tokens=1700, output_tokens=170, known_input_tokens=1700, known_output_tokens=170,
      warm_median_seconds=2)


class Readiness(unittest.TestCase):
    def test_complete_report_and_native_usage(self):
        self.assertEqual(m.evidence(report()), dict(cases=31, native_calls=17, cold_seconds=2,
          warm_median_seconds=2, input_tokens=1700, output_tokens=170))

    def test_failed_diagnostic_or_activated_report_rejected(self):
        for field, value in [('passed', False), ('quality_passed', False), ('cleanup_verified', False),
          ('production_unchanged', False), ('weights_unloaded', False), ('diagnostic_only', True),
          ('eligible_for_activation', True), ('production_activated', True), ('ledger_writes', True),
          ('revision', 'a'*40), ('catalog_sha256', 'a'*64), ('cloud_calls', 1), ('unknown_usage_calls', 1)]:
            row = report(); row[field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError): m.evidence(row)

    def test_duplicate_case_cannot_replace_a_missing_case(self):
        row=report(); row['cases'][-1]=copy.deepcopy(row['cases'][0])
        with self.assertRaisesRegex(RuntimeError, 'CASES'): m.evidence(row)

    def test_usage_must_match_each_native_response(self):
        for field, value in [('input_tokens', 1), ('known_input_tokens', None), ('output_tokens', None)]:
            row=report(); row[field]=value
            with self.assertRaisesRegex(RuntimeError, 'USAGE'): m.evidence(row)
        row=report(); row['cases'][0]['native'][0]['prompt_eval_count']=True
        with self.assertRaisesRegex(RuntimeError, 'USAGE'): m.evidence(row)

    def test_incomplete_and_wrong_native_models_rejected(self):
        for field,value in [('done', False), ('done_reason', 'length'), ('model', 'unqualified')]:
            row=report(); row['cases'][0]['native'][0][field]=value
            with self.assertRaisesRegex(RuntimeError, 'NATIVE'): m.evidence(row)

    def test_claimed_timing_pass_does_not_override_actual_deadlines(self):
        for index,seconds in [(0,25.1),(1,12.1)]:
            row=report(); row['cases'][index]['seconds']=seconds
            with self.assertRaisesRegex(RuntimeError,'LATENCY'): m.evidence(row)
        row=report(); row['warm_median_seconds']=.1
        with self.assertRaisesRegex(RuntimeError,'LATENCY'): m.evidence(row)

    def test_read_rejects_symlink_nonregular_and_size_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder); file=folder/'file'; file.write_bytes(b'abc')
            self.assertEqual(m.read(file), b'abc')
            with self.assertRaisesRegex(RuntimeError,'LIMIT'): m.read(file,2)
            link=folder/'link'; link.symlink_to(file)
            with self.assertRaisesRegex(RuntimeError,'SYMLINK'): m.read(link)
            with self.assertRaisesRegex(RuntimeError,'LIMIT'): m.read(folder)

    def test_command_errors_cannot_print_child_secrets(self):
        with self.assertRaisesRegex(RuntimeError,'READINESS_COMMAND_FAILED') as failure:
            m.run('python3','-c',"import sys;print('synthetic-private-marker');sys.exit(1)")
        self.assertNotIn('synthetic-private-marker',str(failure.exception))

    def test_baseline_keeps_the_actual_newer_code_mount_and_mode_zero(self):
        sources={'/inputs/stats':'/opt/fegcraft-updated/data/world/players/stats',
          '/inputs/usercache.json':'/opt/fegcraft-updated/data/usercache.json',
          '/inputs/mods.json':str(m.INSTALL/'mods.json'),'/inputs/recipes.json':str(m.INSTALL/'recipes.json'),
          '/run/secrets/vector_fegcraft_token':'/opt/fegcraft-updated/data/DiscordIntegration-Data/vector/token',
          '/state':str(m.INSTALL/'state'),'/code':str(m.ROOT/'releases/newer-owned-code')}
        volumes=[dict(target=k,source=v,read_only=k!='/state') for k,v in sources.items()]
        profile={'services':{'assistant':dict(volumes=volumes,user='1000:1000',entrypoint=['python3','/code/server.py'],
          environment={'VECTOR_FEGCRAFT_KNOWLEDGE':'0'})}}
        manifest=dict(owner='synthetic-owner',backend_revision='70f3adc9e6516c4fb4531cf5289a6cd99c29c7b1')
        def setup():
            raw=json.dumps(profile).encode(); manifest['compose_sha256']=m.sha(raw)
            value=dict(Image=m.PYTHON,Config=dict(Labels={'com.vector.installation':'synthetic-owner',
              'com.docker.compose.project':m.SERVICE,'com.docker.compose.service':'assistant'},
              Env=['VECTOR_FEGCRAFT_KNOWLEDGE=0'],User='1000:1000',Entrypoint=['python3','/code/server.py']),
              HostConfig={'ReadonlyRootfs':True},networks=['mc-net'],
              Mounts=[dict(Type='bind',Destination=v['target'],Source=v['source'],RW=not v['read_only']) for v in volumes])
            def read(path):
                if path.name=='manifest.json':return json.dumps(manifest).encode()
                if path.name=='compose.json':return raw
                return b'synthetic-reviewed-source'
            return value,read
        value,read=setup()
        with patch.object(m,'read',read),patch.object(m,'run',return_value=b'synthetic-reviewed-source'):
            self.assertTrue(m.baseline({'/'+m.SERVICE:value})['owned_mode_zero_baseline'])
            value['Config']['Env']=['VECTOR_FEGCRAFT_KNOWLEDGE=2']
            with self.assertRaisesRegex(RuntimeError,'BASELINE'):m.baseline({'/'+m.SERVICE:value})
        volumes[0]['read_only']=False
        value,read=setup()
        with patch.object(m,'read',read),self.assertRaisesRegex(RuntimeError,'SCOPE'):
            m.baseline({'/'+m.SERVICE:value})

    def test_driver_probe_is_offline_readonly_and_unprivileged(self):
        calls=[]
        def run(*args, **kwargs):
            calls.append(args)
            return b'{"available":false,"version":null,"binary":false}' if args[1]=='run' else b''
        with patch.object(m,'run',run):
            result=m.driver_probe('vector-admission-probe-synthetic','owner')
        self.assertFalse(result['available'])
        cmd=calls[0]
        self.assertEqual(cmd[cmd.index('--network')+1],'none')
        self.assertEqual(cmd[cmd.index('--user')+1],'65534:65534')
        self.assertIn('--read-only',cmd)
        self.assertNotIn('--mount',cmd)
        self.assertNotIn('pip',cmd)
        self.assertEqual(cmd[cmd.index('--pull')+1],'never')

    def test_failed_probe_removes_only_its_owned_container(self):
        calls=[]
        def run(*args, **kwargs):
            calls.append(args)
            if args[1]=='run':raise RuntimeError('synthetic-timeout')
            if args[1]=='ps':return b'probe-id' if len(calls)==2 else b''
            if args[1]=='inspect':return json.dumps([{'Config':{'Labels':{'com.vector.admission-audit':'owner'}}}]).encode()
            return b''
        with patch.object(m,'run',run),self.assertRaisesRegex(RuntimeError,'timeout'):
            m.driver_probe('vector-admission-probe-synthetic','owner')
        self.assertIn(('docker','rm','-f','probe-id'),calls)

    def test_probe_refuses_removing_a_differently_owned_container(self):
        calls=[]
        def run(*args, **kwargs):
            calls.append(args)
            if args[1]=='run':return b'{"available":false,"version":null,"binary":false}'
            if args[1]=='ps':return b'foreign'
            if args[1]=='inspect':return b'[{"Config":{"Labels":{"com.vector.admission-audit":"other"}}}]'
            raise AssertionError('must never remove this container')
        with patch.object(m,'run',run),self.assertRaisesRegex(RuntimeError,'OWNERSHIP'):
            m.driver_probe('vector-admission-probe-synthetic','owner')
        self.assertFalse(any('rm' in args for args in calls))


if __name__=='__main__': unittest.main()
