"""Source-grounded acceptance contracts, checked before any execution.

Runtime evaluation lives in the portable runner; this module only checks evidence.
"""
import json
import re
from pathlib import Path


class ContractConflict(ValueError):
    def __init__(self, conflicts):
        self.conflicts = conflicts
        self.lane = 'contract'
        self.code = 'contract_conflict'
        super().__init__('Inconsistent acceptance contract: ' + json.dumps(conflicts, ensure_ascii=False))


# What is promised about invalid input is separate from whether that promise was
# verified. The three states have different obligations:
#   required          the caller, the delivered interface or the source states a rule
#   none_documented   the examined materials declare none, and nobody promised one
#   not_applicable    the operation has no caller-supplied business input at all
INPUT_STATES = ('required', 'none_documented', 'not_applicable')
AGGREGATE = {'required': 3, 'none_documented': 2, 'not_applicable': 1}
# The fields each state must carry. The prompt audit derives its needles from this,
# so a validator rule cannot be added without the model-visible text following.
CONTRACT_FIELDS = {'required': ('constraint',),
                   'none_documented': ('reason', 'scope', 'limitation', 'checked', 'review'),
                   'not_applicable': ('reason',)}
CONTRACT_LINKAGE = ('materials_sha256', 'context')


def materials_digest(checked):
    """Identity of the exact materials a classification claims to have examined."""
    from creation_pipeline.contracts import fingerprint
    return fingerprint([{'source_path': item['source_path'], 'sha256': item['sha256']}
                        for item in checked])


def input_contract(record, index, source, where='Input contract'):
    """Validate one invalid-input classification and return its state.

    ``none_documented`` is a recorded absence, never an invented proof: it names the
    examined materials by fingerprint, the examined scope, the reason and the residual
    limitation, and it is bound to an independent confirmation. A quotation may be
    attached as context but never replaces that record.
    """
    if not isinstance(record, dict):
        raise ValueError(where + ': invalid input classification must be an object')
    status = record.get('status')
    if status not in INPUT_STATES:
        raise ValueError(where + ': invalid input status must be one of ' + ', '.join(INPUT_STATES))
    if status == 'required':
        if not isinstance(record.get('constraint'), str) or not record['constraint'].strip():
            raise ValueError(where + ': required input policy must identify the input constraint')
        return status
    if status == 'not_applicable':
        if not isinstance(record.get('reason'), str) or not record['reason'].strip():
            raise ValueError(where + ': not_applicable needs a reason why no caller input exists')
        return status
    for field in CONTRACT_FIELDS['none_documented']:
        value = record.get(field)
        filled = value.strip() if isinstance(value, str) else value
        if not filled:
            raise ValueError(where + ': none_documented needs a nonempty ' + field)
    checked = record.get('checked')
    if not isinstance(checked, list) or not checked:
        raise ValueError(where + ': none_documented must list the materials it examined')
    for item in checked:
        if not isinstance(item, dict) or set(item) != {'source_path', 'sha256'}:
            raise ValueError(where + ': checked materials are exactly {source_path, sha256}')
        entry = index.get('files', {}).get(item['source_path'])
        if item['source_path'] not in index.get('read_files', index.get('files', {})):
            raise ValueError(where + ': checked material was never read: ' + str(item['source_path']))
        if not entry or entry.get('sha256') != item['sha256']:
            raise ValueError(where + ': checked material fingerprint does not match: ' + str(item['source_path']))
    if 'context' in record and not grounded(record['context'], index, source):
        raise ValueError(where + ': a context quotation must be grounded, or omitted; it never proves absence')
    review = record.get('review')
    if (not isinstance(review, dict) or review.get('status') != 'confirmed'
            or not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip()):
        raise ValueError(where + ': none_documented needs an independent confirmation of this classification')
    if review.get('materials_sha256') != materials_digest(checked):
        raise ValueError(where + ': the independent confirmation is not bound to the examined materials')
    return status


