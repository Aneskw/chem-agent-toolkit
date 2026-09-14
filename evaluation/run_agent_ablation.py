#!/usr/bin/env python3
"""Run a user-supplied agent command under no-skill/with-skill conditions."""
import argparse
import json
import os
import shlex
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-cmd", required=True, help="command that reads TASK_PROMPT and optional SKILL_PATH")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    tasks = json.loads((Path(__file__).with_name("agent_tasks.json")).read_text())
    rows = []
    for task in tasks:
        skill_path = next(ROOT.rglob(f"{task['skill']}/SKILL.md"), None)
        for condition in ("no-skill", "with-skill"):
            env = os.environ.copy()
            env["TASK_ID"] = task["id"]
            env["TASK_PROMPT"] = task["request"]
            env["SKILL_PATH"] = str(skill_path) if condition == "with-skill" and skill_path else ""
            start = time.monotonic()
            completed = subprocess.run(shlex.split(args.agent_cmd), env=env, capture_output=True, text=True)
            rows.append({"task_id": task["id"], "condition": condition, "model": env.get("MODEL", "unspecified"),
                         "ok": completed.returncode == 0, "output": completed.stdout,
                         "stderr": completed.stderr, "exit_code": completed.returncode,
                         "retries": 0, "elapsed_seconds": round(time.monotonic() - start, 3)})
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    print(f"wrote {len(rows)} attempts to {output}")


if __name__ == "__main__":
    main()
