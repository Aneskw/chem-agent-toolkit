"""Requirement-aware delivery. Archival, drafts and execution are distinct outcomes."""
from pathlib import Path
import copy
import time

from runtime_common import read, write, sha, digest
from candidate_identity import load, resolve, identity
from validate_skill_format import validate as format_check
import runtime_docker

VERSION = 1


def cli_mode(args, parser):
    if args.runtime_mode == 'off' and not args.draft_only:
        parser.error('--runtime-mode off now requires --draft-only; normal creation cannot skip required tools')
    if args.draft_only and args.success_policy == 'execution':
        parser.error('--draft-only conflicts with --success-policy execution')
    # creation is a deprecated spelling of the new delivery policy, not a bypass.
    args.success_policy = 'draft' if args.draft_only else ('execution' if args.success_policy == 'execution' else 'delivery')
    args.runtime_mode = 'off' if args.draft_only else 'auto'


def seal_content(root, candidate, bundle):
    root = Path(root)
    write(root/'delivery/source.json', {'candidate': candidate, 'bundle': bundle,
          'original_skill_sha256': sha(root/'SKILL.md')})


def content(root):
    from core.creation_schema import validate
    root = Path(root)
    data = read(root/'delivery/source.json')
    candidate, bundle = data['candidate'], data['bundle']
    actual = load(root)
    if actual != identity(candidate, bundle, bundle['paper_id']):
        raise ValueError('Candidate/source identity changed')
    checks = validate({'contract_version':'1.1', 'schema_version':3, 'paper_id':bundle['paper_id'],
                       'candidates':[candidate], 'no_skill_reason':''}, bundle)
    if format_check(root/'SKILL.md'):
        raise ValueError('Skill format check failed')
    original = root/'runtime/source-SKILL.md' if (root/'runtime/source-SKILL.md').exists() else root/'SKILL.md'
    if sha(original) != data['original_skill_sha256']:
        raise ValueError('Source-validated Skill content changed')
    # The portable snapshot is the content/source audit input; runtime source roots
    # and binding hashes are additionally checked by the existing Docker evidence gate.
    return candidate, bundle, checks[0]


def cited_reason(reason, bundle):
    if not isinstance(reason, dict) or not reason.get('text') or not reason.get('citations'):
        raise ValueError('No-tool decision requires a cited reason')
    sources = {s['id']:s for s in bundle['sources']}
    for c in reason['citations']:
        s = sources[c['source_id']]
        if not 1 <= c['start'] <= c['end'] <= len(s['lines']) or not c.get('quote') or c['quote'] not in '\n'.join(s['lines'][c['start']-1:c['end']]):
            raise ValueError('Requirement reason citation is invalid')


