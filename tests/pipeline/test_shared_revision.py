"""Regression specifications for the second revision; execution is deferred by the user."""
import copy
import tempfile
import unittest
from pathlib import Path

from creation_pipeline.shared.contracts import runtime
from creation_pipeline.shared.environment import compatible, OperationError
from creation_pipeline.shared.failures import InfrastructureError, route
from creation_pipeline.shared.investigation import Investigations
from creation_pipeline.shared.pipeline import archive_candidate
from creation_pipeline.shared.verification import TestPlanError, ReviewPlanError
from tests.pipeline.test_shared_creation import env_plan


class RevisionTests(unittest.TestCase):
    def test_investigation_notes_never_enter_delivery_or_matching(self):
        plan = env_plan()
        plan['investigation_notes'] = ['Pinned by host; probe not executed during preparation']
        projected = runtime(plan)
        self.assertNotIn('Pinned', str(projected))
        self.assertNotIn('probe', str(projected))
        other = copy.deepcopy(plan)
        other['investigation_notes'] = ['Different build history']
        self.assertTrue(compatible(plan, other))
        other['conditions']['accelerator'] = 'nvidia'
        self.assertFalse(compatible(plan, other))

    def test_explicit_selection_cannot_override_wrong_typed_conditions(self):
        record = {**env_plan(), 'id': 'env-python', 'version': 'one'}
        request = copy.deepcopy(record)
        request.update(selection='reuse', environment_id='env-python', environment_version='one')
        request['conditions']['network_required'] = True
        self.assertFalse(compatible(record, request))

    def test_failure_owners_are_deterministic(self):
        self.assertEqual(route(TestPlanError('bad fixture path'), 'prepare-tests'), 'prepare-tests')
        self.assertEqual(route(ReviewPlanError('wrong line range'), 'review'), 'review')
        self.assertEqual(route(PermissionError('sharing failure'), 'execute'), 'blocked')
        self.assertEqual(route(InfrastructureError('container not started'), 'execute'), 'blocked')
        self.assertEqual(route(OperationError('registry unavailable'), 'publish'), 'blocked')
        self.assertEqual(route(OperationError('result mismatch'), 'execute'), 'diagnose')

    def test_prepared_facts_are_reused_only_for_exact_unambiguous_sources(self):
        class Sources:
            evidence = [{'id': 'e1', 'kind': 'source_locator', 'path': 'source.txt', 'sha256': 'abc'}]
        source = Sources()
        entity = {'tool_requirements': [{'name': 'python', 'kind': 'runtime', 'version': '3.11'}],
                  'environment_gaps': [], 'resources': []}
        with tempfile.TemporaryDirectory() as temp:
            cache = Investigations(temp)
            cache.remember(env_plan(), source)
            self.assertEqual(cache.resolve(entity, source)['tools'], env_plan()['tools'])
            entity['environment_gaps'] = ['GPU requirement unknown']
            self.assertIsNone(cache.resolve(entity, source))
            entity['environment_gaps'] = []
            source.evidence = [{**source.evidence[0], 'sha256': 'changed'}]
            self.assertIsNone(cache.resolve(entity, source))

    def test_repeated_archive_does_not_hash_its_own_record_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'candidate'
            source.mkdir()
            (source / 'SKILL.md').write_text('Frozen content', encoding='utf-8')
            result = {'name': 'a', 'group': 'g', 'status': 'verified', 'record': 'working/record.json'}
            archived = archive_candidate(root, 'batch', 'g', 'a', source, result)
            retried = archive_candidate(root, 'batch', 'g', 'a', source, {**archived, 'adoption_error': 'transient'})
            self.assertEqual(archived['record'], retried['record'])


if __name__ == '__main__':
    unittest.main()
