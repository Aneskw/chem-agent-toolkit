"""Portable standard-library-only runner for model-planned packages."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import uuid
import math
import time
import os
import signal
import re
import hashlib
import shutil
from contextlib import contextmanager, ExitStack


# Migrated from d5b77dc runtime_package; no old CLI, package schema or publisher.
class WindowsProcessJob:
    """Kernel-owned descendant lifetime; works without taskkill process enumeration."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes as w
        self.ctypes = ctypes
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        size = ctypes.c_size_t
        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong), ("flags", w.DWORD),
                        ("min_ws", size), ("max_ws", size), ("active", w.DWORD), ("affinity", size),
                        ("priority", w.DWORD), ("scheduling", w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]
        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_memory", size), ("job_memory", size),
                        ("peak_process", size), ("peak_job", size)]
        k = self.kernel
        k.CreateJobObjectW.argtypes = [w.LPVOID, w.LPCWSTR]; k.CreateJobObjectW.restype = w.HANDLE
        k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD]
        k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        k.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
        k.CloseHandle.argtypes = [w.HANDLE]
        self.handle = k.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = Extended(); info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            self.close(); raise ctypes.WinError(ctypes.get_last_error())

    def attach_and_resume(self, proc):
        c = self.ctypes
        try:
            if not self.kernel.AssignProcessToJobObject(self.handle, int(proc._handle)):
                raise c.WinError(c.get_last_error())
        except OSError:
            proc.kill()
            raise
        ntdll = c.WinDLL("ntdll")
        ntdll.NtResumeProcess.argtypes = [c.c_void_p]
        ntdll.NtResumeProcess.restype = c.c_long
        if ntdll.NtResumeProcess(int(proc._handle)) != 0:
            self.terminate()
            raise OSError("Unable to resume supervised child process")

    def terminate(self):
        self.kernel.TerminateJobObject(self.handle, 1)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def stop_process_tree(proc, owns_group=True):
    if proc.poll() is not None:
        return
    if os.name == "nt":
        killer = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/taskkill.exe"
        try:
            subprocess.run([str(killer), "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=10)
        finally:
            if proc.poll() is None:
                proc.kill()
    else:
        try:
            if owns_group:
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except ProcessLookupError:
            pass


def cleanup_scope(scope):
    """Remove only containers carrying this supervised command's ownership label."""
    observations = []
    try:
        found = subprocess.run(["docker", "ps", "-aq", "--filter", "label=skillnet.scope=" + scope],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        observations.append({"phase": "list_owned_containers", "exit_code": found.returncode, "stderr": found.stderr})
        ids = [line for line in found.stdout.splitlines() if re.fullmatch(r"[a-f0-9]{12,64}", line)]
        if ids:
            removed = subprocess.run(["docker", "rm", "--force", *ids], capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=10)
            observations.append({"phase": "remove_owned_containers", "ids": ids, "exit_code": removed.returncode,
                                 "stdout": removed.stdout, "stderr": removed.stderr})
    except (OSError, subprocess.TimeoutExpired) as exc:
        observations.append({"phase": "cleanup_failed", "error": str(exc)})
    # Keep the ownership selector even when the daemon cannot list any IDs.
    # This is the recovery handle, not a claim that cleanup succeeded.
    for observation in observations:
        observation['scope'] = scope
    return observations


def create_directory(path, mode=0o755):
    path = Path(path)
    if not path.exists():
        path.mkdir(parents=True)
        if os.name == 'posix': path.chmod(mode)
        return True
    if not path.is_dir(): raise ValueError('Expected a directory: ' + str(path))
    return False


def output_directory(path):
    path = Path(path)
    create_directory(path, 0o1777)
    if os.name == 'posix':
        info = path.stat()
        bits = (info.st_mode >> (6 if info.st_uid == 10001 else 3 if info.st_gid == 10001 else 0)) & 7
        if bits & 3 != 3:
            raise ValueError('Output directory must be writable/searchable by container UID/GID 10001:10001; '
                             'existing permissions were not changed: ' + str(path))
    return path


def fixture_parent(input_dir, relative):
    node = Path(input_dir)
    for part in Path(relative).parent.parts:
        node = node / part
        create_directory(node, 0o755)
    return node


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def process(args, timeout=60, cwd=None, *, supervise=None):
    supervised = any(Path(str(arg)).name == "runner.py" for arg in args[1:]) if supervise is None else supervise
    scope = uuid.uuid4().hex if supervised else None
    env = os.environ.copy()
    if scope:
        env["SKILLNET_EXECUTION_SCOPE"] = scope
    job = WindowsProcessJob() if os.name == "nt" else None
    owns_group = supervised or not os.environ.get("SKILLNET_EXECUTION_SCOPE")
    kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | 0x4} if job else {"start_new_session": owns_group}
    try:
        proc = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace", env=env, **kwargs)
        if job:
            job.attach_and_resume(proc)
    except BaseException:
        if job:
            job.close()
        raise
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return {"command": args, "exit_code": proc.returncode, "stdout": stdout, "stderr": stderr}
    except subprocess.TimeoutExpired as exc:
        cleanup = []
        try:
            if job:
                job.terminate()
            else:
                stop_process_tree(proc, owns_group)
            stdout, stderr = proc.communicate(timeout=10)
            exc.output, exc.stderr = stdout, stderr
            cleanup.append({"phase": "terminate_process_tree", "method": "windows_job" if job else "process_group",
                            "pid": proc.pid, "exit_code": proc.returncode})
        except (OSError, subprocess.TimeoutExpired) as cleanup_error:
            cleanup.append({"phase": "process_tree_cleanup_failed", "error": str(cleanup_error)})
            if proc.poll() is None:
                proc.kill()
        finally:
            if scope:
                cleanup += cleanup_scope(scope)
            exc.cleanup, exc.scope = cleanup, scope
        raise
    finally:
        if job:
            job.close()
        elif supervised and owns_group:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def subset(expected, actual, tolerance=0):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and subset(v, actual[k], tolerance) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(subset(a, b, tolerance) for a, b in zip(expected, actual))
    if tolerance and type(expected) in (float, int) and type(actual) in (float, int):
        return math.isclose(expected, actual, rel_tol=0, abs_tol=tolerance)
    return type(expected) is type(actual) and expected == actual


def invocation(tool, image, args, name, input_dir=None, output_dir=None, entrypoint=None):
    limits = tool.get("limits", {})
    cmd = ["docker", "run", "--rm", "--name", name, "--network", "bridge" if tool.get("runtime_network") else "none", "--read-only",
           "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "10001:10001",
           "--pids-limit", str(limits.get("pids", 64)), "--memory", limits.get("memory", "512m"), "--cpus", str(limits.get("cpus", "1")),
           "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"]
    scope = tool.get('execution_scope') or os.environ.get('SKILLNET_EXECUTION_SCOPE')
    if scope:
        cmd += ["--label", "skillnet.scope=" + scope]
    if (input_dir or output_dir) and not tool["behavior"].get("file_io"):
        raise ValueError("File IO is not supported by the reviewed contract")
    for directory, target, readonly in ((input_dir, "/input", True), (output_dir, "/output", False)):
        if directory:
            directory = Path(directory).resolve()
            if "," in str(directory):
                raise ValueError("Docker --mount paths cannot contain commas")
            if readonly and not directory.is_dir():
                raise ValueError("Input directory does not exist")
            if not readonly:
                output_directory(directory)
            cmd += ["--mount", f"type=bind,source={directory},target={target}" + (",readonly" if readonly else "")]
    cmd += ["--workdir", tool.get("workdir", "/opt/skill")]
    if tool.get("source_mount"):
        cmd += ["--mount", "type=bind,source=" + str(Path(tool["source_mount"]).resolve()) + ",target=/sources,readonly"]
    if entrypoint:
        cmd += ["--entrypoint", entrypoint]
    return cmd + [image, *args]


def run(tool, image, args, input_dir=None, output_dir=None, entrypoint=None, timeout=60):
    name = "skillnet-v2-" + uuid.uuid4().hex
    result, error = None, None
    try:
        result = process(invocation(tool, image, args, name, input_dir, output_dir, entrypoint), timeout)
        return result
    except subprocess.TimeoutExpired as exc:
        error = exc
        exc.scope = tool.get('execution_scope') or getattr(exc, 'scope', None)
        raise
    finally:
        # A killed Docker client does not necessarily stop its container.
        try:
            cleanup = process(["docker", "rm", "--force", name], 30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            cleanup = {'phase': 'cleanup_failed', 'error': str(exc), 'container': name}
        if result is not None:
            result['cleanup'] = cleanup
        if error is not None:
            error.cleanup = getattr(error, 'cleanup', []) + [cleanup]


def retain_outputs(source, destination, observation, limit=None):
    """Preserve bounded output evidence before temporary mounts disappear."""
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    record={'directory':destination.name,'files':{},'omitted':[],'byte_limit':limit};used=0
    for path in sorted(source.rglob('*')):
        relative=path.relative_to(source).as_posix()
        if path.is_symlink():record['omitted'].append({'path':relative,'reason':'symlink'});continue
        if not path.is_file():continue
        try:
            size=path.stat().st_size
            if limit is not None and used+size>limit:
                record['omitted'].append({'path':relative,'reason':'byte budget'});continue
            target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target);used+=size
            record['files'][relative]={'bytes':size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
        except OSError as exc:record['omitted'].append({'path':relative,'reason':str(exc)})
    observation['output_artifacts']=record


def run_case(root, tool, image, case, deadline=None, artifact_dir=None):
    observation = {"name": case["name"], "origin": case["origin"], "basis": case["basis"], "status": "failed"}
    for key in ("layer", "kind", "oracle_status", "tolerance", "source_paths", "limitations"):
        if key in case:
            observation[key] = case[key]
    try:
        with tempfile.TemporaryDirectory(prefix="skillnet-fixture-") as tmp, ExitStack() as capture:
            tmp = Path(tmp)
            input_dir, output_dir = tmp / "input", tmp / "output"
            create_directory(input_dir, 0o755); output_directory(output_dir)
            if artifact_dir is not None:
                capture.callback(retain_outputs,output_dir,artifact_dir,observation)
            for relative, text in case.get("input_files", {}).items():
                path = (input_dir / relative).resolve()
                if not path.is_relative_to(input_dir.resolve()):
                    raise ValueError("Fixture path escapes input directory")
                fixture_parent(input_dir, relative)
                path.write_text(text, encoding="utf-8", newline="")
                path.chmod(0o644)
            timeout = case.get("timeout_seconds", 30)
            if type(timeout) is not int or not 1 <= timeout <= tool.get("limits", {}).get("test_seconds", 60):
                raise ValueError("Fixture timeout exceeds configured test_seconds")
            tool = dict(tool, workdir=case.get("workdir", tool.get("workdir", "/opt/skill")))
            if case.get("mapped_check"):
                tool["behavior"] = dict(tool["behavior"], file_io=True)
            def invoke(args, entrypoint=None):
                allowed = timeout if deadline is None else min(timeout, deadline - time.monotonic())
                if allowed <= 0:
                    raise ValueError("Test time budget exhausted")
                return run(tool, image, args, input_dir if "input_files" in case else None,
                           output_dir if case.get("mapped_check") or (case.get("output_file") and (not case.get('capture_stdout') or tool['behavior'].get('file_io'))) else None, entrypoint, allowed)
            if case.get("relation"):
                relation = case["relation"]
                results = [invoke(r["args"], r.get("entrypoint")) for r in relation["runs"]]
                ok = relation_matches(case, results)
                observation.update(status="passed" if ok else "failed", runs=results)
                return observation
            result = invoke(case["args"], case.get("entrypoint"))
            observation.update(result)
            ok = result["exit_code"] == case.get("expected_exit", 0)
            text = result["stdout"]
            if case.get("output_file"):
                output = (output_dir / case["output_file"]).resolve()
                if not output.is_relative_to(output_dir.resolve()):
                    raise ValueError("Output path escapes output directory")
                if case.get("capture_stdout"):
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text(result["stdout"], encoding="utf-8", newline="")
                text = output.read_text(encoding="utf-8")
                observation["persisted_output"] = text  # read AFTER --rm container exit
            output_ok = ok and output_matches(case, result, text)
            ok = ok and output_ok
            assertion = case.get('acceptance', {}).get('assertion', {})
            if result['exit_code'] == case.get('expected_exit', 0) and not output_ok:
                missing = [part for part in case.get('stdout_contains', []) if part not in result['stdout']]
                if missing:
                    observation['assertion_failures'] = [{
                        'case': case['name'], 'kind': 'stdout_contains', 'channel': 'stdout',
                        'missing_literals': missing,
                        'detail': 'Required literal substrings did not occur in actual stdout; comparison remains exact'}]
            if (result['exit_code'] == case.get('expected_exit', 0) and not output_ok
                    and assertion.get('kind') == 'text_regex'
                    and re.fullmatch(assertion['pattern'], text) is None):
                observation['assertion_failure'] = {
                    'case': case['name'], 'kind': 'text_regex',
                    'channel': 'output_file' if case.get('output_file') else 'stdout',
                    'output_file': case.get('output_file'), 'pattern': assertion['pattern'],
                    'source_path': assertion.get('source_path'),
                    'actual_characters': len(text), 'actual_tail': text[-160:],
                    'detail': 'Full-match pattern did not match the actual text; output was not trimmed or normalized to satisfy it'}
            if case.get("forbidden_input_file"):
                ok = ok and not (input_dir / case["forbidden_input_file"]).exists()
            for name in case.get("artifacts", []):
                path = (output_dir / name).resolve()
                ok = (ok and path.is_relative_to(output_dir.resolve()) and path.is_file()
                      and not path.is_symlink() and (not case.get('mapped_check') or path.stat().st_size > 0))
            observation["status"] = "passed" if ok else "failed"
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        observation["error"] = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, subprocess.TimeoutExpired):
            text = lambda v: v.decode("utf-8", errors="replace") if isinstance(v, bytes) else v or ""
            observation.update(timed_out=True, stdout=text(exc.output), stderr=text(exc.stderr),
                               cleanup=getattr(exc, "cleanup", []), scope=getattr(exc, "scope", None))
    return observation


def output_matches(case, result, text):
    ok = True
    if "expected_json_lines" in case:
        actual = [json.loads(line) for line in text.splitlines() if line.strip()]
        ok = subset(case["expected_json_lines"], actual, case.get("tolerance", 0))
    if "stdout_contains" in case:
        ok = ok and all(part in result["stdout"] for part in case["stdout_contains"])
    if "stdout_equals" in case:
        ok = ok and result["stdout"].strip() == case["stdout_equals"]
    for key, expected in case.get("json_equals", {}).items():
        try:
            value = json.loads(result["stdout"])
            for part in key.split("."):
                value = value[int(part)] if isinstance(value, list) else value[part]
            # Native json_equals is exact Python JSON equality (including numeric
            # int/float equality), not the legacy runner's typed subset oracle.
            # Keep legacy expected_json_lines/acceptance predicates unchanged.
            ok = ok and value == expected
        except (ValueError, KeyError, IndexError, TypeError):
            return False
    assertion = case.get('acceptance', {}).get('assertion')
    if assertion:
        try:
            if assertion['kind'] == 'stdout_equals':
                ok = ok and text.strip() == assertion['value']
            elif assertion['kind'] == 'stderr_contains':
                ok = ok and assertion['value'] in result.get('stderr', '')
            elif assertion['kind'] == 'text_regex':
                ok = ok and re.fullmatch(assertion['pattern'], text) is not None
            elif assertion['kind'] in {'json', 'jsonl'}:
                value = (json.loads(text.splitlines()[assertion['record_index']])
                         if assertion['kind'] == 'jsonl' else json.loads(text))
                for key in assertion['path']:
                    value = value[key]
                ok = ok and any(subset(expected, value) for expected in assertion['allowed_values'])
            else:
                return False
        except (ValueError, KeyError, IndexError, TypeError):
            return False
    return ok

def relation_matches(case, results):
    relation = case["relation"]
    texts = [r["stdout"].strip() for r in results]
    ok = all(r["exit_code"] == case.get("expected_exit", 0) for r in results)
    if relation["type"] == "equal_stdout":
        ok = ok and all(t == texts[0] for t in texts[1:])
    elif relation["type"] == "jsonl_concat":
        rows = [[json.loads(line) for line in t.splitlines() if line.strip()] for t in texts]
        ok = ok and subset(rows[0], sum(rows[1:], []), case.get("tolerance", 0))
    elif relation["type"] == "numeric_scale":
        ok = ok and math.isclose(float(texts[1]), float(texts[0]) * relation["factor"],
                                 rel_tol=0, abs_tol=case.get("tolerance", 0))
    else:
        raise ValueError("Unsupported relation")
    return ok
