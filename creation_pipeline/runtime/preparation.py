"""Attach one grounded runtime plan to the native candidate, never author a skill."""
import copy
import json
import re
import shutil
import time
from pathlib import Path

from creation_pipeline.artifacts.evidence import checked_copy
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.contracts import fingerprint, versioned
from creation_pipeline.records import safe_relative, write_json, redact, sanitized
from . import planner


class RuntimeBlocked(ValueError):
    def __init__(self, code, detail, lane="environment"):
        self.code, self.lane = code, lane
        super().__init__(detail)


def validate_spec(spec):
    if not isinstance(spec, dict) or set(spec) - {'binding', 'plan', 'options', 'resource_refs', 'constraints',
                                                  'requirements', 'locked_cases', 'previous_plan', 'feedback',
                                                  'native_model'}:
        raise ValueError('Unsupported runtime preparation settings')
    for key in ('binding', 'plan', 'options', 'resource_refs', 'native_model'):
        if key in spec and not isinstance(spec[key], dict):
            raise ValueError('runtime.' + key + ' must be an object')
    if not isinstance(spec.get('constraints', []), list) or any(not isinstance(s, str) for s in spec.get('constraints', [])):
        raise ValueError('Runtime constraints must be text items')
    if not isinstance(spec.get('requirements', []), list) or any(not isinstance(s, str) for s in spec.get('requirements', [])):
        raise ValueError('Runtime requirements must be text items')
    for ref in spec.get('resource_refs', {}).values():
        if not isinstance(ref, dict) or set(ref) - {'path', 'sha256', 'env'} or any(not isinstance(v, str) for v in ref.values()):
            raise ValueError('Resource references support only path/sha256 or environment-variable names; no credential values')
    for entry in spec.get('plan', {}).get('environment', []):
        if isinstance(entry, dict) and re.search(r'(?i)password|credential|secret|token|api_?key', str(entry.get('name', ''))):
            raise ValueError('Credential values cannot be supplied as Docker environment literals')
    if redact(json.dumps(spec, ensure_ascii=False)) != json.dumps(spec, ensure_ascii=False):
        raise ValueError('Runtime settings contain credential-like literals; use references')
    planner.options(spec.get('options', {}))


def bind(package, sources, proposal=None, entry=None):
    """Automatic binding requires byte identity; adapted entrypoints need explicit evidence.

    ``entry`` restricts the automatic byte-identity search to one declared delivered
    path, so a declaration cannot be satisfied by a different file that happens to
    equal a source.
    """
    files = manifest(package)
    source_files = [(s, f) for s in sources for f in s["inventory"]]
    if proposal is None:
        matches = [(f, s, sf) for f in files if f["path"].endswith((".py", ".sh"))
                   and (entry is None or f["path"] == entry)
                   for s, sf in source_files if f["sha256"] == sf["sha256"]]
        if len(matches) != 1:
            raise RuntimeBlocked("binding_unresolved", "No unique delivered executable/source identity; configure a binding", "binding")
        f, s, sf = matches[0]
        proposal = {"entry": f["path"], "source_id": s["id"], "source_path": sf["path"], "association": "identical"}
    p = copy.deepcopy(proposal)
    try:
        entry = next(f for f in files if f["path"] == p["entry"])
        source, original = next((s, f) for s, f in source_files if s["id"] == p["source_id"] and f["path"] == p["source_path"])
        safe_relative(package, p["entry"])
        if p.get("association") == "identical":
            if entry["sha256"] != original["sha256"]:
                raise ValueError("Claimed identical entry differs from source")
        elif p.get("association") == "explicit":
            # Explicit user association is not a model's self-certification.
            if not p.get("reason") or not p.get("quote"):
                raise ValueError("Explicit association needs reason and exact source quote")
            root = Path(source["path"])
            text = (root if root.is_file() else safe_relative(root, original["path"])).read_text(encoding="utf-8")
            if p["quote"] not in text:
                raise ValueError("Binding source quote mismatch")
        else:
            raise ValueError("Unsupported association")
        p.update(entry_sha256=entry["sha256"], source_sha256=original["sha256"])
        return p
    except (KeyError, StopIteration, OSError, ValueError) as exc:
        raise RuntimeBlocked("binding_unresolved", str(exc), "binding") from exc


