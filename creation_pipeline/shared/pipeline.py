"""Serial resource groups, independent recoverable candidates and tool-only environments."""
import copy
import json
import shutil
import time
import uuid
from collections import Counter
from pathlib import Path

from creation_pipeline.agent.backend import NativeSession
from creation_pipeline.agent.metrics import summarize_usage
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.generation.discovery import normalize, validate_discovery
from creation_pipeline.generation.content_author import author, review
from creation_pipeline.models import load_config, ModelCallError, bound
from creation_pipeline.paths import ROOT, PROMPTS
from creation_pipeline.records import lease, read_json, write_json, safe_relative, now, redact, file_digest, long_path
from creation_pipeline.resources.intake import Sources
from . import prompts, schemas
from .contracts import CONTRACT_VERSION, validate as validate_environment
from .investigation import Investigations
from .failures import IntegrityError, route
from .preflight import startup
from .checks import static_checks
from .environment import EnvironmentLibrary, OperationError, fingerprint, runtime
from .verification import bind_items, validate_plan, execute
from .resources import index
from .delivery import finalize, adopt


class PausedCandidate(ValueError):
    pass


def call(session, phase, instructions, context, schema):
    result = session.stage(instructions, {**context, '_phase': phase}, schema=schema)
    try:
        session.sources.verify()
    except ValueError as exc:
        raise IntegrityError(str(exc)) from exc
    return result


def specifications():
    paths = ['docs/skills/docker-minimum.md', 'docs/skills/docker-packaging.md',
             'creation_pipeline/generation/prompts/content-author.md',
             'creation_pipeline/generation/prompts/content-review.md',
             'creation_pipeline/generation/prompts/content-analyze.md',
             'creation_pipeline/shared/prompts.py',
             'creation_pipeline/shared/contracts.py', 'creation_pipeline/shared/schemas.py',
             'creation_pipeline/shared/checks.py', 'creation_pipeline/shared/verification.py']
    return {p: file_digest(ROOT / p) for p in paths}


def archive_candidate(state_root, bid, gid, name, source, result):
    """Immutable evidence copy exists before an exported catalog points to it."""
    result = copy.deepcopy(result)
    for field in ('record', 'archive_error', 'adoption_error', 'adoption'):
        result.pop(field, None)
    relative = 'records/' + bid + '/evidence/' + fingerprint(result)[:16]
    target = safe_relative(state_root, relative)
    result = copy.deepcopy(result)
    result['record'] = str(target / 'record.json')
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        stage = target.with_name(target.name + '.writing-' + uuid.uuid4().hex[:8])
        source_files = manifest(source)
        shutil.copytree(long_path(source), long_path(stage))
        if manifest(stage) != source_files or manifest(source) != source_files:
            raise ValueError('Candidate archive copy differs from source')
        write_json(stage / 'record.json', result)
        stage.rename(target)
    elif read_json(target / 'record.json') != result:
        raise ValueError('Immutable candidate archive differs')
    return result


