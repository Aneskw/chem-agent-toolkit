"""Production batch boundaries; replay decisions, never live inference or Docker."""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline import pipeline
from creation_pipeline.agent.backend import NativeSession
from creation_pipeline.models import load_config, BudgetError
from creation_pipeline.records import read_json,write_json
from tests.pipeline import test_discovery as fixture
from tests.pipeline.support import ReplayStages,ARTIFACT


class BatchReadinessTests(unittest.TestCase):
    def setUp(self):
        self.c=fixture.DiscoveryTests();self.c.setUp();self.addCleanup(self.c.tearDown)
        self.c.options['checks']=[]
        self.c.options['model']={'backend':'codex_cli','name':'offline-fixture'}
        self.c.options['limits'].update(model_calls=16,max_candidates=2,max_builds=2)
        self.client=patch('creation_pipeline.agent.command.codex_command',return_value=['fixture-client'])
        self.client.start();self.addCleanup(self.client.stop)
        self.live=patch('creation_pipeline.runtime.model_call.call',side_effect=AssertionError('No live model'))
        self.live.start();self.addCleanup(self.live.stop)

    def run_build(self,values,**kwargs):
        write_json(self.c.config,self.c.options);replay=ReplayStages(values)
        self.sessions=[]
        def factory(*args,**options):
            session=replay(*args,**options);self.sessions.append(session)
            replay_stage=session.stage
            def stage(*values,**settings):
                answer=replay_stage(*values,**settings)
                # NativeSession.stage persists its own turns; keep this double faithful.
                write_json(session.state_path,session.state)
                return answer
            session.stage=stage
            return session
        result=pipeline.build(self.c.config,self.c.state,_session_factory=factory,keep_debug=True,**kwargs)
        return result,read_json(Path(result['output'])/'summary.json'),replay

    def failure(self,output,record,executor,**kwargs):
        record['status']='failed'
        return {'status':'build_failed','execution_status':'build_failed','gaps':[{'code':'fixture_build_failure'}]}

    def test_runtime_failure_gate_stops_the_batch_and_defers_remaining_skills(self):
        self.c.options['execution']={'stop_on_runtime_failure':True}
        other=copy.deepcopy(ARTIFACT);other['files'][0]['content']=other['files'][0]['content'].replace('name: add-numbers','name: second')
        values=[fixture.discovery(fixture.candidate(),fixture.candidate('second')),ARTIFACT,other]
        with patch('creation_pipeline.runtime.service.execute_prepared',side_effect=self.failure) as execute:
            result,summary,replay=self.run_build(values)
        self.assertFalse(result['errors'],result)
        self.assertEqual([e['name'] for e in result['entities']],['add-numbers'])
        self.assertIn('second',result['deferred']);self.assertEqual(execute.call_count,1)
        self.assertEqual(result['model_calls'],3)  # discovery, author, independent review
        self.assertIn('runtime_failure_gate',summary)
        self.assertFalse((Path(result['output'])/'records/second.json').exists())

    def test_disabled_failure_gate_keeps_independent_next_skill(self):
        self.c.options['execution']={'stop_on_runtime_failure':False}
        other=copy.deepcopy(ARTIFACT);other['files'][0]['content']=other['files'][0]['content'].replace('name: add-numbers','name: second')
        with patch('creation_pipeline.runtime.service.execute_prepared',side_effect=self.failure):
            result,_,_=self.run_build([fixture.discovery(fixture.candidate(),fixture.candidate('second')),ARTIFACT,other])
        self.assertFalse(result['errors'],result);self.assertEqual(len(result['entities']),2)
        self.assertEqual(result['model_calls'],5)

    def test_runtime_admission_is_durable_before_invocation_and_survives_cancel(self):
        observed=[]
        def cancel(record,package,sources,workspace,spec,executor,call_guard=None,**kwargs):
            ticket=call_guard();ticket.update(phase='runtime_planning',backend='codex_cli')
            session=self.sessions[0]
            observed.append(len(read_json(session.state_path)['receipts']))
            raise KeyboardInterrupt()
        with patch('creation_pipeline.runtime.preparation.prepare',side_effect=cancel):
            result,summary,_=self.run_build([fixture.discovery(fixture.candidate()),ARTIFACT])
        self.assertEqual(result['status'],'interrupted');self.assertEqual(result['model_calls'],4)
        self.assertEqual(observed,[4])
        saved=read_json(self.sessions[0].state_path)['receipts']
        self.assertEqual(len(saved),4);self.assertEqual(saved[-1]['phase'],'runtime_planning')

    def test_restored_session_cannot_forget_runtime_model_budget(self):
        from creation_pipeline.runtime.preparation import prepare as real_prepare
        def admit(record,package,sources,workspace,spec,executor,call_guard=None,**kwargs):
            ticket=call_guard();ticket.update(phase='acceptance_only_planner',status='completed',backend='codex_cli')
            return real_prepare(record,package,sources,workspace,spec,executor,**kwargs)
        self.c.options['limits']['model_calls']=4
        with patch('creation_pipeline.runtime.preparation.prepare',side_effect=admit):
            result,summary,_=self.run_build([fixture.discovery(fixture.candidate()),ARTIFACT])
        self.assertEqual(result['model_calls'],4);self.assertFalse(result['errors'],result)
        session=self.sessions[0]
        restored=NativeSession(session.config,session.sources,session.limits.copy(),session.work)
        self.assertEqual(len(restored.receipts),4)
        with patch('creation_pipeline.agent.backend.codex_command',side_effect=AssertionError('No client after exhausted budget')):
            with self.assertRaises(BudgetError):restored.stage('must not run',{}, {})

    def test_completed_runtime_receipt_is_checkpointed_on_normal_failure(self):
        from creation_pipeline.runtime.preparation import prepare as real_prepare
        def admit(record,package,sources,workspace,spec,executor,call_guard=None,**kwargs):
            ticket=call_guard();ticket.update(status='failed',phase='runtime_planning',backend='codex_cli',elapsed_seconds=1.25)
            return real_prepare(record,package,sources,workspace,spec,executor,**kwargs)
        with patch('creation_pipeline.runtime.preparation.prepare',side_effect=admit):
            result,summary,_=self.run_build([fixture.discovery(fixture.candidate()),ARTIFACT])
        saved=read_json(self.sessions[0].state_path)['receipts']
        self.assertEqual(saved,summary['model_metrics']['receipts'])
        self.assertEqual(saved[-1]['elapsed_seconds'],1.25)


if __name__=='__main__':unittest.main()
