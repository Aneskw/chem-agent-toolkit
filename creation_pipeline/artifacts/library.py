"""Adopt independently verified skills; a catalog is the single active name registry."""
import re
import shutil
import tempfile
from pathlib import Path
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.validation.acceptance import require_ready
from creation_pipeline.records import read_json, write_json, safe_relative, has_link, sanitized


def slug(value):
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:70].rstrip("-")
    if not value:
        raise ValueError("Batch label needs a readable ASCII name")
    return value


def render_index(root, catalog):
    """Describe available packages and collections without publishing build history."""
    tags = {item["path"]: item.get("tags", []) for item in catalog["skills"]}
    collections, packages = [], []
    for path in sorted(Path(root).iterdir(), key=lambda p: p.name):
        if not path.is_dir() or has_link(path):
            continue
        if (path / "SKILL.md").is_file():
            labels = ", ".join(tags.get(path.name, []))
            packages.append(f"- [{path.name}]({path.name}/SKILL.md)" + (f": {labels}" if labels else ""))
        elif (path / "README.md").is_file():
            title = (path / "README.md").read_text(encoding="utf-8").partition("\n")[0].lstrip("# ").strip() or path.name
            collections.append(f"- [{title}]({path.name}/README.md)")
    lines = ["# Skill library", "",
             "Each skill is a directory containing `SKILL.md` and any supporting files. Read the package's prerequisites before use. Collection indexes group related tasks; individual packages are listed below.", "",
             "Available instructions do not establish successful tool execution, scientific validity or measured benefit to an agent.", ""]
    if collections:
        lines.extend(["## Collections", "", *collections, ""])
    if packages:
        lines.extend(["## Individual packages", "", *packages, ""])
    return "\n".join(lines)


def adopt(output, records, config, destination):
    root = Path(destination).absolute()
    if has_link(root):
        raise ValueError("Linked library path")
    root.mkdir(parents=True, exist_ok=True)
    lock = safe_relative(root, ".catalog.lock")
    with lock.open("x") as handle:
        handle.close()
        try:
            catalog_path = safe_relative(root, "catalog.json")
            safe_relative(root, "README.md")
            catalog = read_json(catalog_path) if catalog_path.exists() else {"version": 1, "skills": []}
            old_catalog = catalog_path.read_bytes() if catalog_path.exists() else None
            old_readme = (root / "README.md").read_bytes() if (root / "README.md").exists() else None
            catalog = {"version": 1, "skills": [
                {"name": item["name"], "path": item["path"], "tags": item.get("tags", [])}
                for item in catalog["skills"]]}
            active = {v["name"]: v for v in catalog["skills"]}
            results, created = [], []
            try:
                for record in records:
                    name = record["name"]
                    if record["status"] != "ready":
                        results.append({"name": name, "status": "not_eligible"})
                        continue
                    require_ready(record)
                    source = safe_relative(Path(output) / "bundle/skills", name)
                    if manifest(source) != record["files"]:
                        raise ValueError("Changed package before adoption: " + name)
                    if name in active:
                        existing = safe_relative(root, active[name]["path"])
                        status = "already_present" if manifest(existing) == record["files"] else "conflict"
                        results.append({"name": name, "status": status, "path": str(existing)})
                        continue
                    # Also protect unmanaged skills with the same frontmatter name.
                    collision = any(re.search(r"(?m)^name:\s*[\"']?" + re.escape(name) + r"[\"']?\s*$",
                        p.read_text(encoding="utf-8")) for p in root.rglob("SKILL.md"))
                    target = safe_relative(root, name)
                    if collision or target.exists():
                        results.append({"name": name, "status": "conflict"})
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with tempfile.TemporaryDirectory(dir=root, prefix=".adopt-") as tmp:
                        staged = Path(tmp) / name
                        shutil.copytree(source, staged)
                        if manifest(staged) != record["files"]:
                            raise ValueError("Adoption copy mismatch")
                        staged.rename(target)
                    created.append(target)
                    item = {"name": name, "path": target.relative_to(root).as_posix(),
                            "tags": config["batch"]["tags"]}
                    catalog["skills"].append(item)
                    active[name] = item
                    results.append({"name": name, "status": "adopted", "path": str(target)})
                write_json(catalog_path, sanitized(catalog))
                (root / "README.md").write_text(render_index(root, catalog), encoding="utf-8")
                return results
            except Exception:
                for target in created:
                    shutil.rmtree(target)
                for path, original in ((catalog_path, old_catalog), (root / "README.md", old_readme)):
                    if original is None:
                        path.unlink(missing_ok=True)
                    else:
                        path.write_bytes(original)
                raise
        finally:
            lock.unlink(missing_ok=True)
