"""Read-only file input is a reviewed source scope, not a planner exemption.

Pure mechanism tests; no models, Docker, chemistry or geometry execution.
"""
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from creation_pipeline.artifacts.package import manifest
from creation_pipeline.contracts import requirement
from creation_pipeline.generation.author import review
from creation_pipeline.runtime.coverage import acceptance_coverage
from creation_pipeline.runtime.preparation import input_anchors, merged_anchors, RuntimeBlocked
from creation_pipeline.runtime import planner
from tests.pipeline import test_runtime_build as build_fixtures


DOC = 'Read request files without changing them. Results are JSON on stdout; no output files are written.'


def output_contract():
    return {'mode': 'read_only_stdout', 'reason': 'Documented read-only input and stdout results',
            'citations': [{'source_id': 'tool', 'path': 'api.txt', 'quote': DOC}]}


def gate_fixture():
    check = {'id': 'nonempty', 'channel': 'input_files', 'key': 'request.txt',
             'argument_index': 1, 'pattern': r'(?s).*\S.*'}
    operation = {'id': 'file', 'selector': {'args': [{'index': 0, 'equals': '--request'}]},
                 'checks': ['nonempty'], 'purposes': ['computation'], 'require_persistence': False}
    policy = {'invalid_input': 'required', 'purposes': ['computation'], 'checks': [check],
              'operations': [operation]}
    cases = []
    for valid in (True, False):
        contract = {'purpose': 'computation' if valid else 'input_rejection', 'assertion': {
            'kind': 'json', 'role': 'completion' if valid else 'rejection',
            'path': ['status'], 'allowed_values': ['success' if valid else 'error']}}
        if not valid:
            contract.update(violates='nonempty', invalid_input_reason='Empty request')
        case = {'name': 'report' if valid else 'invalid', 'layer': 'behavior',
                'oracle_status': 'supported', 'args': ['--request', '/input/request.txt'],
                'input_files': {'request.txt': 'valid request' if valid else ''},
                'expected_exit': 0 if valid else 2, 'acceptance': contract}
        if valid:
            case.update(output_file='report.json', capture_stdout=True)
        cases.append(case)
    tool = {'entrypoint': ['python', '/opt/skill/package/main.py'], 'behavior': {'file_io': True},
            'acceptance_version': 2, 'acceptance_policy': policy}
    return tool, cases


class ReviewedOutputRequirementTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); (root / 'api.txt').write_text(DOC, encoding='utf-8')
        self.sources = [{'id': 'tool', 'path': str(root), 'inventory': manifest(root)}]
        self.proposal = {'status': 'required', 'reason': 'Executable file-input procedure',
                         'citations': output_contract()['citations'], 'file_output': output_contract()}
        self.review = {'status': 'pass', 'requirement_assessment': 'confirmed',
                       'file_output_assessment': 'confirmed'}

    def test_only_exact_source_and_explicit_independent_confirmation_resolve_mode(self):
        self.assertEqual(requirement(self.proposal, self.sources, self.review), self.proposal)
        for assessment in (None, 'unknown', 'conflict'):
            review = dict(self.review, file_output_assessment=assessment)
            self.assertEqual(requirement(self.proposal, self.sources, review)['status'], 'unknown')
        bad = copy.deepcopy(self.proposal)
        bad['file_output']['citations'][0]['quote'] = 'The writer has no --output flag (invented)'
        self.assertEqual(requirement(bad, self.sources, self.review)['status'], 'unknown')

    def test_no_self_confirmation_or_no_execution_variant(self):
        for field, value in (('review', {'status': 'confirmed'}), ('mode', 'arbitrary')):
            bad = copy.deepcopy(self.proposal); bad['file_output'][field] = value
            self.assertEqual(requirement(bad, self.sources, self.review)['status'], 'unknown')
        bad = dict(self.proposal, status='not_required')
        self.assertEqual(requirement(bad, self.sources, self.review)['status'], 'unknown')
        for citations in ('untyped citation', ['not an object']):
            bad = copy.deepcopy(self.proposal); bad['file_output']['citations'] = citations
            self.assertEqual(requirement(bad, self.sources, self.review)['status'], 'unknown')

    def test_review_separately_assesses_readonly_scope_and_writer_conflicts(self):
        session = SimpleNamespace(stage=Mock(return_value={'status': 'pass', 'resolution': 'none',
            'findings': [], 'file_output_assessment': 'confirmed'}), workspace={'resource_index': {}},
            sources=SimpleNamespace(index=lambda: [], validate_evidence=lambda evidence: []))
        config = {'prompt': '', 'notes': '', 'constraints': [], '_docker_checks': True,
                  'runtime_requirements': {'fixture': self.proposal}}
        review(session, {'name': 'fixture', 'evidence': []}, {}, [], config)
        args = session.stage.call_args
        self.assertIn('file_output_assessment', args.kwargs['schema']['required'])
        self.assertIn('A documented output-file flag or write obligation conflicts', args.args[0])
        self.assertEqual(args.args[1]['execution_requirement'], self.proposal)

    def test_reviewed_contract_is_frozen_and_cannot_change_on_repair(self):
        accepted = requirement(self.proposal, self.sources, self.review)
        record = {'delivery': {'inputs': {'requirement': accepted, 'acceptance': {'payload': {}}}}}
        anchors = input_anchors(record)
        self.assertEqual(anchors['file_output'], output_contract())
        record['delivery']['inputs']['acceptance']['payload']['input_anchors'] = copy.deepcopy(anchors)
        self.assertEqual(merged_anchors(record)['file_output'], output_contract())
        del record['delivery']['inputs']['requirement']['file_output']
        with self.assertRaisesRegex(RuntimeBlocked, 'cannot change'):
            merged_anchors(record)

    def test_existing_writer_obligation_cannot_be_converted_during_repair(self):
        record = {'delivery': {'inputs': {'requirement': self.proposal,
                  'acceptance': {'payload': {'input_anchors': {'basis': 'writer contract'}}}}}}
        with self.assertRaisesRegex(RuntimeBlocked, 'cannot change'):
            merged_anchors(record)


