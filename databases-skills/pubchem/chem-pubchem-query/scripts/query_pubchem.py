#!/usr/bin/env python3
"""Minimal PubChem PUG REST compound-property query."""
import argparse
import json
import ssl
import sys
import urllib.parse
import urllib.request


def query_pubchem(value: str) -> dict:
    encoded = urllib.parse.quote(value, safe="")
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
        f"{encoded}/property/CanonicalSMILES,MolecularFormula,MolecularWeight/JSON"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "chem-pubchem-query/0.1"})
    # macOS Python installations may not load the system CA bundle by default.
    context = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
    with urllib.request.urlopen(request, timeout=20, context=context) as response:
        payload = json.load(response)
    rows = payload.get("PropertyTable", {}).get("Properties", [])
    if not rows or "CID" not in rows[0]:
        raise ValueError("PubChem returned no compound properties")
    row = rows[0]
    return {
        "ok": True,
        "input": value,
        "cid": row["CID"],
        "properties": {
            "canonical_smiles": row.get("ConnectivitySMILES") or row.get("CanonicalSMILES"),
            "molecular_formula": row.get("MolecularFormula"),
            "molecular_weight": row.get("MolecularWeight"),
        },
        "source_url": url,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = query_pubchem(args.query)
        code = 0
    except Exception as exc:  # keep CLI output machine-readable
        result = {"ok": False, "input": args.query, "error": f"{type(exc).__name__}: {exc}"}
        code = 2
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
