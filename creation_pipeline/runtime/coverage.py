"""Pure pre-execution contract coverage, migrated from d5b77dc; no runtime approval."""
import re

from .acceptance import materials_digest

def business_args(tool, case):
    """Only the configured user entrypoint, never an environment/test runner."""
    if case.get('relation') or case.get('layer') == 'environment':
        return None
    args = case.get('args', [])
    if not case.get('entrypoint'):
        return args
    entry = tool['entrypoint']
    if case['entrypoint'] == entry[0] and args[:len(entry)-1] == entry[1:]:
        return args[len(entry)-1:]
    return None


def operation_matches(operation, args):
    return args is not None and all(
        item['index'] < len(args) and args[item['index']] == item['equals']
        for item in operation['selector']['args'])


def input_check(case, check, args):
    """None means absent/unbound material, not a demonstrated invalid value."""
    try:
        if check['channel'] == 'args':
            value = args[check['key']]
        else:
            value = case.get('input_files', {})[check['key']]
            if 'argument_index' in check and args[check['argument_index']] != '/input/' + check['key']:
                return None
    except (IndexError, KeyError, TypeError):
        return None
    values = value.splitlines() if check.get('mode') == 'each_line' else [value]
    return bool(values) and all(re.fullmatch(check['pattern'], item) is not None for item in values)


def _statuses(policy, operations):
    """Invalid-input classification per scope unit: one operation, or the whole tool."""
    if operations:
        if all('input_contract' in operation for operation in operations):
            return {operation['id']: operation['input_contract']['status'] for operation in operations}
        return {operation['id']: policy.get('invalid_input') for operation in operations}
    declared = policy.get('input_contract')
    return {'': declared['status'] if isinstance(declared, dict) else policy.get('invalid_input')}


def _contract(policy, operations, operation_id):
    """The classification record behind one status (for reporting, never for trust)."""
    if isinstance(policy.get('input_contract'), dict) and not operation_id:
        return policy['input_contract']
    return next((operation['input_contract'] for operation in operations
                 if operation['id'] == operation_id and isinstance(operation.get('input_contract'), dict)), {})


