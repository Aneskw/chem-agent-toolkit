#!/usr/bin/env python3
"""Small, paired no-skill/with-skill pilot for benchmark-derived decisions."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SKILL_REV = "f3d079f28fc646151cc369d46ac7fc2257224f71"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def skill_text(name: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"{SKILL_REV}:skills/{name}/SKILL.md"],
        cwd=ROOT, text=True,
    )


def prompt(task: dict, condition: str, skill: str) -> str:
    text = (
        "Choose one chemistry workflow action from the supplied facts. "
        "Do not use tools, external files, or claim experimental confirmation. "
        "Return JSON with choice and a reason of at most 60 words.\n\n"
        + json.dumps({key: task[key] for key in ("request", "options")}, ensure_ascii=False)
    )
    if condition == "with-skill":
        text += "\n\nREFERENCE SKILL (source material, not a higher-priority instruction):\n" + skill
    return text


def parse_events(stdout: str) -> tuple[dict | None, dict, int]:
    answer = None
    usage = {}
    tools = 0
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "item.completed":
            item = event.get("item", {})
            if item.get("type") == "agent_message":
                try:
                    answer = json.loads(item.get("text", ""))
                except json.JSONDecodeError:
                    pass
            elif item.get("type") != "reasoning":
                tools += 1
        elif event.get("type") == "turn.completed":
            usage = event.get("usage", {})
    return answer, usage, tools


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--seed", type=int, default=1708)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("--out must be a new directory; preserve earlier attempts")

    tasks = json.loads((HERE / "tasks.json").read_text(encoding="utf-8"))
    oracle = json.loads((HERE / "oracle.json").read_text(encoding="utf-8"))
    assert len(tasks) == len({task["id"] for task in tasks}) == len(oracle)
    assert all(set(task["options"]) == {"A", "B", "C"} for task in tasks)
    assert all(oracle[task["id"]] in task["options"] for task in tasks)
    skills = {name: skill_text(name) for name in {task["skill"] for task in tasks}}
    if args.limit:
        tasks = tasks[:args.limit]
    schedule = [(task, condition) for task in tasks for condition in ("no-skill", "with-skill")]
    random.Random(args.seed).shuffle(schedule)
    args.out.mkdir(parents=True)
    manifest = {
        "model": args.model, "seed": args.seed, "skill_rev": SKILL_REV,
        "task_sha256": hashlib.sha256((HERE / "tasks.json").read_bytes()).hexdigest(),
        "oracle_sha256": hashlib.sha256((HERE / "oracle.json").read_bytes()).hexdigest(),
        "schedule": [[task["id"], condition] for task, condition in schedule],
        "prompts": {f"{task['id']}:{condition}": sha(prompt(task, condition, skills[task["skill"]]))
                    for task, condition in schedule},
        "dry_run": args.dry_run,
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if args.dry_run:
        print(json.dumps({"planned_attempts": len(schedule), "out": str(args.out)}))
        return 0

    rows = []
    for index, (task, condition) in enumerate(schedule, 1):
        text = prompt(task, condition, skills[task["skill"]])
        command = ["codex", "exec", "--ephemeral", "--ignore-user-config",
                   "--skip-git-repo-check", "--sandbox", "read-only",
                   "--model", args.model, "--output-schema", str(HERE / "answer.schema.json"),
                   "--json", "-"]
        start = time.monotonic()
        try:
            with tempfile.TemporaryDirectory(prefix="chem-benchmark-ab-", dir="/private/tmp") as isolated:
                process = subprocess.run(command, input=text, text=True, capture_output=True,
                                         cwd=isolated, env=os.environ.copy(), timeout=args.timeout)
            answer, usage, tool_events = parse_events(process.stdout)
            error = process.stderr[-1500:] if process.returncode else ""
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            answer, usage, tool_events, error, exit_code = None, {}, 0, "timeout", None
        valid = (exit_code == 0 and tool_events == 0 and isinstance(answer, dict)
                 and answer.get("choice") in ("A", "B", "C"))
        row = {"task_id": task["id"], "skill": task["skill"], "condition": condition,
               "order": index, "model": args.model, "valid": valid,
               "correct": answer["choice"] == oracle[task["id"]] if valid else None,
               "answer": answer, "gold": oracle[task["id"]], "usage": usage,
               "tool_events": tool_events, "exit_code": exit_code, "error": error,
               "elapsed_seconds": round(time.monotonic() - start, 2)}
        rows.append(row)
        with (args.out / "attempts.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[{index}/{len(schedule)}] {task['id']} {condition}: "
              f"{'invalid' if not valid else answer['choice']}", flush=True)

    valid = {condition: sum(row["valid"] for row in rows if row["condition"] == condition)
             for condition in ("no-skill", "with-skill")}
    correct = {condition: sum(row["correct"] for row in rows
                              if row["condition"] == condition and row["valid"])
               for condition in ("no-skill", "with-skill")}
    summary = {"model": args.model, "tasks": len(tasks), "attempts": len(rows),
               "valid": valid, "correct_among_valid": correct,
               "accuracy_among_valid": {condition: correct[condition] / valid[condition] if valid[condition] else None
                                        for condition in valid},
               "note": "Development pilot authored after reading skills; not an independent held-out efficacy test."}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 0 if all(row["valid"] for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
