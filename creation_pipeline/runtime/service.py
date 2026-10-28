"""Integration facade: freeze, build, persist; never discover or author on recovery."""
import copy
import uuid
from pathlib import Path

from creation_pipeline.contracts import runtime_request
from creation_pipeline.records import safe_relative, read_json, file_digest, now
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.artifacts.evidence import verify
from .local import LocalExecutor


def execute_prepared(output, record, executor, *, build_only=False, reuse_build=None, attempt_relative=None, persist_record=False):
    output = Path(output)
    ref = record["durable_evidence"]
    relative = attempt_relative or "runtime/" + record["delivery"]["candidate_id"] + "/" + uuid.uuid4().hex
    request = runtime_request(record["delivery"], safe_relative(output, ref["path"]), ref["freeze_sha256"], safe_relative(output, relative))
    if persist_record:
        from creation_pipeline.records import write_json, sanitized
        record['pending_runtime'] = {'path':relative,'revision_id':record['delivery']['revision_id'],'started_at':now()}
        write_json(safe_relative(output,'records/' + record['name'] + '.json'),sanitized(record))
    if reuse_build is None:
        receipt = executor.build(request)
    else:
        import shutil
        target = Path(request.attempt_directory); target.mkdir(parents=True)
        for filename in ('receipt.json', 'build-log.json', 'image.id'):
            source = Path(reuse_build) / filename
            if source.is_file():
                shutil.copyfile(source, target / filename)
        receipt = read_json(target / 'receipt.json')
    if receipt['status'] == 'built' and not build_only:
        try:
            executor.validate(request, receipt)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            from creation_pipeline.records import write_json, redact
            from .local import binding_identity
            write_json(Path(request.attempt_directory) / 'execution/report.json', {
                'version': 1, 'acceptance_version': 2, 'status': 'execution_failed',
                'request': binding_identity(request), 'image_id': receipt['image_id'], 'tag': receipt['tag'],
                'repair_lane': 'contract', 'cases': [], 'error': redact(str(exc)), 'finished_at': now()})
        receipt = effective_receipt(Path(request.attempt_directory), receipt)
    record["runtime"] = {"path": relative, "files": manifest(output / relative),
                         "status": receipt["status"], "execution_status": receipt["execution_status"],
                         "image_id": receipt["image_id"], "host": receipt["host"],
                         "gaps": receipt["gaps"], "revision_id": record["delivery"]["revision_id"]}
    record['execution_location'] = str(output.resolve())
    record.pop('pending_runtime', None)
    if receipt.get('execution'):
        record['runtime']['execution'] = 'execution/report.json'
        record['runtime']['repair_lane'] = receipt['execution'].get('repair_lane')
        record['runtime']['content_revoked'] = receipt['execution'].get('repair_lane') == 'content'
    if receipt["status"] in {"runtime_blocked", "build_failed"}:
        record["status"] = "blocked" if receipt["status"] == "runtime_blocked" else "failed"
    elif receipt['status'] == 'execution_passed':
        from creation_pipeline.contracts import qualify
        accepted, _ = qualify(record['delivery'], runtime_root=output, runtime_ref=record['runtime'],
                             frozen_directory=request.frozen_directory, freeze_sha256=request.freeze_sha256, executor=executor)
        record['status'] = 'ready' if accepted else 'not_run'
    elif receipt['status'] == 'execution_failed':
        record['status'] = 'failed'
        if receipt['execution'].get('repair_lane') == 'content':
            record['content_status'] = 'failed'
    else:
        record["status"] = "not_run"
    return receipt


def effective_receipt(directory, build):
    receipt = copy.deepcopy(build)
    path = Path(directory) / 'execution/report.json'
    if path.exists():
        report = read_json(path)
        if report['request'] != build['request'] or report['image_id'] != build['image_id'] or report['tag'] != build['tag']:
            raise ValueError('Execution attempt differs from bound build')
        receipt.update(build_status=build['status'], status=report['status'], execution=report,
            execution_status='passed' if report['status'] == 'execution_passed' else report['status'],
            business_acceptance='passed' if report['status'] == 'execution_passed' else 'not_passed',
            gaps=report.get('gaps', []), host=report.get('current_host', {}).get('preflight', {}).get('host', build['host']))
    return receipt


