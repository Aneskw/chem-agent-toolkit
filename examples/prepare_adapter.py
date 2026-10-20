"""Recover a pinned existing tool and prepare a lightweight-adapter acceptance case."""
from pathlib import Path
import subprocess
import argparse
import sys
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from creation_pipeline.records import digest, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--http-only", action="store_true")
    args = parser.parse_args()
    base = ROOT / ".pipeline/sample-sources/descriptor-adapter"
    base.mkdir(parents=True, exist_ok=True)
    historical = "tools-skills/rdkit/chem-rdkit-descriptors/scripts/calc_descriptors.py"
    proc = subprocess.run(["git", "show", "6bb535a:" + historical], cwd=ROOT, capture_output=True, check=True)
    tool = base / "calc_descriptors.py"
    tool.write_bytes(proc.stdout)
    revision = subprocess.run(["git", "rev-parse", "6bb535a"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    remote = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    if remote.startswith("git@github.com:"):
        repository = "https://github.com/" + remote.split(":", 1)[1].removesuffix(".git")
    elif remote.startswith("https://"):
        parsed = urlsplit(remote)
        repository = urlunsplit((parsed.scheme, parsed.hostname or "", parsed.path.removesuffix(".git"), "", ""))
    else:
        raise ValueError("This example needs a GitHub SSH or HTTPS origin to document portable source acquisition")
    requirement = base / "requirements.md"
    requirement.write_text("""# Task contract: batch JSON adapter for an existing descriptor tool

The source is this repository's MIT-licensed descriptor script at commit 6bb535a.
Preserve its calculate(text) behavior. This is format adaptation, not a new descriptor.
Create scripts/batch_descriptors.py, accepting --tool-path (the external original
calc_descriptors.py) and --input (a UTF-8 file containing one SMILES per line).
Load the original calculate function rather than copying the descriptor algorithm.
Write one JSON array to stdout, each row containing all original fields plus its
zero-based index. Preserve failed rows and input order. Exit 0 if all ok, 2 if any
row fails or the input file is empty. Empty file: return [] and exit 2.
The original tool returns ethanol CCO molecular_weight 46.069 and canonical_smiles
CCO; ethane CC has weight 30.07. Invalid 'not-a-smiles' returns ok false with
'Invalid or empty SMILES'. Check these stable fields, not cosmetic whitespace.
The original source must be available after installation; document --tool-path
and the pinned source acquisition location. Do not assume a local build path exists
on another machine. No prediction, experimental or drug-likeness claims are added.
""", encoding="utf-8")
    with requirement.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## Verified acquisition metadata\n\nRepository: {repository}\nPinned revision: {revision}\n"
                     f"Original repository-relative file: {historical}\n"
                     f"Source SHA-256: {digest(proc.stdout)}\n"
                     f"In an accessible checkout, recover it with `git show {revision}:{historical}` "
                     "and save stdout as calc_descriptors.py. Repository access may require the user's credentials. "
                     "Do not assume the historical active-tree path exists on the pipeline development branch.\n")
    good, mixed, empty = [base / name for name in ("valid.smi", "mixed.smi", "empty.smi")]
    good.write_text("CCO\nCC\n", encoding="utf-8")
    mixed.write_text("CCO\nnot-a-smiles\nCC\n", encoding="utf-8")
    empty.write_text("", encoding="utf-8")
    config = {"task": "Build the lightweight batch JSON adapter described by requirements.md for the existing descriptor tool. The skill must include the adapter and portable invocation instructions, preserving upstream behavior.",
              "http_only": args.http_only,
              "sources": [{"id": "tool", "path": str(tool), "sha256": digest(proc.stdout), "license": "MIT"},
                          {"id": "requirements", "path": str(requirement)},
                          {"id": "good", "path": str(good)}, {"id": "mixed", "path": str(mixed)},
                          {"id": "empty", "path": str(empty)}],
              "checks": [], "limits": {"model_calls": 14, "model_timeout": 240}}
    for name, source, expected_exit, expected in (
        ("preserve_valid_rows", "good", 0, {"0.ok": True, "0.index": 0, "0.descriptors.molecular_weight": 46.069, "1.index": 1}),
        ("preserve_failed_row_and_order", "mixed", 2, {"0.ok": True, "1.ok": False, "1.index": 1, "2.index": 2, "2.ok": True})):
        config["checks"].append({"name": name, "argv": ["{python}", "{package}/scripts/batch_descriptors.py",
            "--tool-path", "{source:tool}", "--input", "{source:" + source + "}"],
            "expected_exit": expected_exit, "json_equals": expected,
            "kind": "positive" if source == "good" else "negative"})
    config["checks"].append({"name": "empty_file", "argv": ["{python}", "{package}/scripts/batch_descriptors.py",
        "--tool-path", "{source:tool}", "--input", "{source:empty}"], "expected_exit": 2,
        "stdout_contains": ["[]"], "kind": "boundary"})
    write_json(ROOT / ".pipeline/sample-configs/descriptor-adapter.json", config)
    print("Prepared .pipeline/sample-configs/descriptor-adapter.json; no model called")


if __name__ == "__main__":
    main()
