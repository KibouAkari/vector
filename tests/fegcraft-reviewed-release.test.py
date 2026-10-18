import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
m=module('reviewed_release','scripts/deploy/release-fegcraft-reviewed-help.py')
installer=module('initial_install','scripts/deploy/install-fegcraft-assistant.py')


def profile():
    p=installer.profile(m.INSTALL,65534,65534,Path('/synthetic/token'))
    p['services']['assistant']['labels']={'com.vector.installation':'synthetic'}
    return p


def role_report():
    return dict(revision=m.ROLE_REV,driver_image=m.IMAGE,passed=True,dedicated_db_role_qualified=True,
      role_owned=True,database_destination_verified=True,cleanup_verified=True,production_containers_and_profiles_unchanged=True,
      production_activated=False,eligible_for_activation=False,model_calls=0,cloud_calls=0,messages_sent=0,
      role_secret_path=str(m.SECRET),privileges=dict(checked_databases=3,global_public_acl_changed=False,
      no_application_object_privileges=True,no_permanent_create_privileges=True,no_security_definer_or_foreign_access=True,
      inherited_public_temp=True,system_catalog_access_retained=True),shared_slot=dict(role_login_verified=True,
      same_database_shared_slot_verified=True,both_contention_directions_verified=True,release_verified=True))


