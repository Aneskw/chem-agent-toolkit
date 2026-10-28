# PUG REST contract

The wrapper requests `ConnectivitySMILES,SMILES,MolecularFormula,MolecularWeight` in JSON from the official compound property API. `name`, `cid` and `inchikey` select path namespaces; `smiles` uses form POST.

One returned compound is required. Multiple records are reported as ambiguous with their CIDs; this is a package convention, not a claim that PubChem names are unique.

See [PUG REST](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest) for additional namespaces and operations. The wrapper intentionally does not expose them all.