def candidate(session, config, entity, directory, library, notify):
    directory.mkdir(parents=True, exist_ok=True)
    checkpoint = directory / 'checkpoint.json'
    state = read_json(checkpoint) if checkpoint.exists() else {
        'name': entity['name'], 'group': config['_group_id'], 'stage': 'environment',
        'status': 'building', 'history': [], 'feedback': [], 'record': str(directory / 'record.json')}
    if state['stage'] != 'done':
        state['status'] = 'building'
        state.pop('failure_owner', None)
    else:
        state.pop('reason', None)
        state.pop('resume_when', None)
    package = directory / 'package'
    package.mkdir(exist_ok=True)
    investigations = Investigations(library.root)
    start_calls = len(session.receipts)
    previous_limit = session.limits['model_calls']
    cap = min(bound(previous_limit), start_calls + bound(config['limits']['candidate_calls']))
    session.limits['model_calls'] = None if cap == float('inf') else cap
    def save():
        write_json(checkpoint, state)
        write_json(directory / 'record.json', state)
    def goto(stage):
        state['stage'] = stage
        save()
    try:
        while state['stage'] != 'done':
            phase = state['stage']
            notify(config['_group_id'] + '/' + entity['name'] + ': ' + phase)
            context = {'plan': entity, 'resource_index': session.workspace['resource_index'],
                       'recent_history': state['history'][-2:], 'history_file': str(checkpoint),
                       'feedback': state['feedback']}
            before = manifest(package)
            try:
                if phase == 'environment':
                    result = None if state['feedback'] else investigations.resolve(entity, session.sources)
                    reused_preparation = result is not None
                    if result is None:
                        catalog = [{k: r[k] for k in ('id', 'version', 'platform', 'tools', 'resources', 'conditions', 'image', 'path')}
                                   for r in library.records() if r.get('contract_version') == CONTRACT_VERSION]
                        result = call(session, 'environment', prompts.ENVIRONMENT,
                                      {**context, 'catalog': catalog,
                                       'prepared_investigations': investigations.context(entity, session.sources),
                                       'previous_plan': state.get('environment_plan')}, schemas.ENVIRONMENT)
                    result['contract_version'] = CONTRACT_VERSION
                    if result['status'] == 'blocked':
                        state['resume_when'] = result['resume_when']
                        raise PausedCandidate(result['reason'])
                    validate_environment(result)
                    known_evidence = {e['id'] for e in session.sources.evidence}
                    if any(e not in known_evidence for e in result['evidence']):
                        raise ValueError('Environment evidence must reference registered group-local IDs')
                    investigations.remember(result, session.sources)
                    state['preparation_reused'] = reused_preparation
                    unchanged_contract = state.get('environment_plan') and runtime(state['environment_plan']) == runtime(result)
                    state['environment_plan'] = result
                    if not state.get('content_repair_pending'):
                        state['feedback'] = []
                    write_json(directory / 'environment-plan.json', result)
                    goto('build' if unchanged_contract and not state.get('content_repair_pending') and state.get('reviewed_files') == manifest(package) else 'author')
                elif phase == 'author':
                    config['_environment_plan'] = state['environment_plan']
                    write_json(package / 'runtime.json', runtime(state['environment_plan']))
                    state['artifact'] = author(session, config, entity, package,
                                               state['feedback'], state.get('artifact'))
                    if any(i.get('blocking') and not i.get('resolution') for i in state['artifact'].get('issues', [])):
                        raise ValueError('Author reported unresolved blocking issues')
                    # runtime is a host-owned factual projection, not an author declaration.
                    write_json(package / 'runtime.json', runtime(state['environment_plan']))
                    goto('review')
                elif phase == 'review':
                    config['_environment_plan'] = state['environment_plan']
                    checks = static_checks(package, entity['name'], expected_runtime=runtime(state['environment_plan']))
                    if any(c['status'] == 'fail' for c in checks):
                        state['feedback'] = checks
                        goto('author')
                        continue
                    result = review(session, entity, state['artifact'], checks, config)
                    if manifest(package) != before:
                        raise IntegrityError('Semantic reviewer changed the package')
                    state['semantic_review'] = result
                    if result['status'] != 'pass':
                        state['feedback'] = [result]
                        if result['resolution'] == 'supply_evidence':
                            raise PausedCandidate('Essential source evidence unavailable: ' + str(result['findings']))
                        owners = {f['owner'] for f in result['findings'] if f['blocking']}
                        state['content_repair_pending'] = 'content' in owners
                        goto('environment' if 'environment' in owners else 'author')
                        continue
                    state['feedback'] = []
                    state.pop('content_repair_pending', None)
                    state['execution_items'] = bind_items(package, result['execution_items'], session.work)
                    state['reviewed_files'] = manifest(package)
                    state['reviewed_main'] = (package / 'SKILL.md').read_text(encoding='utf-8')
                    write_json(directory / 'execution-manifest.json', state['execution_items'])
                    goto('build')
                elif phase == 'build':
                    if state.get('environment') and fingerprint(state['environment_plan']) == state.get('built_plan'):
                        library.probe(state['environment'].get('image') or state['environment']['tag'], state['environment_plan'], directory)
                    else:
                        state['environment'] = library.ensure(state['environment_plan'], directory)
                        state['built_plan'] = fingerprint(state['environment_plan'])
                    env = state['environment']
                    identity = {k: env[k] for k in ('id', 'version', 'platform')}
                    active, cached = [], []
                    for item in state['execution_items']:
                        if not item['necessary']:
                            continue
                        key = fingerprint({'environment': identity, 'file': item['file'],
                                           'code': item['sha256'], 'check': item['expected_check']})
                        saved = state.get('execution_cache', {}).get(key)
                        if saved:
                            cached.append(saved)
                        else:
                            active.append({**item, 'cache_key': key})
                    state['active_execution_items'], state['cached_observations'] = active, cached
                    goto('prepare-tests')
                elif phase == 'prepare-tests':
                    items = state['active_execution_items']
                    if not any(i['necessary'] for i in items):
                        state['verification'] = {'status': 'verified', 'observations': state['cached_observations'], 'deferred': []}
                        goto('publish')
                        continue
                    result = call(session, 'execution', prompts.EXECUTION,
                                  {**context, 'items': items, 'package': str(package), 'environment': state['environment_plan']}, schemas.EXECUTION)
                    if result['status'] == 'blocked':
                        state['feedback'] = [{'name': 'execution_preparation', 'findings': [result['reason']]}]
                        if result['blocked_owner'] == 'content':
                            goto('author')
                            continue
                        state['resume_when'] = result['resume_when']
                        raise PausedCandidate(result['reason'])
                    validate_plan(items, result)
                    state['execution_plan'] = result
                    goto('audit-tests' if result['audit_risks'] or any(Path(f['path']).suffix.lower() in {'.py', '.sh', '.r', '.js', '.ps1'} for c in result['cases'] for f in c['files']) or result['deferred'] else 'execute')
                elif phase == 'audit-tests':
                    result = call(session, 'execution-audit', prompts.AUDIT,
                                  {**context, 'items': state['active_execution_items'], 'tests': state['execution_plan']},
                                  schemas.obj({'status': {'type': 'string', 'enum': ['pass', 'fail']}, 'reason': schemas.S}))
                    if result['status'] != 'pass':
                        state['feedback'] = [result]
                        goto('prepare-tests')
                        continue
                    goto('execute')
                elif phase == 'execute':
                    if manifest(package) != state['reviewed_files']:
                        raise IntegrityError('Package changed after semantic approval')
                    env = state['environment']
                    result = execute(package, env.get('image') or env['tag'], env['platform'],
                                     state['active_execution_items'], state['execution_plan'], directory,
                                     library.timeout, library.run)
                    for observation in result['observations']:
                        if observation['status'] == 'passed':
                            item = next(i for i in state['active_execution_items'] if i['id'] == observation['item_id'])
                            state.setdefault('execution_cache', {})[item['cache_key']] = observation
                    result['observations'] += state['cached_observations']
                    state['verification'] = result
                    if result['status'] == 'failed':
                        raise OperationError('Necessary execution checks failed', result)
                    goto('publish')
                elif phase == 'publish':
                    if not config['environments'].get('publish', True):
                        state['status'] = 'local-' + state['verification']['status']
                        state.pop('reason', None)
                        state.pop('resume_when', None)
                        state['local_image'] = state['environment'].get('image') or state['environment']['tag']
                        state['delivery_note'] = 'Local validation only; image not published, package not qualified for export'
                        goto('done')
                        continue
                    state['environment'] = library.publish(state['environment'])
                    goto('finalize')
                elif phase == 'finalize':
                    # Allow only the exact host projection, including interrupted finalization.
                    current = {i['path']: i for i in manifest(package)}
                    if set(current) != {i['path'] for i in state['reviewed_files']}:
                        raise IntegrityError('Package changed before finalization')
                    for item in state['reviewed_files']:
                        if item['path'] not in {'SKILL.md', 'runtime.json'} and current[item['path']] != item:
                            raise IntegrityError('Code changed before finalization')
                    expected_main = state['reviewed_main'].replace('{{image}}', state['environment']['image'])
                    if (package / 'SKILL.md').read_text(encoding='utf-8') not in {state['reviewed_main'], expected_main}:
                        raise IntegrityError('Unreviewed changes in final Skill text')
                    allowed_runtime = [runtime(state['environment_plan']), runtime(state['environment_plan'], state['environment']['image'])]
                    if read_json(package / 'runtime.json') not in allowed_runtime:
                        raise IntegrityError('Unreviewed changes in runtime requirements')
                    state['final_files'] = finalize(package, state['environment_plan'], state['environment'])
                    if any(c['status'] == 'fail' for c in static_checks(package, entity['name'], expected_runtime=runtime(state['environment_plan'], state['environment']['image']))):
                        raise ValueError('Final package static checks failed')
                    state['status'] = state['verification']['status']
                    state.pop('reason', None)
                    state.pop('resume_when', None)
                    goto('done')
                else:
                    raise ValueError('Unknown candidate stage: ' + phase)
                if phase not in {'author', 'finalize'} and manifest(package) != before:
                    raise IntegrityError('Non-writing stage changed the package: ' + phase)
            except PausedCandidate:
                raise
            except ModelCallError:
                state['failure_owner'] = 'model_transport'
                if config.get('_preflight_receipt'):
                    Path(config['_preflight_receipt']).unlink(missing_ok=True)
                raise
            except (ValueError, OSError, KeyError, TypeError) as exc:
                failure = {'stage': phase, 'error': redact(exc), 'observation': getattr(exc, 'observation', None), 'at': now()}
                state['history'].append(failure)
                save()
                target = route(exc, phase)
                if target == 'blocked':
                    state['failure_owner'] = 'infrastructure'
                    state['resume_when'] = 'Resolve the recorded infrastructure/integrity failure, then resume this stage'
                    raise PausedCandidate(redact(exc))
                if target != 'diagnose':
                    state['feedback'] = [failure, {'action': 'Correct this stage record only; do not add test or infrastructure restrictions to the Skill'}]
                    goto(target)
                    continue
                decision = call(session, 'repair-' + phase, prompts.REPAIR,
                                {**context, 'recent_history': state['history'][-2:], 'failure': failure}, schemas.REPAIR)
                if decision['action'] in {'blocked', 'pipeline'}:
                    state['resume_when'] = decision['resume_when']
                    raise PausedCandidate(decision['reason'])
                if not decision['reason'].strip() or not decision['new_evidence_or_change'].strip():
                    raise PausedCandidate('Repair provided no concrete basis for another attempt')
                state['history'].append({'decision': decision, 'at': now()})
                state['feedback'] = [failure, decision]
                if decision['action'] == 'content' and (not decision['defect_location'].strip() or not decision['defect_evidence'].strip()):
                    raise PausedCandidate('Content repair requires a concrete original-code defect and source evidence')
                if phase == 'build' and decision['action'] in {'content', 'test'}:
                    decision['action'] = 'environment'
                stage = {'environment': 'environment', 'content': 'author', 'test': 'prepare-tests'}.get(decision['action'], phase)
                if stage == 'environment':
                    state.pop('environment', None)
                goto(stage)
            limit = config['limits']['repair_rounds']
            if limit is not None and len(state['history']) > limit * 2:
                raise PausedCandidate('Explicit development repair limit reached')
    except KeyboardInterrupt:
        state.update(status='interrupted', reason='User interrupted')
        save()
        raise
    except (ValueError, OSError, KeyError, TypeError) as exc:
        state.update(status='blocked', reason=redact(exc))
    finally:
        session.limits['model_calls'] = previous_limit
        save()
    return state