class Release(unittest.TestCase):
    def test_candidate_preserves_state_inputs_and_security_changes_only_opt_in_scope(self):
        p=profile();before=copy.deepcopy(p);v=m.candidate(p,Path('/synthetic/code'),Path('/synthetic/catalog'))
        self.assertEqual(p,before)
        old=p['services']['assistant'];new=v['services']['assistant']
        self.assertEqual(new['image'],m.IMAGE);self.assertEqual(new['environment']['VECTOR_FEGCRAFT_KNOWLEDGE'],'3')
        self.assertEqual(new['user'],old['user']);self.assertEqual(new['healthcheck'],old['healthcheck'])
        self.assertEqual(new['networks'],['mc-net','vector-internal','vector-local-inference'])
        for k in ('cap_drop','security_opt','read_only','mem_limit','pids_limit','cpus','entrypoint'):self.assertEqual(new[k],old[k])
        for row in old['volumes']:
            if row['target']!='/code':self.assertIn(row,new['volumes'])
        extras=[r for r in new['volumes'] if r['target'] in (m.SLOT_TARGET,'/inputs/documentation.json')]
        self.assertEqual(len(extras),2);self.assertTrue(all(r['read_only'] and not r['bind']['create_host_path'] for r in extras))

    def test_changed_or_duplicate_baseline_mounts_are_refused(self):
        for change in ('duplicate','existing-secret','mode'):
            p=profile();s=p['services']['assistant']
            if change=='duplicate':s['volumes'].append(copy.deepcopy(s['volumes'][0]))
            elif change=='existing-secret':s['volumes'].append(dict(source='/x',target=m.SLOT_TARGET,read_only=True))
            else:s['environment']['VECTOR_FEGCRAFT_KNOWLEDGE']='2'
            with self.assertRaisesRegex(RuntimeError,'BASELINE_CHANGED'):m.candidate(p,Path('/code'),Path('/catalog'))

    def test_role_evidence_requires_actual_both_way_qualification(self):
        m.role_evidence(role_report())
        for field in ('passed','database_destination_verified','dedicated_db_role_qualified'):
            r=role_report();r[field]=False
            with self.assertRaises(RuntimeError):m.role_evidence(r)
        r=role_report();r['shared_slot']['same_database_shared_slot_verified']=False
        with self.assertRaises(RuntimeError):m.role_evidence(r)
        r=role_report();r['privileges']['no_application_object_privileges']=False
        with self.assertRaises(RuntimeError):m.role_evidence(r)

    def test_protected_hashes_hide_configuration_and_omit_only_intended_changes(self):
        before={'/vector-app':{'Config':{'secret':'synthetic'}},'/'+m.SERVICE:{'Id':'old'},str(m.INSTALL/'compose.json'):'old','/game':'unchanged'}
        after=copy.deepcopy(before);after['/'+m.SERVICE]={'Id':'new'};after[str(m.INSTALL/'compose.json')]='new'
        self.assertEqual(m.protected(before),m.protected(after))
        self.assertNotIn('synthetic',json.dumps(m.protected(before)))
        after['/vector-app']['Config']['secret']='changed'
        self.assertNotEqual(m.protected(before),m.protected(after))

    def test_protected_live_does_not_require_the_failed_assistant(self):
        record=dict(Name='/fegcraft-updated',Id='same',Image='same',Config={},HostConfig={},Mounts=[],
          State=dict(Running=True,StartedAt='same',Health={'Status':'healthy'}),NetworkSettings={'Networks':{'mc-net':{}}})
        h=SimpleNamespace(NAMES=('fegcraft-updated',m.SERVICE),ADDON=Path('/addon'),canonical_mounts=lambda x:x)
        with patch.object(m,'run',return_value=json.dumps([record]).encode()) as run,patch.object(m,'read',return_value=b'synthetic'):
            actual=m.protected_live(h)
        self.assertNotIn(m.SERVICE,str(run.call_args));self.assertIn('/fegcraft-updated',actual)

    def test_stage_cleanup_preserves_foreign_container(self):
        calls=[]
        def run(*args,**kwargs):
            calls.append(args)
            if args[1]=='ps':return b'id'
            return json.dumps([{'Config':{'Labels':{m.LABEL:'foreign'}}}]).encode()
        with patch.object(m,'run',run),self.assertRaisesRegex(RuntimeError,'FOREIGN'):m.cleanup_stage('synthetic','ours')
        self.assertFalse(any('rm' in args for args in calls))

    def rollback_fixture(self,root):
        install=root/'install';install.mkdir();release=root/'releases'/'vector-fegcraft-reviewed-help-synthetic';release.mkdir(parents=True)
        old=json.dumps(profile()).encode();newp=m.candidate(profile(),Path('/newcode'),Path('/catalog'));new=json.dumps(newp).encode()
        manifest=json.dumps({'owner':'synthetic'}).encode();next_manifest=json.dumps({'owner':'synthetic','new':True}).encode()
        for path,raw in ((release/'compose.before.json',old),(release/'compose.candidate.json',new),
          (release/'manifest.before.json',manifest),(install/'compose.json',new),(install/'manifest.json',next_manifest)):
            path.write_bytes(raw)
        record=dict(old_profile_sha=m.sha(old),new_profile_sha=m.sha(new),old_manifest_sha=m.sha(manifest),new_manifest_sha=m.sha(next_manifest),protected={'hash':'same'})
        (release/'deployment.json').write_text(json.dumps(record));return install,release,old

    def test_rollback_recovers_partial_compose_transition_and_retains_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);install,release,old=self.rollback_fixture(root)
            state=install/'events.sqlite';state.write_bytes(b'keep all events and usage')
            with patch.object(m,'ROOT',root),patch.object(m,'INSTALL',install),patch.object(m,'protected_live',return_value={'hash':'same'}),\
              patch.object(m,'run',return_value=b'existing-id'),patch.object(m,'check_runtime') as checked,\
              patch.object(m,'compose') as compose,patch.object(m,'healthy'):
                m.rollback(release,SimpleNamespace())
            self.assertEqual((install/'compose.json').read_bytes(),old);compose.assert_called_once()
            self.assertEqual(state.read_bytes(),b'keep all events and usage')
            self.assertEqual(checked.call_args[0][1]['environment']['VECTOR_FEGCRAFT_KNOWLEDGE'],'0')

    def test_rollback_never_overwrites_later_profile_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);install,release,_=self.rollback_fixture(root);(install/'compose.json').write_bytes(b'later-edit')
            with patch.object(m,'ROOT',root),patch.object(m,'INSTALL',install),patch.object(m,'compose') as compose:
                with self.assertRaisesRegex(RuntimeError,'LATER_EDIT'):m.rollback(release,SimpleNamespace())
            compose.assert_not_called();self.assertEqual((install/'compose.json').read_bytes(),b'later-edit')


if __name__=='__main__':unittest.main()