def determine(root, job_id, bindings=None):
    candidate, bundle, check = content(root)
    declared = candidate.get('tool_requirement', {})
    # A referenced document/data resource alone is not an executable-tool demand.
    # Missing declarations remain unknown; only an explicit execution contract or
    # caller-owned binding can decide a procedural candidate's tool requirement.
    required = candidate['kind'] == 'tool_usage' or declared.get('status') == 'required'
    if candidate['kind'] == 'tool_usage' and declared.get('status') == 'not_required':
        raise ValueError('Candidate tool_usage kind contradicts its no-tool declaration')
    rule = None
    association = None
    if bindings:
        settings = read(bindings)
        runtime_docker.require_model_runtime(settings)
        try:
            rule, association = resolve(settings, root, job_id)
        except ValueError as exc:
            if 'Tool association unresolved:' not in str(exc) or declared.get('status') != 'not_required':
                raise
    status = rule.get('requirement') if rule else declared.get('status', 'unknown')
    if rule and declared.get('status') in {'required', 'not_required'} and status != declared['status']:
        raise ValueError('Explicit binding contradicts the sourced candidate tool requirement')
    if required and status == 'not_required':
        raise ValueError('No-tool exemption contradicts candidate execution requirements')
    if required:
        status = 'required'
    result = {'requirement':status, 'association':association,
              'basis':rule if rule else declared, 'content_checks':check,
              'source_sha256':sha(Path(root)/'delivery/source.json'),
              'candidate_sha256':sha(Path(root)/'candidate.json'),
              'bindings_path':str(Path(bindings).resolve()) if bindings else None,
              'bindings_sha256':sha(bindings) if bindings else None, 'job_id':job_id}
    if status == 'not_required':
        reason = rule.get('reason') if rule else declared.get('reason')
        cited_reason(reason, bundle)
        if candidate['unknowns'] or check['missing_repo_files'] or check['external_assets_unverified']:
            raise ValueError('Unresolved candidate dependencies/unknowns prevent no-tool delivery')
        if rule and rule.get('tools'):
            raise ValueError('No-tool binding declares tools')
    elif status == 'required':
        if not rule or not rule.get('tools'):
            result['blocker'] = 'Required tool binding missing'
        elif any(key not in settings['tools'] for key in rule['tools']):
            result['blocker'] = 'Binding references undeclared tools'
        else:
            resolved = {}
            for missing in check['missing_repo_files']:
                matches = []
                for key in rule['tools']:
                    source = (Path(bindings).parent/settings['tools'][key]['root']).resolve()
                    path = (source/missing).resolve()
                    if path.is_relative_to(source) and path.is_file():
                        matches.append({'tool':key,'path':missing,'sha256':sha(path)})
                if not matches:
                    result['blocker'] = 'Unresolved candidate source dependency: '+missing
                resolved[missing] = matches
            result['resolved_source_dependencies'] = resolved
    else:
        result.update(requirement='unknown', blocker='Tool requirement needs confirmation')
    return result


def runtime_stages(root, measured):
    prepared_path = Path(root)/'runtime/prepared.json'
    prepared = read(prepared_path) if prepared_path.exists() else {}
    tools = measured.get('tools', [])
    builds = [read(p) for p in Path(root).glob('runtime/tools/*/attempts/*/build.json')]
    return {'environment_preparation':prepared.get('status','not_run'),
            'docker_build':('passed' if tools and all(t.get('image_id') for t in tools) else
                            'failed' if builds and builds[-1].get('exit_code') else 'not_verified'),
            'tool_validation':measured.get('status','not_run')}


def candidate_report(root, mode='delivery'):
    root = Path(root)
    row = {'candidate':root.name, 'path':str(root.resolve()), 'deliverable':False,
           'execution_accepted':False, 'stages':{'generation':'passed', 'content':'not_verified',
            'dependency_decision':'not_run', 'environment_preparation':'not_run',
            'docker_build':'not_run', 'tool_validation':'not_run'}}
    try:
        content(root)
        row['stages']['content'] = 'passed'
        if mode == 'draft':
            row.update(delivery_status='draft_only', requirement='unassessed')
            return row
        saved = read(root/'delivery/requirement.json')
        if saved.get('error'):
            raise ValueError(saved['error'])
        current = determine(root, saved['job_id'], saved.get('bindings_path'))
        if current != saved:
            raise ValueError('Requirement/source/binding evidence changed; resolve inputs before retry')
        row['requirement'] = current['requirement']
        row['stages']['dependency_decision'] = current['requirement']
        if current.get('blocker'):
            row.update(delivery_status='blocked', error=current['blocker'])
        elif current['requirement'] == 'not_required':
            row.update(delivery_status='delivered', deliverable=True)
            row['stages'].update(environment_preparation='not_required', docker_build='not_required', tool_validation='not_required')
        else:
            measured = runtime_docker.evidence(root)
            row['stages'].update(runtime_stages(root, measured))
            passed = (measured.get('status') == 'execution_passed' and measured.get('acceptance_version') == 2
                      and measured.get('current_acceptance_validated') is True)
            row.update(deliverable=passed, execution_accepted=passed,
                       delivery_status='delivered' if passed else 'blocked',
                       runtime_status=measured.get('status'), error=measured.get('error'))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        row.update(delivery_status='needs_confirmation', error=str(exc))
    return row


