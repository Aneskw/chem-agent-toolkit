"""Adopt independently verified skills; a catalog is the single active name registry."""
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.records import read_json, write_json, safe_relative, has_link, sanitized


def slug(value):
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:70].rstrip("-")
    if not value:
        raise ValueError("Batch label needs a readable ASCII name")
    return value


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
            active = {v["name"]: v for v in catalog["skills"]}
            batch = datetime.now().strftime("%Y-%m-%d") + "-" + slug(config["batch"]["label"])
            results, created = [], []
            try:
                for record in records:
                    name = record["name"]
                    if record["status"] != "ready":
                        results.append({"name": name, "status": "not_eligible"})
                        continue
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
                    target = safe_relative(root, batch + "/" + name)
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
                    item = {"name": name, "path": target.relative_to(root).as_posix(), "batch": batch,
                            "tags": config["batch"]["tags"], "build_id": Path(output).name,
                            "scope": record["plan"]["scope"], "files": record["files"],
                            "checks": [{k: c.get(k) for k in ("name", "status", "evidence_kind")} for c in record["checks"]],
                            "issues": record.get("issues", []), "notes": record.get("notes", []),
                            "unverified": [{"name": c["name"], "findings": c.get("findings", [])} for c in record["checks"] if c["status"] == "not_run"], "agent_efficacy": "not_evaluated"}
                    doc = read_json(Path(output) / "plan.json")
                    item["sources"] = [{k: s[k] for k in ("id", "url", "repo", "resolved_ref", "snapshot_id") if k in s} for s in doc["sources"]]
                    catalog["skills"].append(item)
                    active[name] = item
                    results.append({"name": name, "status": "adopted", "path": str(target)})
                write_json(catalog_path, sanitized(catalog))
                lines = ["# Skills", "", "Reviewed packages; inspect recorded checks and unverified scope. Agent benefit remains unmeasured.", "",
                         "| Skill | Tags | Batch |", "| --- | --- | --- |"]
                for item in catalog["skills"]:
                    lines.append(f"| [{item['name']}]({item['path']}/SKILL.md) | {', '.join(item['tags'])} | {item['batch']} |")
                (root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
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
