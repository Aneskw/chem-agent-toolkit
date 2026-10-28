"""Prove the acceptance path sends prompts built by the current code and record them.

Three claims are checked offline, with no model request:

1. Production never reads the small frozen fixture. Only the ``validation`` scripts
   do, so a stale frozen copy cannot become what the acceptance batch sends.
2. The prompt and the answer schema come from the live module objects: the policy for
   a round, the schema for a round, and the acceptance description inside it.
3. The bytes that would be sent are identified now, and a real batch records the same
   identity per planning round (``prompt-provenance-<n>.json`` next to the prompt).

Modes: ``freeze`` writes ``prompt-provenance.json``; ``check`` regenerates it and
fails on any drift.
"""
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TARGET = HERE / 'prompt-provenance.json'
FROZEN = HERE / 'frozen'
ORIGINAL = HERE / 'original-case'
sys.path.insert(0, str(ROOT))

from creation_pipeline.runtime import planner  # noqa: E402

KINDS = ('none', 'rejected_candidate', 'accepted_plan')
# The production tree must not depend on any frozen prompt/schema copy.
FROZEN_REFERENCE = re.compile(r'validation[/\\]deepseek-api|frozen[/\\](?:prompt|schema|manifest)')


def sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def fixture_material():
    """A deterministic, obviously synthetic round payload."""
    return {'index': {'files': {'package/tool.py': {'size': 1}}},
            'materials': {'package/tool.py': 'print("ok")\n'},
            'not_read_count': 0, 'omissions': {}, 'omission_counts': {},
            'read_budget': {'used_chars': 11, 'max_chars': None},
            'entry_hint': 'package/tool.py', 'user_constraints': [],
            'execution_budget': {'test_seconds': 600, 'document_seconds': 60, 'total_seconds': 3600},
            'previous_plan': None, 'diagnostic': {}, 'read_rounds_remaining': None,
            'base_kind': 'none'}


def production_references():
    """Any production file that mentions the frozen copies (should be none)."""
    offenders = []
    for path in sorted((ROOT / 'creation_pipeline').rglob('*')):
        if path.suffix not in {'.py', '.md', '.json'} or not path.is_file():
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        for match in FROZEN_REFERENCE.finditer(text):
            offenders.append('%s: %s' % (path.relative_to(ROOT).as_posix(), match.group(0)))
    return offenders


def identity_problems():
    problems = []
    if planner.schema_for('none') is not planner.PLAN_SCHEMA:
        problems.append('full-plan rounds must send the live PLAN_SCHEMA object')
    for kind in ('rejected_candidate', 'accepted_plan'):
        if planner.schema_for(kind) is not planner.PATCH_SCHEMA:
            problems.append(kind + ' rounds must send the live PATCH_SCHEMA object')
    if planner.policy_for('none') != planner.POLICY:
        problems.append('full-plan rounds must send the live POLICY text')
    for kind in ('rejected_candidate', 'accepted_plan'):
        policy = planner.policy_for(kind)
        if not policy.startswith(planner.POLICY) or 'PATCH PROTOCOL' not in policy:
            problems.append(kind + ' rounds must append the patch protocol to the live policy')
    node = planner.PLAN_SCHEMA['properties']['plan']['properties']['acceptance_json']
    if node.get('description') != planner.ACCEPTANCE_SPEC:
        problems.append('the acceptance_json description must be the current ACCEPTANCE_SPEC')
    if planner.PATCH_SCHEMA.get('description') != planner.ACCEPTANCE_SPEC:
        problems.append('the patch schema description must be the current ACCEPTANCE_SPEC')
    if planner.INPUT_CONTRACT_SPEC not in planner.ACCEPTANCE_SPEC:
        problems.append('the acceptance description must carry the shared contract block')
    if planner.INPUT_CONTRACT_SPEC not in planner.POLICY:
        problems.append('the policy body must carry the shared contract block')
    return problems


def round_prompts():
    """The exact prompt/schema identity for each round kind, from production code."""
    material = fixture_material()
    return {kind: planner.provenance(material, kind) for kind in KINDS}


