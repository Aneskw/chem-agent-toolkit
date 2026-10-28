---
name: chem-pubchem-query
description: "Retrieve one PubChem compound by explicit name, CID, InChIKey or SMILES, preserving identity, properties and query provenance."
license: MIT
---


# Query a PubChem compound

Use Python 3.10+ and network access; only the standard library is required. Run the included wrapper from any directory:

```bash
python <skill-dir>/scripts/query_pubchem.py --namespace name --query caffeine
python <skill-dir>/scripts/query_pubchem.py --namespace cid --query 2244 --output aspirin.json
python <skill-dir>/scripts/query_pubchem.py --namespace smiles --query 'CC(=O)Oc1ccccc1C(=O)O'
```

`--namespace`: `name` (default), `cid`, `inchikey`, or `smiles`. Use an explicit namespace rather than guessing an identifier's meaning. SMILES are sent by form POST to avoid path-character problems.

Check exit code **0** and `ok:true`. Read `cid`, `properties`, `source_url` and `retrieved_at`; preserve the original query. `connectivity_smiles` omits stereochemistry; `isomeric_smiles` retains the service's stereo/isotope representation. The legacy `canonical_smiles` field aliases connectivity SMILES, not a stereo-preserving identity. Molecular weight is returned as supplied by PubChem in g/mol.

Exit **2** / `ok:false` means invalid input, service failure, no usable record or an ambiguous match. If `matched_cids` is returned, choose the intended compound and query its CID; the wrapper does not silently choose the first match. Missing properties remain null. Do not equate a database annotation with a measurement of the supplied sample.

Interface: [official PUG REST documentation](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest). No account key or model weights are needed.
