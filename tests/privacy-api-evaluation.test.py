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

stage_spec=importlib.util.spec_from_file_location('privacy_api_pipeline',ROOT/'scripts/deploy/stage-and-evaluate-privacy-api.py')
pipeline=importlib.util.module_from_spec(stage_spec);stage_spec.loader.exec_module(pipeline)

class PrivacyAPIEvaluationTests(unittest.TestCase):
    def test_new_image_handoff_requires_one_successful_exact_revision_and_image(self):
        revision='a'*40;image='sha256:'+'b'*64
        output='=== PRIVACY STAGING PASSED ===\nCommit: '+revision+'\nImage tag: vector-app:staging-'+revision[:7]+'-fixture\nImage ID: '+image+'\n'
        self.assertEqual(pipeline.staging_handoff(output,revision),
            dict(VECTOR_PRIVACY_API_APP_REV=revision,VECTOR_PRIVACY_API_APP_IMAGE_ID=image))
        for invalid in [output.replace('=== PRIVACY STAGING PASSED ===','FAILED'),
            output.replace(revision,'c'*40),output+('Image ID: '+image+'\n'),
            output.replace('Image ID: '+image,'Image ID: latest'),output.replace('staging-'+revision[:7],'staging-ddddddd')]:
            with self.assertRaises(RuntimeError):pipeline.staging_handoff(invalid,revision)
    def test_bad_staged_identity_overrides_fail_before_git_or_docker(self):
        with patch.object(module,'STAGED_REV','latest'),patch.object(module,'run') as command:
            with self.assertRaises(RuntimeError):module.require_staged_app_unchanged('a'*40)
            command.assert_not_called()
        with patch.object(module,'APP_IMAGE','vector-app:latest'),patch.object(module,'run') as command:
            with self.assertRaises(RuntimeError):module.require_staged_app_unchanged('a'*40)
            command.assert_not_called()
    def test_client_refuses_nonisolated_configuration_before_loading_database_or_connecting(self):
        script=ROOT/'tests/privacy-api.integration.mjs'
        parsed=subprocess.run(['node','--check',str(script)],capture_output=True,text=True)
        self.assertEqual(parsed.returncode,0,parsed.stderr)
        result=subprocess.run(['node',str(script)],env={**os.environ,'VECTOR_PRIVACY_API_EVALUATION':'0'},capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Refusing privacy API tests outside the disposable evaluation.',result.stderr)
        self.assertNotIn('Cannot find module',result.stderr)
    def test_api_client_uses_application_identity_and_read_only_dependencies(self):
        args=module.api_client_args('client','private-network',Path('/tmp/synthetic'),Path('/tmp/test.env'))
        self.assertEqual(args[args.index('--user')+1],'1001:1001')
        self.assertEqual(args[args.index('--workdir')+1],'/app')
        self.assertIn('--read-only',args);self.assertIn('ALL',args)
        self.assertNotIn('--privileged',args);self.assertNotIn('--publish',args)
        self.assertTrue(any('dst=/work,readonly' in value for value in args))
        self.assertEqual(args[-2:], [module.APP_IMAGE,'/work/api-test.mjs'])
        expected=dict(uid=1001,gid=1001,package_readable=True,pg_client_available=True,script_readable=True)
        module.validate_client_preflight(expected)
        for change in [dict(uid=0),dict(uid=65534),dict(gid=65534),dict(pg_client_available=False),dict(package_readable=False)]:
            with self.assertRaises(RuntimeError):module.validate_client_preflight(dict(expected,**change))
    def test_package_access_failure_is_bounded_and_does_not_echo_error_or_config(self):
        code=module.CLIENT_PREFLIGHT.replace("const fs=require('node:fs');",
            "const fs={readFileSync:()=>{throw Object.assign(Error('private-config-do-not-print'),{code:'EACCES'});}};")
        code="process.getuid=()=>1001;process.getgid=()=>1001;"+code
        result=subprocess.run(['node','--eval',code],capture_output=True,text=True)
        self.assertEqual(result.returncode,1)
        self.assertEqual(json.loads(result.stderr),dict(error='API_CLIENT_PREFLIGHT_FAILED',stage='package',code='EACCES'))
        self.assertNotIn('private-config',result.stderr)
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
            expected.update(revision=module.SERVICE_QUALIFIED_REV,case_count=32,cloud_calls=0)
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
