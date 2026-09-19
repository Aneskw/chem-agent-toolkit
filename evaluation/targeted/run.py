#!/usr/bin/env python3
"""Run paired, isolated Codex attempts with optional matching skill packages."""
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from score import check

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def usage_from_events(output: str) -> dict:
    usage = {}
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed":
            usage = event.get("usage", {})
    return usage


def run_one(task: dict, condition: str, model: str, repeat: int, target: Path, timeout: int) -> dict:
    work = Path(tempfile.mkdtemp(prefix=f"chem-eval-{task['id']}-{condition}-"))
    for dst, source in task["fixtures"].items():
        destination = work / dst
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / source, destination)
    package = ROOT / task["skill"]
    if condition == "with-skill":
        shutil.copytree(package, work / "skill", symlinks=False)
    if condition == "tools-only":
        tool = work / "tool"
        tool.mkdir()
        for folder in ("scripts", "resources"):
            if (package / folder).is_dir():
                shutil.copytree(package / folder, tool / folder)
    skill_instruction = {
        "no-skill": "",
        "tools-only": "Implementation scripts, when present, are available in ./tool/scripts. No skill guidance is supplied.\n",
        "with-skill": "A relevant skill is available in ./skill. Read SKILL.md and use its scripts if applicable.\n",
    }[condition]
    prompt = (
        "Complete this chemistry task using only files in the current workspace and installed tools. "
        "Do not read parent directories or invent missing source data. Write the requested artifact. "
        "If blocked, make the requested error artifact.\n"
        + skill_instruction + "\nTask:\n" + task["task"]
    )
    cmd = ["codex", "exec", "--json", "--ephemeral", "--skip-git-repo-check",
           "--sandbox", "workspace-write", "--model", model, "-C", str(work), "-"]
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout)
        status = "completed" if proc.returncode == 0 else "agent_failed"
        events, stderr = proc.stdout, proc.stderr
        exit_code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        status, exit_code = "timeout", None
        events = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout or ""
        stderr = (exc.stderr or b"").decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr or ""
    target.mkdir(parents=True, exist_ok=True)
    (target / "events.jsonl").write_text(events, encoding="utf-8")
    (target / "stderr.txt").write_text(stderr, encoding="utf-8")
    score = check(task, work)
    artifact = work / task["expected_artifact"]
    saved_artifact = target / "artifact" / task["expected_artifact"]
    if artifact.is_file():
        saved_artifact.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(artifact, saved_artifact)
    shutil.rmtree(work)
    return {"task_id": task["id"], "condition": condition, "repeat": repeat,
            "model": model, "status": status, "exit_code": exit_code,
            "elapsed_seconds": round(time.monotonic() - start, 3), "usage": usage_from_events(events),
            "score": score, "artifact": str(saved_artifact) if saved_artifact.is_file() else None}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", type=Path, default=HERE / "tasks.json")
    p.add_argument("--task-id", action="append")
    p.add_argument("--model", default="gpt-6-astra")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--seed", type=int, default=20260919)
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--output", type=Path, default=HERE / "results" / "pilot")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    tasks = [x for x in json.loads(args.tasks.read_text()) if not args.task_id or x["id"] in args.task_id]
    attempts = [(task, condition, repeat) for task in tasks for repeat in range(args.repeats)
                for condition in ("no-skill", "tools-only", "with-skill")]
    random.Random(args.seed).shuffle(attempts)
    if args.dry_run:
        print(json.dumps({"attempts": len(attempts), "tasks": [x["id"] for x in tasks],
                          "order": [[x["id"], condition, repeat] for x, condition, repeat in attempts]}, ensure_ascii=False))
        return 0
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for index, (task, condition, repeat) in enumerate(attempts):
        target = output / f"{index:03d}-{task['id']}-{condition}-r{repeat}"
        row = run_one(task, condition, args.model, repeat, target, args.timeout)
        rows.append(row)
        (output / "attempts.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows))
        print(json.dumps({"attempt": index + 1, "task": task["id"], "condition": condition,
                          "passed": row["score"]["passed"]}, ensure_ascii=False), flush=True)
    print(json.dumps({"output": str(output / 'attempts.jsonl'), "attempts": len(rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
