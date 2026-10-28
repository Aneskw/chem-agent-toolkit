"""Transactional dual-zone library. Catalog replacement is the commit point.

Readers share the writer lock; interrupted updates have a recovery journal.
An abandoned lock must be inspected/removed only after its owner has stopped.
"""
import copy
import json
import re
import shutil
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from creation_pipeline.artifacts.package import manifest
from creation_pipeline.artifacts.evidence import verify
from creation_pipeline.contracts import qualify
from creation_pipeline.records import read_json, write_json, safe_relative, has_link, now


def slug(value):
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:70].rstrip("-")
    if not value:
        raise ValueError("Batch label needs a readable ASCII name")
    return value


def remove(root, path):
    path = safe_relative(root, Path(path).relative_to(root).as_posix())
    if path.exists():
        manifest(path)  # Check every descendant for links before recursive removal.
        shutil.rmtree(path)


def catalog(root):
    path = safe_relative(root, "catalog.json")
    value = read_json(path) if path.exists() else {"version": 2, "transaction": None, "skills": []}
    if value.get("version") != 2:
        raise ValueError("Legacy catalog has no integrated delivery qualification; regenerate outputs")
    return value


def recover(root):
    journal = safe_relative(root, ".transaction.json")
    if not journal.exists():
        return
    tx = read_json(journal)
    committed = catalog(root).get("transaction") == tx["id"]
    for op in reversed(tx["operations"]):
        target, backup = safe_relative(root, op["target"]), safe_relative(root, op["backup"])
        if not committed:
            if backup.exists():
                if target.exists():
                    remove(root, target)
                target.parent.mkdir(parents=True, exist_ok=True)
                backup.rename(target)
            elif not op["existed"] and target.exists():
                remove(root, target)
    stage = safe_relative(root, ".transactions/" + tx["id"])
    if stage.exists():
        remove(root, stage)
    journal.unlink()


# The writer creates the lock file before writing its pid, so an ownerless lock
# can also mean "another process is in that window right now".
EMPTY_LOCK_GRACE_SECONDS = 5.0


def _archive_lock(root, lock, data):
    """Move an inspected-ownerless lock aside, preserving it as evidence."""
    if lock.read_bytes() != data:
        raise ValueError('Catalog lock changed during recovery')
    archive = safe_relative(root, 'lock-recoveries/' + uuid.uuid4().hex + '.txt')
    archive.parent.mkdir(parents=True, exist_ok=True)
    lock.rename(archive)


def _ownerless(root, lock, data):
    """An unreadable lock is only dead once it is too old to be mid-acquisition."""
    if time.time() - lock.stat().st_mtime < EMPTY_LOCK_GRACE_SECONDS:
        raise ValueError('Catalog lock is being acquired by another process; retry shortly')
    _archive_lock(root, lock, data)


def release_dead_lock(root):
    """Explicit crash recovery only; never steal a live/unknown owner's lock."""
    import os
    root = Path(root).absolute()
    lock = safe_relative(root, '.catalog.lock')
    if not lock.exists():
        return
    guard = safe_relative(root, '.lock-recovery.guard')
    with guard.open('x') as handle:
        handle.close()
        try:
            data = lock.read_bytes()
            text = data.strip()
            if not text:
                _ownerless(root, lock, data)
                return
            try:
                pid = int(text)
            except ValueError:
                _ownerless(root, lock, data)
                return
            if pid <= 0:
                raise ValueError('Invalid lock owner')
            if os.name == 'nt':
                import ctypes
                from ctypes import wintypes
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
                kernel.OpenProcess.restype = wintypes.HANDLE
                kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
                handle = kernel.OpenProcess(0x1000, False, pid)
                if handle:
                    code = wintypes.DWORD()
                    try:
                        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259:
                            raise ValueError('Catalog lock owner is still alive or cannot be inspected')
                    finally:
                        kernel.CloseHandle(handle)
                elif ctypes.get_last_error() != 87:  # ERROR_INVALID_PARAMETER: no such PID
                    raise ValueError('Cannot establish that catalog lock owner exited')
            else:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    pass
                else:
                    raise ValueError('Catalog lock owner is still alive')
            if lock.read_bytes() != data:
                raise ValueError('Catalog lock changed during recovery')
            archive = safe_relative(root, 'lock-recoveries/' + uuid.uuid4().hex + '.txt')
            archive.parent.mkdir(parents=True, exist_ok=True)
            lock.rename(archive)
        finally:
            guard.unlink()


