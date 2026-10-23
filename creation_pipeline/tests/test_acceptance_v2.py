"""Mocked engine/registry and local fault injection; no chemistry or real Docker."""
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import test_runtime_model as base
import runtime_model as planner
import runtime_model_lifecycle as lifecycle
import runtime_package as runner
import runtime_transaction as transaction
from runtime_common import files, read, write
from runtime_common import digest
from runtime_examples import select_usage_case


DOC = ('Integer input is required; non-integer input prints invalid with exit 7. '
       'For input 3 the result is 6. '
       'The completed field is true when calculation completed, including uncertain results; '
       'runtime failures set completed false. '
       'This no-input report operation has no user-controlled input.')


class AcceptanceV2Tests(unittest.TestCase):
    generate = base.ModelRuntimeTests.generate
    fake_process = base.ModelRuntimeTests.fake_process
    fake_case = base.ModelRuntimeTests.fake_case

    def setUp(self):
        base.ModelRuntimeTests.setUp(self)
        self.plan['tests'] = self.plan['tests'][:3]
        (self.source / 'README.md').write_text(DOC, encoding='utf-8')
        self.policy = dict(invalid_input='required', scope='integer doubling', purposes=['operation'],
                           constraint='integer argument', source_path='README.md', source_quote=DOC,
                           checks=[dict(id='integer', channel='args', key=0, pattern=r'-?[0-9]+',
                                        source_path='README.md', source_quote=DOC)])
        self.plan['acceptance_json'] = json.dumps(self.policy)
        for i in (1, 2):
            case = json.loads(self.plan['tests'][i]['case_json'])
            case['acceptance'] = self.contract('operation', 'result', '6')
            self.plan['tests'][i]['case_json'] = json.dumps(case)
        negative = copy.deepcopy(self.plan['tests'][2])
        negative['name'] = 'reject-invalid'
        contract = self.contract('input_rejection', 'rejection', 'invalid')
        contract.update(violates='integer', invalid_input_reason='abc fails the integer grammar')
        negative['case_json'] = json.dumps(dict(args=['abc'], expected_exit=7, stdout_equals='invalid', acceptance=contract))
        self.plan['tests'].append(negative)

    def contract(self, purpose, role, value):
        return dict(purpose=purpose, source_path='README.md', source_quote=DOC,
                    assertion=dict(role=role, kind='stdout_equals', value=value, source_path='README.md', source_quote=DOC))

    def generated(self):
        self.assertEqual(self.generate()['status'], 'prepared')
        tool = read(self.skill / 'runtime/package.json')['tools']['double']
        cases = read(self.skill / tool['context'] / tool['fixtures'])['cases']
        return tool, cases

    def validate_mock(self):
        with patch.object(runner, 'process', side_effect=self.fake_process), \
             patch.object(runner, 'run_case', side_effect=self.fake_case), \
             patch.object(lifecycle, 'verify_examples', return_value=[{'status': 'passed'}]):
            return lifecycle.validate(self.skill)

    def test_completed_uncertain_vs_runtime_failure(self):
        tool, cases = self.generated()
        case = copy.deepcopy(cases[2]); case.pop('stdout_equals')
        case['acceptance']['purpose'] = 'computation'
        case['acceptance']['assertion'] = dict(kind='json', role='completion', path=['completed'],
                                               allowed_values=[True], source_path='README.md', source_quote=DOC)
        for completed, expected in [(False, 'failed'), (True, 'passed')]:
            receipt = dict(exit_code=0, stdout=json.dumps(dict(completed=completed, result='inconclusive',
                           detail='execution_error' if not completed else 'legitimate uncertain result')), stderr='')
            with patch.object(runner, 'run', return_value=receipt):
                self.assertEqual(runner.run_case(self.skill, tool, 'image', case)['status'], expected)

    def test_no_global_error_string_heuristic(self):
        tool, cases = self.generated()
        case = copy.deepcopy(cases[2]); case.pop('stdout_equals')
        case['acceptance']['assertion']['value'] = 'execution_error is a documented word'
        with patch.object(runner, 'run', return_value=dict(exit_code=0, stdout='execution_error is a documented word', stderr='')):
            self.assertEqual(runner.run_case(self.skill, tool, 'image', case)['status'], 'passed')

    def test_actual_negative_rejection_exit_seven(self):
        tool, cases = self.generated()
        with patch.object(runner, 'run', return_value=dict(exit_code=7, stdout='invalid', stderr='')):
            self.assertEqual(runner.run_case(self.skill, tool, 'image', cases[-1])['status'], 'passed')
        with patch.object(runner, 'run', return_value=dict(exit_code=7, stdout='unrelated crash', stderr='')):
            self.assertEqual(runner.run_case(self.skill, tool, 'image', cases[-1])['status'], 'failed')
        zero_exit_contract = dict(cases[-1], expected_exit=0)
        with patch.object(runner, 'run', return_value=dict(exit_code=0, stdout='invalid', stderr='')):
            self.assertEqual(runner.run_case(self.skill, tool, 'image', zero_exit_contract)['status'], 'passed')

    def test_failed_completion_never_reaches_acceptance(self):
        self.generated()
        def failure(root, tool, image, case, **kwargs):
            return dict(case, status='failed' if case['name'] == 'double' else 'passed')
        with patch.object(runner, 'process', side_effect=self.fake_process), \
             patch.object(runner, 'run_case', side_effect=failure), \
             patch.object(lifecycle, 'verify_examples') as examples:
            report = lifecycle.validate(self.skill, budget={'max_attempts': 1})
        self.assertNotEqual(report['status'], 'execution_passed')
        self.assertEqual(report['tools'][0]['last_failure'], 'execution_failed')
        examples.assert_not_called()

    def assert_prelock_incomplete(self):
        # Stronger boundary: invalid contracts are rejected before execution/lock.
        result = self.generate()
        self.assertEqual(result['status'], 'validation_incomplete')
        self.assertEqual(read(self.skill / 'runtime/prepared.json')['status'], 'validation_incomplete')
        self.assertEqual(read(self.skill / 'runtime/package.json')['tools'], {})
        self.assertFalse(any(e['kind'] == 'usage' for e in read(self.skill / 'runtime/examples.json')['examples']))
        self.assertFalse(list(self.skill.glob('runtime/tools/*/context')))

    def test_missing_result_contract_cannot_claim_computation(self):
        self.policy['purposes'] = ['computation']; self.plan['acceptance_json'] = json.dumps(self.policy)
        for i in (1, 2):
            case = json.loads(self.plan['tests'][i]['case_json']); case.pop('acceptance')
            self.plan['tests'][i]['case_json'] = json.dumps(case)
        self.assert_prelock_incomplete()

    def test_missing_negative_final_state_incomplete(self):
        self.plan['tests'].pop()
        self.assert_prelock_incomplete()

    def test_only_negative_has_no_normal_example(self):
        for i in (1, 2):
            case = json.loads(self.plan['tests'][i]['case_json']); case.pop('acceptance')
            self.plan['tests'][i]['case_json'] = json.dumps(case)
        self.assert_prelock_incomplete()

    def test_labels_do_not_make_valid_input_negative(self):
        case = json.loads(self.plan['tests'][-1]['case_json']); case['args'] = ['3']
        self.plan['tests'][-1]['case_json'] = json.dumps(case)
        self.assert_prelock_incomplete()

    def test_only_negative_file_tool_is_incomplete_without_usage(self):
        self.plan['file_io'] = True
        negative = self.plan['tests'][-1]
        negative['layer'] = 'interface'
        case = json.loads(negative['case_json'])
        case.update(output_file='report.txt', capture_stdout=True, input_files={'invalid.txt':'abc'})
        negative['case_json'] = json.dumps(case)
        self.plan['tests'] = [self.plan['tests'][0], negative]
        self.assert_prelock_incomplete()

    def test_not_applicable_requires_source_and_scope(self):
        self.policy.update(invalid_input='not_applicable', checks=[], scope='no-input report', purposes=['report'])
        self.plan['acceptance_json'] = json.dumps(self.policy)
        self.plan['tests'].pop()
        self.plan['tests'] = [self.plan['tests'][0], self.plan['tests'][2]]
        self.plan['entrypoint'] = ['python', '-c', 'print(6)']
        case = json.loads(self.plan['tests'][1]['case_json']); case['args'] = []
        case['acceptance']['purpose'] = 'report'; case['acceptance']['assertion']['role'] = 'report'
        self.plan['tests'][1]['layer'] = 'interface'
        self.plan['tests'][1]['case_json'] = json.dumps(case)
        tool, cases = self.generated()
        self.assertTrue(runner.acceptance_coverage(tool, cases)['complete'])
        bad = copy.deepcopy(self.plan); policy = dict(self.policy, source_quote='invented exemption')
        bad['acceptance_json'] = json.dumps(policy)
        with self.assertRaises(ValueError): planner.validate_plan(bad, planner.inventory(self.source, planner.options({})), self.source)

    def test_computation_scope_cannot_be_satisfied_by_report(self):
        self.policy['purposes'] = ['computation']; self.plan['acceptance_json'] = json.dumps(self.policy)
        self.assert_prelock_incomplete()

    def test_contract_and_input_policy_locked(self):
        tool, cases = self.generated()
        changed = copy.deepcopy(self.plan); policy = dict(self.policy, invalid_input='not_applicable')
        changed['acceptance_json'] = json.dumps(policy)
        with self.assertRaisesRegex(ValueError, 'locked'):
            planner.validate_plan(changed, planner.inventory(self.source, planner.options({})), self.source, cases)
        changed = copy.deepcopy(self.plan); case = json.loads(changed['tests'][2]['case_json'])
        case['acceptance']['assertion']['value'] = 'wrong'; changed['tests'][2]['case_json'] = json.dumps(case)
        with self.assertRaisesRegex(ValueError, 'locked'):
            planner.validate_plan(changed, planner.inventory(self.source, planner.options({})), self.source, cases)

    def rematerialize(self, opts=None):
        return planner.materialize(self.source, {}, self.skill / 'runtime/tools/double/context', 'double', self.plan,
                                   planner.inventory(self.source, planner.options({})), planner.options(opts or {}))

    def test_registry_failure_preserves_whole_working_package(self):
        self.generated(); before = files(self.skill)
        with patch('runtime_reproducibility.resolve_base', side_effect=OSError('offline')):
            with self.assertRaises(OSError): self.rematerialize({'pin_base_image': True})
        self.assertEqual(files(self.skill), before)

    def test_attempt_evidence_failure_happens_before_commit(self):
        self.generated(); before = files(self.skill)
        with self.assertRaises(OSError):
            planner.materialize(self.source, {}, self.skill / 'runtime/tools/double/context', 'double', self.plan,
                planner.inventory(self.source, planner.options({})), planner.options({}),
                before_commit=lambda *args: (_ for _ in ()).throw(OSError('audit snapshot unavailable')))
        self.assertEqual(files(self.skill), before)

    def test_last_replace_failure_restores_context_metadata_and_package(self):
        self.generated(); before = files(self.skill); original = os.replace
        self.plan['environment'] = [dict(name='NEW', value='value')]
        def replace(source, target):
            if Path(source).name == 'package.json' and Path(source).parent.name.startswith('.generation-'):
                raise OSError('injected final replacement failure')
            return original(source, target)
        with patch.object(transaction.os, 'replace', side_effect=replace):
            with self.assertRaises(OSError): self.rematerialize()
        self.assertEqual(files(self.skill), before)

    def test_exception_after_directory_move_also_restores(self):
        self.generated(); before = files(self.skill); original = os.replace
        fired = False
        def replace(source, target):
            nonlocal fired
            result = original(source, target)
            if not fired and Path(source).name == 'context' and Path(source).parent.name.startswith('.generation-'):
                fired = True
                raise OSError('injected exception after directory move')
            return result
        with patch.object(transaction.os, 'replace', side_effect=replace):
            with self.assertRaises(OSError): self.rematerialize()
        self.assertEqual(files(self.skill), before)

    def test_rollback_failure_retains_recoverable_backup(self):
        self.generated(); original = os.replace
        old_context = files(self.skill / 'runtime/tools/double/context')
        def replace(source, target):
            if Path(source).name == 'package.json' or Path(source).name.startswith('backup-'):
                raise OSError('injected commit/rollback failure')
            return original(source, target)
        with patch.object(transaction.os, 'replace', side_effect=replace):
            with self.assertRaisesRegex(OSError, 'retained recovery files'): self.rematerialize()
        recovery = list((self.skill / 'runtime/tools/double').glob('.generation-*'))
        self.assertEqual(len(recovery), 1)
        self.assertEqual(files(recovery[0] / 'backup-0'), old_context)
        self.assertTrue((recovery[0] / 'recovery.json').is_file())

    def test_success_commits_matching_plan_configuration_and_proof(self):
        self.generated(); self.plan['environment'] = [dict(name='NEW', value='value')]
        tool, proof = self.rematerialize()
        root = self.skill / 'runtime/tools/double'
        self.assertEqual(read(root / 'environment_plan.json'), self.plan)
        self.assertEqual(read(root / 'tool.json'), tool)
        self.assertEqual(read(self.skill / 'runtime/package.json')['tools']['double'], tool)
        self.assertEqual(read(root / 'provenance.json'), proof)
        self.assertEqual(read(root / 'context/.skillnet/fixtures.json')['cases'], proof['cases'])
        self.assertIn('ENV NEW=', (root / 'context/Dockerfile').read_text())

    def test_failed_reprepare_restores_old_runtime_and_keeps_failure(self):
        self.generated(); before = {k:v for k,v in files(self.skill).items() if not k.startswith('reports/')}
        self.settings['planner']['pin_base_image'] = True; write(self.bindings, self.settings)
        with patch('runtime_reproducibility.resolve_base', side_effect=OSError('offline')):
            result = self.generate()
        self.assertTrue(result['restored_previous_runtime'])
        self.assertTrue(Path(result['failed_generation']).is_dir())
        self.assertEqual(before, {k:v for k,v in files(self.skill).items() if not k.startswith('reports/')})

    def test_v2_pass_requires_coverage_and_legacy_is_not_promoted(self):
        self.generated(); result = self.validate_mock()
        self.assertEqual(result['status'], 'execution_passed')
        self.assertTrue(result['tools'][0]['acceptance']['complete'])
        tool = read(self.skill / 'runtime/package.json')['tools']['double']
        tool.pop('acceptance_version')
        self.assertEqual(runner.acceptance_coverage(tool, [])['version'], 1)
        self.assertFalse(runner.acceptance_coverage(tool, [])['complete'])

    def test_legacy_inspection_and_publication_do_not_upgrade_or_rewrite(self):
        self.generated(); self.validate_mock()
        prepared = read(self.skill / 'runtime/prepared.json'); prepared.pop('acceptance_version')
        write(self.skill / 'runtime/prepared.json', prepared)
        report = read(self.skill / 'runtime/execution.json'); report.pop('acceptance_version')
        report['prepared_sha256'] = digest(prepared)
        write(self.skill / 'runtime/execution.json', report)
        before = files(self.skill)
        with patch.object(runner, 'process', side_effect=self.fake_process):
            inspected = lifecycle.evidence(self.skill)
        self.assertEqual(inspected['status'], 'execution_passed')
        self.assertEqual(inspected['acceptance_version'], 1)
        self.assertFalse(inspected['current_acceptance_validated'])
        self.assertEqual(before, files(self.skill))
        import publish_run
        from types import SimpleNamespace
        with patch.object(publish_run, 'evidence', return_value=inspected), patch('candidate_identity.load', return_value={}):
            publish_run.stage_reports(SimpleNamespace(run_id='review'), {'runtime_mode':'docker'}, [self.skill], self.root, {})
        manifest = read(self.root / 'PUBLISHING.json')
        self.assertFalse(manifest['current_acceptance_validated'])
        self.assertEqual(manifest['acceptance_versions'][self.skill.name], 1)


if __name__ == '__main__':
    unittest.main()
