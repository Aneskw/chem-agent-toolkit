"""The content gate must precede Docker without granting runtime qualification."""
import copy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from creation_pipeline.generation.author import review
from creation_pipeline.records import read_json
from tests.pipeline import test_discovery as fixtures
from tests.pipeline.support import ARTIFACT


class ReviewScopeTests(unittest.TestCase):
    def test_content_pass_with_deferred_runtime_remains_blocked_without_docker(self):
        fixture = fixtures.DiscoveryTests(); fixture.setUp(); self.addCleanup(fixture.tearDown)
        verdict = {'status': 'pass', 'resolution': 'none', 'findings': [
            {'location': 'runtime', 'problem': 'Docker execution pending',
             'evidence': 'No runtime stage yet', 'impact': 'No business qualification',
             'action': 'Execute locked checks in Docker after this review',
             'blocking': False, 'category': 'check'}]}
        result, _ = fixture.run_case(fixtures.discovery(fixtures.candidate()), ARTIFACT, verdict)
        record = read_json(Path(result['output']) / 'records/add-numbers.json')
        self.assertEqual(next(c for c in record['checks'] if c['name'] == 'content_review')['status'], 'pass')
        self.assertEqual(record['status'], 'blocked')
        self.assertFalse(record['delivery']['qualification']['accepted'])
        prompt = next(p for p in fixture.last_backend.prompts if '"_phase": "review"' in p)
        self.assertIn('"business_execution": "deferred_to_bound_docker"', prompt)
        self.assertIn('"runtime_evidence_required_for_content_approval": false', prompt)
        self.assertIn('Docker report cannot exist until this content review passes', prompt)
        self.assertIn('"cross_check_state_shared": false', prompt)
        author_prompt = next(p for p in fixture.last_backend.prompts if '"_phase": "author"' in p)
        self.assertIn('"cross_check_state_shared": false', author_prompt)

    def review_answer(self, answer):
        session = SimpleNamespace(stage=Mock(return_value=copy.deepcopy(answer)),
            workspace={'resource_index': {}}, sources=SimpleNamespace(
                index=lambda: [], validate_evidence=lambda evidence: []))
        config = {'prompt': 'Require complete Docker acceptance', 'notes': '', 'constraints': [],
                  '_docker_checks': True, 'execute_generated_checks': False}
        return review(session, {'name': 'fixture', 'evidence': []}, {}, [], config)

    def test_a_real_content_defect_is_never_auto_approved(self):
        result = self.review_answer({'status': 'fail', 'resolution': 'revise_files', 'findings': [
            {'blocking': True, 'category': 'file', 'problem': 'Delivered result contradicts source'}]})
        self.assertEqual(result['status'], 'fail')

    def test_missing_evidence_is_not_silently_reclassified_as_pass(self):
        # Includes the old reviewer verdict: the host does not fabricate a pass
        # from category/check text; the clarified protocol needs a fresh review.
        for category in ('source', 'check'):
            with self.subTest(category=category):
                result = self.review_answer({'status': 'fail', 'resolution': 'supply_evidence',
                    'findings': [{'blocking': True, 'category': category, 'problem': 'Missing evidence'}]})
                self.assertEqual(result['status'], 'not_run')


if __name__ == '__main__':
    unittest.main()
