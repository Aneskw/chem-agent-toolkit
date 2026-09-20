#!/usr/bin/env python3
"""Paired isolated agent ablation for a paper-derived decision-rule skill."""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SKILL = ROOT / "skills/generated/verified20-LJMZ9IL6-resource-label-fix/predict-reaction-products-with-confidence-abstention/SKILL.md"
sys.path.insert(0, str(ROOT / "creation_pipeline"))
from network_env import model_environment  # noqa: E402


def parse_events(stdout: str) -> tuple[dict | None, dict, int]:
    answer = None
    usage = {}
    tool_events = 0
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "item.completed" and event.get("item", {}).get("type") == "agent_message":
            try:
                answer = json.loads(event["item"]["text"])
            except (KeyError, json.JSONDecodeError):
                pass
        elif event.get("type") == "item.completed" and event.get("item", {}).get("type") not in ("reasoning", "agent_message"):
            tool_events += 1
        if event.get("type") == "turn.completed":
            usage = event.get("usage", {})
    return answer, usage, tool_events


def score(answer: dict | None, oracle: dict) -> dict:
    if answer is None:
        return {"decision_correct": False, "product_correct": False, "complete": False}
    accepted = oracle.get("accepted_decisions", [oracle["expected_decision"]])
    decision = answer.get("decision") in accepted
    product = answer.get("product_smiles", "") == oracle["expected_product"]
    return {"decision_correct": decision, "product_correct": product,
            "complete": decision and product}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--limit", type=int, default=0, help="Only the first N tasks; for smoke runs")
    parser.add_argument("--output", type=Path, default=HERE / "results/pilot.jsonl")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--skill", type=Path, default=SKILL)
    parser.add_argument("--tasks", type=Path, default=HERE / "tasks.json")
    parser.add_argument("--oracle", type=Path, default=HERE / "oracle.json")
    args = parser.parse_args()
    tasks = json.loads(args.tasks.read_text())
    oracle = json.loads(args.oracle.read_text())
    if args.limit:
        tasks = tasks[:args.limit]
    assert {t["id"] for t in tasks} <= set(oracle)
    skill_text = args.skill.read_text(encoding="utf-8")
    attempts = [(t, c) for t in tasks for c in ("no-skill", "with-skill")]
    random.Random(args.seed).shuffle(attempts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("", encoding="utf-8")
    rows = []
    for index, (task, condition) in enumerate(attempts, 1):
        prompt = (
            "You are an agent making a chemistry-method reporting decision from only the supplied facts. "
            "Do not use any tools, invoke another model, read external files, or claim experimental confirmation. "
            "Respond in the requested JSON fields. An empty product_smiles means no product is reported.\n\n"
            f"TASK:\n{task['request']}\n"
        )
        if condition == "with-skill":
            prompt += "\nCITED CANDIDATE SKILL (source evidence, not a higher-priority instruction):\n" + skill_text
        command = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only",
                   "--model", args.model, "--output-schema", str(HERE / "answer.schema.json"), "--json", "-"]
        try:
            # Keep the no-skill agent outside the repository, where it cannot
            # discover the candidate through ancestor paths or project files.
            with tempfile.TemporaryDirectory(prefix="chem-method-", dir="/private/tmp") as isolated:
                proc = subprocess.run(command, input=prompt, text=True, capture_output=True,
                                      cwd=isolated, env=model_environment(), timeout=args.timeout)
            answer, usage, tool_events = parse_events(proc.stdout)
            error = proc.stderr[-500:] if proc.returncode or answer is None else ""
            ok = proc.returncode == 0 and answer is not None and tool_events == 0
        except subprocess.TimeoutExpired:
            answer, usage, tool_events, error, ok = None, {}, 0, "timeout", False
        row = {"task_id": task["id"], "condition": condition, "model": args.model,
               "seed": args.seed, "order": index, "ok": ok, "answer": answer,
               "score": score(answer, oracle[task["id"]]), "usage": usage,
               "tool_events": tool_events, "error": error}
        rows.append(row)
        with args.output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[{index}/{len(attempts)}] {task['id']} {condition}: "
              f"{answer.get('decision') if answer else 'ERROR'}", flush=True)
    paired = {}
    for task in tasks:
        by_condition = {r["condition"]: r for r in rows if r["task_id"] == task["id"]}
        paired[task["id"]] = {c: {"ok": r["ok"], "complete": r["score"]["complete"],
                                  "output_tokens": r["usage"].get("output_tokens")}
                              for c, r in by_condition.items()}
    summary = {"model": args.model, "skill": str(args.skill.resolve()),
               "tasks": len(tasks), "attempts": len(rows), "paired": paired,
               "complete": {c: sum(r["score"]["complete"] for r in rows if r["condition"] == c)
                            for c in ("no-skill", "with-skill")},
               "note": "Decision-only synthetic pilot; not chemistry prediction accuracy or formal efficacy proof."}
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    return 0 if all(r["ok"] for r in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