@contextmanager
def locked(root):
    root = Path(root).absolute()
    if has_link(root):
        raise ValueError("Linked library path")
    root.mkdir(parents=True, exist_ok=True)
    lock = safe_relative(root, ".catalog.lock")
    with lock.open("x") as handle:
        handle.write(str(__import__("os").getpid()))
    try:
        recover(root)
        yield root
    finally:
        lock.unlink()


def commit(root, value, packages):
    """Active relative path -> replacement source or None, committed with catalog."""
    txid = uuid.uuid4().hex
    stage = safe_relative(root, ".transactions/" + txid)
    stage.mkdir(parents=True)
    operations = []
    try:
        for index, (relative, source) in enumerate(packages.items()):
            target = safe_relative(root, relative)
            staged = stage / f"new-{index}"
            if source is not None:
                shutil.copytree(source, staged)
                if manifest(staged) != manifest(source):
                    raise ValueError("Library staged copy changed")
            operations.append({"target": relative, "backup": f".transactions/{txid}/backup-{index}",
                               "existed": target.exists(), "new": staged.relative_to(root).as_posix() if source is not None else None})
        write_json(root / ".transaction.json", {"id": txid, "operations": operations})
        for op in operations:
            target = safe_relative(root, op["target"])
            if target.exists():
                manifest(target)
                target.rename(safe_relative(root, op["backup"]))
            if op["new"]:
                target.parent.mkdir(parents=True, exist_ok=True)
                safe_relative(root, op["new"]).rename(target)
        updated = copy.deepcopy(value)
        updated["transaction"] = txid
        write_json(root / "catalog.json", updated)
    finally:
        if (root / ".transaction.json").exists():
            recover(root)
        elif stage.exists():
            remove(root, stage)


def check(root, entry):
    record = verify(safe_relative(root, entry["evidence"]), entry["freeze_sha256"])
    if manifest(safe_relative(root, entry["path"])) != record["files"]:
        raise ValueError("Active package changed after final freeze")
    if entry["revision_id"] != record["delivery"]["revision_id"] or entry["delivery"] != record["delivery"]:
        raise ValueError("Catalog delivery differs from durable evidence")
    if entry.get("runtime"):
        from creation_pipeline.runtime.service import verify_attempt
        verify_attempt(root, entry["runtime"], entry["delivery"], entry["freeze_sha256"])
    return record


def qualification(root, entry):
    if entry.get('current_content', {}).get('status') == 'failed':
        return False, 'Current content approval was revoked'
    if entry['delivery']['inputs']['requirement']['status'] == 'required':
        if entry.get('execution_location') != str(Path(root).resolve()):
            return False, 'Library location changed or is unbound; explicitly revalidate the candidate'
        if entry.get('pending_runtime'):
            return False, 'Runtime recovery is pending; no current execution qualification'
    return qualify(entry['delivery'], runtime_root=root, runtime_ref=entry.get('runtime'),
                   frozen_directory=safe_relative(root, entry['evidence']), freeze_sha256=entry['freeze_sha256'])


def host_unavailable():
    """True when the local runtime host, not the stored evidence, blocks a check.

    A query must not convert "Docker is not running right now" into a permanent
    loss of the recorded acceptance: the fact stays, the live qualification is
    reported as deferred, and a later query re-verifies it.
    """
    from creation_pipeline.runtime.local import LocalExecutor
    try:
        return bool(LocalExecutor().host().get('gaps'))
    except (OSError, ValueError, KeyError, TypeError):
        return True


