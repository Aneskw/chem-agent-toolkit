"""Local Linux/amd64 Docker build and migrated business-test executor."""
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from creation_pipeline.artifacts.evidence import verify
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.contracts import fingerprint
from creation_pipeline.records import write_json, read_json, redact, now, file_digest, has_link


def process(args, timeout=60, cwd=None):
    try:
        from .runner import process as supervised_process
        p = supervised_process(args, timeout, cwd)
        return dict(p, stdout=redact(p['stdout']), stderr=redact(p['stderr']))
    except (OSError, subprocess.TimeoutExpired) as exc:
        def text(value):
            return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''
        return {"exit_code": None, "stdout": redact(text(getattr(exc,'output',''))),
                "stderr": redact(text(getattr(exc,'stderr','')) or str(exc)), "error": type(exc).__name__,
                "cleanup": getattr(exc,'cleanup',[]), "scope": getattr(exc,'scope',None)}


def gap(code, detail, lane="environment"):
    unsupported = {'platform_unsupported', 'unsupported_resource', 'resource_mount_unresolved',
                   'credential_delivery_unresolved', 'service_unverified'}
    unresolved = {'resources_unknown', 'requirements_unknown', 'plan_unresolved', 'resource_binding_changed', 'draft_only'}
    temporary = {'docker_unavailable', 'memory_insufficient', 'cpu_insufficient', 'resource_missing', 'credential_missing',
                 'base_image_unresolved', 'base_image_unavailable'}
    kind = ('unsupported_contract' if code in unsupported else 'unresolved_input' if code in unresolved
            else 'temporary_resource' if code in temporary else 'caller_limit' if code == 'explicit_budget' else 'failure')
    return {"code": code, "detail": detail, "repair_lane": lane, 'blocker_kind': kind}


def base_image_reference(reference):
    """The repository part of an image reference (tag and digest removed)."""
    reference = str(reference).split('@')[0]
    last = reference.rsplit('/', 1)[-1]
    return reference.rsplit(':', 1)[0] if ':' in last else reference


def pinned_base_gap(pin, probe_timeout=30):
    """A pinned base image must still resolve locally before a build reuses it."""
    if not isinstance(pin, dict) or not pin.get('repo_digest'):
        return None
    probe = process(['docker', 'image', 'inspect', pin['repo_digest'], '--format', '{{.Id}}'], probe_timeout)
    if probe['exit_code'] != 0:
        return gap('base_image_unavailable',
                   'Pinned base image is not present locally: ' + str(pin['repo_digest']))
    return None


def binding_identity(request):
    return {k: v for k, v in asdict(request).items() if k not in {"frozen_directory", "attempt_directory"}}