def acceptance_coverage(tool, cases, observations=None):
    """No output-string heuristics: coverage and success follow locked contracts.

    ``coverage_complete`` says whether the applicable declared checks are covered.
    ``validation_gaps`` lists behavior that has no contract basis and is therefore not
    verified. ``blockers`` is nonempty when a stated obligation has no verifiable
    contract: that can never be traded for a recorded gap.
    """
    if tool.get('acceptance_version') != 2:
        return {'version': 1, 'complete': False, 'coverage_complete': False, 'validation_gaps': [],
                'blockers': ['Legacy evidence; current acceptance not evaluated'],
                'reasons': ['Legacy evidence; current acceptance not evaluated']}
    policy = tool.get('acceptance_policy', {})
    anchors = tool.get('input_anchors') or {}
    coverage_reasons, gaps, blockers = [], [], []
    supported = [c for c in cases if c.get('oracle_status') == 'supported' and c.get('acceptance')]
    direct = [c for c in supported if business_args(tool, c) is not None]
    positive = [c for c in direct if c['acceptance']['purpose'] in {'computation', 'operation', 'report'}
                and c.get('expected_exit', 0) == 0 and not c.get('relation')
                and not any(a in {'--help', '--version', '-h', '-V'} for a in c['args'])]
    negative = [c for c in direct if c['acceptance']['purpose'] == 'input_rejection']
    checks = policy.get('checks', [])
    operations = policy.get('operations', [])
    statuses = _statuses(policy, operations)
    declared = bool(operations and all('input_contract' in operation for operation in operations)) \
        or (not operations and isinstance(policy.get('input_contract'), dict))
    def routes(case):
        return [op for op in operations if operation_matches(op, business_args(tool, case))]
    def applicable(case):
        if not operations:
            return checks
        matched = routes(case)
        if len(matched) != 1:
            return None
        return [check for check in checks if check['id'] in matched[0]['checks']]
    def accepts(case, check):
        return input_check(case, check, business_args(tool, case))
    def valid(case):
        selected = applicable(case)
        return selected is not None and all(accepts(case, check) is True for check in selected)
    positive = [c for c in positive if valid(c)]
    completed_negative = [c for c in direct if c['acceptance']['purpose'] in {'computation', 'operation', 'report'}
                          and c.get('expected_exit', 0) != 0 and valid(c)]
    def outcome(case):
        assertion = case['acceptance']['assertion']
        return (case.get('expected_exit', 0), {k:v for k,v in assertion.items()
                if k not in {'source_path', 'source_quote', 'role'}})
    def rejects(case, check):
        selected = applicable(case)
        return (case['acceptance'].get('violates') == check['id'] and selected is not None
                and check in selected and accepts(case, check) is False
                and all(outcome(case) != outcome(normal) for normal in positive))
    if not positive:
        coverage_reasons.append('No grounded normal input with a result assertion')
    purposes = policy.get('purposes')
    if (not isinstance(purposes, list) or not purposes
            or not set(purposes) <= {c['acceptance']['purpose'] for c in positive}):
        coverage_reasons.append('Declared purposes are not covered by grounded normal cases')

    def unit_positive(operation_id):
        if not operation_id:
            return positive
        operation = next(o for o in operations if o['id'] == operation_id)
        return [c for c in positive if operation_matches(operation, business_args(tool, c))]

    def supplied_input(operation_id):
        """Business input the caller supplies, beyond the documented invocation tokens."""
        if not operation_id:
            return any(c.get('args') or c.get('input_files') for c in positive)
        operation = next(o for o in operations if o['id'] == operation_id)
        tokens = (operation.get('selector') or {}).get('args') or []
        for c in unit_positive(operation_id):
            if c.get('input_files') or len(business_args(tool, c) or []) > len(tokens):
                return True
        return False

    def missing_rejections(operation):
        return [check['id'] for check in checks
                if check['id'] in operation.get('checks', []) and not any(rejects(c, check) for c in negative)]

    if declared:
        for operation_id, state in statuses.items():
            label = 'Operation ' + operation_id if operation_id else 'Acceptance'
            record = _contract(policy, operations, operation_id)
            if state == 'required':
                if operation_id:
                    continue
                # A tool-level requirement covers every declared check.
                if not checks:
                    coverage_reasons.append('Input constraint lacks a checkable fixture predicate')
                for check in checks:
                    if not [c for c in negative if rejects(c, check)]:
                        coverage_reasons.append('Missing actual invalid-input rejection: ' + check['id'])
                continue
            if state == 'not_applicable':
                if supplied_input(operation_id):
                    blockers.append(label + ': not_applicable is only valid for an operation without '
                                           'supplied user input; declare required or none_documented instead')
                continue
            if state != 'none_documented':
                continue
            if anchors.get('forbids_none_documented'):
                blockers.append(label + ': invalid-input verification is required by '
                                + str(anchors.get('basis') or 'a stated obligation')
                                + '; none_documented cannot waive it. Supply a verifiable contract or block')
            gaps.append({'unit': operation_id or 'tool', 'status': state,
                         'reason': record.get('reason', ''), 'scope': record.get('scope', ''),
                         'limitation': record.get('limitation', ''),
                         'materials_sha256': materials_digest(record.get('checked') or []),
                         'reviewer': (record.get('review') or {}).get('reviewer', '')})
    else:
        # Legacy policies classify the tool as a whole; unchanged behavior.
        state = policy.get('invalid_input')
        if state == 'required':
            if not checks:
                coverage_reasons.append('Input constraint lacks a checkable fixture predicate')
            for check in checks:
                if not [c for c in negative if rejects(c, check)]:
                    coverage_reasons.append('Missing actual invalid-input rejection: ' + check['id'])
        elif state != 'not_applicable' or not policy.get('source_quote') or not policy.get('scope'):
            coverage_reasons.append('Input applicability not grounded')
        elif any(c.get('args') or c.get('input_files') for c in positive):
            coverage_reasons.append('Not-applicable exemption only supports operations without supplied user input')

    operation_coverage = {}
    for operation in operations:
        normal = [c for c in positive if operation_matches(operation, business_args(tool, c))]
        rejected = [c for c in negative if operation_matches(operation, business_args(tool, c))]
        missing = []
        if not normal or not set(operation['purposes']) <= {c['acceptance']['purpose'] for c in normal}:
            missing.append('normal business purpose')
        if operation.get('require_persistence') and not any(c.get('output_file') and not c.get('capture_stdout') for c in normal):
            missing.append('persisted output')
        state = statuses.get(operation['id'])
        if state == 'required' or (not declared and policy.get('invalid_input') == 'required'):
            for check in checks:
                if check['id'] in operation['checks'] and not any(rejects(c, check) for c in rejected):
                    missing.append('rejection for ' + check['id'])
        operation_coverage[operation['id']] = {'normal_cases': [c['name'] for c in normal],
                                               'invalid_input': state, 'missing': missing}
        coverage_reasons.extend('Operation ' + operation['id'] + ' missing ' + item for item in missing)
    # file_io remains a persistence obligation independently of which example is selected.
    if tool.get('behavior', {}).get('file_io') and not any(c.get('output_file') and not c.get('capture_stdout') for c in positive):
        coverage_reasons.append('No grounded normal persisted-output case for declared file IO')
    if observations is not None:
        passed = {c['name'] for c in observations if c['status'] == 'passed'}
        required = positive + negative + completed_negative
        if any(c['name'] not in passed for c in required):
            coverage_reasons.append('Required acceptance cases did not pass')
    coverage_complete = not coverage_reasons
    reasons = coverage_reasons + blockers
    return {'version': 2, 'complete': coverage_complete and not blockers,
            'coverage_complete': coverage_complete, 'validation_gaps': gaps, 'blockers': blockers,
            'reasons': reasons,
            'normal_cases': [c['name'] for c in positive],
            'operations': operation_coverage,
            'completed_negative_cases': [c['name'] for c in completed_negative],
            'purposes': sorted({c['acceptance']['purpose'] for c in positive}),
            'scientific_correctness': 'not_evaluated'}


def forwarded_args(tool, case):
    return business_args(tool, case)


class NoUsageCase(ValueError):
    """A valid contract may still lack a selectable normal invocation."""


def select_usage_case(tool,cases):
    candidates = [(c, forwarded_args(tool, c)) for c in cases if c.get("oracle_status") == "supported"]
    candidates = [(c, args) for c, args in candidates if c.get('expected_exit', 0) == 0]
    if tool.get('acceptance_version') == 2:
        normal = acceptance_coverage(tool, cases)['normal_cases']
        candidates = [(c, args) for c, args in candidates if c['name'] in normal]
    candidates = [(c, args) for c, args in candidates if args is not None and
                  (args or (tool.get('acceptance_version') == 2 and tool.get('acceptance_policy', {}).get('invalid_input') == 'not_applicable'))
                  and not any(a in {"--help", "--version", "-V", "-h"} for a in args)]
    if not candidates:
        raise NoUsageCase("No supported, directly invocable usage example; add a test exercising the configured entrypoint with real input/output")
    candidates.sort(key=lambda item: (item[0].get("expected_exit", 0) != 0, not item[0].get("output_file")))
    return candidates[0]
