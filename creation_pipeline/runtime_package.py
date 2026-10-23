"""Portable standard-library-only runner for model-planned packages."""
from __future__ import annotations

import argparse
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


def context(root, tool):
    path = (root / tool["context"]).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Context escapes package")
    metadata=path/'.skillnet/source-metadata.json'
    if metadata.exists():
        import stat
        for name,expected in read(metadata).items():
            source=path/name
            if source.is_symlink() or not source.resolve().is_relative_to(path):raise ValueError('Linked/escaped source metadata path')
            actual=source.stat()
            if {'mtime_ns':actual.st_mtime_ns,'mode':stat.S_IMODE(actual.st_mode)}!=expected:
                raise ValueError('Execution inputs changed (source context metadata); prepare again: '+name)
    return path


def build(root, tool, tag=None):
    # A mutable tag may move between build completion and inspection. The iidfile
    # belongs to this build, so subsequent validation inspects its immutable ID.
    with tempfile.TemporaryDirectory(prefix="skillnet-build-id-") as directory:
        iidfile = Path(directory) / "image-id"
        result = process(["docker", "build", "--platform", tool["platform"], "--tag", tag or tool["local_tag"],
                          "--iidfile", str(iidfile), str(context(root, tool))], tool.get("limits", {}).get("build_seconds", 600))
        if result["exit_code"] == 0:
            image_id = iidfile.read_text(encoding="utf-8").strip()
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id): raise ValueError("Docker build did not return a valid image ID")
            result["image_id"] = image_id
        return result