# Wording that states an invalid-input obligation. It is a deterministic anchor, not a
# semantic reading: a match only ever makes the gate stricter.
REQUIRED_INPUT_PHRASES = re.compile(
    r'(?i)\binvalid[ -](?:input|argument|value)s?\b|\breject(?:s|ed|ion)?\b|\berror handl\w*\b|'
    r'\binput validation\b|\bvalidation error\b|非法输入|错误处理')


def input_anchors(record, requirements=()):
    """Obligations a ``none_documented`` classification may not waive.

    Only frozen or caller-declared facts are consulted: the author's own rejection
    checks, the independently reviewed execution requirement, and the caller's stated
    requirements. The creation prompt is not an anchor source on its own.
    """
    delivery = record.get('delivery') or {}
    payload = (delivery.get('inputs', {}).get('acceptance') or {}).get('payload') or {}
    definitions = payload.get('author_tests', payload) if isinstance(payload, dict) else {}
    rejected = sorted(
        str(test.get('name')) for origin in ('configured', 'generated', 'reviewed')
        for test in (definitions.get(origin) or []) if isinstance(test, dict)
        if type(test.get('expected_exit', 0)) is int and test.get('expected_exit') != 0)
    required = (delivery.get('inputs', {}).get('requirement') or {})
    texts = [required.get('reason') or '', *[str(item) for item in requirements]]
    texts += [citation.get('quote') or '' for citation in required.get('citations') or []
              if isinstance(citation, dict)]
    matches = sorted({match.group(0).lower() for text in texts if isinstance(text, str)
                      for match in REQUIRED_INPUT_PHRASES.finditer(text)})
    basis = []
    if rejected:
        basis.append('the delivered interface declares rejection checks: ' + ', '.join(rejected))
    if matches:
        basis.append('the stated requirement asks for invalid-input verification: ' + ', '.join(matches))
    return {'rejection_checks': rejected, 'requirement_matches': matches,
            'forbids_none_documented': bool(rejected or matches), 'basis': '; '.join(basis)}


def merged_anchors(record, requirements=()):
    """Anchors only ever accumulate: a repair cannot forget an earlier obligation."""
    fresh = input_anchors(record, requirements)
    previous = ((record.get('delivery') or {}).get('inputs', {}).get('acceptance') or {}).get('payload') or {}
    old = previous.get('input_anchors') if isinstance(previous, dict) else None
    if not isinstance(old, dict):
        return fresh
    rejected = sorted(set(fresh['rejection_checks']) | set(old.get('rejection_checks') or []))
    matches = sorted(set(fresh['requirement_matches']) | set(old.get('requirement_matches') or []))
    basis = '; '.join(item for item in (old.get('basis'), fresh['basis']) if item)
    return {'rejection_checks': rejected, 'requirement_matches': matches,
            'forbids_none_documented': bool(rejected or matches or old.get('forbids_none_documented')),
            'basis': basis}


def none_documented_units(policy):
    """Units that classify invalid input as an undocumented absence."""
    if not isinstance(policy, dict):
        return []
    operations = policy.get('operations') or []
    if operations and all(isinstance(o, dict) and 'input_contract' in o for o in operations):
        units = [(o.get('id'), o['input_contract']) for o in operations]
    elif isinstance(policy.get('input_contract'), dict):
        units = [('tool', policy['input_contract'])]
    else:
        return []
    return [str(name) for name, contract in units
            if isinstance(contract, dict) and contract.get('status') == 'none_documented']


def confirm_gaps(policy, review_evidence):
    """A recorded absence needs an independent confirmation, never self-attestation."""
    units = none_documented_units(policy)
    if not units:
        return
    review = (review_evidence or {}).get('review') or {}
    if review.get('status') != 'pass':
        raise RuntimeBlocked(
            'invalid_input_review_missing',
            'none_documented needs an independent review that confirms the examined materials: '
            + ', '.join(units) + '; without it the classification is only a declaration',
            'contract')


def handoff(package, sources, destination):
    """One verified source handoff shared by planner and context renderer."""
    destination.mkdir(parents=True)
    for f in manifest(package):
        checked_copy(safe_relative(package, f["path"]), safe_relative(destination, "package/" + f["path"]), f["sha256"])
    for source in sources:
        root = Path(source["path"])
        for f in source["inventory"]:
            checked_copy(root if root.is_file() else safe_relative(root, f["path"]),
                         safe_relative(destination, "sources/" + source["id"] + "/" + f["path"]), f["sha256"])