def _classification(policy, index, source):
    """Resolve the authoritative classification, and keep the legacy field honest."""
    operations = policy.get('operations', [])
    if not isinstance(operations, list) or not all(isinstance(o, dict) for o in operations):
        raise ValueError('Acceptance operations must be objects')
    if operations:
        declared = ['input_contract' in operation for operation in operations]
        if any(declared) and not all(declared):
            raise ValueError('Every operation must classify its own invalid-input contract')
        if all(declared) and declared:
            states = [input_contract(operation['input_contract'], index, source,
                                     'Operation ' + str(operation.get('id'))) for operation in operations]
            aggregate = max(states, key=lambda state: AGGREGATE[state])
            if policy.get('invalid_input') != aggregate:
                raise ValueError('invalid_input must equal the per-operation aggregate: ' + aggregate)
            return 'operations', aggregate
        return 'legacy', policy.get('invalid_input')
    if 'input_contract' in policy:
        status = input_contract(policy['input_contract'], index, source)
        if policy.get('invalid_input') != status:
            raise ValueError('invalid_input must equal the declared input contract: ' + status)
        return 'declared', status
    return 'legacy', policy.get('invalid_input')


def consistency(cases):
    """Prove contradictions only within one invocation and one output channel.

    The runner's text is stdout, or output_file (unless capture_stdout). Never
    compare a file predicate to stdout merely because they belong to one case.
    This checks satisfiability, not whether either expectation is source-correct.
    """
    from .runner import subset
    conflicts = []
    for case in cases:
        if case.get('relation'):
            continue
        assertion = case.get('acceptance', {}).get('assertion', {})
        same_channel = not case.get('output_file') or case.get('capture_stdout')
        if 'stdout_equals' not in case or not same_channel:
            continue
        text = case['stdout_equals']
        kind = assertion.get('kind')
        reason = None
        try:
            if kind in {'json', 'jsonl'}:
                value = (json.loads(text.splitlines()[assertion['record_index']])
                         if kind == 'jsonl' else json.loads(text))
                for key in assertion['path']:
                    value = value[key]
                if not any(subset(expected, value) for expected in assertion['allowed_values']):
                    reason = 'Exact stdout field cannot satisfy typed allowed_values (no coercion or tolerance)'
            elif kind == 'stdout_equals' and text.strip() != assertion['value']:
                reason = 'Two exact assertions on stdout disagree'
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            reason = 'Exact stdout cannot satisfy the required JSON/JSONL path: ' + type(exc).__name__
        if reason:
            conflicts.append({'case': case['name'], 'channel': 'stdout', 'field': assertion.get('path'),
                              'assertions': ['stdout_equals', 'acceptance.assertion'], 'basis': reason})
    return conflicts


def _normalise_quotes(text):
    return ' '.join(text.split())


def quote_matches(text, quote):
    """How a citation matches the material: exact, whitespace-only, or not at all.

    The wording must be verbatim in every accepted mode. Line wrapping, indentation
    and other whitespace differences are tolerated because a model reproducing a
    passage cannot be expected to keep the author's formatting byte for byte; the
    match mode is recorded so a normalised citation stays visible in the evidence.
    """
    if not isinstance(quote, str) or not quote.strip():
        return None
    if quote in text:
        return 'exact'
    normalised = _normalise_quotes(quote)
    if normalised and normalised in _normalise_quotes(text):
        return 'normalized'
    return None


def grounding_problem(record, index, source):
    """Why a citation is not grounded, in the words a repair needs.

    A bare "not grounded" tells the planner nothing it can act on, so it repeats the same
    citation until the no-progress rule stops the round (run 44). The reason names the
    unread path or quotes the first line that does not occur in the material.
    """
    if not isinstance(record, dict):
        return 'the citation is not an object'
    path, quote = record.get('source_path'), record.get('source_quote')
    readable = index.get('read_files', index['files'])
    if not path:
        return 'source_path is missing'
    if not isinstance(path, str):
        return 'source_path must be a string'
    if path not in readable:
        listed = ', '.join(sorted(str(name) for name in readable)[:6]) or 'the read materials'
        return 'source_path ' + str(path) + ' is not read material; quote one of ' + listed
    target = (Path(source) / path).resolve()
    if not target.exists() and (path.startswith('entry/') or path == 'source-identities.json'):
        # Frozen deterministic materials live outside the delivery/source trees.
        target = (Path(source) / 'runtime/context' / path).resolve()
    if not target.is_relative_to(Path(source).resolve()) or not target.is_file():
        return 'source_path ' + str(path) + ' is not a readable file in the source tree'
    if not isinstance(quote, str) or not quote.strip():
        return 'source_quote is empty'
    if quote_matches(target.read_text(encoding='utf-8'), quote) is None:
        first = quote.strip().splitlines()[0][:100]
        return ('source_quote does not occur verbatim in ' + str(path)
                + ' (whitespace differences are tolerated, wording changes are not); '
                  'the quote starts: ' + json.dumps(first))
    return None


