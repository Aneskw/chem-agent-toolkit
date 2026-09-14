#!/usr/bin/env python3
"""Small Responses API adapter for run_agent_ablation.py (stdlib only)."""
import json
import os
import urllib.request
from pathlib import Path


def main():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("OPENAI_API_KEY is not set")
    prompt = os.environ["TASK_PROMPT"]
    skill_path = os.environ.get("SKILL_PATH", "")
    if skill_path:
        prompt += "\n\nRead and follow this skill document:\n" + Path(skill_path).read_text(encoding="utf-8")
    body = {"model": os.environ.get("OPENAI_MODEL", "gpt-5-nano"), "input": prompt, "max_output_tokens": 1200}
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = json.load(response)
    text = payload.get("output_text")
    if text is None:
        text = "".join(part.get("text", "") for item in payload.get("output", []) for part in item.get("content", []))
    print(text)


if __name__ == "__main__":
    main()