def saved_case_prompt():
    """Run the real planner up to (not into) the first model call on the saved case.

    The guard aborts immediately before the request, so the written prompt and its
    provenance are the production bytes for that material, with no request sent.
    """
    handoff = ORIGINAL / 'handoff'
    if not handoff.is_dir():
        return {'status': 'not_available'}
    binding = json.loads((ORIGINAL / 'binding.json').read_text(encoding='utf-8'))
    request = json.loads((ORIGINAL / 'original-request.json').read_text(encoding='utf-8'))
    prompt_file = ORIGINAL / 'prompt-0.txt'
    if not prompt_file.is_file():
        return {'status': 'prompt_missing'}

    class Stop(Exception):
        pass

    def guard():
        raise Stop()

    with tempfile.TemporaryDirectory(prefix='provenance-') as directory:
        audit = Path(directory) / 'audit'
        options = planner.options({'model': request.get('model'),
                                   'model_timeout': 600, 'total_seconds': None,
                                   'progress_watch': 'terminate', 'transport': 'default',
                                   'context_chars': None, 'max_read_rounds': 1})
        config = {'script': binding.get('runtime_entry') or binding.get('entry'), 'constraints': []}
        try:
            planner.plan(handoff, config, audit, options, None, call_guard=guard)
        except Exception as exc:  # Stop, or a budget/planning stop before any request
            if not (audit / 'prompt-provenance-0.json').is_file():
                return {'status': 'no_prompt', 'detail': type(exc).__name__ + ': ' + str(exc)[:200]}
        sent = json.loads((audit / 'prompt-provenance-0.json').read_text(encoding='utf-8'))
        written = (audit / 'prompt-0.txt').read_text(encoding='utf-8')
        return {'status': 'built', 'provenance': sent,
                'written_prompt_matches_provenance': sha256(written) == sent['prompt_sha256']}


def build():
    return {
        'generated_by': 'validation/deepseek-api/verify_acceptance_prompt.py freeze',
        'note': ('These are the prompt/schema identities the current code produces. The '
                 'formal acceptance batch builds the same bytes at call time and records '
                 'them per planning round as <audit>/prompt-provenance-<n>.json; the small '
                 'frozen fixture under frozen/ is a separate offline diagnostic and is '
                 'never read by production.'),
        'code': {
            'policy_sha256': sha256(planner.POLICY),
            'policy_bytes': len(planner.POLICY.encode('utf-8')),
            'acceptance_spec_sha256': sha256(planner.ACCEPTANCE_SPEC),
            'acceptance_spec_bytes': len(planner.ACCEPTANCE_SPEC.encode('utf-8')),
            'input_contract_spec_sha256': sha256(planner.INPUT_CONTRACT_SPEC),
            'plan_schema_sha256': sha256(planner.canonical_schema(planner.PLAN_SCHEMA)),
            'patch_schema_sha256': sha256(planner.canonical_schema(planner.PATCH_SCHEMA)),
        },
        'rounds': round_prompts(),
        'saved_case': saved_case_prompt(),
        'frozen_fixture': frozen_identity(),
    }


def frozen_identity():
    """The small fixture's identity, recorded only to show it is a different path."""
    manifest = FROZEN / 'manifest.json'
    if not manifest.is_file():
        return {'status': 'not_frozen'}
    data = json.loads(manifest.read_text(encoding='utf-8'))
    return {'status': 'frozen', 'prompt_sha256': data.get('prompt_sha256'),
            'prompt_bytes': data.get('prompt_bytes'), 'schema_sha256': data.get('schema_sha256'),
            'used_by': 'validation/deepseek-api/verify_planner.py only'}


def check(verbose=True):
    problems = []
    offenders = production_references()
    if offenders:
        problems.append('production references a frozen copy: ' + '; '.join(offenders[:5]))
    problems.extend(identity_problems())
    current = build()
    if TARGET.is_file():
        recorded = json.loads(TARGET.read_text(encoding='utf-8'))
        if recorded != current:
            for key in sorted(set(recorded) | set(current)):
                if recorded.get(key) != current.get(key):
                    problems.append('drifted: ' + key)
    else:
        problems.append('prompt-provenance.json is missing; run freeze')
    if verbose:
        print('production references to frozen copies:', len(offenders))
        print('round identities:')
        for kind, sent in current['rounds'].items():
            print('  %-18s prompt=%d B %s  schema=%d B %s'
                  % (kind, sent['prompt_bytes'], sent['prompt_sha256'][:16],
                     sent['schema_bytes'], sent['schema_sha256'][:16]))
        saved = current['saved_case']
        print('saved RECAP case round 0:', saved.get('status'),
              (saved.get('provenance') or {}).get('prompt_sha256', '')[:16])
        print('frozen fixture (not the acceptance path):', current['frozen_fixture'].get('status'),
              str(current['frozen_fixture'].get('prompt_sha256'))[:16])
    return problems


def main(argv):
    if len(argv) != 2 or argv[1] not in ('freeze', 'check'):
        print('usage: verify_acceptance_prompt.py freeze|check')
        return 2
    if argv[1] == 'freeze':
        current = build()
        TARGET.write_text(json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
                          encoding='utf-8')
        print('recorded', TARGET.relative_to(ROOT).as_posix())
        print('full-plan prompt: %d B sha256=%s' % (current['rounds']['none']['prompt_bytes'],
                                                    current['rounds']['none']['prompt_sha256']))
        print('full-plan schema: %d B sha256=%s' % (current['rounds']['none']['schema_bytes'],
                                                    current['rounds']['none']['schema_sha256']))
        return 0
    problems = check()
    if problems:
        for problem in problems:
            print('PROBLEM:', problem)
        return 1
    print('\nthe acceptance path sends prompts and schemas built by the current code, and '
          'their identity is recorded')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