def grounded(record, index, source):
    return grounding_problem(record, index, source) is None


def input_check_problems(check, index, source, position=0):
    """Independent check defects can be reported together before another paid turn."""
    label = 'Input check ' + (check['id'] if isinstance(check.get('id'), str) and check['id']
                              else '#' + str(position))
    problems = []
    def problem(message):
        problems.append(label + ': ' + message)
    if not isinstance(check.get('id'), str) or not check['id']:
        problem('id must be a nonempty string')
    channel = check.get('channel')
    if not isinstance(channel, str) or channel not in {'args', 'input_files'}:
        problem('channel must be args or input_files')
    if channel == 'args' and (type(check.get('key')) is not int or check['key'] < 0):
        problem('Argument check key must be a nonnegative index')
    if channel == 'input_files' and not isinstance(check.get('key'), str):
        problem('File check key must be a path')
    if not isinstance(check.get('pattern'), str):
        problem('needs a pattern string')
    else:
        try:
            re.compile(check['pattern'])
        except re.error as exc:
            problem('pattern is not a valid regular expression: ' + str(exc))
    mode = check.get('mode', 'full_text')
    if not isinstance(mode, str) or mode not in {'full_text', 'each_line'}:
        problem('Input check mode must be full_text or each_line')
    if mode == 'each_line' and channel != 'input_files':
        problem('each_line applies only to fixture contents')
    citation = grounding_problem(check, index, source)
    if citation:
        problem(citation)
    return problems


