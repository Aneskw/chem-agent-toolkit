#!/usr/bin/env python3
"""Replay the saved original RECAP planner request against the DeepSeek backend.

The small fixture in ``verify_planner.py`` proves that the adapter connects and that
the structured contract holds; it is a ~8.6 KB synthetic request and says nothing
about the original slow case. This script uses the *saved* request instead:

* ``prompt-0.txt``   - the historical ~44 KB RDKit RECAP planning prompt
* ``schema.json``    - the schema the CLI enforced for that request (PLAN_SCHEMA)
* ``handoff/``       - the exact material tree the prompt was built from
* ``inventory.json`` - the index recorded for that request
* ``binding.json``   - the explicit markdown-python binding of that delivery
* ``locked-tests.json`` - the locked acceptance cases of that preparation

Fingerprints are checked against the original request record before anything is
sent, so the replay is the real request and not a lookalike.

Modes
  check  Verify the saved fingerprints and rebuild the inventory offline. No request.
  run    Re-verify, then make AT MOST ONE DeepSeek request (hard cap 600 s, no
         retries, no continuation) and apply the unchanged plan validators.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from creation_pipeline.records import redact, write_json            # noqa: E402
from creation_pipeline.runtime import model_call, planner, preparation  # noqa: E402
from creation_pipeline.runtime import entry as entry_module         # noqa: E402

HERE = Path(__file__).resolve().parent
CASE = HERE / 'original-case'
HANDOFF = CASE / 'handoff'
RUNS = HERE / 'runs'
RESULT = HERE / 'result-original-case.json'
HARD_CAP_SECONDS = 600

# Provider settings: the stage-1 validated DeepSeek configuration. The model name is
# never guessed - it comes from DEEPSEEK_MODEL / .env.
API_OPTIONS = {'api_model': None, 'api_retries': 0, 'api_stream': True,
               'api_max_output_tokens': 65536, 'reasoning_effort': 'medium'}
OPTS = {'model': None, 'api_model': None, 'backend': 'deepseek_api', 'api_retries': 0,
        'api_stream': True, 'api_max_output_tokens': 65536, 'model_timeout': 600,
        'total_seconds': 600, 'reasoning_effort': 'medium', 'max_read_rounds': 1}


def load(name):
    return json.loads((CASE / name).read_text(encoding='utf-8'))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def check(verbose=True):
    """Prove the saved prompt, schema, tree and binding are the historical ones."""
    prompt = (CASE / 'prompt-0.txt').read_text(encoding='utf-8')
    schema_bytes = (CASE / 'schema.json').read_bytes()
    original = load('original-request.json')
    saved_inventory = load('inventory.json')
    binding = load('binding.json')

    prompt_ok = sha256(prompt.encode('utf-8')) == original['prompt_sha256']
    schema_ok = sha256(schema_bytes) == original['schema_sha256']

    index = planner.inventory(HANDOFF, planner.options(OPTS))
    inventory_ok = index == saved_inventory

    actual_binding, code = entry_module.markdown_entry(HANDOFF / 'package')
    binding_ok = (actual_binding['extraction'] == binding['extraction']
                  and sha256(code) == binding['extraction']['code_sha256']
                  and actual_binding['runtime_entry'] == binding['runtime_entry'])

    # Offline rehearsal of the gate the replay will apply: the plan that this case
    # actually accepted must still pass the unchanged validators. If it does not, the
    # replay verdict would not be comparable to the historical one.
    opts = planner.options(OPTS)
    locked = load('locked-tests.json').get('cases', [])
    try:
        cases = preparation.validate(load('accepted-plan.json'), index, HANDOFF, binding,
                                     opts, locked)
        gate_ok, gate_detail = True, {'accepted_cases': len(cases)}
    except Exception as exc:                              # noqa: BLE001 - reported, not hidden
        gate_ok, gate_detail = False, {'error': '%s: %s' % (type(exc).__name__, exc)}

    result = {'prompt_matches_original_request': prompt_ok,
              'schema_matches_original_request': schema_ok,
              'inventory_rebuilt_from_handoff': inventory_ok,
              'binding_matches_delivered_package': binding_ok,
              'historical_plan_passes_unchanged_gates': gate_ok,
              'gate_detail': gate_detail,
              'prompt_bytes': len(prompt.encode('utf-8')),
              'prompt_sha256': sha256(prompt.encode('utf-8')),
              'schema_sha256': sha256(schema_bytes),
              'prompt_chars': len(prompt),
              'handoff_files': len(index['files'])}
    if verbose:
        for key, value in result.items():
            print('%s: %s' % (key, value))
    return result, index


def _ledger(audit):
    entries = []
    for path in sorted(Path(audit).glob('model-*/attempts.json')):
        payload = json.loads(path.read_text(encoding='utf-8'))
        entries.append({'path': str(path.relative_to(HERE)),
                        'request_count': payload.get('request_count'),
                        'attempts': [{k: a.get(k) for k in ('attempt', 'status', 'http_status',
                                                            'error_class', 'request_id')}
                                     for a in payload.get('attempts', [])]})
    return {'request_count': sum(e['request_count'] or 0 for e in entries), 'ledgers': entries}


OUTPUT_CODES = {'model_output_invalid', 'model_schema_mismatch', 'model_output_empty',
                'model_output_truncated', 'model_output_incomplete', 'model_content_filtered'}


def failure_status(code):
    """Distinct verdicts, so a transport fault never reads like a rejected plan."""
    if code == 'model_config_invalid':
        return 'blocked_config_invalid'
    if code in OUTPUT_CODES:
        return 'blocked_model_output_invalid'
    return 'blocked_model_unavailable'


def run(timeout):
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    if timeout > HARD_CAP_SECONDS:
        raise SystemExit('the hard cap for one verification request is %d s' % HARD_CAP_SECONDS)
    outcome = {'mode': 'run', 'case': 'saved-original-recap-planner-request',
               'started_at': stamp, 'timeout_seconds': timeout, 'single_request': True,
               'retries': 0, 'continuation': False, 'backend': 'deepseek_api'}
    try:
        checked, index = check(verbose=False)
    except Exception as exc:                              # noqa: BLE001 - reported, not hidden
        outcome.update(status='blocked_case_unavailable',
                       reason=redact('%s: %s' % (type(exc).__name__, exc)), request_count=0)
        write_json(RESULT, outcome)
        print(json.dumps(outcome, ensure_ascii=False, indent=2))
        return 2
    outcome['case_integrity'] = checked
    if not all(checked[key] for key in ('prompt_matches_original_request',
                                        'schema_matches_original_request',
                                        'inventory_rebuilt_from_handoff',
                                        'binding_matches_delivered_package',
                                        'historical_plan_passes_unchanged_gates')):
        outcome.update(status='blocked_case_drifted', request_count=0,
                       reason='the saved case no longer matches its recorded fingerprints; '
                              'no request was sent')
        write_json(RESULT, outcome)
        print(json.dumps(outcome, ensure_ascii=False, indent=2))
        return 2

    prompt = (CASE / 'prompt-0.txt').read_text(encoding='utf-8')
    schema = json.loads((CASE / 'schema.json').read_text(encoding='utf-8'))
    binding = load('binding.json')
    locked = load('locked-tests.json').get('cases', [])
    opts = planner.options(OPTS)
    audit = RUNS / stamp
    calls = {'n': 0}

    def guard():
        calls['n'] += 1
        if calls['n'] > 1:
            raise planner.BudgetExceeded('this replay permits exactly one model request')

    deadline = time.monotonic() + min(timeout, HARD_CAP_SECONDS)
    started = time.monotonic()
    outcome['case_integrity'] = checked
    try:
        # The caller-side budget guard is exercised through the same planner option
        # wrapper production uses; here it also hard-caps the request count.
        guard()
        answer, receipt = model_call.call(
            prompt, schema, planner.backend_model(opts), timeout=min(opts['model_timeout'], timeout),
            audit_dir=audit / 'model-0', reasoning=opts['reasoning_effort'],
            tier=opts['service_tier'], backend=opts['backend'],
            api_options=planner.api_options(opts))
        outcome['answer_action'] = answer.get('action')
        write_json(audit / 'answer.json', answer)
        if answer.get('action') != 'plan' or not isinstance(answer.get('plan'), dict):
            outcome.update(status='no_plan_in_one_call',
                           reason='the single request returned %r instead of a plan; not continued'
                                  % (answer.get('action'),))
        else:
            plan = answer['plan']
            cases = preparation.validate(plan, index, HANDOFF, binding, opts, locked)
            outcome.update(status='plan_accepted', cases=len(cases),
                           plan_sha256=sha256(json.dumps(plan, sort_keys=True).encode('utf-8')),
                           plan_summary={key: plan.get(key) for key in
                                         ('base_image', 'platform', 'script', 'entrypoint')})
            write_json(audit / 'plan.json', plan)
    except model_call.ModelConfigError as exc:
        outcome.update(status=failure_status(exc.code), error_class=exc.code,
                       reason=redact(str(exc))[:600])
    except model_call.ModelOutputInvalid as exc:
        outcome.update(status=failure_status(exc.code), error_class=exc.code,
                       reason=redact(str(exc))[:600])
    except model_call.ModelExecutionError as exc:
        outcome.update(status=failure_status(exc.code), error_class=exc.code,
                       reason=redact(str(exc))[:600])
    except planner.ModelUnavailable as exc:
        outcome.update(status=failure_status(getattr(exc, 'code', None)),
                       error_class=getattr(exc, 'code', None), reason=redact(str(exc))[:600])
    except planner.PlanningError as exc:
        outcome.update(status='plan_rejected', error_class=getattr(exc, 'code', None),
                       reason=redact(str(exc))[:600])
    except (ValueError, OSError) as exc:
        outcome.update(status='failed', error_class=getattr(exc, 'code', None),
                       reason=redact(str(exc))[:600])
    outcome['elapsed_seconds'] = round(time.monotonic() - started, 3)
    outcome['ledger'] = _ledger(audit) if Path(audit).exists() else {'request_count': 0, 'ledgers': []}
    outcome['request_count'] = outcome['ledger']['request_count']
    if outcome['request_count'] > 1:
        outcome['status'] = 'violation_more_than_one_request'
    leaks = []
    if Path(audit).exists():
        for path in Path(audit).rglob('*'):
            if path.is_file():
                text = path.read_text(encoding='utf-8', errors='replace')
                if redact(text) != text:
                    leaks.append(str(path.relative_to(HERE)))
    outcome['redaction'] = {'files_with_redacted_shapes': leaks, 'api_key_recorded': False}
    write_json(RESULT, outcome)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome['status'] == 'plan_accepted' else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('check', 'run'))
    parser.add_argument('--timeout', type=float, default=HARD_CAP_SECONDS)
    arguments = parser.parse_args(argv)
    if arguments.mode == 'check':
        checked, _ = check()
        return 0 if all(value for key, value in checked.items() if isinstance(value, bool)) else 1
    return run(arguments.timeout)


if __name__ == '__main__':
    raise SystemExit(main())
