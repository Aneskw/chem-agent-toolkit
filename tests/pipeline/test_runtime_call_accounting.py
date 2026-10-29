"""Mixed-backend planner receipts must not be labelled as the native CLI model."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from creation_pipeline.runtime import planner
from creation_pipeline.runtime.accounting import admit,observe


class RuntimeCallAccountingTests(unittest.TestCase):
    def planner_call(self,guard,side_effect=None):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'source'; source.mkdir()
            (source/'fixture.txt').write_text('positive example',encoding='utf-8')
            receipt={'backend':'deepseek_api','model':'deepseek-example',
                     'usage':{'prompt_tokens':17,'completion_tokens':9},'elapsed_seconds':2.5,
                     'request_count':2,'completion':{'status':'completed'}}
            with patch.object(planner.model_call,'call',return_value=(
                    {'action':'read','requested_files':['fixture.txt'],'reason':'already read'},receipt),
                    side_effect=side_effect) as model:
                with self.assertRaises((planner.PlanningError,planner.ModelUnavailable)):
                    planner.plan(source,{'script':'fixture.txt'},root/'audit',
                        planner.options({'backend':'deepseek_api','api_model':'deepseek-example',
                                         'model':'native-codex-model'}),None,call_guard=guard)
                return model,receipt

    def test_actual_planner_updates_one_admission_with_provider_identity_and_raw_usage(self):
        ledger=[]
        def guard():
            ticket={'phase':'runtime_model','model':None,'status':'attempted','usage':None}
            ledger.append(ticket)
            return ticket
        model,receipt=self.planner_call(guard)
        self.assertEqual(len(ledger),1)
        self.assertEqual(model.call_count,1)
        self.assertEqual(ledger[0]['phase'],'runtime_planning')
        self.assertEqual(ledger[0]['backend'],'deepseek_api')
        self.assertEqual(ledger[0]['model'],'deepseek-example')
        self.assertEqual(ledger[0]['usage'],receipt['usage'])
        self.assertEqual(ledger[0]['request_count'],2)
        self.assertEqual(ledger[0]['elapsed_seconds'],2.5)
        self.assertEqual(ledger[0]['status'],'completed')

    def test_guard_denial_prevents_model_call_and_none_returning_guards_still_work(self):
        denied=Mock(side_effect=planner.PlanningError('budget denied'))
        model,_=self.planner_call(denied)
        model.assert_not_called()
        denied.assert_called_once_with()
        legacy=Mock(return_value=None)
        model,_=self.planner_call(legacy)
        legacy.assert_called_once_with(); model.assert_called_once()

    def test_failed_transport_keeps_admission_but_does_not_fabricate_usage(self):
        ticket={}
        guard=Mock(return_value=ticket)
        model,_=self.planner_call(guard,planner.model_call.ModelExecutionError('offline failure'))
        self.assertEqual(ticket['model'],'deepseek-example')
        self.assertEqual(ticket['status'],'attempted')
        self.assertIsNone(ticket['usage'])
        guard.assert_called_once_with(); model.assert_called_once()

    def test_review_metadata_copy_has_no_request_headers_and_preserves_failure_status(self):
        ticket={}
        receipt={'backend':'codex_cli','model':'native-model','status':'timed_out',
                 'usage':None,'elapsed_seconds':600,'headers':{'Authorization':'not-copied'}}
        original=copy.deepcopy(receipt)
        admit(lambda:ticket,'independent_runtime_review','codex_cli','native-model')
        observe(ticket,receipt)
        self.assertEqual(ticket['status'],'timed_out')
        self.assertNotIn('headers',ticket)
        self.assertEqual(receipt,original)


if __name__=='__main__':
    unittest.main()
