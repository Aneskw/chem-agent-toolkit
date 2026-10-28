"""Deterministic structure checks, source references and syntax; no target execution."""
from __future__ import annotations

import ast
import tokenize
import re
import time
from pathlib import Path
from urllib.parse import unquote

from creation_pipeline.artifacts.package import manifest
from creation_pipeline.records import redact, safe_relative


def python_source(path):
    with tokenize.open(path) as stream:
        return stream.read()


def result(name, problems, required=True, **extra):
    return {"name": name, "status": "fail" if problems else "pass", "required": required,
            "findings": problems, **extra}


def runtime_path_problems(package, files):
    problems = []
    for item in files:
        path = package / item["path"]
        if path.suffix.lower() not in {".md", ".txt", ".py", ".sh", ".json", ".yaml", ".yml", ".toml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            continue
        if re.search(r"\{(?:package|source:|run\}|bundle\}|tool:|verification\}|example_runner\})", text) or re.search(r"[A-Za-z]:[/\\].*?\.pipeline[/\\]", text):
            problems.append("Pipeline-only path/macro in runtime file: " + item["path"])
    return problems


def static_checks(package, name=None, *, bundle=None, tool=False):
    package = Path(package)
    files = manifest(package)
    if tool:
        problems = []
        for item in files:
            if item["path"].endswith(".py"):
                try:
                    ast.parse(python_source(package / item["path"]))
                except (SyntaxError, UnicodeError) as exc:
                    problems.append(str(exc))
        if not any(f["path"].startswith("scripts/") for f in files):
            problems.append("Tool missing scripts")
        return [result("tool_structure", problems), result("runtime_paths", runtime_path_problems(package, files))]
    if not (package / "SKILL.md").is_file():
        return [result("structure", ["Missing SKILL.md"])]
    main = (package / "SKILL.md").read_text(encoding="utf-8-sig")
    problems = []
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", main, re.S)
    if not match:
        problems.append("Missing YAML frontmatter")
    else:
        try:
            import yaml
            metadata = yaml.safe_load(match[1])
            if not isinstance(metadata, dict):
                raise ValueError("Frontmatter must be a mapping")
            for field in ("name", "description"):
                if not isinstance(metadata.get(field), str) or not metadata[field].strip():
                    problems.append("Missing frontmatter " + field)
            if name and metadata.get("name") != name:
                problems.append("Skill name differs from approved plan")
        except ImportError:
            # Accept basic one-line metadata without requiring YAML for JSON-only builds.
            for field in ("name", "description"):
                value = re.search(rf"^{field}:\s*(\S.*)$", match[1], re.M)
                if not value or value[1].strip() in ("|", ">", ">-", "|-"):
                    problems.append("Install PyYAML for multiline frontmatter; otherwise use one-line fields")
                elif field == "name" and name and value[1].strip("\"'") != name:
                    problems.append("Skill name differs from approved plan")
        except Exception as exc:
            problems.append("Invalid YAML frontmatter: " + str(exc))
    for item in files:
        path = package / item["path"]
        if path.suffix.lower() == ".py":
            try:
                ast.parse(python_source(path), filename=item["path"])
            except (SyntaxError, UnicodeError) as exc:
                problems.append(f"Python syntax error in {item['path']}: {exc}")
        if path.suffix.lower() != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        # Inline Markdown links; code examples are not interpreted as Markdown links.
        prose = re.sub(r"```.*?```", "", text, flags=re.S)
        for href in re.findall(r"\]\((<[^>]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\)", prose):
            href = unquote(href.strip("<>"))
            if re.match(r"^[a-zA-Z][\w+.-]*:", href) or href.startswith("#"):
                continue
            relative = href.split("#", 1)[0]
            target = path.parent / relative
            if not target.resolve().is_relative_to(Path(bundle or package).resolve()) or not target.is_file():
                problems.append(f"Broken or external package link in {item['path']}: {href}")
    checks = [result("structure", problems)]
    checks.append(result("runtime_paths", runtime_path_problems(package, files)))
    return checks



def classify(checks):
    required = [item for item in checks if item.get("required")]
    if any(item["status"] == "fail" for item in required):
        return "failed"
    if not required or any(item["status"] != "pass" for item in required):
        return "incomplete"
    return "ready"