def verify_attempt(root, ref, delivery, freeze_sha256):
    directory = safe_relative(root, ref["path"])
    if manifest(directory) != ref["files"]:
        raise ValueError("Runtime evidence changed")
    receipt = read_json(directory / "receipt.json")
    from .local import binding_identity
    expected = {"candidate_id": delivery["candidate_id"], "revision_id": delivery["revision_id"],
                "package_fingerprint": delivery["fingerprints"]["files"], "source_fingerprint": delivery["fingerprints"]["sources"],
                "binding_fingerprint": delivery["fingerprints"]["bindings"], "environment_fingerprint": delivery["fingerprints"]["environment"],
                "acceptance_fingerprint": delivery["fingerprints"]["acceptance"], "freeze_sha256": freeze_sha256,
                "executor_kind": "local-docker", "target_id": "local"}
    if receipt["request"] != expected or receipt["log_sha256"] != file_digest(directory / "build-log.json"):
        raise ValueError("Runtime evidence does not bind this frozen delivery")
    receipt = effective_receipt(directory, receipt)
    if any(ref[k] != receipt[k] for k in ("status", "execution_status", "image_id", "host", "gaps")):
        raise ValueError("Runtime summary differs from receipt")
    if ref.get('content_revoked', False) != (receipt.get('execution', {}).get('repair_lane') == 'content'):
        raise ValueError('Content revocation differs from execution evidence')
    return receipt


def resume_build(library, name, resource_refs=None, *, reuse_image=False, recover_lock=False):
    """Explicit candidate-only recovery; previous attempts remain immutable."""
    from creation_pipeline.artifacts import store
    if recover_lock:
        store.release_dead_lock(library)
    selected = store.get(library, name, include_candidates=True)
    if (selected.get('current_content', {}).get('status') == 'failed'
            or selected.get('runtime', {}).get('repair_lane') in {'unknown', 'contract'}):
        frozen = Path(library).resolve() / selected['evidence']
        record = verify(frozen, selected['freeze_sha256'])
        opts = record['delivery']['inputs']['environment']['payload'].get('limits', {})
        return automatic_revision(library, selected, record, frozen,
                                  {'options': opts, 'resource_refs': resource_refs or {}})
    with store.locked(library) as root:
        value = store.reconcile(root, store.catalog(root))
        entry = next((e for e in value["skills"] if e["name"] == name), None)
        if entry is None or entry.get("invalidated"):
            raise ValueError("Select an intact candidate explicitly")
        frozen = verify(root / entry["evidence"], entry["freeze_sha256"])
        if frozen["delivery"]["mode"] == "draft":
            raise ValueError("Draft needs a normal reviewed revision before runtime build")
        if entry.get('current_content', {}).get('status') == 'failed':
            raise ValueError('Content approval was revoked; independent review must distinguish a content/call defect '
                             'from an acceptance-contract error. Do not rewrite correct source; a source-backed '
                             'contract correction uses runtime-prepare --oracle-correction before revalidation')
        env = frozen["delivery"]["inputs"]["environment"]["payload"]
        if not env or not env.get("plan"):
            raise ValueError("No validated plan: prepare a new runtime revision first")
        frozen["durable_evidence"] = {"path": entry["evidence"], "freeze_sha256": entry["freeze_sha256"]}
        executor = LocalExecutor(resource_refs)
        from .recovery import choose_build
        reuse, decision = choose_build(root, entry, executor, reuse_image)
        pending = entry.get('pending_runtime')
        if pending:
            prior_path = safe_relative(root, pending['path'])
            cleanup = []
            if prior_path.exists() and pending.get('owner_location') == str(root.resolve()):
                from .runner import cleanup_scope
                cleanup = cleanup_scope(prior_path.name)
            entry.setdefault('interrupted_attempts', []).append(dict(pending,
                files=manifest(prior_path) if prior_path.exists() else [], observed_at=now(), cleanup=cleanup))
        relative = 'runtime/' + entry['candidate_id'] + '/' + uuid.uuid4().hex
        entry['pending_runtime'] = {'path': relative, 'revision_id': entry['revision_id'],
                                    'started_at': now(), 'decision': decision, 'owner_location':str(root.resolve())}
        entry['current_qualification'] = {'accepted': False, 'reason': 'Explicit runtime recovery pending'}
        packages = {}
        if entry['zone'] == 'accepted':
            previous_path = entry['path']
            entry.update(zone='candidates', path='candidates/' + name)
            packages[entry['path']] = root / previous_path
            packages[previous_path] = None
        store.commit(root, value, packages)
        # Journal is durable before any Docker work; a crash leaves a resumable pointer.
        receipt = execute_prepared(root, frozen, executor, reuse_build=reuse, attempt_relative=relative)
        if entry.get("runtime"):
            entry.setdefault("runtime_history", []).append(copy.deepcopy(entry["runtime"]))
        entry["runtime"] = frozen["runtime"]
        entry.pop('pending_runtime', None)
        entry['execution_location'] = str(root.resolve())
        entry.setdefault('recovery_history', []).append({'at': now(), 'decision': decision, 'attempt': relative})
        entry["current_execution"] = {"status": receipt["execution_status"], "business_acceptance": receipt['business_acceptance']}
        entry["current_host"] = receipt["host"]
        entry['current_content'] = {'status': 'failed' if frozen['runtime'].get('content_revoked') else frozen['delivery']['content']['status']}
        accepted, reason = store.qualification(root, entry)
        entry['current_qualification'] = {'accepted': accepted, 'reason': reason}
        packages = {}
        if accepted:
            previous_path = entry['path']
            entry.update(zone='accepted', path='accepted/' + name)
            packages[entry['path']] = root / entry['evidence'] / 'package'
            if previous_path != entry['path']:
                packages[previous_path] = None
            entry.pop('runtime_invalidated', None)
        store.commit(root, value, packages)
        return {"status": receipt["status"], "name": name, "revision_id": entry["revision_id"],
                "image_id": receipt["image_id"], "business_acceptance": receipt['business_acceptance'], "gaps": receipt["gaps"], 'accepted': accepted,
                'recovery': decision}


