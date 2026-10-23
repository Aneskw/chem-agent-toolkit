"""Shared state, integrity and documentation helpers for model-driven runtimes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def files(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()
            and "__pycache__" not in p.parts}


def aggregate(states):
    states = list(states)
    if not states:
        return "needs_review"
    for state in ("execution_failed", "build_failed", "blocked_resources", "budget_exhausted", "needs_review", "validation_incomplete", "untested_no_fixture", "prepared"):
        if state in states:
            return state
    if any(s not in {"execution_passed", "not_required"} for s in states):
        return "needs_review"
    return "execution_passed" if "execution_passed" in states else "not_required"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def artifacts(root):
    return {k: v for k, v in files(root).items() if not k.startswith("reports/")
            and k not in {"runtime/prepared.json", "runtime/execution.json"}
            and not re.fullmatch(r"runtime/tools/[^/]+/build.json", k)}


def withdraw_claims(root, status):
    """Fail closed even when package configuration cannot be parsed to render docs."""
    original = (root / "runtime/source-SKILL.md").read_text(encoding="utf-8")
    text = original.replace("## Credibility\n", f"## Credibility\n\nTool execution has NOT been accepted: {status}. Regenerate the runtime package.\n")
    (root / "SKILL.md").write_text(text, encoding="utf-8")
    (root / "DOCKER.md").write_text(f"# Runtime not accepted\n\nStatus: {status}. Evidence or configuration is invalid; regenerate and revalidate.\n", encoding="utf-8")


def sync_skill(original, package, status):
    # Change only runtime statements, leaving cited claims, fixed headings and confidence tier intact.
    text = original
    text = re.sub(r"^compatibility:.*$", "compatibility: Docker Linux amd64; Python 3.11+ runner; see DOCKER.md", text, flags=re.M)
    text = re.sub(r"^allowed-tools:.*$", "allowed-tools: 'Read Bash(python:*) Bash(docker:*)'", text, flags=re.M)
    text = text.replace("Do not use as evidence of successful execution.", "Execution status and scope are recorded in DOCKER.md.")
    text = text.replace("not an execution-validated package", "with tool execution status documented below")
    text = text.replace("State: `draft_unexecuted`.", "Source review state: `source_validated_candidate`.")
    text = text.replace("Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.",
                        "Source-line citations were checked; semantic completeness and scientific validity remain unverified. Tool execution is evaluated separately below.")
    acceptance = ("Declared tool tests and documented examples passed. This does not validate scientific claims or Agent effectiveness."
                  if status == "execution_passed" else f"Tool execution has NOT been accepted: {status}. Do not claim test success.")
    text = text.replace("## Credibility\n", "## Credibility\n\n" + acceptance + "\n")
    commands = "\n".join(f"python runtime/runner.py build --tool {key}\npython runtime/runner.py test --tool {key}" for key in package["tools"])
    text = text.replace("## Procedure Guidance\n", "## Procedure Guidance\n\nUse the packaged Docker runner; see [DOCKER.md](DOCKER.md) for tested inputs, mounts and recovery. "
                        "Build creates a candidate image; test/run/case use the image ID accepted by the build host's validate_runtime.py. "
                        "A rebuild does not switch acceptance. Missing or changed bindings require preparation and validation.\n\n```powershell\n" + commands + "\n```\n")
    text = text.replace("## Matters & Troubleshooting\n", "## Matters & Troubleshooting\n\nRuntime resources and pinned dependencies: [DOCKER.md](DOCKER.md), `runtime/package.json`, and `runtime/tools/`. The original source extraction's resource statements below are not a runtime inventory.\n")
    return text
