"""Migrate d5b77dc recovery/transaction regression scenarios to native contracts.

Filesystem fault injections and Docker doubles test mechanics only. Real recovery
is recorded by validation/stage4/real_recovery.py.
"""
import copy
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from creation_pipeline.artifacts import store
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.records import write_json, read_json
from creation_pipeline.records import file_digest
from creation_pipeline.contracts import runtime_request
from creation_pipeline.runtime.local import binding_identity
from creation_pipeline.runtime.local import LocalExecutor
from creation_pipeline.runtime.service import execute_prepared, resume_build
from creation_pipeline.runtime.recovery import relocate, choose_build, import_candidate
from tests.pipeline import test_runtime_build as fixtures


class RecoveryTests(unittest.TestCase):
    setUp=fixtures.RuntimeBuildTests.setUp
    tearDown=fixtures.RuntimeBuildTests.tearDown
    prepared=fixtures.RuntimeBuildTests.prepared

    def seed(self):
        self.prepared();self.lib=self.root/'library'
        store.adopt(self.root/'output',[self.record],{'revision_parents':{},'batch':{'label':'unit','tags':[]}},self.lib)
        return store.get(self.lib,'probe',include_candidates=True)

    def test_success_then_source_drift_invalidates_all_current_results(self):
        # Migrated old test_runtime_hardening: changed source stops before model/Docker.
        entry=self.seed()
        source=self.lib/entry['evidence']/'sources/tool/main.py'
        source.write_text('print(999)')
        with patch.object(LocalExecutor,'build',side_effect=AssertionError('Must not build changed inputs')), \
             patch('creation_pipeline.runtime.planner.plan',side_effect=AssertionError('Must not replan changed inputs')):
            with self.assertRaises(ValueError):resume_build(self.lib,'probe',reuse_image=None)
        entry=store.get(self.lib,'probe',include_candidates=True)
        self.assertTrue(entry['invalidated'])
        self.assertFalse(entry['current_qualification']['accepted'])

    def test_relocation_drift_fails_before_mutation(self):
        entry=self.seed();before=(self.lib/'catalog.json').read_bytes()
        (self.lib/entry['path']/'main.py').write_text('changed')
        with self.assertRaises(ValueError):relocate(self.lib,'probe')
        self.assertEqual((self.lib/'catalog.json').read_bytes(),before)

    def test_path_relocation_keeps_inputs_and_requires_explicit_revalidation(self):
        entry=self.seed();new=self.root/'moved';shutil.copytree(self.lib,new)
        result=relocate(new,'probe')
        self.assertFalse(result['accepted'])
        updated=store.get(new,'probe',include_candidates=True)
        self.assertEqual(entry['delivery'],updated['delivery'])
        self.assertEqual(entry['freeze_sha256'],updated['freeze_sha256'])
        self.assertFalse(updated['relocation_history'][-1]['acceptance_retained'])
        self.assertEqual(store.entries(new),[])
        with self.assertRaises(ValueError):store.install_from_library(new,'probe',self.root/'installed')

    def test_interrupted_attempt_is_durable_and_retry_never_authors(self):
        self.seed()
        with patch.object(LocalExecutor,'build',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):resume_build(self.lib,'probe',reuse_image=None)
        pending=store.catalog(self.lib)['skills'][0]['pending_runtime']
        self.assertFalse((self.lib/'.catalog.lock').exists())
        shutil.rmtree(self.root/'output');shutil.rmtree(self.source);shutil.rmtree(self.package)
        with patch.object(LocalExecutor,'host',return_value={'status':'unavailable','gaps':[{'code':'docker_unavailable'}]}), \
             patch('creation_pipeline.pipeline._candidate',side_effect=AssertionError('No author')) as author, \
             patch('creation_pipeline.pipeline.analyze',side_effect=AssertionError('No discovery')) as discovery, \
             patch('creation_pipeline.runtime.planner.plan',side_effect=AssertionError('No planner')) as planner:
            result=resume_build(self.lib,'probe',reuse_image=None)
        self.assertEqual(result['status'],'runtime_blocked')
        self.assertEqual([author.call_count,discovery.call_count,planner.call_count],[0,0,0])
        entry=store.get(self.lib,'probe',include_candidates=True)
        self.assertEqual(entry['interrupted_attempts'][-1]['path'],pending['path'])
        self.assertNotIn('pending_runtime',entry)

    def test_live_lock_is_not_stolen_and_dead_lock_is_archived(self):
        self.seed();lock=self.lib/'.catalog.lock';lock.write_text(str(os.getpid()))
        with self.assertRaises(ValueError):store.release_dead_lock(self.lib)
        self.assertTrue(lock.exists());self.assertFalse((self.lib/'.lock-recovery.guard').exists())
        child=subprocess.Popen([sys.executable,'-c','pass']);child.wait()
        lock.write_text(str(child.pid));store.release_dead_lock(self.lib)
        self.assertFalse(lock.exists())
        self.assertEqual(len(list((self.lib/'lock-recoveries').glob('*.txt'))),1)

    def test_ownerless_lock_is_only_dead_after_the_acquisition_window(self):
        self.seed();lock=self.lib/'.catalog.lock'
        lock.write_text('',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'being acquired'):
            store.release_dead_lock(self.lib)
        self.assertTrue(lock.exists())
        self.assertFalse((self.lib/'.lock-recovery.guard').exists())
        stale=time.time()-60;os.utime(lock,(stale,stale))
        store.release_dead_lock(self.lib)
        self.assertFalse(lock.exists())
        self.assertEqual(len(list((self.lib/'lock-recoveries').glob('*.txt'))),1)
        lock.write_text('not-a-pid',encoding='utf-8');os.utime(lock,(stale,stale))
        store.release_dead_lock(self.lib)
        self.assertFalse(lock.exists())
        self.assertEqual(len(list((self.lib/'lock-recoveries').glob('*.txt'))),2)

    def test_unsupported_resources_do_not_become_supported_when_supplied(self):
        p=fixtures.plan();p['resources']=[{'kind':'weight','description':'weights','available':True,'required_for_execution':True,'evidence':fixtures.QUOTE}]
        request=self.prepared(p)
        with patch.object(LocalExecutor,'host',return_value=fixtures.HOST):
            result=LocalExecutor().preflight(request)
        by_code={g['code']:g for g in result['gaps']}
        self.assertEqual(by_code['resource_missing']['blocker_kind'],'temporary_resource')
        self.assertEqual(by_code['resource_mount_unresolved']['blocker_kind'],'unsupported_contract')
        self.assertEqual(result['status'],'runtime_blocked')

    def test_reuse_requires_bound_receipt_log_and_current_image(self):
        entry=self.seed();directory=self.lib/'runtime/pending';directory.mkdir(parents=True)
        entry['pending_runtime']={'path':'runtime/pending'}
        request=runtime_request(entry['delivery'],self.lib/entry['evidence'],entry['freeze_sha256'],directory)
        write_json(directory/'build-log.json',[])
        receipt={'status':'built','request':binding_identity(request),'image_id':'sha256:unit',
                 'log_sha256':file_digest(directory/'build-log.json')}
        good=copy.deepcopy(receipt);receipt['request']['source_fingerprint']='changed'
        write_json(directory/'receipt.json',receipt)
        with patch.object(LocalExecutor,'verify_current',side_effect=AssertionError('Bad binding must stop before Docker')):
            self.assertEqual(choose_build(self.lib,entry,LocalExecutor(),None)[1]['action'],'build')
        write_json(directory/'receipt.json',good)
        with patch.object(LocalExecutor,'verify_current',return_value={'status':'available'}):
            selected,decision=choose_build(self.lib,entry,LocalExecutor(),None)
        self.assertEqual(selected,directory);self.assertEqual(decision['action'],'validate')
        write_json(directory/'build-log.json',['tampered'])
        with patch.object(LocalExecutor,'verify_current',side_effect=AssertionError('Bad log must stop before Docker')):
            self.assertEqual(choose_build(self.lib,entry,LocalExecutor(),None)[1]['action'],'build')

    def test_new_host_cannot_inherit_historical_acceptance(self):
        from creation_pipeline.runtime.execution import evidence
        library=Path(__file__).resolve().parents[2]/'validation/stage3/rdkit-library'
        entry=next(e for e in store.catalog(library)['skills'] if e['name']=='rdkit-descriptor-delivery')
        attempt=library/entry['runtime']['path']
        request=runtime_request(entry['delivery'],library/entry['evidence'],entry['freeze_sha256'],attempt)
        current={'status':'available','preflight':{'host':{'engine_id':'different-host'}}}
        with patch.object(LocalExecutor,'verify_current',return_value=current):
            with self.assertRaisesRegex(ValueError,'host changed'):
                evidence(LocalExecutor(),request,read_json(attempt/'receipt.json'),attempt/'execution')

    def test_reading_only_relocation_rechecks_without_docker(self):
        from tests.pipeline.test_delivery_protocol import DeliveryProtocolTests
        case=DeliveryProtocolTests();case.setUp();self.addCleanup(case.tearDown)
        case.run_text();before=store.get(case.lib,'add-numbers')
        moved=self.root/'reading';shutil.copytree(case.lib,moved)
        with patch.object(LocalExecutor,'host',side_effect=AssertionError('Reading-only delivery needs no Docker')):
            result=relocate(moved,'add-numbers',revalidate=True)
            self.assertTrue(result['accepted'])
            self.assertEqual(store.get(moved,'add-numbers')['revision_id'],before['revision_id'])

    def test_first_creation_interruption_imports_without_reauthoring(self):
        self.prepared();output=self.root/'output'
        with patch.object(LocalExecutor,'build',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                execute_prepared(output,self.record,LocalExecutor(),persist_record=True)
        saved=read_json(output/'records/probe.json')
        self.assertTrue(saved['pending_runtime'])
        library=self.root/'imported'
        imported=import_candidate(output,library,'probe')
        self.assertEqual(imported['status'],'not_run')
        entry=store.get(library,'probe',include_candidates=True)
        self.assertEqual(entry['delivery'],self.record['delivery'])
        with self.assertRaises(ValueError):import_candidate(output,library,'probe')
        self.assertEqual(store.get(library,'probe',include_candidates=True),entry)
        write_json(output/'records/probe.json',dict(saved,content_status='failed'))
        attempt=output/saved['pending_runtime']['path']
        request=runtime_request(saved['delivery'],output/saved['durable_evidence']['path'],saved['durable_evidence']['freeze_sha256'],attempt)
        write_json(attempt/'execution/report.json',{'request':binding_identity(request),'repair_lane':'environment'})
        revoked=self.root/'revoked-import'
        import_candidate(output,revoked,'probe')
        with patch('creation_pipeline.runtime.diagnosis.model_call.call', side_effect=ValueError('Source diagnosis unresolved')):
            result = resume_build(revoked,'probe',reuse_image=None)
        self.assertEqual(result['status'], 'review_required')
        self.assertFalse(store.get(revoked, 'probe', include_candidates=True)['current_qualification']['accepted'])
        shutil.rmtree(output);shutil.rmtree(self.package);shutil.rmtree(self.source)
        with patch.object(LocalExecutor,'host',return_value={'status':'unavailable','gaps':[{'code':'docker_unavailable'}]}), \
             patch('creation_pipeline.pipeline._candidate',side_effect=AssertionError('No author')):
            result=resume_build(library,'probe',reuse_image=None)
        self.assertEqual(result['status'],'runtime_blocked')


class MigratedTransactionTests(unittest.TestCase):
    """Old test_runtime_consistency transaction scenarios, same rollback assertions.

    The old runtime_transaction staging/backup mechanism already exists in store;
    adapt targets/entry point, do not import a second transaction manager.
    """
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir()
        (self.source/'value').write_text('new')
        self.value={'version':2,'transaction':None,'skills':[]}
        write_json(self.root/'catalog.json',self.value)

    def old(self):
        for name in ('alpha','beta'):
            (self.root/name).mkdir();(self.root/name/'value').write_text('old')

    def test_copy_failure_does_not_destroy_existing_replacement(self):
        self.old();actual=shutil.copytree;calls=0
        def copy(source,target,*a,**kw):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('injected copy failure')
            return actual(source,target,*a,**kw)
        with patch.object(store.shutil,'copytree',side_effect=copy),self.assertRaises(OSError):
            store.commit(self.root,self.value,{'alpha':self.source,'beta':self.source})
        for n in ('alpha','beta'):self.assertEqual((self.root/n/'value').read_text(),'old')

    def test_commit_failure_restores_all_existing_targets(self):
        self.old();actual=Path.rename
        def rename(source,target):
            if source.name=='new-1':raise OSError('second install failed')
            return actual(source,target)
        with patch.object(Path,'rename',rename),self.assertRaises(OSError):
            store.commit(self.root,self.value,{'alpha':self.source,'beta':self.source})
        for n in ('alpha','beta'):self.assertEqual((self.root/n/'value').read_text(),'old')
        self.assertFalse((self.root/'.transaction.json').exists())

    def test_commit_failure_removes_new_targets(self):
        actual=store.write_json
        def write(path,value):
            if Path(path).name=='catalog.json':raise OSError('catalog failed')
            return actual(path,value)
        with patch.object(store,'write_json',side_effect=write),self.assertRaises(OSError):
            store.commit(self.root,self.value,{'alpha':self.source,'beta':self.source})
        for n in ('alpha','beta'):self.assertFalse((self.root/n).exists())

    def test_failed_rollback_preserves_original_backup_and_recovery_journal(self):
        self.old();actual=Path.rename
        def rename(source,target):
            if source.name=='new-1' or source.name.startswith('backup-'):raise OSError('install/rollback unavailable')
            return actual(source,target)
        with patch.object(Path,'rename',rename),self.assertRaises(OSError):
            store.commit(self.root,self.value,{'alpha':self.source,'beta':self.source})
        self.assertTrue((self.root/'.transaction.json').exists())
        self.assertTrue(list((self.root/'.transactions').rglob('backup-*')))
        store.recover(self.root)
        for n in ('alpha','beta'):self.assertEqual((self.root/n/'value').read_text(),'old')
        self.assertFalse((self.root/'.transaction.json').exists())