def reconcile(root, value):
    packages, changed = {}, False
    for entry in value["skills"]:
        if entry.get("invalidated"):
            continue
        try:
            check(root, entry)
            if entry['zone'] == 'accepted':
                valid, reason = qualification(root, entry)
                if not valid:
                    required = entry['delivery']['inputs']['requirement']['status'] == 'required'
                    if required and host_unavailable():
                        # Keep the zone and the frozen history; record that the
                        # live check could not run, not that it failed.
                        entry.update(current_qualification={'accepted': False,
                                        'reason': 'Live execution check deferred: runtime host unavailable',
                                        'deferred': True, 'upstream_reason': reason},
                                    current_host={'status': 'unavailable', 'observed_at': now()})
                        changed = True
                        continue
                    changed = True
                    old = safe_relative(root, entry['path'])
                    new = 'candidates/' + entry['name']
                    packages[new] = old
                    packages[entry['path']] = None
                    entry.update(zone='candidates', path=new,
                        current_qualification={'accepted': False, 'reason': reason},
                        current_host={'status': 'unavailable', 'observed_at': now()},
                        runtime_invalidated={'at': now(), 'reason': reason})
                elif entry.get('current_qualification', {}).get('deferred'):
                    # The host came back: clear the deferral without touching the
                    # historical acceptance fact.
                    entry['current_qualification'] = {'accepted': True, 'reason': reason}
                    entry['current_host'] = {'status': 'available', 'observed_at': now()}
                    changed = True
        except (ValueError, OSError, KeyError, TypeError) as exc:
            changed = True
            old = safe_relative(root, entry["path"])
            entry["invalidated"] = {"at": now(), "reason": str(exc), "previous_revision": entry["revision_id"]}
            entry["current_qualification"] = {"accepted": False, "reason": "Inputs/evidence drifted; new revision and review required"}
            entry["current_host"] = {"status": "not_checked", "observed_at": None}
            if entry["zone"] == "accepted":
                new = "candidates/" + entry["name"]
                if old.exists() and not has_link(old):
                    packages[new] = old
                packages[entry["path"]] = None
                entry.update(zone="candidates", path=new)
    if changed:
        commit(root, value, packages)
    return value


def entries(root, *, include_candidates=False):
    with locked(root) as root:
        value = reconcile(root, catalog(root))
        return copy.deepcopy([e for e in value["skills"] if include_candidates or e["zone"] == "accepted"])


def get(root, name, *, include_candidates=False):
    found = [e for e in entries(root, include_candidates=include_candidates) if e["name"] == name]
    if len(found) != 1:
        raise ValueError("No eligible entry; candidate access requires explicit selection")
    return found[0]