def prepare_revision(library, name, spec, *, correction=None):
    """New environment revision, same authored bytes/sources and locked assertions."""
    from creation_pipeline.artifacts import store
    from creation_pipeline.artifacts.evidence import seal
    from .preparation import prepare
    entry = store.get(library, name, include_candidates=True)
    if entry["zone"] != "candidates" or entry.get("invalidated"):
        raise ValueError("Select an intact candidate explicitly")
    root = Path(library).resolve()
    frozen = root / entry["evidence"]
    record = verify(frozen, entry["freeze_sha256"])
    if record["delivery"]["mode"] == "draft" or record["delivery"]["content"]["status"] != "passed":
        raise ValueError("Runtime-only preparation requires normally reviewed content")
    from .acceptance import consistency
    needs_diagnosis = (entry.get('current_content', {}).get('status') == 'failed'
        or entry.get('runtime', {}).get('repair_lane') in {'unknown', 'contract'}
        or consistency(record['delivery']['inputs']['acceptance']['payload'].get('cases', [])))
    if correction is None and not spec.get('plan') and needs_diagnosis and record['delivery']['inputs']['environment']['payload'].get('plan'):
        return automatic_revision(library, entry, record, frozen, spec)
    if entry.get('current_content', {}).get('status') == 'failed' and correction is None:
        raise ValueError('Content failure needs author repair/review or an independently reviewed source-backed oracle correction')
    sources = []
    identity = {s["id"]: s for s in record["delivery"]["inputs"]["sources"]}
    for ref in read_json(frozen / "sources.json"):
        sources.append(dict(identity[ref["id"]], path=str(safe_relative(frozen, ref["path"]))))
    spec = copy.deepcopy(spec)
    if not spec.get('plan') and record['delivery']['inputs']['environment']['payload'].get('incomplete'):
        # Resume a rejected, never-frozen plan proposal with its exact diagnostic.
        # This is not an accepted contract and must not be passed as previous_plan.
        rejected = list((frozen / 'runtime/planning').glob('*/rejection.json'))
        if rejected:
            latest = max(rejected, key=lambda p: int(p.parent.name))
            spec.setdefault('feedback', read_json(latest))
    acceptance = record["delivery"]["inputs"]["acceptance"]["payload"]
    if isinstance(acceptance, dict) and acceptance.get("cases") and correction is None:
        spec["locked_cases"] = acceptance["cases"]
        if not spec.get('plan'):
            spec.setdefault('previous_plan', record['delivery']['inputs']['environment']['payload'].get('plan'))
            runtime = entry.get('runtime')
            if runtime:
                spec.setdefault('feedback', {'phase': runtime.get('status'),
                    'diagnostic': effective_receipt(safe_relative(root, runtime['path']),
                                                   read_json(safe_relative(root, runtime['path']) / 'receipt.json')),
                    'policy': 'Fix environment only; source and tests are immutable'})
    output = root / "preparations" / uuid.uuid4().hex
    review_evidence = None
    if correction is not None:
        review_evidence = approve_correction(record, frozen, sources, spec, correction, output)
    executor = LocalExecutor(spec.get("resource_refs"))
    record.pop("durable_evidence", None)
    materials = prepare(record, frozen / "package", sources, output / "work", spec, executor, review_evidence=review_evidence)
    if materials is None:
        raise ValueError("Candidate is not eligible for runtime preparation")
    freeze = seal(output / "evidence/revision", frozen / "package", record, sources, materials)
    record["durable_evidence"] = {"path": "evidence/revision", "freeze_sha256": freeze}
    receipt = execute_prepared(output, record, executor)
    result = store.adopt(output, [record], {"revision_parents": {name: entry["revision_id"]}, "batch": entry["batch"]}, root)
    return {"status": receipt["status"], "revision_id": record["delivery"]["revision_id"], "adoption": result, "gaps": receipt["gaps"]}


