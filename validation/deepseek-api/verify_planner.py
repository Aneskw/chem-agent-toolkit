#!/usr/bin/env python3
"""One bounded, reproducible DeepSeek planner check.

This script exercises exactly one stage - the structured planner call - against a
fixed prompt and the unchanged plan validators. It does not run discovery,
authoring, independent review, Docker or business acceptance, and it never
continues after a failure.

Modes
  freeze  Build the production planner prompt for the fixed fixture and store it
          under ``frozen/``. No model request is made.
  check   Rebuild the prompt offline and prove it still matches the frozen copy.
          No model request is made.
  run     Re-verify the frozen prompt, then make AT MOST ONE DeepSeek request
          (hard cap 600 s, no retries, no continuation) and report the outcome.

The planner prompt is produced by ``creation_pipeline.runtime.planner.plan``
itself, so what is frozen is what production sends - not a hand-written copy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from creation_pipeline.records import redact, write_json          # noqa: E402
from creation_pipeline.runtime import model_call, planner, preparation  # noqa: E402

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'fixture-source'
FROZEN = HERE / 'frozen'
RUNS = HERE / 'runs'
RESULT = HERE / 'result.json'

BINDING = {'kind': 'script', 'entry': 'tool.py', 'runtime_entry': 'package/tool.py'}
SCRIPT = 'package/tool.py'
CONSTRAINTS = [
    'Invoke the unchanged delivered package entry, not only the upstream tool.',
    'The delivered tool has no third-party dependency; keep the image minimal.',
]
# ``model`` is the native Agent identity (unused here); ``api_model`` is the API
# provider's model. Both are left None on purpose: the DeepSeek model name comes from
# the operator's local configuration (DEEPSEEK_MODEL / .env) and is never guessed.
OPTIONS = {
    'model': None,
    'api_model': None,
    'backend': 'deepseek_api',
    'model_timeout': 600,
    'total_seconds': 600,
    'api_retries': 0,
    'api_max_output_tokens': 65536,
    'api_stream': True,
    'reasoning_effort': 'medium',
    'progress_watch': 'observe',
    'max_read_rounds': 1,
}
HARD_CAP_SECONDS = 600


class _Captured(Exception):
    """Raised by the offline stub once the planner has produced its prompt."""


OUTPUT_CODES = {'model_output_invalid', 'model_schema_mismatch', 'model_output_empty',
                'model_output_truncated', 'model_output_incomplete', 'model_content_filtered'}


def failure_status(code):
    """Distinct verdicts, so a transport fault never reads like a rejected plan."""
    if code == 'model_config_invalid':
        return 'blocked_config_invalid'
    if code in OUTPUT_CODES:
        return 'blocked_model_output_invalid'
    return 'blocked_model_unavailable'


def fixture_digests():
    return {path.relative_to(SOURCE).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(SOURCE.rglob('*')) if path.is_file()}


def build_prompt(directory):
    """Return (prompt text as persisted, captured call arguments)."""
    captured = {}

    def stub(prompt, schema, model, **kwargs):
        captured.update(prompt=prompt, schema=schema, model=model, kwargs=kwargs)
        raise _Captured()

    original = model_call.call
    model_call.call = stub
    try:
        planner.plan(SOURCE, {'script': SCRIPT, 'constraints': CONSTRAINTS}, Path(directory),
                     planner.options(OPTIONS), time.monotonic() + 60)
    except _Captured:
        pass
    finally:
        model_call.call = original
    if 'schema' not in captured:
        raise RuntimeError('the planner did not reach its model call')
    text = (Path(directory) / 'prompt-0.txt').read_text(encoding='utf-8')
    captured['persisted_equals_sent'] = redact(captured['prompt']) == text
    return text, captured


def freeze():
    with tempfile.TemporaryDirectory(prefix='ds-freeze-') as tmp:
        text, captured = build_prompt(tmp)
    FROZEN.mkdir(parents=True, exist_ok=True)
    (FROZEN / 'prompt-0.txt').write_text(text, encoding='utf-8', newline='\n')
    (FROZEN / 'schema.json').write_text(
        json.dumps(captured['schema'], ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8', newline='\n')
    manifest = {
        'source_commit': '78003de47c8bee93c705cd3a2098ee1f90646aae',
        'generated_by': 'validation/deepseek-api/verify_planner.py freeze',
        'planner_policy_sha256': hashlib.sha256(planner.POLICY.encode('utf-8')).hexdigest(),
        'prompt_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'prompt_bytes': len(text.encode('utf-8')),
        'persisted_prompt_equals_sent_prompt': captured['persisted_equals_sent'],
        'schema_sha256': hashlib.sha256(
            json.dumps(captured['schema'], ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest(),
        'fixture_files': fixture_digests(),
        'binding': BINDING,
        'script': SCRIPT,
        'constraints': CONSTRAINTS,
        'options': OPTIONS,
    }
    write_json(FROZEN / 'manifest.json', manifest)
    print('frozen prompt: %d bytes sha256=%s' % (manifest['prompt_bytes'], manifest['prompt_sha256']))
    print('frozen schema sha256=%s' % manifest['schema_sha256'])
    return manifest


def check(verbose=True):
    """Prove the frozen prompt/schema still reproduce exactly. No request is made."""
    expected_prompt = (FROZEN / 'prompt-0.txt').read_text(encoding='utf-8')
    expected_schema = json.loads((FROZEN / 'schema.json').read_text(encoding='utf-8'))
    manifest = json.loads((FROZEN / 'manifest.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='ds-check-') as tmp:
        actual_prompt, captured = build_prompt(tmp)
    same_prompt = actual_prompt == expected_prompt
    same_schema = (json.dumps(captured['schema'], ensure_ascii=False, sort_keys=True)
                   == json.dumps(expected_schema, ensure_ascii=False, sort_keys=True))
    same_fixture = fixture_digests() == manifest['fixture_files']
    clean_prompt = captured['persisted_equals_sent']
    if verbose:
        print('prompt identical:', same_prompt)
        print('schema identical:', same_schema)
        print('fixture identical:', same_fixture)
        print('frozen file equals the sent prompt (no redaction applied):', clean_prompt)
    return {'prompt_identical': same_prompt, 'schema_identical': same_schema,
            'fixture_identical': same_fixture,
            'persisted_equals_sent': clean_prompt,
            'prompt_sha256': hashlib.sha256(actual_prompt.encode('utf-8')).hexdigest(),
            'schema_sha256': hashlib.sha256(
                json.dumps(captured['schema'], ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()}


def _ledger(audit):
    attempts = sorted(Path(audit).glob('model-*/attempts.json'))
    entries = []
    for path in attempts:
        payload = json.loads(path.read_text(encoding='utf-8'))
        entries.append({'path': str(path.relative_to(HERE)), 'request_count': payload.get('request_count'),
                        'attempts': [{k: a.get(k) for k in ('attempt', 'status', 'http_status',
                                                            'error_class', 'request_id')}
                                     for a in payload.get('attempts', [])]})
    return {'request_count': sum(e['request_count'] or 0 for e in entries), 'ledgers': entries}


def run(timeout):
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    if timeout > HARD_CAP_SECONDS:
        raise SystemExit('the hard cap for one verification request is %d s' % HARD_CAP_SECONDS)
    outcome = {'mode': 'run', 'started_at': stamp, 'timeout_seconds': timeout,
               'single_request': True, 'retries': 0, 'continuation': False,
               'backend': 'deepseek_api', 'model_from_configuration_only': True}
    try:
        outcome['frozen'] = check(verbose=False)
    except Exception as exc:                             # noqa: BLE001 - reported, not hidden
        outcome.update(status='blocked_frozen_prompt_unavailable',
                       reason=redact('%s: %s' % (type(exc).__name__, exc)), request_count=0)
        write_json(RESULT, outcome)
        print(json.dumps(outcome, ensure_ascii=False, indent=2))
        return 2
    if not all(outcome['frozen'][key] for key in
               ('prompt_identical', 'schema_identical', 'fixture_identical',
                'persisted_equals_sent')):
        outcome.update(status='blocked_frozen_prompt_drifted', request_count=0,
                       reason='the rebuilt prompt/schema no longer matches the frozen copy, '
                              'or the prompt contains redacted material; no request was sent')
        write_json(RESULT, outcome)
        print(json.dumps(outcome, ensure_ascii=False, indent=2))
        return 2

    audit = RUNS / stamp
    opts = planner.options(OPTIONS)
    calls = {'n': 0}

    def guard():
        calls['n'] += 1
        if calls['n'] > 1:
            raise planner.BudgetExceeded('this verification permits exactly one model request')

    deadline = time.monotonic() + min(timeout, HARD_CAP_SECONDS)
    started = time.monotonic()
    plan = index = None
    try:
        plan, index, reason = planner.plan(SOURCE, {'script': SCRIPT, 'constraints': CONSTRAINTS},
                                           audit, opts, deadline, call_guard=guard)
        cases = preparation.validate(plan, index, SOURCE, BINDING, opts, None)
        outcome.update(status='plan_accepted', reason=redact(reason), cases=len(cases),
                       plan_sha256=hashlib.sha256(
                           json.dumps(plan, sort_keys=True).encode('utf-8')).hexdigest())
    except planner.ModelUnavailable as exc:
        outcome.update(status=failure_status(getattr(exc, 'code', None)),
                       error_class=getattr(exc, 'code', None),
                       reason=redact(str(exc))[:600])
    except planner.BudgetExceeded as exc:
        outcome.update(status='stopped_budget', reason=redact(str(exc))[:600])
    except (planner.PlanningError, ValueError, OSError) as exc:
        outcome.update(status='stopped_invalid_or_incomplete',
                       error_class=getattr(exc, 'code', None),
                       reason=redact(str(exc))[:600])
    outcome['elapsed_seconds'] = round(time.monotonic() - started, 3)
    outcome['guard_invocations'] = calls['n']
    outcome['ledger'] = _ledger(audit) if Path(audit).exists() else {'request_count': 0, 'ledgers': []}
    outcome['request_count'] = outcome['ledger']['request_count']
    if outcome['request_count'] > 1:
        outcome['status'] = 'violation_more_than_one_request'

    # Credential and shape checks on everything this run wrote.
    leaks = []
    for path in Path(audit).rglob('*') if Path(audit).exists() else []:
        if path.is_file() and redact(path.read_text(encoding='utf-8', errors='replace')) != \
                path.read_text(encoding='utf-8', errors='replace'):
            leaks.append(str(path.relative_to(HERE)))
    outcome['redaction'] = {'files_with_redacted_shapes': leaks,
                            'api_key_recorded': False,
                            'note': 'authentication material is never written to disk'}
    if plan is not None:
        outcome['plan_summary'] = {key: plan.get(key) for key in
                                   ('base_image', 'platform', 'script', 'entrypoint')}
        outcome['tests'] = len(plan.get('tests', []))
    write_json(RESULT, outcome)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome['status'] == 'plan_accepted' else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('freeze', 'check', 'run'))
    parser.add_argument('--timeout', type=float, default=HARD_CAP_SECONDS,
                        help='total deadline for the single request (max %d s)' % HARD_CAP_SECONDS)
    arguments = parser.parse_args(argv)
    if arguments.mode == 'freeze':
        freeze()
        return 0
    if arguments.mode == 'check':
        return 0 if all(check().values()) else 1
    return run(arguments.timeout)


if __name__ == '__main__':
    raise SystemExit(main())
