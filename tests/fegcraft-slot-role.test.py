import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('role_setup',ROOT/'scripts/deploy/prepare-fegcraft-slot-role.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def evidence():
    inner=dict(server_version_num=170011,driver_version='3.2.13',global_public_acl_changed=False,production_role_created=False)
    for key in ('passed','binary','disposable_database','application_read_denied','permanent_create_denied',
      'contention_both_directions_passed','normal_and_exception_release_passed','fixture_role_and_schema_removed',
      'inherited_public_temp','temporary_table_creation_possible'):inner[key]=True
    return dict(revision=m.DRIVER_REV,driver_image=m.IMAGE,wheel_manifest_sha256=m.WHEEL_SHA,
      passed=True,cleanup_verified=True,production_unchanged=True,production_activated=False,
      eligible_for_activation=False,production_role_created=False,model_calls=0,cloud_calls=0,messages_sent=0,isolated_admission=inner)


class RoleSetup(unittest.TestCase):
    def test_uses_exact_successful_owner_image_and_fixture_evidence(self):
        m.driver_evidence(evidence())
        for key,new in [('driver_image','wrong'),('passed',False),('production_activated',True),('model_calls',1)]:
            value=evidence();value[key]=new
            with self.assertRaises(RuntimeError):m.driver_evidence(value)
        for key,new in [('driver_version','wrong'),('global_public_acl_changed',True),('temporary_table_creation_possible',False)]:
            value=evidence();value['isolated_admission'][key]=new
            with self.assertRaises(RuntimeError):m.driver_evidence(value)

    def test_exclusive_private_write_refuses_overwrite_and_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);target=p/'secret'
            m.write_new(target,b'synthetic',0o400,os.getuid(),os.getgid())
            self.assertEqual(target.stat().st_mode&0o777,0o400)
            with self.assertRaises(FileExistsError):m.write_new(target,b'changed',uid=os.getuid(),gid=os.getgid())
            (p/'link').symlink_to(p,target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError,'SYMLINK'):m.write_new(p/'link'/'other',b'x')
            self.assertEqual(target.read_bytes(),b'synthetic')

    def test_intent_requires_exact_format_and_root_private_mode(self):
        value={'owner':'a'*32,'password':'b'*64}
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);path=p/'intent.json';path.write_text(json.dumps(value));path.chmod(0o600)
            h=SimpleNamespace(read=lambda path:path.read_bytes())
            real=Path.stat
            def root_stat(path,*args,**kwargs):
                row=real(path,*args,**kwargs)
                return SimpleNamespace(st_uid=0,st_mode=row.st_mode)
            with patch.object(m,'STATE',p),patch.object(Path,'stat',root_stat):
                self.assertEqual(m.read_intent(h),value)
                path.chmod(0o644)
                with self.assertRaisesRegex(RuntimeError,'PERMISSIONS'):m.read_intent(h)
                path.chmod(0o600);path.write_text(json.dumps(dict(value,extra='unexpected')))
                with self.assertRaisesRegex(RuntimeError,'INVALID'):m.read_intent(h)

    def test_rollback_refuses_any_container_binding_secret_or_parent(self):
        secret=Path('/private/slot/slot-dsn')
        for source in ('/private/slot/slot-dsn','/private/slot','/private','/'):
            def run(*args,**kw):
                if args[1]=='ps':return b'container'
                return json.dumps([{'Mounts':[{'Type':'bind','Source':source}]}]).encode()
            with self.subTest(source=source),patch.object(m,'run',run),self.assertRaisesRegex(RuntimeError,'IN_USE'):
                m.no_mounted_secret(secret)
        with patch.object(m,'run',side_effect=[b'container',b'[{"Mounts":[{"Type":"bind","Source":"/other"}]}]']):
            m.no_mounted_secret(secret)

    def test_cleanup_never_deletes_foreign_container(self):
        calls=[]
        def run(*args,**kw):
            calls.append(args)
            if args[1]=='ps':return b'id'
            if args[1]=='inspect':return b'[{"Config":{"Labels":{"com.vector.slot-role-probe":"foreign"}}}]'
            raise AssertionError('no delete allowed')
        with patch.object(m,'run',run),self.assertRaisesRegex(RuntimeError,'OWNER_CHANGED'):m.cleanup('probe','ours')
        self.assertFalse(any('rm' in args for args in calls))

    def test_actor_never_exposes_driver_error_or_private_output(self):
        intent={'owner':'a'*32,'password':'b'*64}
        for error,expected in [(b'private DSN or raw driver output','SLOT_ROLE_DATABASE_OPERATION_FAILED'),
          (b'SLOT_ROLE_DATABASE_OPERATION_FAILED ROLE_FOREIGN_OR_ABSENT','ROLE_FOREIGN_OR_ABSENT')]:
            with patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout=b'',stderr=error)),self.assertRaisesRegex(RuntimeError,expected) as failure:
                m.actor(b'// synthetic','prepare',intent)
            self.assertNotIn('private DSN',str(failure.exception))

    def test_probe_failure_releases_coordinator_and_cleans_every_owned_container(self):
        process=object();removed=[]
        with patch.object(m,'run',side_effect=[b'{"passed":true}',RuntimeError('synthetic failure')]),\
          patch.object(m.subprocess,'Popen',return_value=process),patch.object(m,'ready'),\
          patch.object(m,'release') as release,patch.object(m,'cleanup',side_effect=lambda name,owner:removed.append(name)):
            with self.assertRaisesRegex(RuntimeError,'synthetic failure'):m.probe(Path('/code'),Path('/secret'),1001,1001,'owned')
        release.assert_called_once_with(process);self.assertEqual(len(removed),3)

    def test_cleanup_attempts_all_owned_probes_even_after_one_failure(self):
        removed=[]
        def clean(name,owner):
            removed.append(name)
            if 'hold' in name:raise RuntimeError('synthetic cleanup failure')
        with patch.object(m,'run',side_effect=RuntimeError('synthetic probe failure')),patch.object(m,'cleanup',clean):
            with self.assertRaisesRegex(RuntimeError,'PROBE_CLEANUP_FAILED'):m.probe(Path('/code'),Path('/secret'),1001,1001,'owned')
        self.assertEqual(len(removed),3)


if __name__=='__main__':unittest.main()
