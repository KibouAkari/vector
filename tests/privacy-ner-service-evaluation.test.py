import importlib.util
import json
import os
import stat
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('service_evaluation',ROOT/'scripts/deploy/evaluate-privacy-ner-service.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class ServiceEvaluationTests(unittest.TestCase):
    def test_bind_root_is_traversable_under_the_actual_restrictive_umask(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            original=os.umask(0o077)
            try:
                broken=root/'original';broken.mkdir(mode=0o755)
                self.assertEqual(stat.S_IMODE(broken.stat().st_mode),0o700)
                work=module.prepare_work_directory(root/'corrected')
            finally:os.umask(original)
            self.assertEqual(stat.S_IMODE(work.stat().st_mode),0o755)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode),0o700)
            fixture=work/'integration.mjs';fixture.write_text('synthetic');fixture.chmod(0o644)
    def test_preflight_rejects_missing_files_without_printing_secrets(self):
        # Inject only fs, keeping the exact preflight's error/output behavior.
        stub="const fs={readFileSync:path=>{throw Object.assign(Error('do-not-echo'),{code:'EACCES',path});}};"
        code=module.PREFLIGHT.replace("const fs=require('node:fs');",stub)
        code="process.getuid=()=>65534;"+code
        result=subprocess.run(['node','--eval',code],capture_output=True,text=True)
        self.assertEqual(result.returncode,1)
        report=json.loads(result.stderr)
        self.assertEqual(report['code'],'EACCES')
        self.assertEqual(report['path'],'/work/integration.mjs')
        self.assertNotIn('do-not-echo',result.stderr)
    def test_private_unprivileged_read_only_runtime_and_exact_observed_image(self):
        args=module.service_args('owned-service',module.QUALIFIED_IMAGE,'internal-evaluation',Path('/tmp/work'),Path('/tmp/token'))
        for flag,value in [('--network','internal-evaluation'),('--network-alias','vector-privacy-ner'),
            ('--user','65534:65534'),('--cpus','2'),('--memory','4g'),('--memory-swap','4g'),
            ('--pids-limit','128'),('--cap-drop','ALL'),('--pull','never')]:
            self.assertEqual(args[args.index(flag)+1],value)
        self.assertIn('--read-only',args)
        self.assertNotIn('--privileged',args);self.assertNotIn('--publish',args)
        self.assertIn('HF_HUB_OFFLINE=1',args);self.assertIn('TRANSFORMERS_OFFLINE=1',args)
        self.assertEqual(module.QUALIFIED_REV,'f7b5bb4de3ad99f945050fc23740407839508501')
        self.assertTrue(any('dst=/run/secrets/vector_privacy_ner_token,readonly' in a for a in args))
        self.assertNotIn('/var/run/docker.sock',' '.join(args))
    def test_node_harnesses_parse_without_running_or_contacting_services(self):
        for source in [module.HARNESS,module.FAIL_CLOSED,module.PREFLIGHT]:
            result=subprocess.run(['node','--input-type=module','--check'],input=source,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
    def test_known_qualification_counts_and_lifecycle_gates_remain_mandatory(self):
        # Full native/model evidence is owner-run, not replaced with fake findings.
        self.assertIn('observations.length,32',module.HARNESS)
        self.assertIn('plan.sanitized.includes(value)',module.HARNESS)
        self.assertIn("confirm('replace')",module.HARNESS)
        self.assertIn("confirm('original')",module.HARNESS)
        self.assertIn("destination:'local'",module.HARNESS)
        self.assertIn("state==='sleeping'",module.HARNESS)
        self.assertIn('generation,2',module.HARNESS)
        self.assertIn('assert.rejects(requestPrivacyScan',module.FAIL_CLOSED)

if __name__=='__main__':unittest.main()
