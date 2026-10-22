"""Deterministic structure checks, explicit evidence gaps and execution dispatch."""
from __future__ import annotations

import ast
import re
import time
from pathlib import Path
from urllib.parse import unquote

from .package import manifest
from .records import redact, safe_relative
from .runtime import execute, validate_test


def result(name, problems, required=True, **extra):
    return {"name": name, "status": "fail" if problems else "pass", "required": required,
            "findings": problems, **extra}


def runtime_path_problems(package, files):
    problems = []
    for item in files:
        text = (package / item["path"]).read_text(encoding="utf-8")
        if re.search(r"\{(?:package|source:|run\}|bundle\}|tool:)", text) or re.search(r"[A-Za-z]:[/\\].*?\.pipeline[/\\]", text):
            problems.append("Pipeline-only path/macro in runtime file: " + item["path"])
    return problems


def static_checks(package, name=None, coverage=None, bundle=None, tool=False):
    package = Path(package)
    files = manifest(package)
    if tool:
        problems = []
        for item in files:
            if item["path"].endswith(".py"):
                try:
                    ast.parse((package / item["path"]).read_text(encoding="utf-8"))
                except SyntaxError as exc:
                    problems.append(str(exc))
        if not any(f["path"].startswith("scripts/") for f in files):
            problems.append("Tool missing scripts")
        return [result("tool_structure", problems), result("runtime_paths", runtime_path_problems(package, files))]
    if not (package / "SKILL.md").is_file():
        return [result("structure", ["Missing SKILL.md"])]
    main = (package / "SKILL.md").read_text(encoding="utf-8")
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
                ast.parse(path.read_text(encoding="utf-8"), filename=item["path"])
            except SyntaxError as exc:
                problems.append(f"Python syntax error in {item['path']}: {exc}")
        if path.suffix.lower() != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        # Inline Markdown links; code examples are not interpreted as Markdown links.
        prose = re.sub(r"```.*?```", "", text, flags=re.S)
        for href in re.findall(r"\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)", prose):
            href = unquote(href.strip("<>"))
            if re.match(r"^[a-zA-Z][\w+.-]*:", href) or href.startswith("#"):
                continue
            relative = href.split("#", 1)[0]
            target = path.parent / relative
            if not target.resolve().is_relative_to(Path(bundle or package).resolve()) or not target.is_file():
                problems.append(f"Broken or external package link in {item['path']}: {href}")
    checks = [result("structure", problems)]
    checks.append(result("runtime_paths", runtime_path_problems(package, files)))
    if coverage is not None:
        missing = []
        for key in ("scope", "io", "usage", "result_checks"):
            quote = coverage.get(key) if isinstance(coverage, dict) else None
            if not isinstance(quote, str) or not quote.strip() or quote not in main:
                missing.append("Missing exact author coverage quotation: " + key)
        checks.append(result("minimum_author_attestation", missing,
                             evidence_kind="author_attestation_not_semantic_proof"))
    return checks


def run_checks(config, artifact, package, sources, work, allow_generated=False):
    tests = [(item, "configured") for item in config["checks"]]
    tests += [(item, "generated") for item in artifact["tests"]]
    results = []
    known_evidence = {item["id"] for item in sources.evidence if item["excerpt"].strip()}
    for index, (test, origin) in enumerate(tests):
        try:
            remaining = config.get("_deadline", float("inf")) - time.monotonic()
            if remaining <= 0:
                results.append({"name": "build_time_budget", "status": "not_run", "required": True,
                                "findings": ["Build time budget exhausted before check execution"]})
                break
            validate_test(test)
            if origin == "generated" and (test.get("evidence") not in known_evidence or not test.get("purpose")):
                raise ValueError("Generated checks need real source evidence and purpose")
            if origin == "generated" and not allow_generated:
                results.append({"name": test["name"], "status": "not_run", "required": not bool(config["checks"]),
                                "origin": origin, "findings": ["Generated execution requires --execute-generated-checks"]})
                continue
            report = execute(test, package, sources, Path(work) / f"check-{index + 1}",
                             min(config["limits"]["check_timeout"], remaining), config["environment"].get("allow", []))
            report["origin"] = origin
            results.append(report)
        except (ValueError, OSError) as exc:
            results.append({"name": test.get("name", f"check-{index + 1}") if isinstance(test, dict) else "invalid-check",
                            "status": "fail", "required": True, "origin": origin, "findings": [redact(exc)]})
    if not tests:
        results.append({"name": "minimal_execution", "status": "not_run", "required": True,
                        "findings": ["No minimal result-checking execution test was provided"]})
    return results


def classify(checks):
    required = [item for item in checks if item.get("required")]
    if any(item["status"] == "fail" for item in required):
        return "failed"
    if not required or any(item["status"] == "not_run" for item in required):
        return "draft"
    return "ready"