def approve_correction(record, frozen, sources, spec, correction, output, call_guard=None):
    if not isinstance(correction, dict) or not correction.get('reason') or not correction.get('citations') or not spec.get('plan'):
        raise ValueError('Oracle correction needs a replacement plan, reason and exact source citations')
    import json
    if correction.get('parent_revision', record['delivery']['revision_id']) != record['delivery']['revision_id']:
        raise ValueError('Correction parent revision changed')
    if correction.get('acceptance_fingerprint', record['delivery']['fingerprints']['acceptance']) != record['delivery']['fingerprints']['acceptance']:
        raise ValueError('Correction acceptance identity changed')
    previous_plan = record['delivery']['inputs']['environment']['payload']['plan']
    prior_policy, new_policy = json.loads(previous_plan['acceptance_json']), json.loads(spec['plan']['acceptance_json'])
    if (not {t['name'] for t in previous_plan['tests']} <= {t['name'] for t in spec['plan']['tests']}
            or not set(prior_policy['purposes']) <= set(new_policy['purposes'])
            or not {o['id'] for o in prior_policy.get('operations', [])} <= {o['id'] for o in new_policy.get('operations', [])}):
        raise ValueError('Oracle correction cannot drop promised tests/purposes/operations; scope changes need a new author revision')
    by_id = {s['id']: s for s in sources}
    for citation in correction['citations']:
        source = by_id[citation['source_id']]
        if citation['path'] not in {f['path'] for f in source['inventory']} or not citation['quote'] or citation['quote'] not in safe_relative(Path(source['path']), citation['path']).read_text(encoding='utf-8'):
            raise ValueError('Oracle correction cites unavailable or mismatched source')
    from .review import review_snapshot
    review_evidence = review_snapshot(record, frozen / 'package', sources, output / 'independent-review',
        proposed_plan=spec['plan'], correction=correction, model=spec.get('options', {}).get('model'),
        timeout=spec.get('options', {}).get('model_timeout', 600),
        total_seconds=spec.get('options', {}).get('total_seconds'), call_guard=call_guard,
        transport=spec.get('options', {}).get('transport', 'default'),
        reasoning_effort=spec.get('options', {}).get('reasoning_effort'),
        service_tier=spec.get('options', {}).get('service_tier'))
    reviewed = review_evidence['review']
    if reviewed['status'] != 'pass' or reviewed.get('oracle_changes_verified') is not True or reviewed.get('requirement_assessment') != 'confirmed':
        raise ValueError('Independent reviewer did not confirm a source-backed oracle correction; review evidence retained')
    record['checks'] = [c for c in record.get('checks', []) if c['name'] != 'content_review'] + [reviewed]
    record['content_status'] = 'passed'
    return review_evidence