def adopt(output, records, config, destination):
    output = Path(output)
    with locked(destination) as root:
        value = reconcile(root, catalog(root))
        active = {e["name"]: e for e in value["skills"]}
        packages, results, created = {}, [], []
        try:
            for record in records:
                name, ref = record["name"], record["durable_evidence"]
                source = safe_relative(output, ref["path"])
                frozen = verify(source, ref["freeze_sha256"])
                if frozen["delivery"] != record["delivery"]:
                    raise ValueError("Publication record differs from frozen evidence")
                accepted, qualification_reason = qualify(frozen['delivery'], runtime_root=output, runtime_ref=record.get('runtime'),
                    frozen_directory=source, freeze_sha256=ref['freeze_sha256'])
                zone = "accepted" if accepted else "candidates"
                previous = active.get(name)
                if previous and config.get('new_only'):
                    results.append({'name':name,'status':'conflict','reason':'Explicit import cannot replace an existing candidate'})
                    continue
                same_delivery = previous and not previous.get("invalidated") and previous["delivery"] == record["delivery"]
                if (same_delivery
                        and previous.get("runtime", {}).get("files") == record.get("runtime", {}).get("files")
                        and previous.get('runtime_diagnosis', {}).get('files') == record.get('runtime_diagnosis', {}).get('files')):
                    results.append({"name": name, "status": "already_present", "zone": previous["zone"]})
                    continue
                if previous and not same_delivery and config.get("revision_parents", {}).get(name) != previous["revision_id"]:
                    results.append({"name": name, "status": "conflict", "reason": "Revision update requires the expected current revision ID"})
                    continue
                if not previous and any((root / z / name).exists() for z in ("accepted", "candidates")):
                    raise ValueError("Unmanaged active package collision: " + name)
                relative = "evidence/" + record["delivery"]["candidate_id"] + "/" + uuid.uuid4().hex
                evidence = safe_relative(root, relative)
                evidence.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, evidence)
                created.append(evidence)
                verify(evidence, ref["freeze_sha256"])
                history = copy.deepcopy(previous.get("history", [])) if previous else []
                for prior in record.get('runtime_history_records', []):
                    prior_source = safe_relative(output, prior['durable_evidence']['path'])
                    prior_record = verify(prior_source, prior['durable_evidence']['freeze_sha256'])
                    if prior_record['delivery'] != prior['delivery'] or prior['delivery']['candidate_id'] != record['delivery']['candidate_id']:
                        raise ValueError('Repair history differs from frozen candidate identity')
                    prior_relative = 'evidence/' + prior['delivery']['candidate_id'] + '/' + uuid.uuid4().hex
                    shutil.copytree(prior_source, safe_relative(root, prior_relative)); created.append(root / prior_relative)
                    from creation_pipeline.runtime.service import verify_attempt
                    verify_attempt(output, prior['runtime'], prior['delivery'], prior['durable_evidence']['freeze_sha256'])
                    prior_runtime = copy.deepcopy(prior['runtime'])
                    prior_runtime_path = 'runtime/' + prior['delivery']['candidate_id'] + '/' + uuid.uuid4().hex
                    safe_relative(root, prior_runtime_path).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(safe_relative(output, prior_runtime['path']), safe_relative(root, prior_runtime_path)); created.append(root / prior_runtime_path)
                    prior_runtime['path'] = prior_runtime_path
                    history.append({'revision_id': prior['delivery']['revision_id'], 'delivery': prior['delivery'],
                                    'evidence': prior_relative, 'freeze_sha256': prior['durable_evidence']['freeze_sha256'], 'runtime': prior_runtime})
                    if prior.get('runtime_diagnosis'):
                        diagnostic = copy.deepcopy(prior['runtime_diagnosis'])
                        origin = safe_relative(output, diagnostic['path'])
                        if manifest(origin) != diagnostic['files']:
                            raise ValueError('Historical diagnosis evidence changed')
                        diagnostic['path'] = 'diagnostics/' + record['delivery']['candidate_id'] + '/' + uuid.uuid4().hex
                        target = safe_relative(root, diagnostic['path'])
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copytree(origin, target); created.append(target)
                        history[-1]['runtime_diagnosis'] = diagnostic
                if previous:
                    history.append({k: copy.deepcopy(previous[k]) for k in
                                    ("revision_id", "evidence", "freeze_sha256", "delivery", "invalidated", "runtime", "runtime_history",
                                     "pending_runtime", "interrupted_attempts", "recovery_history", "current_content",
                                     "current_execution", "current_host", "current_qualification", "runtime_diagnosis") if k in previous})
                    if previous["path"] != zone + "/" + name:
                        packages[previous["path"]] = None
                item = {"name": name, "path": zone + "/" + name, "zone": zone,
                        "execution_location": str(root.resolve()),
                        "candidate_id": record["delivery"]["candidate_id"], "revision_id": record["delivery"]["revision_id"],
                        "evidence": relative, "freeze_sha256": ref["freeze_sha256"], "delivery": record["delivery"],
                        "current_qualification": {"accepted": accepted, "reason": qualification_reason},
                        "current_host": copy.deepcopy(record["delivery"]["host"]),
                        "history": history, "batch": config["batch"], "build_id": output.name,
                        "unverified": list({json.dumps(c, sort_keys=True, default=str): c
                                    for c in record.get("checks", []) if c["status"] == "not_run"}.values())}
                if record.get("runtime"):
                    from creation_pipeline.runtime.service import verify_attempt
                    runtime = copy.deepcopy(record["runtime"])
                    verify_attempt(output, runtime, record["delivery"], ref["freeze_sha256"])
                    runtime_path = "runtime/" + record["delivery"]["candidate_id"] + "/" + uuid.uuid4().hex
                    target = safe_relative(root, runtime_path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(safe_relative(output, runtime["path"]), target)
                    created.append(target)
                    runtime["path"] = runtime_path
                    item["runtime"] = runtime
                    item["current_execution"] = {"status": runtime["execution_status"], "business_acceptance":
                        'passed' if runtime['execution_status'] == 'passed' else 'not_passed' if runtime['execution_status'] == 'execution_failed' else 'not_run'}
                    item['current_content'] = {'status': 'failed' if runtime.get('content_revoked') else record['delivery']['content']['status']}
                    item["current_host"] = runtime["host"]
                    verify_attempt(root, runtime, record["delivery"], ref["freeze_sha256"])
                if record.get('runtime_diagnosis'):
                    if same_delivery and previous.get('current_content', {}).get('status') == 'failed':
                        item['current_content'] = copy.deepcopy(previous['current_content'])
                    if record['runtime_diagnosis']['outcome'].get('attribution') == 'content':
                        item['current_content'] = {'status': 'failed', 'reason': 'Source-backed diagnosis requires author repair and independent review'}
                    diagnostic = copy.deepcopy(record['runtime_diagnosis'])
                    origin = safe_relative(output, diagnostic['path'])
                    if manifest(origin) != diagnostic['files']:
                        raise ValueError('Diagnosis evidence changed')
                    diagnostic['path'] = 'diagnostics/' + record['delivery']['candidate_id'] + '/' + uuid.uuid4().hex
                    target = safe_relative(root, diagnostic['path'])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(origin, target); created.append(target)
                    item['runtime_diagnosis'] = diagnostic
                active[name] = item
                packages[item["path"]] = evidence / "package"
                results.append({"name": name, "status": "already_present" if same_delivery else "adopted" if accepted else "candidate_saved",
                                "observation_updated": bool(same_delivery),
                                "zone": zone, "path": str(root / item["path"])})
            value["skills"] = list(active.values())
            commit(root, value, packages)
            return results
        except BaseException:
            referenced = {e["evidence"] for e in catalog(root)["skills"]} | {e["runtime"]["path"] for e in catalog(root)["skills"] if e.get("runtime")}
            for path in created:
                if path.relative_to(root).as_posix() not in referenced:
                    remove(root, path)
            raise


def install_from_library(root, name, destination):
    with locked(root) as root:
        value = reconcile(root, catalog(root))
        found = [e for e in value["skills"] if e["name"] == name and e["zone"] == "accepted"]
        if len(found) != 1:
            raise ValueError("Only currently qualified accepted skills may be installed")
        entry = found[0]
        check(root, entry)
        if not qualification(root, entry)[0]:
            raise ValueError('Current Docker evidence no longer qualifies for installation')
        target = safe_relative(Path(destination).absolute(), name)
        if target.exists():
            raise ValueError("Installation destination exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copytree(safe_relative(root, entry["path"]), target)
            if manifest(target) != entry["delivery"]["inputs"]["files"]:
                raise ValueError("Installed files differ from accepted revision")
            if entry.get('runtime'):
                from creation_pipeline.runtime.installation import install_envelope
                install_envelope(root, entry['evidence'], entry['runtime']['path'], target.parent / '.runtime' / name)
        except BaseException:
            if target.exists():
                remove(target.parent, target)
            raise
        return {"installed": str(target), "revision_id": entry["revision_id"]}