def contracts(plan, cases, index, source, *, check_consistency=True):
    """Missing contracts are incomplete, malformed/invented contracts are rejected."""
    policy = json.loads(plan.get('acceptance_json', '{}'))
    if not isinstance(policy, dict):
        raise ValueError('acceptance_json must be an object')
    if policy:
        # Model output is data: a nested object where a string belongs must be a clean
        # rejection, never a TypeError from a set membership test (run 34).
        purposes = policy.get('purposes')
        if (not isinstance(purposes, list) or not purposes
                or any(not isinstance(item, str) or item not in {'computation', 'operation', 'report'}
                       for item in purposes)):
            raise ValueError('Acceptance scope must declare its required purposes as strings')
        mode, aggregate = _classification(policy, index, source)
        if not isinstance(policy.get('scope'), str) or not policy['scope'].strip():
            raise ValueError('Acceptance scope must state which input forms are promised')
        invalid = policy.get('invalid_input')
        if mode == 'legacy' and (not isinstance(invalid, str)
                                 or invalid not in {'required', 'none_documented', 'not_applicable'}
                                 or not grounded(policy, index, source)):
            raise ValueError('Input policy requires scope and an exact quotation from read source')
        if aggregate == 'required' and not grounded(policy, index, source) and not (
                isinstance(policy.get('input_contract'), dict) and grounded(policy['input_contract'], index, source)):
            # A required classification still needs a citable basis: the delivered
            # interface or the source that states the rule.
            raise ValueError('Required input classification needs an exact quotation from read source or the delivered entry')
        if mode != 'legacy' and aggregate != 'required' and policy.get('checks'):
            raise ValueError('Input checks describe a constraint, so at least one operation must be required')
        if mode != 'legacy' and aggregate == 'required' and not policy.get('checks') and not policy.get('operations'):
            # Say it where the plan is rejected, and name both ways out (run 28 spent
            # six patch attempts on a diagnostic that did not say how to fix it).
            raise ValueError('invalid_input=required needs at least one named check with a matching '
                             'rejection case; if no checkable predicate can be expressed and nothing '
                             'promised rejection, declare input_contract status=none_documented with '
                             'its recorded evidence (or not_applicable for an operation without input)')
        raw_checks = policy.get('checks', [])
        if not isinstance(raw_checks, list) or any(not isinstance(item, dict) for item in raw_checks):
            raise ValueError('Input checks must be objects')
        problems = [p for number, check in enumerate(raw_checks)
                    for p in input_check_problems(check, index, source, number)]
        if problems:
            extra = ('\nAdditional check problems: ' + str(len(problems) - 20)) if len(problems) > 20 else ''
            raise ValueError('Input checks require grounded id/channel/key/pattern:\n'
                             + '\n'.join(problems[:20]) + extra
                             + '\nChecks are validity predicates: match declared VALID inputs; '
                               'a rejection must fail its named predicate. Copy one contiguous '
                               'source quotation; do not join excerpts with ellipses.')
        checks = {check['id']: check for check in policy.get('checks', [])}
        if len(checks) != len(policy.get('checks', [])):
            raise ValueError('Input check IDs must be unique')
        operations = policy.get('operations', [])
        if not isinstance(operations, list) or any(not isinstance(item, dict) for item in operations):
            raise ValueError('Acceptance operations must be objects')
        used, names = set(), set()
        for operation in operations:
            if not operation.get('id') or operation['id'] in names:
                raise ValueError('Operations require unique IDs and read source evidence')
            operation_problem = grounding_problem(operation, index, source)
            if operation_problem:
                raise ValueError('Operation ' + str(operation.get('id')) + ' needs read source evidence: '
                                 + operation_problem)
            names.add(operation['id'])
            selectors = operation.get('selector', {}).get('args')
            if not isinstance(selectors, list) or not selectors:
                raise ValueError('Operation applicability needs actual argument index/equals selectors')
            for item in selectors:
                if not isinstance(item, dict) or type(item.get('index')) is not int or item['index'] < 0:
                    raise ValueError('Operation selector needs a non-negative integer argument index')
                if set(item) == {'index'}:
                    # A positional invocation carries no literal token, so presence is the only
                    # honest predicate. It cannot tell forms apart, so it requires one operation.
                    if len(operations) != 1:
                        raise ValueError('A presence-only selector matches any value at that index, so it is '
                                         'valid only when the policy declares exactly one operation; add the '
                                         'literal index/equals token that distinguishes the other forms')
                    continue
                if (set(item) != {'index', 'equals'} or not isinstance(item['equals'], str) or not item['equals']
                        or item['equals'] not in operation['source_quote']):
                    raise ValueError('Operation selector must match a literal documented invocation token')
            selected = operation.get('checks')
            if isinstance(selected, list) and any(not isinstance(item, str) for item in selected):
                raise ValueError('Operation checks must be check ids (strings)')
            contract = operation.get('input_contract')
            if contract is not None and not isinstance(contract, dict):
                raise ValueError('input_contract must be an object')
            state = (contract or {}).get('status')
            if state is not None and state != 'required' and selected:
                raise ValueError('Operation checks describe a constraint, so that operation must be required')
            if state in ('not_applicable', 'none_documented'):
                # No rejection contract is claimed for this operation, so it names no
                # check. A declared absence is reported as a validation gap instead.
                if selected is None:
                    selected = operation['checks'] = []
                if not isinstance(selected, list) or not set(selected) <= checks.keys():
                    raise ValueError('Operation checks must name declared input checks')
                if selected:
                    raise ValueError('A ' + state + ' operation declares no check; remove its checks or '
                                     'declare the operation required')
            elif state == 'required':
                if not isinstance(selected, list) or not selected or not set(selected) <= checks.keys():
                    missing = ([item for item in selected if item not in checks]
                               if isinstance(selected, list) else [])
                    raise ValueError('Operation ' + str(operation.get('id')) + ' is required but its '
                                     'checks do not reference declared policy checks; missing IDs: '
                                     + (', '.join(missing) or '<no unresolved IDs; selection may be empty>')
                                     + '; selected=' + json.dumps(selected) + '; declared IDs='
                                     + json.dumps(sorted(checks)) + '. Define check objects in the TOP-LEVEL '
                                     'acceptance_json.checks array, not inside input_contract. Keep '
                                     'operations[].checks as a list of string IDs, for example ["nonempty"], '
                                     'and add matching rejection cases. Do not replace these IDs with objects.')
            elif not isinstance(selected, list) or not selected or not set(selected) <= checks.keys():
                raise ValueError('Each input operation must apply named input checks; no per-case exemptions')
            if (not isinstance(operation.get('purposes'), list) or not operation['purposes']
                    or any(not isinstance(item, str) for item in operation['purposes'])
                    or not set(operation['purposes']) <= set(policy['purposes'])):
                raise ValueError('Operation ' + str(operation.get('id'))
                                 + ' business purposes must belong to declared scope; operation='
                                 + json.dumps(operation.get('purposes')) + ', scope='
                                 + json.dumps(policy['purposes']))
            if type(operation.get('require_persistence', False)) is not bool:
                raise ValueError('require_persistence must be boolean')
            used.update(selected)
        if operations and used != checks.keys():
            raise ValueError('Every input check must be associated with an operation')
        if operations:
            for check in checks.values():
                if check['channel'] == 'input_files' and (type(check.get('argument_index')) is not int or check['argument_index'] < 0):
                    raise ValueError('File checks must bind fixture content to its /input/path argument_index')
    case_errors = []
    for case in cases:
        try:
            _case_contract(case, policy, index, source, plan.get('entrypoint'))
        except ValueError as exc:
            case_errors.append('Case ' + str(case.get('name')) + ': ' + str(exc))
    if case_errors:
        remaining = len(case_errors) - 20
        raise ValueError('Case acceptance errors: ' + '; '.join(case_errors[:20])
                         + (f'; {remaining} further case errors omitted' if remaining > 0 else ''))
    conflicts = consistency(cases) if check_consistency else []
    if conflicts:
        raise ContractConflict(conflicts)
    return policy