def validate_bound_entrypoint(p, binding):
    """A path appearing in argv is not proof that the script is executed."""
    from .entry import runtime_path
    entry = runtime_path(binding)
    target = '/opt/skill/' + entry
    argv = p.get('entrypoint') or []
    valid = p.get('script') == entry and bool(argv)
    if valid and argv[0] != target:
        executable = argv[0].rsplit('/', 1)[-1]
        flags = []
        if entry.endswith('.py') and re.fullmatch(r'python(?:[23](?:\.\d+)*)?', executable):
            # Only standalone switches with no code/module/operand semantics.
            flags = ['-u', '-B', '-I', '-E', '-s', '-S', '-O', '-OO', '-q', '-P']
        elif not (entry.endswith('.sh') and executable in {'sh', 'bash', 'dash', 'ash'}):
            valid = False
        position = 1
        while position < len(argv) and argv[position] in flags:
            position += 1
        valid = valid and position < len(argv) and argv[position] == target
    if not valid:
        raise RuntimeBlocked('entry_mismatch',
            'Plan must execute the bound delivered script ' + target
            + ' as the executable or as the script operand of a supported Python/shell interpreter; '
              'inline code (-c), module execution (-m), command wrappers and a path used only as an argument '
              'do not bind execution. Use [python, ' + target + '] for Python. Received: '
            + json.dumps(argv, ensure_ascii=False), 'binding')


def validate(p, index, source, binding, opts, locked=None, anchors=None):
    if redact(json.dumps(p, ensure_ascii=False)) != json.dumps(p, ensure_ascii=False):
        raise RuntimeBlocked("unsafe_plan", "Plan contains credential-like literals", "environment")
    validate_bound_entrypoint(p, binding)
    cases, _, total = planner.validate_plan(p, index, source,
                                            [c for c in locked if c.get('origin') != 'authored_check'] if locked else None,
                                            anchors)
    if any(c.get("timeout_seconds", 30) > opts["test_seconds"] for c in cases):
        raise planner.PlanningError("Case exceeds explicit operation timeout")
    if opts["max_context_bytes"] is not None and total > opts["max_context_bytes"]:
        raise planner.BudgetExceeded("Explicit context byte limit reached")
    return cases


def propose(source, binding, audit, opts, constraints=None, locked=None, feedback=None, call_guard=None,
            previous=None, anchors=None):
    """Reuse planner reads/patches; stop repeated diagnoses instead of hidden quotas."""
    import itertools
    deadline = None if opts["total_seconds"] is None else time.monotonic() + opts["total_seconds"]
    attempts = itertools.count() if opts["max_attempts"] is None else range(opts["max_attempts"])
    diagnoses = set()
    # Cases that came from outside this draft. A repair may withdraw its own
    # over-promises, but never an accepted or author-supplied case.
    required = {c["name"] for c in (locked or []) if c.get("origin") == "model_proposed"}
    from .entry import runtime_path
    for number in attempts:
        p, index, _ = planner.plan(source, {"script": runtime_path(binding),
            "constraints": ["Invoke the unchanged delivered package entry, not only the upstream tool. "
                            "ENTRYPOINT must execute that script directly, or use a supported Python/shell "
                            "interpreter followed by the script path. Python standalone flags such as -u "
                            "are allowed; inline code (-c), module execution (-m), and command wrappers "
                            "cannot substitute for executing the bound script."] + (constraints or [])},
            Path(audit) / str(number), opts, deadline, feedback=feedback, previous=previous, call_guard=call_guard,
            required=required)
        try:
            cases = validate(p, index, source, binding, opts, locked, anchors)
            return p, index, cases
        except (planner.PlanningError, ValueError) as exc:
            diagnostic = str(exc)
            if diagnostic in diagnoses:
                raise RuntimeBlocked("planning_no_progress", diagnostic) from exc
            diagnoses.add(diagnostic)
            feedback = {"rejected_plan": p, "read_files": index.get("read_files", []),
                        "source_fingerprint": fingerprint(index["files"]), "diagnostic": diagnostic}
            write_json(Path(audit) / str(number) / "rejection.json", sanitized(feedback))
    raise RuntimeBlocked("explicit_attempt_limit", "Configured planning attempt limit reached")