def build(config_path=None, state_root=None, *, resume_id=None, plan_only=False, library_root=None,
          no_adopt=False, notify=lambda message: None, _session_factory=None, **options):
    state = Path(state_root or ROOT / '.pipeline').absolute()
    bid = resume_id or (time.strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8])
    work = safe_relative(state, 'runs/' + bid)
    checkpoint = work / 'checkpoint.json'
    with lease(state, bid):
        if resume_id:
            batch = read_json(checkpoint)
            if batch.get('workflow') != 'shared-environments':
                raise ValueError('Legacy run requires explicit legacy recovery')
            config = batch['config']
            batch.pop('status', None)
            batch.pop('reason', None)
            if batch.get('specifications') != specifications():
                raise ValueError('Creation specifications changed; start a new batch rather than reuse old approvals')
        else:
            config = load_config(config_path)
            if config.get('draft_only') or options.get('draft_only'):
                raise ValueError('Use discover to prepare grouped drafts; draft-only legacy qualification is unsupported')
            work.mkdir(parents=True, exist_ok=False)
            write_json(work / 'workspace.json', {'build_id': bid, 'workspace': str(work.resolve())})
            batch = {'workflow': 'shared-environments', 'build_id': bid, 'config': config, 'groups': {},
                     'started_at': now(), 'specifications': specifications()}
        if options.get('rediscover'):
            raise ValueError('Rediscovery creates a new batch; existing candidate evidence is immutable')
        if options.get('plan_path'):
            raise ValueError('Use resume BUILD_ID to continue a grouped discovery checkpoint')
        output = safe_relative(state, 'outputs/' + bid)
        output.mkdir(parents=True, exist_ok=True)
        receipts = []
        started = time.monotonic()
        started_candidates = 0
        envlib = EnvironmentLibrary(config, state)
        try:
            if _session_factory is None:
                receipts.extend(startup(config, state, work, notify, mode='discover' if plan_only else 'build'))
            for group in config['resource_groups']:
                gid = group['id']
                group_work = safe_relative(work, 'groups/' + gid)
                group_work.mkdir(parents=True, exist_ok=True)
                gc = copy.deepcopy(config)
                gc.update(sources=group['sources'], _group_id=gid, _preflight_receipt=str(work / 'preflight-success.json'))
                gs = batch['groups'].setdefault(gid, {'status': 'started', 'entities': {}})
                write_json(checkpoint, batch)
                try:
                    registry = group_work / 'resource-state.json'
                    if registry.exists():
                        from creation_pipeline.resources.supplements import restore
                        sources = restore(group_work)
                    else:
                        sources = Sources(gc, state / 'cache')
                    session = (_session_factory or NativeSession)(gc, sources, gc['limits'], group_work)
                    session.started = started
                    session.notify = notify
                    if options.get('extra_turns') and session.limits['model_calls'] is not None:
                        session.limits['model_calls'] += options['extra_turns']
                    if 'discovery' not in gs:
                        plan = call(session, 'discovery', (PROMPTS / 'content-analyze.md').read_text(encoding='utf-8') +
                                    '\nIdentify tools/resources per candidate with source-supported names and unknowns; do not choose shared images.',
                                    {'sources': sources.index(), 'source_errors': sources.errors, 'user_guidance': gc['prompt']}, schemas.CANDIDATES)
                        if plan['outcome'] in {'blocked', 'incomplete'}:
                            raise PausedCandidate(plan['summary'])
                        if not plan['candidates'] and plan.get('saved_candidates'):
                            plan['candidates'] = [read_json(safe_relative(group_work, 'candidates/' + name + '.json'))
                                                  for name in plan['saved_candidates']]
                        if bool(plan['candidates']) != (plan['outcome'] == 'candidates'):
                            raise ValueError('Discovery outcome contradicts candidate list')
                        originals = {c['name']: c for c in plan['candidates']}
                        normalized = normalize(plan)
                        for c in normalized['candidates']:
                            c.update({k: originals[c['name']][k] for k in ('tools', 'resources', 'tool_requirements', 'environment_gaps')})
                        validate_discovery(normalized, gc, sources)
                        gs['discovery'] = normalized
                        write_json(checkpoint, batch)
                    index(sources)
                    if not plan_only:
                        gs.pop('deferred', None)
                        for entity in gs['discovery']['candidates']:
                            name = entity['name']
                            safe_relative(group_work, 'candidates/' + name)
                            previous = gs['entities'].get(name)
                            if previous and previous['status'] in {'verified', 'pending-validation'}:
                                result = previous
                            else:
                                if started_candidates >= bound(config['limits']['max_builds']):
                                    gs.setdefault('deferred', []).append(name)
                                    continue
                                started_candidates += 1
                                try:
                                    result = candidate(session, gc, entity, group_work / 'candidates' / name, envlib, notify)
                                except (ValueError, OSError, KeyError, TypeError) as exc:
                                    result = {'name': name, 'group': gid, 'status': 'blocked',
                                              'reason': redact(exc), 'failure_owner': 'infrastructure'}
                            # Archive/export errors are separate from computation approval. Continue other candidates.
                            result.pop('archive_error', None)
                            result.pop('adoption_error', None)
                            try:
                                result = archive_candidate(state, bid, gid, name, group_work / 'candidates' / name, result)
                            except (ValueError, OSError) as exc:
                                result['archive_error'] = redact(exc)
                            gs['entities'][name] = result
                            if not result.get('archive_error') and result['status'] in {'verified', 'pending-validation'} and not no_adopt and config['adoption']['enabled']:
                                try:
                                    result['adoption'] = adopt(group_work / 'candidates' / name / 'package', result, library_root or ROOT / 'skills')
                                except (ValueError, OSError) as exc:
                                    result['adoption_error'] = redact(exc)
                            write_json(checkpoint, batch)
                            index(session.sources)
                    gs.pop('reason', None)
                    gs['status'] = 'planned' if plan_only else 'deferred' if gs.get('deferred') else 'completed'
                    receipts.extend(session.receipts)
                except (ValueError, OSError, KeyError, TypeError) as exc:
                    if isinstance(exc, ModelCallError):
                        (work / 'preflight-success.json').unlink(missing_ok=True)
                    gs.update(status='blocked', reason=redact(exc))
                finally:
                    write_json(checkpoint, batch)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            batch.update(status='blocked', reason=redact(exc))
        except KeyboardInterrupt:
            batch['status'] = 'interrupted'
        entities = [e for g in batch['groups'].values() for e in g['entities'].values()]
        counts = dict(Counter(e['status'] for e in entities))
        local_complete = not config['environments'].get('publish', True) and entities and all(
            e['status'] in {'local-verified', 'local-pending-validation'} and not e.get('archive_error') for e in entities) and all(
            g['status'] == 'completed' for g in batch['groups'].values())
        batch.setdefault('status', 'local_validated' if local_complete else 'planned' if plan_only else 'no_candidates' if not entities and all(g['status'] == 'completed' for g in batch['groups'].values())
                         else 'ready' if entities and all(e['status'] in {'verified', 'pending-validation'} and not e.get('adoption_error') and not e.get('archive_error') for e in entities)
                         and all(g['status'] == 'completed' for g in batch['groups'].values()) else 'partial')
        batch.update(counts=counts, finished_at=now(), model_metrics=summarize_usage(receipts))
        write_json(checkpoint, batch)
        write_json(output / 'summary.json', batch)
        archive = safe_relative(state, 'records/' + bid)
        write_json(archive / 'summary.json', batch)
        # Keep recoverable workspaces until explicit, dependency-aware cleanup.
        write_json(archive / 'complete.json', {'workflow': 'shared-environments', 'build_id': bid,
                                            'workspace': str(work), 'summary_sha256': fingerprint(batch)})
        return {'workflow': 'shared-environments', 'build_id': bid, 'status': batch['status'],
                'counts': counts, 'output': str(output), 'workspace': str(work),
                'groups': {gid: {k: g.get(k) for k in ('status', 'reason', 'deferred')} for gid, g in batch['groups'].items()},
                'entities': [{k: e.get(k) for k in ('name', 'group', 'status', 'reason', 'archive_error', 'adoption_error')} for e in entities]}