def evaluate(paths, expected, mode='delivery'):
    paths = list(map(Path, paths))
    rows = {p.name:candidate_report(p, mode) for p in paths}
    passed = (type(expected) is int and expected > 0 and len(rows) == len(paths) == expected
              and len({p.resolve() for p in paths}) == expected and all(r['deliverable'] for r in rows.values()))
    return {'delivery_version':VERSION, 'creation_mode':mode, 'delivery_status':
            'draft_only' if mode == 'draft' else 'delivered' if passed else 'blocked',
            'delivery_accepted':passed, 'delivery_checks':rows,
            'delivered_candidates':sum(r['deliverable'] for r in rows.values())}


def stage(drafts, job_id, bindings=None, *, deadline=None, draft_only=False):
    paths = sorted(p for p in Path(drafts).glob('*') if (p/'SKILL.md').exists())
    states = {}
    for root in paths:
        if draft_only:
            states[root.name] = 'not_run'
            continue
        try:
            requirement = determine(root, job_id, bindings)
            write(root/'delivery/requirement.json', requirement)
            if requirement.get('blocker'):
                states[root.name] = 'needs_review'
                continue
            if requirement['requirement'] == 'not_required':
                states[root.name] = 'not_required'
                continue
            budget = int(deadline-time.monotonic()) if deadline else None
            if budget is not None and budget < 1:
                raise ValueError('Creation budget exhausted before environment preparation')
            prepared = runtime_docker.prepare(root, job_id, bindings, budget_seconds=budget)
            report = runtime_docker.validate(root) if prepared['status'] == 'prepared' else prepared
            states[root.name] = report['status']
        except (OSError, ValueError, KeyError, TypeError) as exc:
            states[root.name] = 'needs_review'
            if not (root/'delivery/requirement.json').exists():
                write(root/'delivery/requirement.json', {'error':str(exc), 'job_id':job_id})
            write(root/'reports/delivery-stage-error.json', {'error':str(exc)})
    return {'runtime_checks':states, 'runtime_status':runtime_docker.aggregate(states.values()),
            **evaluate(paths, len(paths), 'draft' if draft_only else 'delivery')}


def record_passes(record):
    return evaluate(record.get('candidate_paths', []), record.get('candidate_count', 0))['delivery_accepted']


def retry(root, *, prepare=False, job_id=None, bindings=None, budget=None, repair_from_history=False):
    """Resume without extraction. Never re-plan or bless changed locked inputs implicitly."""
    root = Path(root)
    before = candidate_report(root)
    if before['deliverable']:
        return {'status':'already_delivered', 'reused':True, 'delivery':before}
    content(root)
    if prepare:
        if (root/'runtime/prepared.json').exists():
            raise ValueError('Existing runtime must be retried or explicitly re-prepared using prepare_runtime; locked evidence is retained')
        requirement = determine(root, job_id, bindings)
        write(root/'delivery/requirement.json', requirement)
        if requirement.get('blocker'): raise ValueError(requirement['blocker'])
        if requirement['requirement'] == 'not_required': return candidate_report(root)
        prepared = runtime_docker.prepare(root, job_id, bindings, budget_seconds=budget)
        if prepared['status'] != 'prepared': return prepared
    else:
        saved = read(root/'delivery/requirement.json')
        if saved != determine(root, saved['job_id'], saved.get('bindings_path')):
            raise ValueError('Changed requirement inputs; explicit resolution required')
        if saved.get('blocker'): raise ValueError(saved['blocker'])
        if saved['requirement'] == 'not_required': return candidate_report(root)
    return runtime_docker.validate(root, budget={'total_seconds':budget} if budget else None,
                                   repair_from_history=repair_from_history, reuse_build=True)
