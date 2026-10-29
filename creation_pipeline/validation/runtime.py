"""Shell-free checks in per-check workspaces; generated checks require opt-in."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from creation_pipeline.records import redact, safe_relative

NATIVE_CHECK_FIELDS = frozenset({'candidate','name','argv','cwd','expected_exit','stdout_contains',
                               'json_equals','artifacts','evidence','purpose','kind'})


def terminate_tree(proc):
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            pass
        if proc.poll() is None:
            proc.kill()
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.wait(timeout=5)


def validate_test(test):
    if not isinstance(test, dict) or not isinstance(test.get("name"), str) or not test["name"]:
        raise ValueError("Check needs a name")
    unknown = set(test) - NATIVE_CHECK_FIELDS
    if unknown:
        raise ValueError('Native check ' + test['name'] + ' has unsupported fields: '
                         + ', '.join(sorted(str(key) for key in unknown))
                         + '. These constraints cannot be silently ignored. Express each intended '
                           'constraint using the supported native assertions or enforce it in the '
                           'check program; do not discard it. Supported fields: '
                         + ', '.join(sorted(NATIVE_CHECK_FIELDS)))
    if test["name"] in {"structure", "runtime_paths", "content_review", "artifact_immutability", "blocking_issues", "changed_failed_oracles"}:
        raise ValueError("Check name is reserved for host validation")
    argv = test.get("argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(v, str) or "\0" in v for v in argv):
        raise ValueError("Check argv must be a nonempty list of strings")
    if type(test.get("expected_exit", 0)) is not int:
        raise ValueError("expected_exit must be an integer")
    if not isinstance(test.get("cwd", "{run}"), str):
        raise ValueError("Check cwd must be a path string")
    for key in ("stdout_contains", "artifacts"):
        if not isinstance(test.get(key, []), list) or any(not isinstance(s, str) for s in test.get(key, [])):
            raise ValueError(f"{key} must be an array of strings")
    if not isinstance(test.get("json_equals", {}), dict):
        raise ValueError("json_equals must be an object")
    if not test.get("stdout_contains") and not test.get("json_equals") and not test.get("artifacts"):
        raise ValueError("Execution check needs a result assertion, not exit code alone")
    return test


def execute(test, package, sources, work, timeout, env_allow):
    validate_test(test)
    work = Path(work)
    work.mkdir(parents=True, exist_ok=False)
    macros = {"{python}": sys.executable, "{package}": str(Path(package).resolve()), "{run}": str(work.resolve())}
    bundle = Path(package).resolve().parent.parent
    if bundle.name == "bundle":
        macros["{bundle}"] = str(bundle)
        tools = bundle / "tools"
        if tools.is_dir():
            macros.update({"{tool:" + p.name + "}": str(p) for p in tools.iterdir() if p.is_dir()})
    macros.update({"{source:" + key + "}": value["path"] for key, value in sources.entries.items()})
    argv = []
    for arg in test["argv"]:
        for token, value in macros.items():
            arg = arg.replace(token, value)
        argv.append(arg)
    execution_cwd = test.get("cwd", "{run}") or "{run}"
    for token, value in macros.items():
        execution_cwd = execution_cwd.replace(token, value)
    execution_cwd = Path(execution_cwd).absolute()
    if not execution_cwd.is_dir():
        raise ValueError("Check working directory does not exist: " + str(execution_cwd))
    names = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "LANG", "LC_ALL"} | set(env_allow)
    env = {k: v for k, v in os.environ.items() if k.upper() in names or k in names}
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    started = time.monotonic()
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    # Spool output rather than permitting an unbounded pipe allocation.
    with (work / "stdout.log").open("wb") as stdout, (work / "stderr.log").open("wb") as stderr:
        proc = subprocess.Popen(argv, cwd=execution_cwd, stdout=stdout, stderr=stderr, env=env, **options)
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_tree(proc)
    output_limit = 1_000_000
    with (work / "stdout.log").open("rb") as stream:
        raw = stream.read(output_limit + 1)
    with (work / "stderr.log").open("rb") as stream:
        error = stream.read(4000).decode("utf-8", errors="replace")
    stdout_text = raw.decode("utf-8", errors="replace")
    problems = []
    if timed_out:
        problems.append("Check exceeded timeout")
    if proc.returncode != test.get("expected_exit", 0):
        problems.append(f"Exit {proc.returncode}; expected {test.get('expected_exit', 0)}")
    if len(raw) > output_limit:
        problems.append("stdout exceeds check capture limit")
    for literal in test.get("stdout_contains", []):
        if literal not in stdout_text:
            problems.append(f"Missing stdout assertion: {literal[:150]}")
    if test.get("json_equals"):
        try:
            data = json.loads(stdout_text)
            for key, expected in test["json_equals"].items():
                actual = data
                for part in key.split("."):
                    actual = actual[int(part)] if isinstance(actual, list) else actual[part]
                if actual != expected:
                    problems.append(f"JSON assertion differs: {key}")
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            problems.append("Invalid stdout JSON assertion: " + str(exc))
    for relative in test.get("artifacts", []):
        artifact = safe_relative(work, relative)
        if not artifact.is_file() or artifact.stat().st_size == 0:
            problems.append("Missing/empty artifact: " + relative)
    # Never retain unredacted logs, including in keep-debug workspaces.
    (work / "stdout.log").write_text(redact(stdout_text[:output_limit]), encoding="utf-8")
    (work / "stderr.log").write_text(redact(error), encoding="utf-8")
    environment_gap = bool(proc.returncode != test.get("expected_exit", 0) and
        any(token in error for token in ("ModuleNotFoundError:", "No module named", "command not found")))
    if timed_out:
        environment_gap = True
    return {"name": test["name"], "status": "not_run" if timed_out else "fail" if problems else "pass",
            "required": not timed_out, "unverified": timed_out, "possible_environment_gap": environment_gap and not timed_out,
            "kind": test.get("kind", "positive"), "evidence": test.get("evidence"),
            "elapsed_seconds": round(time.monotonic() - started, 3), "exit_code": proc.returncode,
            "cwd": str(execution_cwd),
            "findings": [redact(p) for p in problems], "stdout_excerpt": redact(stdout_text[:2000]),
            "stderr_excerpt": redact(error[:2000])}
