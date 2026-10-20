"""Prepare real local RDKit documentation and explicit engineering checks."""
from pathlib import Path
import inspect
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from creation_pipeline.records import digest, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--http-only", action="store_true", help="Use HTTP for the built-in OpenAI CLI provider")
    args = parser.parse_args()
    from rdkit import Chem, rdBase
    from rdkit.Chem import Descriptors
    base = ROOT / ".pipeline/sample-sources/rdkit"
    base.mkdir(parents=True, exist_ok=True)
    doc = (f"# Local official RDKit API documentation\n\nInstalled version: {rdBase.rdkitVersion}\n"
           "Upstream: https://github.com/rdkit/rdkit (BSD-3-Clause).\n"
           "These are installed API docstrings, not independently written assertions.\n\n"
           "## Chem.MolFromSmiles\n" + Chem.MolFromSmiles.__doc__ + "\n\n"
           "## Descriptors.MolWt\n" + Descriptors.MolWt.__doc__ + "\n\n"
           "MolWt returns a float; molecular weight is expressed in g/mol.\n"
           "An empty parsed molecule is not a meaningful molecular weight input for these tasks.\n")
    (base / "api.md").write_text(doc, encoding="utf-8")
    source = Path(inspect.getfile(Descriptors))
    (base / "Descriptors.py").write_bytes(source.read_bytes())
    write_json(base / "provenance.json", {"version": rdBase.rdkitVersion,
        "installed_descriptor_source": str(source), "sha256": digest(source.read_bytes()),
        "api_sha256": digest(doc.encode()), "license": "BSD-3-Clause"})
    common = {"sources": [{"id": "rdkit", "path": str(base / "api.md")}],
              "http_only": args.http_only,
              "limits": {"model_calls": 14, "repair_rounds": 2, "model_timeout": 240}}
    direct = {**common, "task": "Package the installed RDKit Chem.MolFromSmiles and Descriptors.MolWt API for computing average molecular weight of one nonempty SMILES. Keep it a compact single SKILL.md, with an executable Python example that prints ethane CC's weight (30.07 g/mol). Bind the example input to a smiles variable so configured checks can substitute boundary inputs. Raise ValueError for invalid, empty or whitespace-only input before computing MolWt. No wrapper needed.",
              "checks": [{"name": "documented_ethane_example", "argv": ["{python}", str(ROOT / "examples/verify_python_example.py"), "{package}"],
                          "stdout_contains": ["30.07"], "expected_exit": 0, "kind": "positive"}]}
    for name, smiles in (("reject_empty", ""), ("reject_whitespace", "   "), ("reject_invalid", "C1(CC")):
        direct["checks"].append({"name": name,
            "argv": ["{python}", str(ROOT / "examples/verify_python_example.py"), "{package}",
                     "--smiles", smiles, "--expect-rejection"],
            "stdout_contains": ["input-rejected"], "kind": "boundary"})
    write_json(ROOT / ".pipeline/sample-configs/rdkit-direct.json", direct)
    requirement = ("# Mass window task contract\n\nAdd a user-defined inclusive mass-window decision to RDKit MolWt. "
        "This is a numerical filter, not a drug-likeness or scientific feasibility claim. "
        "Implement scripts/check_mass_window.py with --smiles, --min-mass and --max-mass. "
        "Return JSON with accepted boolean, smiles, mass; exit 0 for valid calculations whether accepted or rejected. "
        "Invalid/empty SMILES or reversed/nonfinite bounds must write JSON containing error to stdout and exit 2. "
        "CC is about 30.07 g/mol according to the upstream MolWt doctest: bounds [29,31] accept, "
        "[31,40] reject, and inclusive equality [30.07,30.07] accepts within the actual computed float representation. "
        "Do not invent scientific cutoffs.\n")
    (base / "mass-window-requirements.md").write_text(requirement, encoding="utf-8")
    extension = {**common, "intent": "extension",
        "sources": common["sources"] + [{"id": "requirements", "path": str(base / "mass-window-requirements.md")}],
        "task": "Package a user-configurable inclusive molecular-weight window decision using RDKit. Follow mass-window-requirements.md and implement its specified CLI. Include a complete minimal example and explain that acceptance only concerns this numerical window.",
        "checks": [
            {"name": "accept_ethane", "argv": ["{python}", "{package}/scripts/check_mass_window.py", "--smiles", "CC", "--min-mass", "29", "--max-mass", "31"], "json_equals": {"accepted": True}, "kind": "positive"},
            {"name": "reject_ethane", "argv": ["{python}", "{package}/scripts/check_mass_window.py", "--smiles", "CC", "--min-mass", "31", "--max-mass", "40"], "json_equals": {"accepted": False}, "kind": "negative"},
            {"name": "invalid_input", "argv": ["{python}", "{package}/scripts/check_mass_window.py", "--smiles", "C1(CC", "--min-mass", "29", "--max-mass", "31"], "expected_exit": 2, "stdout_contains": ["error"], "kind": "boundary"},
            {"name": "inclusive_equality", "argv": ["{python}", "{package}/scripts/check_mass_window.py", "--smiles", "CC", "--min-mass", "30.07", "--max-mass", "30.07"], "json_equals": {"accepted": True}, "kind": "boundary"},
            {"name": "reversed_bounds", "argv": ["{python}", "{package}/scripts/check_mass_window.py", "--smiles", "CC", "--min-mass", "40", "--max-mass", "31"], "expected_exit": 2, "stdout_contains": ["error"], "kind": "boundary"},
            {"name": "nonfinite_bound", "argv": ["{python}", "{package}/scripts/check_mass_window.py", "--smiles", "CC", "--min-mass", "nan", "--max-mass", "31"], "expected_exit": 2, "stdout_contains": ["error"], "kind": "boundary"},
            {"name": "empty_smiles", "argv": ["{python}", "{package}/scripts/check_mass_window.py", "--smiles", " ", "--min-mass", "29", "--max-mass", "31"], "expected_exit": 2, "stdout_contains": ["error"], "kind": "boundary"},
        ]}
    write_json(ROOT / ".pipeline/sample-configs/rdkit-extension.json", extension)
    print(json.dumps({"rdkit": rdBase.rdkitVersion, "configurations": str(ROOT / ".pipeline/sample-configs")}, indent=2))


if __name__ == "__main__":
    main()
