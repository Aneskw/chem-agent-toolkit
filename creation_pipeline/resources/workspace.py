"""Original-source locators and optional views; indexing is not proof of reading."""
from pathlib import Path
import json
import shutil
import subprocess

if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "creation_pipeline.resources"

from creation_pipeline.resources.documents import read_text
from creation_pipeline.paths import PACKAGE_ROOT
from creation_pipeline.records import write_json, read_json, file_digest

IMAGES = {".png", ".jpg", ".jpeg", ".webp"}


def prepare(sources, work):
    work = Path(work)
    views = work / "views"
    views.mkdir(parents=True, exist_ok=True)
    processor = file_digest(Path(__file__).with_name("documents.py"))
    entries = []
    old_index = read_json(work / "resources.json") if (work / "resources.json").exists() else {}
    cached = {(e["source"], e["path"], e["sha256"]): e for e in old_index.get("files", [])}
    known = {(e["source"], e["path"]): e for e in sources.evidence
             if e.get("kind") == "source_locator"}
    for sid, source in sources.entries.items():
        root = Path(source["path"])
        for item in source["inventory"]:
            path = root if root.is_file() else root / item["path"]
            evidence = known.get((sid, item["path"]))
            if evidence is None:
                evidence = dict(source=sid, path=item["path"], sha256=item["sha256"],
                    start=1, end=0, offset=0, kind="source_locator",
                    excerpt="Source locator only; not a record of model reading: " + item["path"],
                    id=f"e{len(sources.evidence)+1}")
                sources.evidence.append(evidence)
            entry = dict(evidence_id=evidence["id"], source=sid, path=item["path"],
                         original=str(path), sha256=item["sha256"], bytes=item["bytes"])
            previous = cached.get((sid, item["path"], item["sha256"]), {})
            if previous.get("view_processor") == processor and previous.get("text_view") and Path(previous["text_view"]).is_file() and file_digest(previous["text_view"]) == previous.get("view_sha256"):
                entry.update({k: previous[k] for k in ("text_view", "view_sha256", "view_processor", "render_command") if k in previous})
                entries.append(entry)
                continue
            if path.suffix.lower() in {".pdf", ".docx", ".ipynb", ".html", ".xlsx"}:
                try:
                    target = views / (evidence["id"] + ".txt")
                    if path.suffix.lower() == ".pdf" and shutil.which("pdftotext"):
                        subprocess.run([shutil.which("pdftotext"), "-layout", "-enc", "UTF-8", str(path), str(target)], check=True, capture_output=True, timeout=sources.limits.get("converter_timeout", 60))
                    else:
                        subprocess.run([__import__("sys").executable, str(Path(__file__).with_name("documents.py")), str(path), str(target)],
                            check=True, capture_output=True, timeout=sources.limits.get("converter_timeout", 60))
                    entry["text_view"] = str(target)
                    entry["view_sha256"] = file_digest(target)
                    entry["view_processor"] = processor
                except Exception as exc:
                    # Optional parsers have different exception hierarchies. Originals survive.
                    detail = exc.stderr.decode("utf-8", errors="replace")[:500] if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc)[:300]
                    entry["view_warning"] = f"{type(exc).__name__}: {detail}"
                if path.suffix.lower() == ".pdf":
                    entry["render_command"] = [__import__("sys").executable,
                        str(Path(__file__).resolve()), str(path), "1", str(views / evidence["id"])]
            entries.append(entry)
    document = {"sources": sources.index(), "files": entries,
                "warning": "eN IDs identify source files, not proof of reading. Cite only inspected passages/pages.",
                "limits": "Snapshots exclude secrets, unsupported formats and files over configured budgets; see omissions.",
                "rendering": "render_command takes PDF, 1-based page, output prefix. Open the resulting PNG with the image tool."}
    document["helper"] = [__import__("sys").executable, str(PACKAGE_ROOT / "agent/tools.py")]
    document["commands"] = {"inventory": "inventory --run RUN [--query PATH_SUBSTRING] [--source ID] [--limit N --offset N]", "candidate": "candidate --run RUN --definition CANDIDATE_JSON", "supplement": "supplement --run RUN --url URL|--repo URL|--paper DOI --reason WHY [--ref COMMIT]",
        "write": "write --package PACKAGE --path RELATIVE --base64 SMALL_UTF8_CHUNK [--append]",
        "finish": "finish --run RUN --package PACKAGE --token TOKEN [--metadata JSON_FILE]",
        "check": "check --run RUN --package PACKAGE --definition JSON_FILE"}
    write_json(work / "resources.json", document)
    write_json(work / "source-evidence.json", sources.evidence)
    write_json(work / "resource-state.json", {"config": {k: v for k, v in sources.config.items() if not k.startswith("_")},
        "cache": str(sources.cache), "sources": sources.manifest(), "evidence": sources.evidence, "errors": sources.errors,
        "network_requests": sources.acquisition.requests})
    return {"helper": document["helper"], "run": str(work.resolve()), "resource_index": str(work / "resources.json"), "resource_count": len(entries),
            "reading_hint": "Avoid printing the full JSON index. Query paths with helper inventory or parse/filter it locally; browse original directories freely.",
            "view_warning_count": sum("view_warning" in e for e in entries),
            "view_warnings": [e for e in entries if "view_warning" in e][:3]}


def render_page(pdf, page, prefix):
    page = int(page)
    if page < 1:
        raise ValueError("Pages are 1-based")
    prefix = Path(prefix).resolve()
    prefix.parent.mkdir(parents=True, exist_ok=True)
    binary = shutil.which("pdftoppm")
    if not binary:
        raise ValueError("PDF page rendering requires pdftoppm (Poppler) on PATH")
    subprocess.run([binary, "-f", str(page), "-l", str(page), "-singlefile",
                    "-scale-to", "1600", "-png", str(Path(pdf).resolve()), str(prefix)],
                   check=True, capture_output=True, timeout=60)
    image = Path(str(prefix) + ".png")
    if not image.is_file():
        raise ValueError("Renderer did not produce the requested page")
    return str(image)


if __name__ == "__main__":
    # The helper is callable directly by an Agent outside the repository cwd.
    import sys
    print(render_page(*sys.argv[1:]))


def sync_sources(sources, work):
    state = read_json(Path(work) / "resource-state.json")
    sources.restore(state["sources"], state["evidence"], state["errors"])
    sources.acquisition.requests = state.get("network_requests", 0)
