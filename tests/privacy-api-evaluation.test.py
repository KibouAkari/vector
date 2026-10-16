import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('privacy_api_evaluation',ROOT/'scripts/deploy/evaluate-privacy-api.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class PrivacyAPIEvaluationTests(unittest.TestCase):
    def test_client_refuses_nonisolated_configuration_before_loading_database_or_connecting(self):
        script=ROOT/'tests/privacy-api.integration.mjs'
        parsed=subprocess.run(['node','--check',str(script)],capture_output=True,text=True)
        self.assertEqual(parsed.returncode,0,parsed.stderr)
        result=subprocess.run(['node',str(script)],env={**os.environ,'VECTOR_PRIVACY_API_EVALUATION':'0'},capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Refusing privacy API tests outside the disposable evaluation.',result.stderr)
        self.assertNotIn('Cannot find module',result.stderr)
    def test_all_isolated_resources_keep_limits_and_no_published_ports_or_host_mounts(self):
        args=module.private_limits('owned-test','private-internal-network','65534:65534')
        for option,value in [('--network','private-internal-network'),('--user','65534:65534'),
            ('--memory','512m'),('--memory-swap','512m'),('--pull','never'),('--cap-drop','ALL')]:
            self.assertEqual(args[args.index(option)+1],value)
        self.assertIn('--read-only',args);self.assertNotIn('--publish',args)
        self.assertNotIn('--privileged',args);self.assertNotIn('/var/run/docker.sock',' '.join(args))
    def test_observed_service_report_must_pass_every_required_gate_at_the_expected_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'result.json'
            expected=dict.fromkeys(['passed','runtime_consent_roundtrip','tool_evidence_masked',
                'auth_and_input_limits','idle_unload_and_wake','service_outage_blocked',
                'production_unchanged','private_network'],True)
            expected.update(revision=module.STAGED_REV,case_count=32,cloud_calls=0)
            with patch.object(module,'SERVICE_REPORT',path):
                path.write_text(json.dumps(expected));self.assertEqual(module.report_checked(),expected)
                for change in [dict(passed=False),dict(service_outage_blocked=False),
                    dict(revision='0'*40),dict(case_count=31),dict(cloud_calls=1)]:
                    path.write_text(json.dumps(dict(expected,**change)))
                    with self.assertRaises(RuntimeError):module.report_checked()
    def test_built_image_reuse_rejects_runtime_changes_but_accepts_test_only_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            repo=Path(directory)
            def git(*args):return subprocess.check_output(['git','-C',directory,*args],text=True).strip()
            git('init','-q');(repo/'lib').mkdir();(repo/'tests').mkdir()
            (repo/'lib/runtime.js').write_text('original');(repo/'tests/check.py').write_text('original')
            def commit():
                git('add','.');git('-c','user.name=Synthetic Test','-c','user.email=test@example.invalid','commit','-qm','fixture')
                return git('rev-parse','HEAD')
            first=commit();(repo/'tests/check.py').write_text('new checks');second=commit()
            actual_run=module.run
            def run(*args,**kwargs):
                if args[:3]==('docker','image','inspect'):return json.dumps([{'Id':module.APP_IMAGE}]).encode()
                return actual_run(*args,**kwargs)
            with patch.object(module,'REPO',repo),patch.object(module,'STAGED_REV',first),patch.object(module,'run',side_effect=run):
                module.require_staged_app_unchanged(second)
                (repo/'lib/runtime.js').write_text('changed');third=commit()
                with self.assertRaises(RuntimeError):module.require_staged_app_unchanged(third)

if __name__=='__main__':unittest.main()