def _case_contract(case, policy, index, source, entrypoint=None):
    """Validate one case without allowing another case's failure to hide its errors."""
    contract = case.get('acceptance')
    if contract is None:
        return
    label = ' [' + str(case.get('name')) + ']'
    problem = grounding_problem(contract, index, source)
    if problem:
        hint = ('; this case is an environment probe, and a probe must not carry a business '
                'acceptance contract at all, so remove acceptance from it'
                if case.get('layer') == 'environment' or case.get('relation') else '')
        raise ValueError('Case acceptance requires a verbatim quotation from read source'
                         + label + ': ' + problem + hint)
    if (not isinstance(contract.get('purpose'), str)
            or contract['purpose'] not in {'computation', 'operation', 'report', 'input_rejection'}):
        raise ValueError('Unknown acceptance purpose' + label + ': ' + repr(contract.get('purpose')))
    assertion = contract.get('assertion')
    assertion_problem = grounding_problem(assertion, index, source)
    if assertion_problem:
        raise ValueError('Result assertion must have source evidence' + label + ': ' + assertion_problem)
    required_role = {'computation': 'completion', 'operation': 'result', 'report': 'report', 'input_rejection': 'rejection'}[contract['purpose']]
    if assertion.get('role') != required_role:
        raise ValueError('Outcome assertion role must match the promised purpose: ' + required_role + label)
    kind = assertion.get('kind')
    if isinstance(kind, str) and kind in {'json', 'jsonl'}:
        if kind == 'jsonl' and (type(assertion.get('record_index')) is not int or assertion['record_index'] < 0):
            raise ValueError('JSONL outcome requires a nonnegative record_index')
        if not isinstance(assertion.get('path'), list) or not assertion['path'] or not all(isinstance(p, (str, int)) for p in assertion['path']):
            raise ValueError('JSON outcome assertion requires a nonempty field path')
        values = assertion.get('allowed_values')
        if not isinstance(values, list) or not values or any(isinstance(v, (dict, list)) for v in values):
            raise ValueError('JSON outcome assertion requires scalar allowed_values')
    elif isinstance(kind, str) and kind in {'stdout_equals', 'stderr_contains'}:
        if not isinstance(assertion.get('value'), str) or not assertion['value'].strip():
            raise ValueError('Outcome text must be nonempty' + label
                             + '; for tool-written output_file, assert its actual JSON/JSONL '
                             'content with kind=json/jsonl, not empty stdout')
    else:
        raise ValueError('Outcome assertion must be json/jsonl or asserted text; exit code alone is insufficient')
    if case.get('relation'):
        raise ValueError('Acceptance outcome requires a direct invocation, not a relation' + label)
    if entrypoint and case.get('layer') != 'environment':
        from .coverage import business_args
        if business_args({'entrypoint': entrypoint}, case) is None:
            raise ValueError('Acceptance invocation must execute the configured business entrypoint'
                             + label + ': received entrypoint=' + repr(case.get('entrypoint'))
                             + ', args=' + repr(case.get('args')) + '; expected '
                             + repr(entrypoint) + '. Use the default entrypoint with business args '
                             'only, or its exact interpreter/script prefix. Do not use sh -c/cat '
                             'wrappers: the runner reads and asserts output_file after container exit.')
    if contract['purpose'] == 'input_rejection' and (not contract.get('violates') or not contract.get('invalid_input_reason')):
        raise ValueError('Rejection requires an identified constraint and explanation of the actual invalid input' + label)
    # Policy is part of each locked case, so repair cannot change applicability.
    case['acceptance_policy'] = policy