class ReadOnlyCoverageTests(unittest.TestCase):
    def test_planner_cannot_turn_off_file_io_for_a_reviewed_readonly_file_contract(self):
        fixture = build_fixtures.RuntimeBuildTests(); fixture.setUp(); self.addCleanup(fixture.tearDown)
        from creation_pipeline.runtime.preparation import handoff
        source = fixture.root / 'handoff'; handoff(fixture.package, fixture.sources, source)
        index = planner.inventory(source, planner.options({})); index['read_files'] = list(index['files'])
        with self.assertRaisesRegex(planner.PlanningError, 'requires file_io=true and actual /input fixtures'):
            planner.validate_plan(build_fixtures.plan(), index, source,
                                  anchors={'file_output': output_contract()})

    def test_legacy_writer_still_requires_an_actual_file_even_with_planner_claim(self):
        tool, cases = gate_fixture()
        tool['acceptance_policy']['file_output'] = output_contract()
        self.assertFalse(acceptance_coverage(tool, cases)['complete'])
        cases[0]['capture_stdout'] = False
        self.assertTrue(acceptance_coverage(tool, cases)['complete'])

    def test_reviewed_readonly_scope_needs_bound_file_input_retained_report_and_rejection(self):
        tool, cases = gate_fixture()
        tool['input_anchors'] = {'file_output': output_contract()}
        self.assertTrue(acceptance_coverage(tool, cases)['complete'])
        for field in ('input_files', 'output_file', 'capture_stdout'):
            broken = copy.deepcopy(cases); broken[0].pop(field)
            self.assertFalse(acceptance_coverage(tool, broken)['complete'], field)
        self.assertFalse(acceptance_coverage(tool, cases[:1])['complete'])
        observations = [{'name': c['name'], 'status': 'passed'} for c in cases]
        self.assertTrue(acceptance_coverage(tool, cases, observations)['complete'])
        observations[0]['status'] = 'failed'
        self.assertFalse(acceptance_coverage(tool, cases, observations)['complete'])

    def test_stdout_capture_never_satisfies_operation_write_promise(self):
        tool, cases = gate_fixture(); tool['input_anchors'] = {'file_output': output_contract()}
        tool['acceptance_policy']['operations'][0]['require_persistence'] = True
        result = acceptance_coverage(tool, cases)
        self.assertFalse(result['complete'])
        self.assertIn('Operation file missing persisted output', result['reasons'])


if __name__ == '__main__':
    unittest.main()
