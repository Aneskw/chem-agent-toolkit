"""Model-driven generation, bounded repair, layered acceptance and local evidence."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

import runtime_model as planner
import runtime_package as runner
from runtime_transaction import preserve_runtime_on_failure
from runtime_examples import usage_example, identity, counts, select_usage_case, NoUsageCase
from runtime_common import read, write, digest, aggregate, files, artifacts, sha, withdraw_claims, sync_skill
from validate_skill_format import validate as format_check

HERE = Path(__file__).resolve().parent
LAYERS = ("environment", "interface", "behavior")


class IntegrityFailure(ValueError):
    """Inputs/evidence changed; model repair must never bypass this check."""


class RepairableFailure(ValueError):
    """A diagnosed environment, entrypoint or invocation configuration failure."""


class InfrastructureFailure(OSError):
    """Docker/service access failed, independently of the tool environment."""


def reset_observations(item):
    for key in ("image_id", "retention_tag", "cases", "validation", "examples", "dependency_observations",
                "installed_versions", "source_integrity", "error", "last_failure", "failure_kind", "example_counts", "acceptance",
                "process_scope", "process_cleanup", "reproducibility"):
        item.pop(key, None)
    item.update(cases=[], validation={layer: "not_verified" for layer in LAYERS}, examples=[])
    item.pop('historical_diagnostic',None)
    if item.get("status") in {"execution_passed", "execution_failed", "build_failed", "budget_exhausted"} and "locked_cases" in item:
        item["status"] = "prepared"


def archive_execution(root, prior):
    relative = "reports/runtime-history/" + uuid.uuid4().hex + ".json"
    write(root / relative, prior)
    return {"path": relative, "sha256": sha(root / relative), "status": prior.get("status"),
            "validation": prior.get("validation", {})}


def invalidate_current(root, report, error):
    relative = "reports/runtime-invalidated/" + report["validation_run_id"] + ".json"
    write(root / relative, {"reason": str(error), "tools": report["tools"], "validation_run_id": report["validation_run_id"]})
    report["invalidated_observations"] = {"path": relative, "sha256": sha(root / relative)}
    for item in report["tools"]:
        reset_observations(item)
        runner.clear_image(root, item['tool_id'])
        item.update(status="needs_review", failure_kind="integrity", error=str(error))
    report.update(status="needs_review", error=str(error), requires_prepare=True,
                  validation={layer: "not_verified" for layer in LAYERS})


def infrastructure_error(result):
    text = (result.get("stderr", "") + result.get("stdout", "")).lower()
    return any(message in text for message in ("cannot connect to the docker daemon", "docker engine unavailable",
               "permission denied while trying to connect", "dockerdesktoplinuxengine", "is the docker daemon running"))


def states(cases):
    result = {}
    for layer in LAYERS:
        group = [c for c in cases if c.get("layer") == layer and c.get("oracle_status") == "supported"]
        result[layer] = ("not_verified" if not group else
                         "passed" if all(c["status"] == "passed" for c in group) else "failed")
    return result


def diagnostic_result(result, limit=12000):
    """Decode a runner receipt before truncating logs; keep complete logs on disk."""
    observed=result
    try:
        nested=json.loads(result.get('stdout',''))
        if isinstance(nested,dict) and {'command','exit_code'} <= nested.keys():observed=nested
    except (ValueError,TypeError):pass
    stderr=str(observed.get('stderr',''))
    if observed is not result and result.get('stderr'):stderr+='\nRunner stderr: '+str(result['stderr'])
    stdout=str(observed.get('stdout',''))
    error_budget=min(len(stderr),limit*3//4)
    return {'command':observed.get('command',result.get('command')),'exit_code':observed.get('exit_code'),
            'runner_exit_code':result.get('exit_code'),'stderr':stderr[-error_budget:] if error_budget else '',
            'stdout':stdout[-(limit-error_budget):], 'logs_truncated':len(stderr)+len(stdout)>limit,
            'note':'Full build.json retained; these are decoded bounded diagnostic tails.'}


def historical_build_failure(root, tool_root, prior_item):
    """Use only a sealed failed Docker receipt for the unchanged current context.

    Called after the normal artifact/source guards, never for integrity failures,
    infra outages, timeouts, accepted packages or an unbuilt newer plan.
    """
    if not prior_item or prior_item.get('failure_kind') or prior_item.get('pending_attempt'):
        return None
    if prior_item.get('status')!='build_failed' and not (prior_item.get('status')=='budget_exhausted' and prior_item.get('last_failure')=='build_failed'):
        return None
    attempts=sorted((tool_root/'attempts').iterdir())
    builds=[a for a in attempts if (a/'build.json').exists()]
    if not builds:return None
    attempt=builds[-1]
    plans=[a for a in attempts if a.name<=attempt.name and (a/'environment_plan.json').exists()]
    if not plans:return None
    baseline=plans[-1]
    if read(baseline/'environment_plan.json')!=read(tool_root/'environment_plan.json'):
        return None
    if not (baseline/'context').is_dir() or files(baseline/'context')!=files(tool_root/'context'):
        return None
    build=read(attempt/'build.json')
    try:receipt=json.loads(build.get('stdout',''))
    except (ValueError,TypeError):return None
    if not isinstance(receipt,dict):return None
    if receipt.get('command',[])[:2]!=['docker','build'] or not receipt.get('exit_code') or infrastructure_error(build):
        return None
    return {'phase':'build_failed','build':diagnostic_result(build),
            'history':{'path':str((attempt/'build.json').relative_to(root)),'sha256':sha(attempt/'build.json'),
                       'policy':'Diagnostic reuse only; no historical pass counts as a current observation.'}}


def acceptance_inputs(root):
    """Mutable diagnostic logs are sealed at the end; executable inputs may not drift."""
    try:
        for tool in read(root/'runtime/package.json')['tools'].values():runner.context(root,tool)
    except (ValueError,OSError) as exc:raise IntegrityFailure('Context metadata invalid: '+str(exc)) from exc
    return {k: v for k, v in artifacts(root).items() if "/attempts/" not in k and k != "runtime/images.json"}


def examples(package):
    result = []
    for key, tool in package["tools"].items():
        result.append({**identity(key, "build"), "name": key + "-build", "argv": ["python", "runtime/runner.py", "build", "--tool", key], "expected_exit": 0})
        for case in read(package["_root"] / tool["context"] / tool["fixtures"])["cases"]:
            if case.get("oracle_status") == "supported":
                result.append({**identity(key, "case", case["name"]), "name": key + "-" + case["name"],
                               "argv": ["python", "runtime/runner.py", "case", "--tool", key, "--case", case["name"]],
                               "expected_exit": 0, "case": case["name"],
                               "timeout_seconds": case.get("timeout_seconds",30) * len(case.get("relation",{}).get("runs",[None]))})
        try:
            result.append(usage_example(package["_root"], key, tool))
        except NoUsageCase:
            if tool.get('acceptance_version') != 2:
                raise
            # Incomplete coverage must not invent a normal invocation example.
    return result


def refresh_docs(root, status):
    root = Path(root)
    package = read(root / "runtime/package.json")
    commands = read(root / "runtime/examples.json")["examples"]
    execution = read(root / "runtime/execution.json") if (root / "runtime/execution.json").exists() else {}
    # Use explicit status argument when invalidating an old execution report.
    layers = execution.get("validation", {}) if status == "execution_passed" else {k: "not_accepted" for k in LAYERS}
    lines = ["# Model-planned Docker execution package", "", f"Acceptance: `{status}`.",
             f"Acceptance rules: v{execution.get('acceptance_version', 1)}. Legacy evidence is not upgraded by inspection.",
             "Verified purposes: " + (json.dumps({t['tool_id']: t.get('acceptance', {}) for t in execution.get('tools', [])})
                                       if status == 'execution_passed' else 'not accepted'),
             "Only the declared tests were evaluated. Scientific validity and Agent effectiveness remain unverified.",
             "Behavior results cover listed cases/properties only, never all possible tool behavior.", "",
             "Requires Docker Linux amd64 and Python 3.11+ for the portable standard-library runner.",
             "Run from the Skill directory. Build can access the network. No host tool dependencies are required.",
             "The image is built locally; it is not embedded. Inference choices are proposals until tested.", "",
             "Build creates a candidate image and prints its immutable image ID; it does not replace acceptance. "
             "run/case/test use the accepted ID in runtime/images.json, never the mutable build tag. "
             "If no accepted binding exists, inputs change, or the retained image is unavailable, run prepare/validate on the build host. "
             "A rebuild alone does not accept a different image. Sealed legacy packages require regeneration with the current runner.", "",
             "## Validation scope", "", json.dumps(layers, ensure_ascii=False), "", "## Reproduce", ""]
    import shlex
    for command in commands:
        if command.get("kind") == "usage":
            continue
        lines += ["```powershell", shlex.join(command["argv"]), "```", "",
                  f"Expected runner exit: {command['expected_exit']}. Case commands check the tool's declared exit code and assertions.", ""]
    for key, tool in package["tools"].items():
        plan = read(root / f"runtime/tools/{key}/environment_plan.json")
        owned = [c for c in commands if c.get("tool_id") == key and c.get("kind") == "usage"]
        if not owned and tool.get('acceptance_version') == 2:
            cases = read(root / tool['context'] / tool['fixtures'])['cases']
            try:
                select_usage_case(tool, cases)
            except NoUsageCase:
                pass
            else:
                raise ValueError('Normal-case example is missing or has lost ownership metadata')
            lines += ['## ' + key, '', 'No verified normal invocation: acceptance coverage is incomplete.', '']
            continue
        if len(owned) != 1:
            raise ValueError('Examples lack explicit, unique tool/type identity; prepare with the current generator')
        example = owned[0]
        expected = usage_example(root, key, tool)
        if any(example.get(field) != expected.get(field) for field in ('tool_id', 'kind', 'case_id', 'example_id', 'case')):
            raise ValueError('Normal-case example ownership metadata does not match the selected locked case')
        lines += ["## " + key, "", "Entrypoint: `" + json.dumps(tool["entrypoint"]) + "`.",
                  "Output contract: " + plan["output_contract"],
                  "Runtime network: " + ("bridge; " + plan["network_reason"] if tool["runtime_network"] else "none (offline)."),
                  "Mounts: --input-dir is read-only at /input; --output-dir is writable at /output. "
                  "Results written to /output survive container removal. UID/GID is 10001. On POSIX, preparation creates new input directories/files as 0755/0644 and new output directories as 01777 (writable with sticky bit), regardless of umask. Existing directory/file permissions are preserved; an existing output directory must grant UID/GID 10001 write and search access.",
                  "### Complete invocation", "",
                  ("The commands below were validated together." if status == "execution_passed" else "Generated commands; acceptance is pending or failed.") +
                  " Replace the sample input after preparing it; keep container paths in tool arguments."]
        if example.get("preparation_argv"):
            lines += ["Create the sample input files and writable output directory:", "", "```powershell",
                      shlex.join(example["preparation_argv"]), "```", "",
                      "Prepared input content: " + json.dumps(example["input_files"], ensure_ascii=False), ""]
        lines += ["```powershell", shlex.join(example["argv"]), "```", "",
                  f"Expected tool exit: {example['expected_exit']}. stdout/stderr and persisted output are checked against `{example['case']}`."]
        if example.get("output_file"):
            lines += ["Persisted result: `" + example["output_dir"] + "/" + example["output_file"] + "`. It remains after the container is removed."]
        lines += ["",
                  "Exit codes and output interpretation are tool-specific; inspect the per-case contract and stdout/stderr.",
                  "Plan-declared limitations and unverified scope (recorded before execution; see current measured coverage above): " + json.dumps(plan["unverified_behavior"], ensure_ascii=False),
                  "Planning-time unresolved choices (historical, before execution; current results are in Validation scope): " + json.dumps(plan["unresolved"], ensure_ascii=False), ""]
    lines += ["## Evidence and recovery", "",
              "environment_plan.json records choices, dependency channels, inference/evidence and test rationale.",
              "Each tool's attempts/ retains prompts, receipts, complete plans, context snapshots, diffs, build logs and cases.",
              "runtime/execution.json records image IDs, available dependency versions, separate environment/interface/behavior status and Agent status.",
              "A candidate or regression oracle does not count as supported behavior evidence. Supported is an evidence classification, not independent human approval.",
              "Changes to source, bindings, plans, tests, runner or docs invalidate acceptance. Re-prepare after input changes; "
              "validate_runtime.py can resume unchanged failed packages with a fresh bounded budget. Previous attempts are retained.",
              "Missing resources require resolving the recorded blocker; repeated build retries cannot supply credentials or weights.", ""]
    lines += ["## Rebuild inputs and transfer", "",
              "See runtime/delivery.json for platform, immutable image IDs and recovery commands. Images are not embedded in this directory.",
              "The optional .skillnet/base-lock.json pins the manifest used by FROM. environment_plan.json records requested dependencies; execution.json reproducibility inventories record installed observations.",
              "pip freeze and system package lists are not complete locks. Conda explicit URLs/checksums do not retain remote artifacts or lock pip-installed additions. Source hashes identify selected local inputs, not every downloaded build dependency.",
              "Build dependency prefixes are explicitly declared in build_layout; legacy plans retain COPY-before-RUN ordering. No shell-text heuristic reorders commands.",
              "CPU, memory and PID settings constrain running containers. Build has a wall-time limit, but does not inherit those runtime resource limits.",
              "After transfer, load an exported image, then verify the exact recorded image ID. A matching tag alone is insufficient. If the ID or source identity cannot be verified, restore original inputs or prepare and revalidate a new package.", ""]
    (root / "DOCKER.md").write_text("\n".join(lines), encoding="utf-8")
    original = (root / "runtime/source-SKILL.md").read_text(encoding="utf-8")
    text = sync_skill(original, package, status)
    text = text.replace("Declared tool tests and documented examples passed.",
                        "Declared supported tool tests and documented examples passed; behavior coverage is limited to recorded cases/properties.")
    (root / "SKILL.md").write_text(text, encoding="utf-8")
    errors = format_check(root / "SKILL.md")
    if errors:
        raise ValueError("Skill format invalid after runtime synchronization: " + "; ".join(errors))


def sync(root, report):
    package = read(root / "runtime/package.json")
    write(root / "runtime/examples.json", {"examples": examples(dict(package, _root=root))})
    write(root / "runtime/execution.json", report)
    refresh_docs(root, report["status"])
    delivery={'schema_version':1,'platform_requirements':['Docker Linux amd64 engine','Host Python 3.11+'],
              'images_embedded':False,'tools':{},'validation_status':report['status'],
              'migration_note':'Original source/binding paths are host-specific. Restore them exactly or create new inputs and revalidate; never edit fingerprints to preserve acceptance.'}
    for key,tool in package['tools'].items():
        item=next((i for i in report.get('tools',[]) if i['tool_id']==key),{})
        image=item.get('image_id')
        delivery['tools'][key]={'platform':tool['platform'],'image_id':image,
            'input_fingerprint':runner.input_fingerprint(root,key),
            'base_lock':str(Path(tool['context'])/'.skillnet/base-lock.json') if (root/tool['context']/'.skillnet/base-lock.json').exists() else None,
            'save_argv':['docker','image','save','-o',key+'-image.tar',image] if image else None,
            'load_argv':['docker','image','load','-i',key+'-image.tar'],
            'inspect_argv':['docker','image','inspect',image] if image else None,
            'revalidate_argv':['python','creation_pipeline/validate_runtime.py',str(root)],
            'accepted':item.get('status')=='execution_passed'}
    write(root/'runtime/delivery.json',delivery)


def next_attempt(tool_root):
    folder = tool_root / "attempts"
    folder.mkdir(exist_ok=True, parents=True)
    n = len(list(folder.iterdir())) + 1
    result = folder / f"{n:04d}"
    result.mkdir()
    return result


def propose(source, config, tool_root, tool_id, opts, deadline, previous=None, locked=None, feedback=None):
    last = None
    acceptance_diagnostics = None
    for _ in range(opts["max_attempts"]):
        attempt = next_attempt(tool_root)
        p,index=None,None
        try:
            p, index, reason = planner.plan(source, config, attempt, opts, deadline, feedback, previous)
            old_files = files(tool_root / "context") if (tool_root / "context").exists() else {}
            old = read(tool_root / 'environment_plan.json') if (tool_root / 'environment_plan.json').exists() else None
            def audit_before_commit(staged, tool, proof):
                new_files = files(staged)
                write(attempt / 'diagnosis.json', {'reason': reason})
                write(attempt / 'changes.json', {'previous_plan_sha256': digest(old), 'new_plan_sha256': digest(p),
                      'changed_fields': [k for k in p if old is None or old.get(k) != p[k]],
                      'files_added': sorted(set(new_files) - set(old_files)),
                      'files_removed': sorted(set(old_files) - set(new_files)),
                      'files_modified': sorted(k for k in new_files if k in old_files and new_files[k] != old_files[k])})
                shutil.copytree(staged, attempt / 'context')
            tool, provenance = planner.materialize(source, config, tool_root / "context", tool_id, p, index,
                dict(opts, registry_seconds=remaining(deadline, opts["registry_seconds"])), locked, before_commit=audit_before_commit)
            if tool is None:
                write(attempt / 'diagnosis.json', {'reason': reason})
                target = attempt if old_files else tool_root
                write(target / "environment_plan.json", p)
                write(target / "provenance.json", provenance)
                return None, provenance, attempt
            return tool, provenance, attempt
        except planner.InputChanged as exc:
            write(attempt/'input-changed.json',{'error':str(exc)})
            raise IntegrityFailure(str(exc)) from exc
        except planner.BudgetExceeded:
            raise
        except planner.ModelUnavailable as exc:
            write(attempt / 'model-unavailable.json', {'phase':'model_service', 'error':str(exc),
                  'action':'Restore model access, then retry with a new bounded budget; no tool-plan repair attempted.'})
            raise
        except subprocess.TimeoutExpired as exc:
            raise planner.BudgetExceeded("Model request time budget exhausted") from exc
        except (ValueError, KeyError, TypeError) as exc:
            last = str(exc)
            acceptance_diagnostics = getattr(exc, 'diagnostics', None)
            retained={k:v for k,v in (feedback or {}).items() if k in {'rejected_plan','read_files','source_fingerprint'}}
            feedback = dict(retained,phase="static_plan_validation",error=last)
            if acceptance_diagnostics is not None:
                feedback['acceptance_diagnostics'] = acceptance_diagnostics
            if p is not None and index is not None:
                feedback.update(rejected_plan=p,read_files=index.get('read_files',[]),source_fingerprint=digest(index['files']))
            write(attempt / "rejection.json", {'phase':feedback['phase'],'error':last,
                  'acceptance_diagnostics':acceptance_diagnostics,
                  'rejected_plan_sha256':digest(p) if p is not None else None,'retained_read_files':feedback.get('read_files',[])})
            if time.monotonic() >= deadline:
                raise planner.BudgetExceeded("Planning time budget exhausted") from exc
    if acceptance_diagnostics is not None:
        raise planner.AcceptancePlanError(dict(acceptance_diagnostics, planning_attempts_exhausted=True))
    raise planner.PlanningError("Invalid model plans exhausted planning attempts: " + str(last))


def blocked_resource_review(root, job_id, bindings_path):
    """Guard an explicit re-evaluation; never replace tests or accepted siblings."""
    out=root/'runtime';prepared=read(out/'prepared.json')
    prior=read(out/'execution.json') if (out/'execution.json').exists() else None
    if prepared['job_id']!=job_id or Path(prepared['bindings_path']).resolve()!=bindings_path:
        raise IntegrityFailure('Resource review must use the original job and bindings')
    if prior and (prior.get('requires_prepare') or prior.get('prepared_sha256')!=digest(prepared)):
        raise IntegrityFailure('Previous integrity failure or changed preparation prevents resource review')
    if artifacts(root)!=(prior or prepared).get('artifacts'):
        raise IntegrityFailure('Generated inputs/evidence changed; resource review stopped')
    current_sources(prepared);acceptance_inputs(root)
    if prepared['status']!='blocked_resources' or read(out/'package.json')['tools']:
        raise ValueError('Resource review requires a wholly resource-blocked package; accepted/prepared siblings are preserved')
    result={}
    for item in prepared['tools']:
        if item.get('status')!='blocked_resources' or not item.get('blockers') or not item.get('source_inventory'):
            raise ValueError('Only source-backed resource blockers can be reviewed')
        tool_root=out/'tools'/item['tool_id']
        result[item['tool_id']]={'plan':read(tool_root/'environment_plan.json'),
                                'cases':read(tool_root/'provenance.json')['cases'],
                                'blockers':item['blockers']}
    if not result:raise ValueError('No source-backed resource blocker to review')
    return result


@preserve_runtime_on_failure
def prepare(candidate, job_id, bindings_path, *, budget_seconds=None, review_blocked=False):
    root, bindings_path = Path(candidate).resolve(), Path(bindings_path).resolve()
    settings = read(bindings_path)
    opts = planner.options(settings.get("planner", {}))
    if budget_seconds is not None:
        total=min(opts['total_seconds'],budget_seconds)
        if opts.get('validation_reserve_seconds',0)>=total:raise planner.BudgetExceeded('Remaining creation budget cannot provide the configured validation reserve')
        opts=planner.options(dict(opts,total_seconds=total))
    deadline = time.monotonic() + opts["total_seconds"]
    out = root / "runtime"
    if out.is_symlink():
        raise ValueError("runtime must not be a symlink")
    reviewed=blocked_resource_review(root,job_id,bindings_path) if review_blocked else {}
    original = (out / "source-SKILL.md").read_text(encoding="utf-8") if (out / "source-SKILL.md").exists() else (root / "SKILL.md").read_text(encoding="utf-8")
    if out.exists():
        # Preserve failed attempts when explicitly regenerating after source changes.
        saved = root / "reports" / ("runtime-archive-" + uuid.uuid4().hex)
        saved.parent.mkdir(exist_ok=True)
        shutil.move(str(out), str(saved))
    out.mkdir()
    (out / "source-SKILL.md").write_text(original, encoding="utf-8")
    report = {"acceptance_version": 2, "schema_version": 3, "backend": "docker", "status": "needs_review", "job_id": job_id,
              "candidate": root.name, "tools": [], "bindings_path": str(bindings_path),
              "bindings_sha256": sha(bindings_path), "options": opts, "agent_effect_status": "not_evaluated"}
    if reviewed:
        report['resource_review']={'previous_runtime':str(saved.relative_to(root)),
                                  'policy':'Real model necessity review; original test contracts remain locked.',
                                  'previous_plan_sha256':{k:digest(v['plan']) for k,v in reviewed.items()},
                                  'locked_cases_sha256':{k:digest(v['cases']) for k,v in reviewed.items()}}
    package = {"schema_version": 3, "image_binding_version": 1, "tools": {}}
    try:
        if format_check(root / "SKILL.md"):
            raise ValueError("Input Skill must pass existing format checks")
        from candidate_identity import resolve
        binding,association=resolve(settings,root,job_id)
        report['association']=association
        if binding.get("requirement") == "not_required" and not binding.get("tools"):
            report["status"] = "not_required"
        elif binding.get("requirement") != "required" or not binding.get("tools"):
            raise ValueError("Tool requirement unresolved")
        else:
            for key in dict.fromkeys(binding["tools"]):
                item = {"tool_id": key, "status": "needs_review"}
                report["tools"].append(item)
                try:
                    if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", key):
                        raise ValueError("Unsafe tool identifier")
                    config = settings["tools"][key]
                    source = (bindings_path.parent / config["root"]).resolve()
                    item.update(source_root=str(source), config=config.get("generation", {}),
                                source_inventory=planner.inventory(source, opts))
                    review=reviewed.get(key)
                    feedback=({'phase':'blocked_resources','blockers':review['blockers'],
                               'instruction':'Re-read source and determine necessity for this entrypoint. Record required_for_execution with evidence, keep availability truthful, retain all locked tests. Do not invent weights or expand supported scope.'}
                              if review else None)
                    tool, provenance, attempt = propose(source, config.get("generation", {}), out / "tools" / key,
                                                        key, opts, deadline-opts['validation_reserve_seconds'],
                                                        previous=review['plan'] if review else None,
                                                        locked=review['cases'] if review else None,feedback=feedback)
                    if tool is None:
                        item.update(status="blocked_resources", blockers=provenance["blockers"])
                    else:
                        package["tools"][key] = tool
                        item.update(status="prepared", locked_cases=provenance["cases"], pending_attempt=str(attempt.relative_to(root)))
                except IntegrityFailure as exc:
                    item.update(status='needs_review',failure_kind='integrity',error=str(exc))
                except planner.BudgetExceeded as exc:
                    item.update(status="budget_exhausted", error=str(exc))
                except planner.ModelUnavailable as exc:
                    item.update(status="blocked_resources", failure_kind="model_service", error=str(exc))
                except planner.AcceptancePlanError as exc:
                    item.update(status='validation_incomplete', failure_kind='acceptance_contract',
                                error=str(exc), acceptance_diagnostics=exc.diagnostics)
                except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
                    item.update(status="needs_review", error=str(exc))
            report["status"] = aggregate(t["status"] for t in report["tools"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report["error"] = str(exc)
    write(out / "package.json", package)
    shutil.copyfile(HERE / "runtime_package.py", out / "runner.py")
    # Preparation is not execution evidence.
    try:
        sync(root, report)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Rendering/integrity failures remain failures, with a durable preparation
        # record. Never leave a prepared tool apparently eligible for execution.
        report.update(status='needs_review', failure_kind='documentation', error=str(exc))
        for item in report['tools']:
            if item['status'] == 'prepared':
                item.update(status='needs_review', failure_kind='documentation', error=str(exc))
        withdraw_claims(root, 'needs_review')
    report["preparation_seconds"] = opts["total_seconds"] - max(0, deadline - time.monotonic())
    report["artifacts"] = artifacts(root)
    write(out / "prepared.json", report)
    (out / "execution.json").unlink(missing_ok=True)
    return report


@preserve_runtime_on_failure
def refresh_renderer(candidate, job_id, bindings_path, budget_seconds=None):
    """Explicit renderer repair with plan replay and identical locked tests.

    This is not a new model plan or a bypass for stale inputs. Old runtime is
    archived before regeneration and new execution is always required.
    """
    root=Path(candidate).resolve();out=root/'runtime'
    prepared=read(out/'prepared.json');prior=read(out/'execution.json') if (out/'execution.json').exists() else prepared
    if prepared['job_id']!=job_id or Path(prepared['bindings_path']).resolve()!=Path(bindings_path).resolve():
        raise IntegrityFailure('Renderer refresh requires original job and bindings')
    if prior.get('requires_prepare') or any(t.get('failure_kind')=='integrity' for t in prior.get('tools',[])):
        raise IntegrityFailure('Resolve recorded input integrity failure before renderer refresh')
    if prior is not prepared and prior.get('prepared_sha256')!=digest(prepared):
        raise IntegrityFailure('Prepared input changed')
    if artifacts(root)!=prior.get('artifacts'):
        raise IntegrityFailure('Generated inputs changed before renderer refresh')
    current_sources(prepared);acceptance_inputs(root)
    old_package=read(out/'package.json')
    if len(old_package['tools'])!=len(prior['tools']):
        raise ValueError('Renderer refresh requires complete prepared plans; no resource review')
    opts=planner.options(dict(prepared['options'],**({'total_seconds':budget_seconds} if budget_seconds else {})))
    started=time.monotonic();deadline=started+opts['total_seconds']
    saved=root/'reports'/('runtime-archive-'+uuid.uuid4().hex)
    saved.parent.mkdir(exist_ok=True)
    # The absolute source/target are confined to this candidate; no external move.
    if out.is_symlink() or not out.resolve().is_relative_to(root):raise IntegrityFailure('Invalid runtime path')
    shutil.move(str(out),str(saved));out.mkdir()
    shutil.copy2(saved/'source-SKILL.md',out/'source-SKILL.md')
    report=copy.deepcopy(prepared);report.update(status='needs_review',tools=[],options=opts,acceptance_version=2)
    report['renderer_refresh']={'previous_runtime':str(saved.relative_to(root)),
        'plan_replay':True,'new_model_planning':False,'reason':'Explicit generic renderer implementation correction; original plans and tests retained'}
    package={'schema_version':3,'image_binding_version':1,'tools':{}}
    for old in prior['tools']:
        key=old['tool_id'];tool_root=out/'tools'/key;tool_root.mkdir(parents=True)
        plan=read(saved/f'tools/{key}/environment_plan.json')
        provenance=read(saved/f'tools/{key}/provenance.json')
        item=copy.deepcopy(old);reset_observations(item)
        try:
            tool,proof=planner.materialize(Path(item['source_root']),item['config'],tool_root/'context',key,
                plan,provenance['source_inventory'],dict(opts,registry_seconds=remaining(deadline,opts['registry_seconds'])),item['locked_cases'])
            if tool is None or digest(proof['cases'])!=digest(item['locked_cases']):
                raise IntegrityFailure('Renderer refresh changed locked tests or resource scope')
            write(tool_root/'environment_plan.json',plan);write(tool_root/'provenance.json',proof)
            attempt=next_attempt(tool_root);write(attempt/'environment_plan.json',plan)
            write(attempt/'renderer-refresh.json',report['renderer_refresh'])
            shutil.copytree(tool_root/'context',attempt/'context')
            item.update(status='prepared',pending_attempt=str(attempt.relative_to(root)))
            package['tools'][key]=tool
        except (OSError,ValueError,KeyError,subprocess.TimeoutExpired) as exc:
            item.update(status='needs_review',error=str(exc))
        report['tools'].append(item)
    report['status']=aggregate(t['status'] for t in report['tools'])
    write(out/'package.json',package);shutil.copyfile(HERE/'runtime_package.py',out/'runner.py')
    sync(root,report);report['preparation_seconds']=time.monotonic()-started
    report['artifacts']=artifacts(root);write(out/'prepared.json',report)
    (out/'execution.json').unlink()
    return report


def current_sources(prepared):
    if sha(prepared["bindings_path"]) != prepared["bindings_sha256"]:
        raise IntegrityFailure("Bindings changed; prepare again")
    for item in prepared["tools"]:
        if "source_inventory" in item:
            current = planner.inventory(item["source_root"], prepared["options"])
            if any(current[k] != item["source_inventory"][k] for k in ("files", "excluded")):
                raise IntegrityFailure("Source files added, removed or changed; prepare again")


def remaining(deadline, ceiling):
    value = deadline - time.monotonic()
    if value <= 0:
        raise planner.BudgetExceeded("Total validation time budget exhausted")
    return max(1, min(int(value), ceiling))


def verify_examples(root, tool_id, deadline):
    """Run actual portable commands in a copied delivery, including persisted IO."""
    import tempfile
    observations = []
    with tempfile.TemporaryDirectory(prefix="skillnet-model-delivery-") as directory, runner.validation_scope(root, tool_id):
        copied = Path(directory) / "skill"
        # Do not recopy potentially large historical contexts.
        shutil.copytree(root, copied, ignore=shutil.ignore_patterns("attempts", "reports"))
        for example in read(root / "runtime/examples.json")["examples"]:
            if example.get("tool_id") != tool_id or example.get("kind") == "build":
                continue
            preparations = []
            if example.get("preparation_argv"):
                prepared = runner.process([sys.executable, *example["preparation_argv"][1:]], remaining(deadline, 30), cwd=copied)
                preparations.append(dict(prepared, **identity(tool_id, "prepare", example.get("case_id")),
                                         parent_example_id=example["example_id"]))
                if prepared["exit_code"]:
                    observations.append(dict(prepared, **identity(tool_id, example["kind"], example.get("case_id")),
                                             name=example["name"], preparation=preparations, executed=False, status="failed", phase="input_preparation"))
                    continue
            observed = runner.process([sys.executable, *example["argv"][1:]], remaining(deadline, read(root / "runtime/package.json")["tools"][tool_id].get("limits",{}).get("document_seconds",180)), cwd=copied)
            if infrastructure_error(observed):
                raise InfrastructureFailure('Docker unavailable during documented invocation: ' + observed.get('stderr', ''))
            ok = observed["exit_code"] == example["expected_exit"]
            if example.get("kind") == "usage":
                tool = read(copied / "runtime/package.json")["tools"][tool_id]
                case = next(c for c in read(copied / tool["context"] / tool["fixtures"])["cases"] if c["name"] == example["case_id"])
                text = observed["stdout"]
                if example.get("output_file"):
                    output = copied / example["output_dir"] / example["output_file"]
                    if output.is_file():
                        text = output.read_text(encoding="utf-8")
                        observed["persisted_output"] = text
                    else:
                        ok = False
                        observed["error"] = "Documented invocation did not persist the expected output: " + str(output)
                ok = ok and runner.output_matches(case, observed, text)
            observed.update(identity(tool_id, example["kind"], example.get("case_id")))
            observed.update(name=example["name"], documented_argv=example["argv"], execution_kind="run" if example["kind"] == "usage" else "case",
                            preparation=preparations, executed=True, status="passed" if ok else "failed")
            observations.append(observed)
    return observations


def validate(candidate, *, budget=None, repair_from_history=False, reuse_build=False):
    validation_started=time.monotonic()
    root = Path(candidate).resolve()
    prepared = read(root / "runtime/prepared.json")
    report = copy.deepcopy(prepared)
    report["prepared_sha256"] = digest(prepared)
    report["validation"] = {k: "not_verified" for k in LAYERS}
    report["validation_run_id"] = uuid.uuid4().hex
    overrides=budget or {}
    allowed={'total_seconds','model_timeout','build_seconds','max_attempts','context_chars','max_read_rounds','repair_reserve_seconds','document_seconds'}
    if set(overrides)-allowed:raise ValueError('Unsupported retry budget options: '+str(sorted(set(overrides)-allowed)))
    opts=planner.options(dict(prepared['options'],**overrides))
    report['effective_options']=opts
    report['budget_overrides']=overrides
    report['repair_from_history_requested']=bool(repair_from_history)
    deadline = time.monotonic() + opts["total_seconds"]
    try:
        prior = read(root / "runtime/execution.json") if (root / "runtime/execution.json").exists() else None
        if prior:
            report["previous_execution"] = archive_execution(root, prior)
        if prior is None:
            deadline -= prepared.get("preparation_seconds", 0)
        if prior and prior.get("requires_prepare"):
            raise IntegrityFailure("Previous stale-input failure requires prepare")
        if artifacts(root) != (prior["artifacts"] if prior else prepared["artifacts"]):
            raise IntegrityFailure("Generated artifacts changed; prepare again")
        if prior:
            # Retain added tests and advance audit directories on independent retries.
            report["tools"] = copy.deepcopy(prior["tools"])
        for item in report["tools"]:
            reset_observations(item)
            runner.clear_image(root, item['tool_id'])
        current_sources(prepared)
        package = read(root / "runtime/package.json")
        if package['tools'] and package.get('image_binding_version') != 1:
            raise IntegrityFailure('Legacy schema 3 runner lacks verified-ID binding; prepare with the current generator')
        if package["tools"]:
            try:
                preflight = runner.process(["docker", "info", "--format", "{{.ServerVersion}}"], remaining(deadline, 30))
            except OSError as exc:
                preflight = {"exit_code": 1, "stdout": "", "stderr": str(exc)}
            report["docker_preflight"] = preflight
            if preflight["exit_code"]:
                for item in report["tools"]:
                    if item["tool_id"] in package["tools"]:
                        item.update(status="blocked_resources", error="Docker engine unavailable; no dependency repair attempted")
                report["status"] = "blocked_resources"
                sync(root, report)
                report["artifacts"] = artifacts(root)
                write(root / "runtime/execution.json", report)
                return report
        for item in report["tools"]:
            key = item["tool_id"]
            if key not in package["tools"] or item.get("blockers"):
                continue
            try:
                for case in item.get('locked_cases',[]):planner.check_probe_syntax(case,package['tools'][key]['entrypoint'])
            except planner.PlanningError as exc:
                item.update(status='needs_review',failure_kind='locked_test_contract',error=str(exc),requires_probe_review=True)
                continue
            tool_root = root / "runtime/tools" / key
            tool = package["tools"][key]
            acceptance_inputs(root)
            expected_context = digest(files(tool_root / "context"))
            previous_item=next((t for t in prior.get('tools',[]) if t['tool_id']==key),None) if prior else None
            historical=historical_build_failure(root,tool_root,previous_item) if repair_from_history else None
            for number in range(opts["max_attempts"]):
                attempt = root / item.pop("pending_attempt") if "pending_attempt" in item else next_attempt(tool_root)
                reset_observations(item)
                runner.clear_image(root, key)
                try:
                    if number==0 and historical:
                        write(attempt/'history-handoff.json',historical)
                        item['historical_diagnostic']=historical['history']
                        current_sources(prepared)
                        p=read(tool_root/'environment_plan.json')
                        tool,provenance,repair=propose(Path(item['source_root']),item['config'],tool_root,key,opts,
                            deadline-opts.get('repair_reserve_seconds',0),p,item['locked_cases'],historical)
                        if tool is None:
                            item.update(status='blocked_resources',blockers=provenance['blockers'])
                            break
                        attempt=repair
                        item['locked_cases']=provenance['cases']
                        package['tools'][key]=tool
                        expected_context=digest(files(tool_root/'context'))
                    # Exact documented build command, with bounded time.
                    tool["limits"]["build_seconds"] = remaining(deadline, opts["build_seconds"])
                    tool["limits"]["document_seconds"] = opts['document_seconds']
                    package["tools"][key] = tool
                    write(root / "runtime/package.json", package)
                    write(root / "runtime/examples.json", {"examples": examples(dict(package, _root=root))})
                    immutable = acceptance_inputs(root)
                    command = [sys.executable, "runtime/runner.py", "build", "--tool", key]
                    build_started=time.monotonic()
                    reusable = (reuse_build and number == 0 and not historical and previous_item
                                and previous_item.get('image_id')
                                and previous_item.get('built_context_sha256') == digest(files(tool_root/'context')))
                    if reusable:
                        # Current sources/artifacts were checked above. The exact ID,
                        # entrypoint, source bytes and ALL locked cases are rechecked below.
                        existing = runner.process(['docker','image','inspect',previous_item['image_id']],remaining(deadline,30))
                        reusable = existing['exit_code'] == 0
                    if reusable:
                        build = {'command':command,'exit_code':0,'stdout':json.dumps({'image_id':previous_item['image_id']}),
                                 'stderr':'','reused_build':True,'previous_execution':report['previous_execution']}
                    else:
                        build = runner.process(command, remaining(deadline, opts["build_seconds"] + 10), cwd=root)
                    build['elapsed_seconds']=round(time.monotonic()-build_started,3)
                    write(attempt / "build.json", build)
                    item["status"] = "build_failed"
                    if build["exit_code"] and infrastructure_error(build):
                        raise InfrastructureFailure("Docker became unavailable during build: " + build.get("stderr", ""))
                    if build["exit_code"] == 0:
                        try:
                            built_id = json.loads(build['stdout'])['image_id']
                        except (ValueError, KeyError, TypeError) as exc:
                            raise RepairableFailure('Build runner did not provide its immutable image ID') from exc
                        if not re.fullmatch(r'sha256:[0-9a-f]{64}', built_id):
                            raise RepairableFailure('Build runner returned an invalid image ID')
                        inspected = runner.process(["docker", "image", "inspect", built_id], remaining(deadline, 30))
                        if inspected["exit_code"]:
                            if infrastructure_error(inspected):
                                raise InfrastructureFailure("Docker image inspection unavailable: " + inspected["stderr"])
                            raise RepairableFailure("Image inspect failed: " + inspected["stderr"])
                        info = json.loads(inspected["stdout"])[0]
                        if info['Id'] != built_id:
                            raise IntegrityFailure('Inspected image ID differs from this build receipt')
                        if info["Os"] + "/" + info["Architecture"] != tool["platform"] or info["Config"]["Entrypoint"] != tool["entrypoint"]:
                            raise RepairableFailure("Image platform/entrypoint mismatch")
                        tag = "skillnet-runtime:" + uuid.uuid4().hex
                        tagged = runner.process(["docker", "tag", info["Id"], tag], remaining(deadline, 30))
                        if tagged["exit_code"]:
                            raise InfrastructureFailure("Cannot retain verified image: " + tagged.get("stderr", ""))
                        item.update(image_id=info["Id"], retention_tag=tag,
                                    built_context_sha256=digest(files(tool_root/'context')))
                        # Record versions from the image, never convert them into behavioral oracles.
                        versions = "python -c 'import sys,importlib.metadata as m; print(sys.version); print(sorted((d.metadata.get(\"Name\"),d.version) for d in m.distributions()))' 2>/dev/null; command -v conda >/dev/null && conda list --json; command -v dpkg-query >/dev/null && dpkg-query -W; true"
                        item["installed_versions"] = runner.run(tool, info["Id"], ["-c", versions], entrypoint="/bin/sh", timeout=remaining(deadline, 30))
                        from runtime_reproducibility import observe
                        item["reproducibility"] = observe(tool, info, tool_root, deadline)
                        write(attempt / "reproducibility.json", item["reproducibility"])
                        # RUN may install/compile but must not patch the supplied implementation.
                        import shlex
                        source_files = read(tool_root / "environment_plan.json")["source_files"]
                        if source_files:
                            checksum = runner.run(tool, info["Id"], ["-c", "cd /opt/skill && sha256sum -- " + " ".join(shlex.quote(p) for p in source_files)],
                                                  entrypoint="/bin/sh", timeout=remaining(deadline, 30))
                            item["source_integrity"] = checksum
                            actual = dict((line[66:], line[:64]) for line in checksum["stdout"].splitlines() if len(line) > 66)
                            expected = {p: sha(tool_root / "context" / p) for p in source_files}
                            if checksum["exit_code"] or actual != expected:
                                if infrastructure_error(checksum):
                                    raise InfrastructureFailure("Docker unavailable during source integrity check")
                                raise IntegrityFailure("Build modified source files or source checksum probe unavailable")
                        observations = []
                        for case in read(tool_root / "context" / tool["fixtures"])["cases"]:
                            remaining(deadline, 60)
                            observed = runner.run_case(root, tool, info["Id"], case, deadline=deadline,
                                artifact_dir=attempt/'case-artifacts'/digest(case['name'])[:16])
                            observations.append(observed)
                            if infrastructure_error(observed):
                                item.update(cases=observations, validation=states(observations))
                                raise InfrastructureFailure("Docker unavailable during container tests")
                        item.update(cases=observations, validation=states(observations))
                        write(attempt / "tests.json", {"cases": observations, "validation": item["validation"]})
                        failed = [c for c in observations if c.get("oracle_status") == "supported" and c["status"] != "passed"]
                        item["status"] = "execution_failed" if failed else "execution_passed"
                        if tool.get('acceptance_version') == 2:
                            item['acceptance'] = runner.acceptance_coverage(tool, item['locked_cases'], observations)
                            if not failed and not item['acceptance']['complete']:
                                item['status'] = 'validation_incomplete'
                                write(attempt / 'result.json', item)
                                break
                        item["dependency_observations"] = [c for c in observations if c.get("layer") == "environment"]
                        if item["status"] == "execution_passed":
                            runner.pin_image(root, key, info['Id'], tag, report['validation_run_id'])
                            item["examples"] = [dict(build, **identity(key, "build"), name=key + "-build", documented_argv=["python", "runtime/runner.py", "build", "--tool", key], status="passed")]
                            item["examples"] += verify_examples(root, key, deadline)
                            item["example_counts"] = counts(item["examples"])
                            if any(e["status"] != "passed" for e in item["examples"]):
                                item["status"] = "execution_failed"
                        if item["status"] == "execution_passed":
                            runner.accept_image(root, key)
                            write(attempt / "result.json", item)
                            if acceptance_inputs(root) != immutable:
                                raise IntegrityFailure("Executable inputs changed during validation")
                            break
                    if acceptance_inputs(root) != immutable:
                        raise IntegrityFailure("Executable inputs changed during validation")
                    write(attempt / "result.json", item)
                    if number + 1 == opts["max_attempts"]:
                        item.update(status="budget_exhausted", last_failure=item["status"], error="Build/repair attempt budget exhausted")
                        break
                    feedback = {"phase": item["status"], "build": diagnostic_result(build),
                                "cases": [{k: (v[-5000:] if isinstance(v, str) else v) for k, v in c.items()}
                                          for c in item.get("cases", [])],
                                "examples": [{k: (v[-5000:] if isinstance(v, str) else v) for k, v in e.items()}
                                             for e in item.get("examples", [])], "locked_tests": {
                                    'count':len(item['locked_cases']),'sha256':digest(item['locked_cases']),
                                    'names':[c['name'] for c in item['locked_cases']], 'policy':'Exact immutable contracts enforced by host; never patch tests.'}}
                    current_sources(prepared)
                    p = read(tool_root / "environment_plan.json")
                    tool, provenance, repair = propose(Path(item["source_root"]), item["config"], tool_root, key, opts,
                                                       deadline-opts.get('repair_reserve_seconds',0), p, item["locked_cases"], feedback)
                    if tool is None:
                        item.update(status="blocked_resources", blockers=provenance["blockers"])
                        break
                    item["pending_attempt"] = str(repair.relative_to(root))
                    # Original tests and all accepted model assertions are locked across repairs.
                    item["locked_cases"] = provenance["cases"]
                    package["tools"][key] = tool
                    write(root / "runtime/package.json", package)
                    expected_context = digest(files(tool_root / "context"))
                except planner.BudgetExceeded as exc:
                    item.update(status="budget_exhausted", error=str(exc))
                    write(attempt / "result.json", item)
                    break
                except planner.ModelUnavailable as exc:
                    item.update(status="blocked_resources", failure_kind="model_service", error=str(exc))
                    write(attempt / "result.json", item)
                    break
                except IntegrityFailure as exc:
                    item.update(status="needs_review", failure_kind="integrity", error=str(exc))
                    write(attempt / "result.json", item)
                    raise
                except InfrastructureFailure as exc:
                    item.update(status="blocked_resources", failure_kind="infrastructure", error=str(exc))
                    write(attempt / "result.json", item)
                    break
                except RepairableFailure as exc:
                    item.update(status="execution_failed", failure_kind="configuration", error=str(exc))
                    write(attempt / "result.json", item)
                    if number + 1 == opts["max_attempts"]:
                        item.update(status="budget_exhausted", last_failure="execution_failed")
                        break
                    if acceptance_inputs(root) != immutable:
                        raise IntegrityFailure("Executable inputs changed during failed validation")
                    current_sources(prepared)
                    p = read(tool_root / "environment_plan.json")
                    tool, provenance, repair = propose(Path(item["source_root"]), item["config"], tool_root, key, opts,
                                                       deadline-opts.get('repair_reserve_seconds',0), p, item["locked_cases"], {"phase": "configuration", "error": str(exc)})
                    if tool is None:
                        item.update(status="blocked_resources", blockers=provenance["blockers"])
                        break
                    item.update(pending_attempt=str(repair.relative_to(root)), locked_cases=provenance["cases"])
                    package["tools"][key] = tool
                    write(root / "runtime/package.json", package)
                    expected_context = digest(files(tool_root / "context"))
                except subprocess.TimeoutExpired as exc:
                    item.update(status="budget_exhausted", error="Build/test request timed out: " + str(exc),
                                process_cleanup=getattr(exc, "cleanup", []), process_scope=getattr(exc, "scope", None))
                    def timeout_text(value):
                        return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''
                    write(attempt / 'timeout.json', {'command':exc.cmd, 'timeout_seconds':exc.timeout,
                        'stdout':timeout_text(exc.output), 'stderr':timeout_text(exc.stderr),
                        'scope':getattr(exc,'scope',None), 'cleanup':getattr(exc,'cleanup',[])})
                    write(attempt / "result.json", item)
                    break
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    item.update(status="build_failed" if "image_id" not in item else "execution_failed", error=str(exc), failure_kind="unclassified")
                    write(attempt / "result.json", item)
                    break
            if digest(files(tool_root / "context")) != expected_context:
                raise IntegrityFailure("Context changed while building/testing")
            if item['status'] != 'execution_passed':
                runner.clear_image(root, key)
        current_sources(prepared)
        report["status"] = aggregate(t["status"] for t in report["tools"]) if report["tools"] else prepared["status"]
        for layer in LAYERS:
            values = [t.get("validation", {}).get(layer, "not_verified") for t in report["tools"]]
            report["validation"][layer] = ("failed" if "failed" in values else "passed" if values and all(v == "passed" for v in values)
                                              else "not_verified" if not values or all(v == "not_verified" for v in values) else "partial_or_unverified")
    except IntegrityFailure as exc:
        invalidate_current(root, report, exc)
    except planner.BudgetExceeded as exc:
        report.update(status="budget_exhausted", error=str(exc))
    except planner.ModelUnavailable as exc:
        # A model failure inside the configuration-repair exception branch also
        # reaches here. Retain the build/tests, but revoke any provisional image.
        item.update(status="blocked_resources", failure_kind="model_service", error=str(exc))
        runner.clear_image(root, item['tool_id'])
        report.update(status="blocked_resources", error=str(exc))
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        report.update(status="needs_review", error=str(exc), requires_prepare=True)
    try:
        sync(root, report)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report.update(status="needs_review", error=str(exc), requires_prepare=True)
        withdraw_claims(root, report["status"])
    report['validation_seconds']=round(time.monotonic()-validation_started,3)
    report["artifacts"] = artifacts(root)
    write(root / "runtime/execution.json", report)
    return report


def evidence(candidate):
    root = Path(candidate).resolve()
    try:
        report = read(root / "runtime/execution.json")
        prepared = read(root / "runtime/prepared.json")
        package = read(root / 'runtime/package.json')
        if package['tools'] and package.get('image_binding_version') != 1:
            raise ValueError('Legacy schema 3 runner lacks verified-ID binding; prepare again, sealed history is unchanged')
        if report["prepared_sha256"] != digest(prepared) or report["artifacts"] != artifacts(root):
            raise ValueError("Runtime artifacts or preparation changed")
        current_sources(prepared)
        if report["status"] == "execution_passed":
            if not report["tools"] or any(t["status"] != "execution_passed" for t in report["tools"]):
                raise ValueError("Incomplete tool evidence")
            for item in report["tools"]:
                if report.get('acceptance_version') == 2:
                    tool = package['tools'][item['tool_id']]
                    coverage = runner.acceptance_coverage(tool, item['locked_cases'], item.get('cases', []))
                    if not coverage['complete']:
                        raise ValueError('Current acceptance coverage incomplete')
                if runner.verified_image(root, item['tool_id']) != item['image_id']:
                    raise ValueError('Runner and acceptance image references differ')
        report.setdefault('acceptance_version', 1)
        report['current_acceptance_validated'] = report['acceptance_version'] == 2 and report['status'] == 'execution_passed'
        return report
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        return {"schema_version": 3, "backend": "docker", "status": "needs_review", "error": str(exc),
                "validation": {k: "not_verified" for k in LAYERS}, "agent_effect_status": "not_evaluated"}