def input_fingerprint(root, tool_id):
    root = Path(root)
    package = read(root / "runtime/package.json")
    if package.get('image_binding_version') != 1:
        raise ValueError('Legacy schema 3 runner requires prepare with the current generator')
    tool = package["tools"][tool_id]
    paths = [root / "runtime/runner.py", root / f"runtime/tools/{tool_id}/environment_plan.json"]
    paths += [p for p in context(root, tool).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    contents = {}
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()): raise ValueError("Linked/escaped execution input")
        contents[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    examples = [e for e in read(root / 'runtime/examples.json')['examples'] if e.get('tool_id') == tool_id]
    data = {'tool': tool, 'files': contents, 'examples': examples}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def image_records(root):
    path = Path(root) / 'runtime/images.json'
    return read(path) if path.exists() else {'schema_version': 3, 'tools': {}}


def save_images(root, data):
    (Path(root) / 'runtime/images.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def clear_image(root, tool_id):
    data = image_records(root)
    if tool_id in data['tools']:
        del data['tools'][tool_id]
        save_images(root, data)


def pin_image(root, tool_id, image_id, retention_tag, validation_id):
    data = image_records(root)
    data['tools'][tool_id] = {'image_id': image_id, 'retention_tag': retention_tag,
                              'inputs_sha256': input_fingerprint(root, tool_id),
                              'validation_id': validation_id, 'state': 'testing'}
    save_images(root, data)


def accept_image(root, tool_id):
    data = image_records(root)
    data['tools'][tool_id]['state'] = 'accepted'
    save_images(root, data)


@contextmanager
def validation_scope(root, tool_id):
    previous = os.environ.get('SKILLNET_IMAGE_VALIDATION')
    record = image_records(root)['tools'].get(tool_id, {})
    if record.get('validation_id'): os.environ['SKILLNET_IMAGE_VALIDATION'] = record['validation_id']
    try:
        yield
    finally:
        if previous is None: os.environ.pop('SKILLNET_IMAGE_VALIDATION', None)
        else: os.environ['SKILLNET_IMAGE_VALIDATION'] = previous


def verified_image(root, tool_id):
    record = image_records(root)['tools'].get(tool_id)
    if not record:
        raise ValueError('No verified image binding for this tool; prepare/validate the package. Build alone does not grant acceptance.')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', record['image_id']): raise ValueError('Invalid verified image ID')
    testing = record.get('state') == 'testing' and os.environ.get('SKILLNET_IMAGE_VALIDATION') == record.get('validation_id')
    if not testing:
        report = read(Path(root) / 'runtime/execution.json')
        matches = [t for t in report['tools'] if t['tool_id'] == tool_id]
        if (report.get('requires_prepare') or report.get('validation_run_id') != record.get('validation_id')
                or record.get('state') != 'accepted' or len(matches) != 1 or matches[0]['status'] != 'execution_passed'
                or any(matches[0].get(k) != record[k] for k in ('image_id', 'retention_tag'))):
            raise ValueError('Image binding is not accepted by the current execution report; validate again')
    if input_fingerprint(root, tool_id) != record['inputs_sha256']:
        raise ValueError('Execution inputs changed; prepare and validate again')
    inspected = process(['docker', 'image', 'inspect', record['retention_tag'], '--format', '{{.Id}}'])
    if inspected['exit_code'] or inspected['stdout'].strip() != record['image_id']:
        raise ValueError('Verified image is missing or its retention reference changed; validate again, no tag fallback. ' + inspected.get('stderr', ''))
    return record['image_id']


def invocation(tool, image, args, name, input_dir=None, output_dir=None, entrypoint=None):
    limits = tool.get("limits", {})
    cmd = ["docker", "run", "--rm", "--name", name, "--network", "bridge" if tool.get("runtime_network") else "none", "--read-only",
           "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "10001:10001",
           "--pids-limit", str(limits.get("pids", 64)), "--memory", limits.get("memory", "512m"), "--cpus", str(limits.get("cpus", "1")),
           "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"]
    if os.environ.get("SKILLNET_EXECUTION_SCOPE"):
        cmd += ["--label", "skillnet.scope=" + os.environ["SKILLNET_EXECUTION_SCOPE"]]
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
    if entrypoint:
        cmd += ["--entrypoint", entrypoint]
    return cmd + [image, *args]


def run(tool, image, args, input_dir=None, output_dir=None, entrypoint=None, timeout=60):
    name = "skillnet-v2-" + uuid.uuid4().hex
    try:
        return process(invocation(tool, image, args, name, input_dir, output_dir, entrypoint), timeout)
    finally:
        # A killed Docker client does not necessarily stop its container.
        process(["docker", "rm", "--force", name], 30)


def retain_outputs(source, destination, observation, limit=128000000):
    """Preserve bounded output evidence before temporary mounts disappear."""
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    record={'directory':str(destination),'files':{},'omitted':[],'byte_limit':limit};used=0
    for path in sorted(source.rglob('*')):
        relative=path.relative_to(source).as_posix()
        if path.is_symlink():record['omitted'].append({'path':relative,'reason':'symlink'});continue
        if not path.is_file():continue
        try:
            size=path.stat().st_size
            if used+size>limit:
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
            def invoke(args, entrypoint=None):
                allowed = timeout if deadline is None else min(timeout, deadline - time.monotonic())
                if allowed <= 0:
                    raise ValueError("Test time budget exhausted")
                return run(tool, image, args, input_dir if "input_files" in case else None,
                           output_dir if case.get("output_file") and (not case.get('capture_stdout') or tool['behavior'].get('file_io')) else None, entrypoint, allowed)
            if case.get("relation"):
                relation = case["relation"]
                results = [invoke(r["args"], r.get("entrypoint")) for r in relation["runs"]]
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
            ok = ok and output_matches(case, result, text)
            if case.get("forbidden_input_file"):
                ok = ok and not (input_dir / case["forbidden_input_file"]).exists()
            observation["status"] = "passed" if ok else "failed"
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        observation["error"] = f"{type(exc).__name__}: {exc}"
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
    assertion = case.get('acceptance', {}).get('assertion')
    if assertion:
        try:
            if assertion['kind'] == 'stdout_equals':
                ok = ok and text.strip() == assertion['value']
            elif assertion['kind'] == 'stderr_contains':
                ok = ok and assertion['value'] in result.get('stderr', '')
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


def business_args(tool, case):
    """Only the configured user entrypoint, never an environment/test runner."""
    if case.get('relation') or case.get('layer') == 'environment':
        return None
    args = case.get('args', [])
    if not case.get('entrypoint'):
        return args
    entry = tool['entrypoint']
    if case['entrypoint'] == entry[0] and args[:len(entry)-1] == entry[1:]:
        return args[len(entry)-1:]
    return None


def operation_matches(operation, args):
    return args is not None and all(
        item['index'] < len(args) and args[item['index']] == item['equals']
        for item in operation['selector']['args'])


def input_check(case, check, args):
    """None means absent/unbound material, not a demonstrated invalid value."""
    try:
        if check['channel'] == 'args':
            value = args[check['key']]
        else:
            value = case.get('input_files', {})[check['key']]
            if 'argument_index' in check and args[check['argument_index']] != '/input/' + check['key']:
                return None
    except (IndexError, KeyError, TypeError):
        return None
    values = value.splitlines() if check.get('mode') == 'each_line' else [value]
    return bool(values) and all(re.fullmatch(check['pattern'], item) is not None for item in values)


def acceptance_coverage(tool, cases, observations=None):
    """No output-string heuristics: coverage and success follow locked contracts."""
    if tool.get('acceptance_version') != 2:
        return {'version': 1, 'complete': False, 'reasons': ['Legacy evidence; current acceptance not evaluated']}
    policy = tool.get('acceptance_policy', {})
    reasons = []
    supported = [c for c in cases if c.get('oracle_status') == 'supported' and c.get('acceptance')]
    direct = [c for c in supported if business_args(tool, c) is not None]
    positive = [c for c in direct if c['acceptance']['purpose'] in {'computation', 'operation', 'report'}
                and c.get('expected_exit', 0) == 0 and not c.get('relation')
                and not any(a in {'--help', '--version', '-h', '-V'} for a in c['args'])]
    negative = [c for c in direct if c['acceptance']['purpose'] == 'input_rejection']
    checks = policy.get('checks', [])
    operations = policy.get('operations', [])
    def routes(case):
        return [op for op in operations if operation_matches(op, business_args(tool, case))]
    def applicable(case):
        if not operations:
            return checks
        matched = routes(case)
        if len(matched) != 1:
            return None
        return [check for check in checks if check['id'] in matched[0]['checks']]
    def accepts(case, check):
        return input_check(case, check, business_args(tool, case))
    def valid(case):
        selected = applicable(case)
        return selected is not None and all(accepts(case, check) is True for check in selected)
    positive = [c for c in positive if valid(c)]
    completed_negative = [c for c in direct if c['acceptance']['purpose'] in {'computation', 'operation', 'report'}
                          and c.get('expected_exit', 0) != 0 and valid(c)]
    def outcome(case):
        assertion = case['acceptance']['assertion']
        return (case.get('expected_exit', 0), {k:v for k,v in assertion.items()
                if k not in {'source_path', 'source_quote', 'role'}})
    def rejects(case, check):
        selected = applicable(case)
        return (case['acceptance'].get('violates') == check['id'] and selected is not None
                and check in selected and accepts(case, check) is False
                and all(outcome(case) != outcome(normal) for normal in positive))
    if not positive:
        reasons.append('No grounded normal input with a result assertion')
    if not policy.get('purposes') or not set(policy['purposes']) <= {c['acceptance']['purpose'] for c in positive}:
        reasons.append('Declared purposes are not covered by grounded normal cases')
    if policy.get('invalid_input') == 'required':
        if not checks:
            reasons.append('Input constraint lacks a checkable fixture predicate')
        for check in checks:
            matching = [c for c in negative if rejects(c, check)]
            if not matching:
                reasons.append('Missing actual invalid-input rejection: ' + check['id'])
    elif policy.get('invalid_input') != 'not_applicable' or not policy.get('source_quote') or not policy.get('scope'):
        reasons.append('Input applicability not grounded')
    elif any(c.get('args') or c.get('input_files') for c in positive):
        reasons.append('Not-applicable exemption only supports operations without supplied user input')
    operation_coverage = {}
    for operation in operations:
        normal = [c for c in positive if operation_matches(operation, business_args(tool, c))]
        rejected = [c for c in negative if operation_matches(operation, business_args(tool, c))]
        missing = []
        if not normal or not set(operation['purposes']) <= {c['acceptance']['purpose'] for c in normal}:
            missing.append('normal business purpose')
        if operation.get('require_persistence') and not any(c.get('output_file') and not c.get('capture_stdout') for c in normal):
            missing.append('persisted output')
        for check in checks:
            if check['id'] in operation['checks'] and not any(
                    rejects(c, check) for c in rejected):
                missing.append('rejection for ' + check['id'])
        operation_coverage[operation['id']] = {'normal_cases': [c['name'] for c in normal], 'missing': missing}
        reasons.extend('Operation ' + operation['id'] + ' missing ' + item for item in missing)
    # file_io remains a persistence obligation independently of which example is selected.
    if tool.get('behavior', {}).get('file_io') and not any(c.get('output_file') and not c.get('capture_stdout') for c in positive):
        reasons.append('No grounded normal persisted-output case for declared file IO')
    if observations is not None:
        passed = {c['name'] for c in observations if c['status'] == 'passed'}
        required = positive + negative + completed_negative
        if any(c['name'] not in passed for c in required):
            reasons.append('Required acceptance cases did not pass')
    return {'version': 2, 'complete': not reasons, 'reasons': reasons,
            'normal_cases': [c['name'] for c in positive],
            'operations': operation_coverage,
            'completed_negative_cases': [c['name'] for c in completed_negative],
            'purposes': sorted({c['acceptance']['purpose'] for c in positive}),
            'scientific_correctness': 'not_evaluated'}


def tests(root, tool, image):
    cases = read(context(root, tool) / tool.get("fixtures", "execution/fixtures.json"))["cases"]
    observations = [run_case(root, tool, image, case) for case in cases]
    accepted = [c for c in observations if c.get("oracle_status", "supported") == "supported"]
    status = ("untested_no_fixture" if not accepted else
              "execution_passed" if all(c["status"] == "passed" for c in accepted) else "execution_failed")
    result = {"status": status, "cases": observations}
    if tool.get('acceptance_version') == 2:
        result['acceptance'] = acceptance_coverage(tool, cases, observations)
        if status == 'execution_passed' and not result['acceptance']['complete']:
            result['status'] = 'validation_incomplete'
    if tool.get("schema_version") == 3:
        result["validation"] = {}
        for layer in ("environment", "interface", "behavior"):
            selected = [c for c in accepted if c.get("layer") == layer]
            result["validation"][layer] = "not_verified" if not selected else "passed" if all(c["status"] == "passed" for c in selected) else "failed"
        result["agent_effect_status"] = "not_evaluated"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "run", "test", "case", "prepare-inputs"])
    parser.add_argument("--tool", required=True)
    parser.add_argument("--case")
    parser.add_argument("--timeout-seconds", type=int)
    parser.add_argument("--example")
    parser.add_argument("--stdout-file", type=Path)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    import sys
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raw = sys.argv[1:]
    split = raw.index("--") if "--" in raw else len(raw)
    args = parser.parse_args(raw[:split])
    forwarded = raw[split + 1:]
    root = Path(__file__).resolve().parent.parent
    tool = read(root / "runtime/package.json")["tools"][args.tool]
    if args.action == "prepare-inputs":
        matches = [e for e in read(root / "runtime/examples.json")["examples"]
                   if e["name"] == args.example and e.get("kind") == "usage" and e.get("tool_id") == args.tool]
        if len(matches) != 1:
            parser.error("Exactly one usage example owned by --tool is required; regenerate legacy examples")
        example = matches[0]
        input_dir = (root / example["input_dir"]).resolve()
        create_directory(input_dir, 0o755)
        for relative, content in example["input_files"].items():
            path = (input_dir / relative).resolve()
            if not path.is_relative_to(input_dir):
                raise ValueError("Example input escapes directory")
            fixture_parent(input_dir, relative)
            if path.exists():
                if path.read_bytes() != content.encode('utf-8'):
                    raise ValueError("Refusing to overwrite existing user input: " + str(path))
            else:
                path.write_text(content, encoding="utf-8", newline="")
                if os.name == 'posix': path.chmod(0o644)
        if example.get("output_dir"):
            output_directory(root / example["output_dir"])
        print(json.dumps({"input_directory": str(input_dir), "files": list(example["input_files"])}, ensure_ascii=True))
        return 0
    if args.action == "build":
        result = build(root, tool)
        print(json.dumps(result, ensure_ascii=True))
        return result['exit_code']
    elif args.action == "run":
        timeout = args.timeout_seconds or tool.get("limits", {}).get("test_seconds", 60)
        if not 1 <= timeout <= tool.get("limits", {}).get("test_seconds", 60):
            parser.error("Timeout exceeds configured test_seconds")
        result = run(tool, verified_image(root, args.tool), forwarded, args.input_dir, args.output_dir, timeout=timeout)
    elif args.action == "case":
        cases = read(context(root, tool) / tool.get("fixtures", "execution/fixtures.json"))["cases"]
        matches = [c for c in cases if c["name"] == args.case]
        if len(matches) != 1:
            parser.error("Exactly one matching case is required")
        result = run_case(root, tool, verified_image(root, args.tool), matches[0])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "passed" else 2
    else:
        result = tests(root, tool, verified_image(root, args.tool))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "execution_passed" else 2
    print(result["stdout"], end="")
    if args.stdout_file:
        args.stdout_file.parent.mkdir(parents=True, exist_ok=True)
        args.stdout_file.write_text(result["stdout"], encoding="utf-8", newline="")
    print(result["stderr"], end="", file=sys.stderr)
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
