#!/usr/bin/env python3
"""Validate the user-defined Chemical Skill v0.3 contract."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

SECTIONS = [
    "Applicability", "Credibility", "Reference", "Input & Output",
    "Procedure Guidance", "Success Criteria", "Matters & Troubleshooting",
]
KEYS = ["name", "description", "license", "compatibility", "allowed-tools"]


def validate(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors = []
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if not match:
        return ["missing YAML frontmatter"]
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return [f"invalid YAML: {exc}"]
    if not isinstance(meta, dict):
        return ["frontmatter must be a mapping"]
    for key in KEYS:
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            errors.append(f"missing or empty {key}")
    if meta.get("name") != path.parent.name:
        errors.append("name must match directory")
    description = str(meta.get("description", ""))
    if "Invoke for:" not in description:
        errors.append("description needs Invoke for: positive prompt")
    headings = re.findall(r"^## (.+)$", text, re.M)
    if headings != SECTIONS:
        errors.append(f"expected sections {SECTIONS}, got {headings}")
    if not re.search(r"\b(high confidence|medium confidence|low confidence)\b", text, re.I):
        errors.append("Credibility needs a confidence tier")
    for placeholder in ("TODO", "TBD", "<skill>"):
        if placeholder in text:
            errors.append(f"unfinished placeholder: {placeholder}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    failed = False
    for path in args.paths:
        skill_file = path / "SKILL.md" if path.is_dir() else path
        errors = validate(skill_file)
        failed |= bool(errors)
        print(f"{skill_file}: {'VALID' if not errors else '; '.join(errors)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
