import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('driver',ROOT/'scripts/deploy/qualify-fegcraft-admission-driver.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def manifest():
    return {'python':'3.12','architecture':'x86_64','files':[
      {'name':f'synthetic{i}.whl','url':f'https://files.pythonhosted.org/packages/example/synthetic{i}.whl',
       'size':3,'sha256':hashlib.sha256(b'abc').hexdigest()} for i in range(3)]}


class Driver(unittest.TestCase):
    def test_real_pins_and_existing_requirements_agree(self):
        value=json.loads((ROOT/m.MANIFEST).read_text());self.assertEqual(len(m.validate_manifest(value)),3)
        lock=(ROOT/m.REQUIREMENTS).read_text()
        for row in value['files']:self.assertIn('--hash=sha256:'+row['sha256'],lock)
        self.assertIn('psycopg[binary]==3.2.13',lock)

    def test_fixed_https_artifact_boundary(self):
        for key,value in [('url','http://files.pythonhosted.org/packages/example/synthetic0.whl'),
          ('url','https://private.invalid/packages/example/synthetic0.whl'),
          ('url','https://files.pythonhosted.org/packages/../synthetic0.whl'),
          ('url','https://files.pythonhosted.org/packages/example/synthetic0.whl?secret=x'),
          ('name','../bad.whl'),('sha256','x'*64),('size',True),('size',9*1024*1024)]:
            row=manifest();row['files'][0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(RuntimeError):m.validate_manifest(row)
        row=manifest();row['files'][1]=copy.deepcopy(row['files'][0])
        with self.assertRaises(RuntimeError):m.validate_manifest(row)

    def test_wrong_architecture_or_python_rejected(self):
        for key,value in [('python','3.13'),('architecture','aarch64')]:
            row=manifest();row[key]=value
            with self.assertRaises(RuntimeError):m.validate_manifest(row)

    def test_existing_verified_wheels_are_reused_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            for row in manifest()['files']:(folder/row['name']).write_bytes(b'abc')
            with patch.object(m.urllib.request,'build_opener') as opener:
                m.fetch_wheels(manifest(),folder)
                opener.return_value.open.assert_not_called()

    def test_changed_existing_wheel_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);target=folder/'synthetic0.whl';target.write_bytes(b'bad')
            with self.assertRaisesRegex(RuntimeError,'EXISTING'):m.fetch_wheels(manifest(),folder)
            self.assertEqual(target.read_bytes(),b'bad')

    def test_download_size_and_hash_checked_before_publish(self):
        for body in (b'ab',b'bad',b'abcd'):
            with tempfile.TemporaryDirectory() as folder,patch.object(m.urllib.request,'build_opener') as opener:
                opener.return_value.open.return_value.__enter__.return_value.read.return_value=body
                with self.assertRaisesRegex(RuntimeError,'DOWNLOADED'):m.fetch_wheels(manifest(),Path(folder))
                self.assertEqual(list(Path(folder).iterdir()),[])

    def test_symlink_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'link').symlink_to(p,target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError,'SYMLINK'):m.fetch_wheels(manifest(),p/'link')

    def test_readiness_must_be_successful_without_prior_activation(self):
        value=dict(revision=m.HELPER,audit_completed=True,production_unchanged=True,cleanup_verified=True,
          production_activated=False,eligible_for_activation=False,
          production_differences={'containers':[],'changed_file_count':0},
          baseline={'owned_mode_zero_baseline':True,'read_only_input_mounts_retained':True},
          installed_addon={'http_wall_deadline_seconds':27},database_catalog={'proposed_role_exists':False})
        m.check_readiness(value)
        for key,new in [('production_unchanged',False),('audit_completed',False),('production_activated',True)]:
            row=copy.deepcopy(value);row[key]=new
            with self.assertRaises(RuntimeError):m.check_readiness(row)

    def test_cleanup_refuses_foreign_container_or_network_endpoints(self):
        calls=[]
        def run(*args,**kwargs):
            calls.append(args)
            if args[1]=='ps':return b'foreign'
            if args[1]=='inspect':return b'[{"Config":{"Labels":{"com.vector.admission-driver":"other"}}}]'
            raise AssertionError('must not delete foreign objects')
        with patch.object(m,'run',run),self.assertRaisesRegex(RuntimeError,'OWNERSHIP'):
            m.cleanup(['synthetic'],'synthetic-network','owner')
        self.assertFalse(any('rm' in args for args in calls))
        calls.clear()
        def network_run(*args,**kwargs):
            calls.append(args)
            if args[1:3]==('network','ls'):return b'network-id'
            if args[1:3]==('network','inspect'):
                return b'[{"Labels":{"com.vector.admission-driver":"owner"},"Containers":{"foreign":{}}}]'
            raise AssertionError('must not remove network with foreign endpoints')
        with patch.object(m,'run',network_run),self.assertRaisesRegex(RuntimeError,'NETWORK'):
            m.cleanup([],'synthetic-network','owner')
        self.assertFalse(any('rm' in args for args in calls))


if __name__=='__main__':unittest.main()
