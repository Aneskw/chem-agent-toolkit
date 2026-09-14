#!/usr/bin/env python3
"""Compare independent baselines with the packaged database/tool skills."""
import argparse
import json
import ssl
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def baseline_rdkit(value):
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors
    mol = Chem.MolFromSmiles(value) if value else None
    if mol is None:
        return {"ok": False}
    return {"ok": True, "molecular_weight": round(Descriptors.MolWt(mol), 3), "tpsa": round(rdMolDescriptors.CalcTPSA(mol), 2)}


def baseline_pubchem(value):
    encoded = urllib.parse.quote(value, safe="")
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded}/property/MolecularFormula/JSON"
    request = urllib.request.Request(url, headers={"User-Agent": "chem-agent-toolkit-eval/0.1"})
    context = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
    with urllib.request.urlopen(request, timeout=20, context=context) as response:
        row = json.load(response)["PropertyTable"]["Properties"][0]
    return {"ok": True, "cid": row["CID"], "molecular_formula": row.get("MolecularFormula")}


def packaged(task):
    if task["skill"] == "rdkit":
        script = ROOT / "tools-skills/rdkit/chem-rdkit-descriptors/scripts/calc_descriptors.py"
        command = [sys.executable, str(script), "--smiles", task["input"]]
    else:
        script = ROOT / "databases-skills/pubchem/chem-pubchem-query/scripts/query_pubchem.py"
        command = [sys.executable, str(script), "--query", task["input"]]
    completed = subprocess.run(command, capture_output=True, text=True)
    if task["skill"] == "rdkit":
        record = json.loads(completed.stdout.splitlines()[0])
    else:
        record = json.loads(completed.stdout)
    return record, completed.returncode


def check(task, result, returncode):
    expected_error = task.get("expected_error", False)
    if expected_error:
        return result.get("ok") is False and returncode != 0
    if result.get("ok") is not True:
        return False
    for key, value in task["expected"].items():
        actual = result.get(key)
        if actual is None:
            actual = result.get("properties", {}).get(key)
        if actual is None:
            actual = result.get("descriptors", {}).get(key)
        if actual != value:
            return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    tasks = json.loads((Path(__file__).with_name("tasks.json")).read_text())
    rows = []
    for task in tasks:
        try:
            baseline = baseline_rdkit(task["input"]) if task["skill"] == "rdkit" else baseline_pubchem(task["input"])
            baseline_ok = check(task, baseline, 0 if baseline.get("ok") else 2)
        except Exception as exc:
            baseline, baseline_ok = {"ok": False, "error": type(exc).__name__}, task.get("expected_error", False)
        try:
            skill_result, code = packaged(task)
            skill_ok = check(task, skill_result, code)
        except Exception as exc:
            skill_result, code, skill_ok = {"ok": False, "error": type(exc).__name__}, 2, False
        rows.append({"id": task["id"], "skill": task["skill"], "baseline_pass": baseline_ok, "skill_pass": skill_ok,
                     "execution_success": code == 0 if not task.get("expected_error") else code != 0,
                     "baseline": baseline, "skill": skill_result})
    summary = {"tasks": len(rows), "baseline_pass": sum(r["baseline_pass"] for r in rows),
               "skill_pass": sum(r["skill_pass"] for r in rows), "rows": rows}
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: summary[k] for k in ("tasks", "baseline_pass", "skill_pass")}, ensure_ascii=False))
    return 0 if summary["skill_pass"] == summary["tasks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