def automatic_correction(output, record, spec, observation, executor, call_guard=None):
    """One source diagnosis, existing independent approval, then full revalidation.

    Returns a lane for the existing caller's feedback loop. Never authors content.
    Failed/rejected/no-progress decisions are durable and do not invoke a loop here.
    """
    from .diagnosis import diagnose, source_list
    from .preparation import prepare
    from creation_pipeline.artifacts.evidence import seal
    from creation_pipeline.records import write_json, sanitized, redact
    import time
    import math
    output = Path(output)
    frozen = safe_relative(output, record['durable_evidence']['path'])
    verify(frozen, record['durable_evidence']['freeze_sha256'])
    relative = 'diagnostics/' + record['delivery']['candidate_id'][-12:] + '/' + record['delivery']['revision_id'][-12:]
    audit = safe_relative(output, relative)
    old = copy.deepcopy(record)
    result = {'attribution': 'unknown', 'status': 'review_required', 'next_action': 'source_diagnosis_required'}
    try:
        spec = copy.deepcopy(spec)
        opts = spec.setdefault('options', {})
        if opts.get('total_seconds') is not None:
            bound = time.monotonic() + opts['total_seconds']
            executor.deadline = min(executor.deadline, bound) if executor.deadline is not None else bound
        def guard(count_call=True):
            if call_guard and count_call:
                call_guard()
            if executor.deadline is not None and math.isfinite(executor.deadline):
                remaining = executor.deadline - time.monotonic()
                if remaining < 1:
                    raise ValueError('Explicit runtime diagnosis time limit reached')
                opts['model_timeout'] = min(opts.get('model_timeout', 600), int(remaining))
                opts['total_seconds'] = int(remaining)
        correction, proposed, decision_dir = diagnose(record, frozen, observation, audit,
                                                      opts, guard)
        result.update(attribution=correction['attribution'], reason=correction['reason'])
        if correction['attribution'] == 'contract':
            revised_spec = copy.deepcopy(spec)
            revised_spec.pop('locked_cases', None)
            revised_spec['plan'] = proposed
            sources = source_list(record, frozen)
            guard(False)
            revised_spec['options'] = copy.deepcopy(opts)
            review = approve_correction(record, frozen, sources, revised_spec, correction, decision_dir, guard)
            # Keep the complete model proposal/reviewer audit inside the final freeze.
            review['diagnosis_audit'] = {p.relative_to(audit).as_posix(): p.read_text(encoding='utf-8', errors='replace')
                                       for p in audit.rglob('*') if p.is_file()}
            materials = prepare(record, frozen / 'package', sources, decision_dir / 'work',
                                revised_spec, executor, call_guard, review_evidence=review)
            if materials is None or record.get('runtime_preparation', {}).get('status') != 'prepared':
                raise ValueError('Approved proposal could not be prepared; old revision retained')
            new_relative = 'evidence/' + record['name'] + '/' + uuid.uuid4().hex
            record.pop('durable_evidence', None)
            freeze = seal(safe_relative(output, new_relative), frozen / 'package', record, sources, materials)
            record['durable_evidence'] = {'path': new_relative, 'freeze_sha256': freeze}
            receipt = execute_prepared(output, record, executor)
            result.update(status=receipt['status'], next_action='complete' if receipt['status'] == 'execution_passed' else 'review_required',
                          execution=receipt)
        else:
            result['next_action'] = {'content': 'author_repair_and_independent_review',
                'environment': 'environment_repair_locked_tests', 'unknown': 'additional_source_evidence'}[correction['attribution']]
    except (ValueError, OSError, KeyError, TypeError) as exc:
        record.clear(); record.update(old)
        if 'already attempted' in str(exc) and (audit / 'outcome.json').exists():
            result.update(read_json(audit / 'outcome.json'))
        else:
            result['attribution'] = 'unknown'
        result.update(status='review_required', reason=redact(str(exc)))
    write_json(audit / 'outcome.json', sanitized(result))
    record['runtime_diagnosis'] = {'path': relative, 'files': manifest(audit), 'outcome': result}
    return result


def automatic_revision(library, entry, record, frozen, spec):
    from creation_pipeline.artifacts import store
    if entry.get('invalidated') or record['delivery']['mode'] == 'draft':
        raise ValueError('Automatic diagnosis requires an intact normally reviewed candidate')
    root = Path(library).resolve()
    record['durable_evidence'] = {'path': entry['evidence'], 'freeze_sha256': entry['freeze_sha256']}
    # Imported failures intentionally have no reusable qualification; retain raw
    # observations from pending import without treating them as current approval.
    ref = entry.get('runtime') or entry.get('pending_runtime')
    if ref is None:
        ref = next((h.get('runtime') or h.get('pending_runtime') for h in reversed(entry.get('history', []))
                    if h.get('runtime') or h.get('pending_runtime')), None)
    observation = {}
    if ref:
        report = safe_relative(root, ref['path']) / 'execution/report.json'
        if report.exists():
            observation = read_json(report)
    if entry.get('runtime'):
        record['runtime'] = copy.deepcopy(entry['runtime'])
    result = automatic_correction(root, record, spec, observation, LocalExecutor(spec.get('resource_refs')))
    adoption = store.adopt(root, [record], {'revision_parents': {record['name']: entry['revision_id']}, 'batch': entry['batch']}, root)
    return dict(result, revision_id=record['delivery']['revision_id'], adoption=adoption)