class LocalExecutor:
    def __init__(self, resource_refs=None, probe_timeout=30, deadline=None):
        # Host paths and credential VALUES are never written to the frozen plan.
        self.resource_refs = resource_refs or {}
        self.probe_timeout = probe_timeout
        self.deadline = deadline

    def host(self):
        probe = process(["docker", "info", "--format", "{{json .}}"], self.probe_timeout)
        result = {"observed_at": now(), "backend": "local-docker", "status": "unavailable", "gaps": []}
        if probe["exit_code"] != 0:
            result["gaps"] = [gap("docker_unavailable", probe["stderr"])]
            return result
        try:
            info = json.loads(probe["stdout"])
            result.update(platform=info["OSType"] + "/" + info["Architecture"],
                          memory_bytes=info["MemTotal"], cpus=info["NCPU"], engine_id=info["ID"], server_version=info["ServerVersion"])
            if info["OSType"] != "linux" or info["Architecture"] not in {"x86_64", "amd64"}:
                result["gaps"].append(gap("platform_unsupported", "First implementation requires local Linux amd64 Docker"))
            result["status"] = "available" if not result["gaps"] else "unavailable"
        except (ValueError, KeyError, TypeError):
            result["gaps"].append(gap("docker_probe_unknown", "Docker returned incomplete host facts"))
        return result

    def resolve_base_image(self, reference, timeout=120):
        """Resolve a base image reference to the digest a build must reuse.

        Pulling first makes the resolved identity an observed fact rather than a tag
        that can move between builds. Failure blocks preparation: pinning that is not
        verified would read as a reproducibility guarantee the build does not have.
        A registry that this network cannot reach does not invalidate an identity that is
        already local: the repository digest of a cached image is the same observed fact,
        and the record states that it came from the local cache instead of the registry.
        """
        from .preparation import RuntimeBlocked
        pull = process(['docker', 'pull', reference], max(1, int(timeout)))
        if pull['exit_code'] != 0:
            cached = self._local_base_image(reference, min(max(1, int(timeout)), 60))
            if cached:
                return dict(cached, resolved_from='local_cache')
            raise RuntimeBlocked('base_image_unresolved',
                                 'Base image could not be pulled and has no cached repository digest: '
                                 + redact(pull['stderr'])[-300:], 'environment')
        pinned = self._local_base_image(reference, min(max(1, int(timeout)), 60))
        if not pinned:
            raise RuntimeBlocked('base_image_unresolved',
                                 'Base image has no verifiable repository digest: ' + str(reference), 'environment')
        return dict(pinned, resolved_from='registry')

    def _local_base_image(self, reference, timeout):
        """The repository digest an already-present image records, if it has one."""
        info = process(['docker', 'image', 'inspect', reference, '--format', '{{json .RepoDigests}}'], timeout)
        try:
            digests = json.loads(info['stdout']) if info['exit_code'] == 0 else None
        except ValueError:
            digests = None
        repo = base_image_reference(reference)
        digest = next((str(item).split('@', 1)[1] for item in (digests or [])
                       if str(item).startswith(repo + '@') and re.fullmatch(r'sha256:[0-9a-f]{64}', str(item).split('@', 1)[1])),
                      None)
        if not digest:
            return None
        return {'reference': str(reference), 'repository': repo, 'digest': digest,
                'repo_digest': repo + '@' + digest}

    def inputs(self, request):
        if request.executor_kind != 'local-docker' or request.target_id != 'local':
            raise ValueError('Remote execution is not implemented or authorized by this local adapter')
        record = verify(request.frozen_directory, request.freeze_sha256)
        d = record["delivery"]
        from creation_pipeline.contracts import runtime_request
        if runtime_request(d, request.frozen_directory, request.freeze_sha256, request.attempt_directory) != request:
            raise ValueError("Request does not match frozen input bindings")
        materials = Path(request.frozen_directory) / "runtime"
        env = d["inputs"]["environment"]["payload"]
        if not env or sorted(manifest(materials), key=lambda f: f['path']) != sorted(env["materials"], key=lambda f: f['path']):
            raise ValueError("Runtime materials differ from the frozen environment plan")
        if env.get('plan'):
            from .entry import verify_material
            verify_material(Path(request.frozen_directory) / 'package', d['inputs']['bindings']['payload'], materials / 'context')
        return record, env, materials

    def preflight(self, request):
        record, env, _ = self.inputs(request)
        host = dict(self.host()) if env.get("plan") else {"status": "not_checked", "observed_at": now(), "gaps": []}
        gaps = list(host["gaps"])
        plan = env.get("plan")
        delivery = record['delivery']
        if env.get('base_image'):
            # A pinned base image is part of the frozen identity; verify it before build.
            pinned = pinned_base_gap(env['base_image'], self.probe_timeout)
            if pinned:
                gaps.append(pinned)
        if delivery['mode'] != 'normal':
            gaps.append(gap('draft_only', 'Drafts cannot execute Docker builds through this adapter', 'requirement'))
        if delivery['inputs']['requirement']['status'] != 'required':
            gaps.append(gap('requirements_unknown', 'A source-bound required execution scope must be established before building', 'requirement'))
        if not plan:
            gaps += record.get("runtime_preparation", {}).get("gaps", [])
            gaps.append(gap("plan_unresolved", "No validated environment plan"))
        else:
            if self.deadline is not None and time.monotonic() >= self.deadline:
                gaps.append(gap("explicit_budget", "Explicit runtime time limit reached"))
            # General scientific/test limitations are preserved, not confused with
            # missing execution resources. The explicit resource assessment governs.
            assessment = plan.get("resource_assessment", {})
            if assessment.get("status") != "complete":
                gaps.append(gap("resources_unknown", "Resource requirement assessment is incomplete", "requirement"))
            if host["status"] == "available":
                if host["memory_bytes"] < assessment.get("memory_bytes", 0):
                    gaps.append(gap("memory_insufficient", "Docker engine memory below declared requirement"))
                if host["cpus"] < assessment.get("cpus", 0):
                    gaps.append(gap("cpu_insufficient", "Docker engine CPU count below declared requirement"))
            for r in plan["resources"]:
                if not r["required_for_execution"]:
                    continue
                kind, name = r["kind"], r["description"]
                ref = self.resource_refs.get(name, {})
                binding = {k: v for k, v in ref.items() if k in {"sha256", "env"}}
                if binding != env.get("resource_inputs", {}).get(name, {}):
                    gaps.append(gap("resource_binding_changed", name + ": prepare a runtime revision for changed resource identity"))
                    continue
                # Never trust model-generated available=true as a host observation.
                if kind in {"weight", "data"}:
                    path = Path(ref.get("path", ""))
                    expected = ref.get("sha256")
                    if not expected or not path.is_file() or has_link(path) or file_digest(path) != expected:
                        gaps.append(gap("resource_missing", kind + ": " + name + " (verified file reference required)"))
                    gaps.append(gap("resource_mount_unresolved", name + " (external resource mount contract is not implemented)"))
                elif kind == "credential":
                    key = ref.get("env")
                    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) or not os.environ.get(key):
                        gaps.append(gap("credential_missing", name + " (environment reference missing)"))
                    gaps.append(gap("credential_delivery_unresolved", name + " (secret delivery is not implemented)"))
                elif kind == "network":
                    # Build downloads are verified by the actual build; runtime network
                    # must be checked by stage-three execution, not presumed available.
                    gaps.append(gap("service_unverified", name + " (runtime network verification not implemented)"))
                else:
                    gaps.append(gap("unsupported_resource", kind + ": " + name + " (no compatible local verifier)"))
        host['docker_status'] = host['status']
        host['status'] = ('not_checked' if not plan else 'unavailable') if gaps else 'available'
        host['resource_gaps'] = [g['code'] for g in gaps]
        return {"host": host, "gaps": gaps, "planning_limitations": plan.get("unresolved", []) if plan else [],
                "status": "runtime_blocked" if gaps else "prepared"}

    def build(self, request):
        record, env, materials = self.inputs(request)
        attempt = Path(request.attempt_directory)
        attempt.mkdir(parents=True, exist_ok=False)
        receipt = {"version": 1, "backend": "local-docker", "request": binding_identity(request), "started_at": now(),
                   "status": "runtime_blocked", "execution_status": "not_run", "business_acceptance": "not_run", "image_id": None}
        preflight = self.preflight(request)
        receipt.update(preflight)
        write_json(attempt / 'attempt-start.json', receipt)
        logs = []
        if preflight["gaps"]:
            receipt["execution_status"] = "runtime_blocked"
        else:
            tag = "chem-integrated:" + request.revision_id[4:28] + "-" + uuid.uuid4().hex[:8]
            from .shared_environment import resolve, SharedEnvironmentError
            timeout = env["limits"]["build_seconds"]
            build_deadline = time.monotonic() + timeout
            if self.deadline is not None:
                build_deadline = min(build_deadline, self.deadline)
            try:
                context, shared, shared_logs = resolve(materials, None,
                                                      preflight['host'], process, build_deadline, attempt)
                if time.monotonic() >= build_deadline:
                    raise SharedEnvironmentError('Build deadline reached before tool image build', shared_logs)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                logs.extend(getattr(exc, 'logs', []))
                status = getattr(exc, 'status', 'runtime_blocked')
                receipt.update(status=status, execution_status=status,
                               gaps=[gap('docker_build_failed' if status == 'build_failed'
                                         else 'shared_environment_unavailable', redact(str(exc)))], finished_at=now())
                logs.append({'exit_code': None, 'stdout': '', 'stderr': redact(str(exc))})
                self.inputs(request)
                write_json(attempt / 'build-log.json', logs)
                receipt['log_sha256'] = file_digest(attempt / 'build-log.json')
                write_json(attempt / 'receipt.json', receipt)
                return receipt
            logs.extend(shared_logs)
            receipt['shared_environment'] = shared
            command = ["docker", "build", "--platform", "linux/amd64", "--iidfile", str(attempt / "image.id"),
                       "--label", "chem.revision=" + request.revision_id,
                       "--label", "chem.environment=" + request.environment_fingerprint,
                       "--tag", tag, str(context)]
            timeout = max(.1, build_deadline - time.monotonic())
            logs.append(process(command, timeout))
            receipt.update(status="build_failed", execution_status="build_failed", tag=tag)
            if logs[-1]["exit_code"] == 0:
                try:
                    image_id = (attempt / "image.id").read_text().strip()
                    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
                        raise ValueError("Docker did not return an immutable image ID")
                    inspection = process(["docker", "image", "inspect", image_id], self.probe_timeout)
                    logs.append(inspection)
                    details = json.loads(inspection["stdout"])[0]
                    plan = env["plan"]
                    from .shared_environment import inheritance_matches
                    if not inheritance_matches(shared, details):
                        raise ValueError('Built tool image did not inherit the resolved shared environment layers/config')
                    if (inspection["exit_code"] != 0 or details["Id"] != image_id or details["Os"] != "linux" or details["Architecture"] != "amd64"
                            or details["Config"]["Entrypoint"] != plan["entrypoint"]
                            or details["Config"]["Labels"].get("chem.revision") != request.revision_id
                            or details["Config"]["Labels"].get("chem.environment") != request.environment_fingerprint):
                        raise ValueError("Built image does not match bound plan")
                    # Inspect the delivered bytes in the image without running its code.
                    container = "chem-inspect-" + uuid.uuid4().hex
                    created = process(["docker", "create", "--name", container, '--label', 'skillnet.scope=' + attempt.name, image_id], self.probe_timeout)
                    logs.append(created)
                    try:
                        if created["exit_code"] != 0:
                            raise ValueError("Could not inspect image filesystem")
                        copied = process(["docker", "cp", container + ":/opt/skill/package", str(attempt / "image-package")], self.probe_timeout)
                        logs.append(copied)
                        if copied["exit_code"] != 0 or manifest(attempt / "image-package") != record["delivery"]["inputs"]["files"]:
                            raise ValueError("Build modified delivered source/support files; environment repair required")
                    finally:
                        logs.append(process(["docker", "rm", "-f", container], self.probe_timeout))
                    receipt.update(status="built", execution_status="not_run", image_id=image_id,
                                   image={k: details.get(k) for k in ("Id", "RepoDigests", "Os", "Architecture", "Created")})
                except (OSError, ValueError, KeyError, IndexError) as exc:
                    receipt["gaps"].append(gap("image_integrity_failed", redact(str(exc))))
            else:
                receipt["gaps"].append(gap("docker_build_failed", "Actual Docker build failed; see build-log.json"))
        # Recheck the complete frozen input after building, not just before it.
        self.inputs(request)
        write_json(attempt / "build-log.json", logs)
        receipt.update(finished_at=now(), log_sha256=file_digest(attempt / "build-log.json"))
        write_json(attempt / "receipt.json", receipt)
        return receipt

    def validate(self, request, build_receipt=None):
        from .execution import validate
        build_receipt = build_receipt or read_json(Path(request.attempt_directory) / 'receipt.json')
        return validate(self, request, build_receipt)

    def verify_current(self, request, evidence):
        self.inputs(request)
        host = self.preflight(request)
        if evidence.get("request") != binding_identity(request) or evidence.get("status") != "built":
            return {"status": "unavailable", "reason": "No matching built image receipt"}
        result = process(["docker", "image", "inspect", "--format", "{{.Id}}", evidence["image_id"]], self.probe_timeout)
        tag = process(["docker", "image", "inspect", "--format", "{{.Id}}", evidence.get('tag', '')], self.probe_timeout)
        return {"status": "available" if not host["gaps"] and result["exit_code"] == 0 and result["stdout"].strip() == evidence["image_id"]
                and tag['exit_code'] == 0 and tag['stdout'].strip() == evidence['image_id'] else "unavailable",
                "observed_at": now(), "preflight": host, "business_acceptance": "not_run"}