def render(source, target, plan, cases, base_image_pin=None):
    """Container-only installation; final delivered code copied unchanged."""
    target.mkdir(parents=True)
    names = set(plan["source_files"]) | {"package/" + f["path"] for f in manifest(source / "package")}
    for name in sorted(names):
        p = safe_relative(source, name)
        from creation_pipeline.records import file_digest
        checked_copy(p, safe_relative(target, name), file_digest(p))
    for f in plan["generated_files"]:
        p = safe_relative(target, f["path"])
        if p.exists() or f["path"].startswith(("package/", "sources/")):
            raise planner.PlanningError("Generated installation file may not replace delivery/source")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f["content"], encoding="utf-8")
    # A pinned base image is the digest observed during preparation, never the tag.
    base = base_image_pin['repo_digest'] if base_image_pin else plan["base_image"]
    lines = ["FROM " + base, "WORKDIR /opt/skill", "ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp"]
    lines += ["ENV " + e["name"] + "=" + json.dumps(e["value"]) for e in plan["environment"]]
    prefix = plan["build_layout"]["prefix_steps"]
    if prefix:
        lines += ["COPY " + json.dumps([n, "./" + n]) for n in plan["build_layout"]["dependency_files"]]
        lines += ["RUN " + s["command"] for s in plan["steps"][:prefix]]
    lines += ["COPY . ./"] + ["RUN " + s["command"] for s in plan["steps"][prefix:]]
    lines += ["USER 10001:10001", "ENTRYPOINT " + json.dumps(plan["entrypoint"])]
    (target / "Dockerfile").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (target / ".dockerignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")


def declared_checks(payload, limit=40):
    """Compact view of the checks the delivered interface already promises."""
    definitions = payload if isinstance(payload, dict) else {}
    if 'author_tests' in definitions:
        definitions = definitions['author_tests']
    if not isinstance(definitions, dict):
        return []
    result = []
    for origin in ('configured', 'generated', 'reviewed'):
        for test in (definitions.get(origin) or []):
            if not isinstance(test, dict) or len(result) >= limit:
                continue
            result.append({'origin': origin, 'name': test.get('name'),
                           'expected_exit': test.get('expected_exit', 0),
                           'purpose': test.get('purpose'),
                           'argv': [str(item)[:120] for item in (test.get('argv') or [])][:8]})
    return result


def pin_base_image(record, plan, opts, executor):
    """The digest a pinned build must reuse, reused across revisions of one reference.

    Resolution is an observed registry fact, not a plan claim: the plan keeps the
    human-meaningful reference and the frozen environment keeps the digest that was
    actually resolved for it.
    """
    if not opts.get('pin_base_image'):
        return None
    previous = ((record.get('delivery') or {}).get('inputs', {}).get('environment') or {}).get('payload') or {}
    pinned = previous.get('base_image') if isinstance(previous, dict) else None
    if (isinstance(pinned, dict) and pinned.get('reference') == plan.get('base_image')
            and re.fullmatch(r'sha256:[0-9a-f]{64}', str(pinned.get('digest')))
            and pinned.get('repo_digest') == str(pinned.get('repository')) + '@' + str(pinned.get('digest'))):
        return pinned
    resolve = getattr(executor, 'resolve_base_image', None)
    if resolve is None:
        raise RuntimeBlocked('base_image_unresolved',
                             'This executor cannot resolve a base image digest for pinning', 'environment')
    return resolve(plan.get('base_image'), opts.get('registry_seconds', 120))


def rebind(record, binding, environment, acceptance):
    d = record["delivery"]
    old_revision = d["revision_id"]
    for key, value in (("bindings", binding), ("environment", environment), ("acceptance", acceptance)):
        old = d["inputs"][key]
        d["inputs"][key] = versioned(value, old["version"] + (old["sha256"] != fingerprint(value)))
    d["revision_id"] = "rev-" + fingerprint(d["inputs"])
    d["fingerprints"] = {k: fingerprint(d["inputs"][k]) for k in d["fingerprints"]}
    if old_revision != d["revision_id"]:
        d["parent_revision"] = old_revision
    d["execution"] = {"status": "not_run", "attempts": [], "reason": "This revision requires fresh bound execution evidence"}
    d["qualification"] = {"accepted": False, "reason": "Docker build is not business acceptance"}


def prepare(record, package, sources, workspace, spec, executor, call_guard=None, review_evidence=None):
    """Return immutable materials plus a diagnostic; deterministic blockers do not call models."""
    validate_spec(spec)
    d = record["delivery"]
    if d["mode"] == "draft" or d["inputs"]["requirement"]["status"] == "not_required" or d["content"]["status"] != "passed":
        return None
    target = Path(workspace) / "materials"
    target.mkdir(parents=True)
    result = {"status": "runtime_blocked", "gaps": [], "model_calls": 0}
    def counted_call_guard():
        if call_guard is not None:
            call_guard()
        # Count admitted invocation attempts, including failed transports, not
        # only successful planner receipts. Entry association uses models too.
        result['model_calls'] += 1
    binding = None
    opts = planner.options(spec.get("options", {}))
    # The association review is an independent model stage like discovery/review, so
    # it must run on the batch's native provider instead of silently using the CLI.
    opts['native_model'] = copy.deepcopy(spec.get('native_model') or {})
    if opts["total_seconds"] is not None:
        deadline = time.monotonic() + opts["total_seconds"]
        executor.deadline = min(executor.deadline, deadline) if executor.deadline is not None else deadline
    try:
        if d["inputs"]["requirement"]["status"] == "unknown":
            raise RuntimeBlocked("requirements_unknown", d["inputs"]["requirement"]["reason"], "requirement")
        from .entry import associate, materialize, preflight
        host = None
        declared = record.get('entry_declaration')
        if spec.get('binding') is not None:
            # 1. The caller bound the entry explicitly. It is validated and a failure
            # blocks; the entry is never silently re-derived.
            binding = bind(package, sources, spec['binding'])
            binding['declaration_source'] = 'user_binding'
        elif declared is not None:
            # 2. The author declared the entry. The declaration selects, then the
            # ordinary checks decide whether it is trustworthy.
            entry = preflight(package, declared)
            binding = None
            if entry['kind'] == 'script':
                try:
                    binding = bind(package, sources, entry=entry['entry'])
                except RuntimeBlocked:
                    binding = None
            if binding is None:
                host = executor.host()
                if host['gaps']:
                    result['gaps'].extend(host['gaps'])
                    raise RuntimeBlocked('planning_deferred', 'Docker unavailable; entry association and planning deferred without model calls')
                binding = associate(record, package, sources, target / 'association', opts,
                                    counted_call_guard, executor.deadline, entry=entry)
            binding['declaration'] = entry.get('declaration')
            binding['declaration_source'] = 'author_declaration'
        else:
            # 3. No declaration: conservative recognition of a single candidate.
            try:
                binding = bind(package, sources)
                binding['declaration_source'] = 'identical_bytes'
            except RuntimeBlocked:
                preflight(package)
                host = executor.host()
                if host['gaps']:
                    result['gaps'].extend(host['gaps'])
                    raise RuntimeBlocked('planning_deferred', 'Docker unavailable; association and planning deferred without model calls')
                binding = associate(record, package, sources, target / 'association', opts, counted_call_guard, executor.deadline)
                binding['declaration_source'] = 'conservative'
        write_json(target / "binding.json", binding)
        source = Path(workspace) / "handoff"
        handoff(package, sources, source)
        materialize(package, binding, source)
        from .entry import source_view
        write_json(source / 'source-identities.json', source_view(sources))
        index = planner.inventory(source, opts)
        host = host if host is not None else executor.host()
        # Stated invalid-input obligations are anchored before any classification is
        # judged, and they only accumulate across revisions.
        anchors = merged_anchors(record, spec.get('requirements') or [])
        p = copy.deepcopy(spec.get("plan"))
        if p is None:
            if host["gaps"]:
                result["gaps"].extend(host["gaps"])
                raise RuntimeBlocked("planning_deferred", "Docker unavailable; no model called. Supply a plan to prepare offline")
            planning_opts = dict(opts)
            if executor.deadline is not None and executor.deadline != float("inf"):
                remaining = executor.deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeBlocked("explicit_budget", "Explicit runtime time limit reached")
                planning_opts["total_seconds"] = max(1, int(remaining))
            entry_constraints = list(spec.get('constraints', []))
            if binding.get('kind') == 'markdown_python':
                entry_constraints += ['entry/skill.py is the exact unchanged Python block extracted from package/SKILL.md; '
                    'do not generate or alter business code. Invocation contract: ' + binding['invocation'],
                    'Existing author checks are additionally locked and executed against the actual Markdown. ' +
                    json.dumps(d['inputs']['acceptance']['payload'], ensure_ascii=False)]
            else:
                declared = declared_checks(d['inputs']['acceptance']['payload'])
                if declared:
                    # The planner must know which rejection behaviour the delivered
                    # interface already promises; otherwise it cannot express a check
                    # for a constraint the author's own checks assert.
                    entry_constraints.append(
                        'Author-declared checks are locked and executed as delivered cases. A declared check '
                        'with a nonzero expected exit means that operation is required and needs a named check '
                        'plus a matching rejection case. Declared checks: '
                        + json.dumps(declared, ensure_ascii=False))
            p, index, _ = propose(source, binding, target / "planning", planning_opts, entry_constraints, spec.get("locked_cases"),
                                  feedback=spec.get('feedback'), call_guard=counted_call_guard,
                                  previous=spec.get('previous_plan'), anchors=anchors)
        else:
            index["read_files"] = list(index["files"])
        if redact(json.dumps(p, ensure_ascii=False)) != json.dumps(p, ensure_ascii=False):
            raise RuntimeBlocked("unsafe_plan", "Plan contains credential-like literals")
        cases = validate(p, index, source, binding, opts, spec.get("locked_cases"), anchors)
        confirm_gaps(json.loads(p['acceptance_json']), review_evidence)
        write_json(target / "input-anchors.json", anchors)
        from .checks import mapped_checks
        original_acceptance = d['inputs']['acceptance']['payload'] or {}
        cases += mapped_checks(original_acceptance, p, [s['id'] for s in sources])
        if spec.get('locked_cases') is not None:
            by_name = {c['name']: c for c in cases}
            if any(fingerprint(by_name.get(c['name'])) != fingerprint(c) for c in spec['locked_cases']):
                raise planner.PlanningError('Environment repair changed locked tests or mapped checks')
        write_json(target / "proposed-plan.json", p)
        write_json(target / "locked-tests.json", {"cases": cases, "policy": json.loads(p["acceptance_json"])})
        base_image_pin = pin_base_image(record, p, opts, executor)
        if base_image_pin:
            write_json(target / "base-image.json", base_image_pin)
        render(source, target / "context", p, cases, base_image_pin)
        write_json(target / "plan.json", p)
        if review_evidence is not None:
            write_json(target / 'independent-contract-review.json', review_evidence)
        (target / "README.md").write_text("Docker build materials only. No business acceptance has run.\n"
            "Build context: context/. Entrypoint is the unchanged delivered package.\n"
            "Run with runtime-validate using locked-tests.json; never substitute host execution.\n", encoding="utf-8")
        result["status"] = "prepared"
        old_acceptance = d["inputs"]["acceptance"]["payload"]
        author_tests = old_acceptance.get("author_tests", old_acceptance) if isinstance(old_acceptance, dict) else old_acceptance
        required_names = {r["description"] for r in p["resources"] if r["required_for_execution"]}
        resource_inputs = {key: {k: v for k, v in value.items() if k in {"sha256", "env"}}
                           for key, value in spec.get("resource_refs", {}).items() if key in required_names}
        environment = {"plan": p, "materials": manifest(target), "limits": opts, "resource_inputs": resource_inputs}
        if base_image_pin:
            environment["base_image"] = base_image_pin
        rebind(record, binding, environment,
               {"cases": cases, "policy": json.loads(p["acceptance_json"]), "author_tests": author_tests,
                "input_anchors": anchors})
    except (RuntimeBlocked, planner.PlanningError, planner.ModelUnavailable, OSError, ValueError, ImportError) as exc:
        result["gaps"].append({"code": getattr(exc, "code", "plan_unresolved"), "detail": redact(str(exc)),
                               "repair_lane": getattr(exc, "lane", "environment"),
                               "blocker_kind": getattr(exc, 'kind', 'unresolved_input')})
        rebind(record, binding, {"materials": manifest(target), "limits": opts, "incomplete": True}, d["inputs"]["acceptance"]["payload"])
        if getattr(exc, 'lane', None) == 'content' and getattr(exc, 'kind', None) == 'content_defect':
            d['content']['status'] = 'failed'
            record['content_status'] = 'failed'
        d["execution"] = {"status": "runtime_blocked", "attempts": [], "reason": result["gaps"][0]["detail"]}
        record["status"] = "blocked"
    record["runtime_preparation"] = result
    return target
