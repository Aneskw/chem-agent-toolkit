# PubChem compound resource contract

The query script is included at `scripts/query_pubchem.py`. Compound records
are fetched at runtime from PubChem PUG REST; no database snapshot is bundled.

API documentation: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest-tutorial

Direct JSON endpoint template:

```text
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/<namespace>/<identifier>/property/CanonicalSMILES,MolecularFormula,MolecularWeight/JSON
```

Example:

```bash
curl -L 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/caffeine/property/CanonicalSMILES,MolecularFormula,MolecularWeight/JSON'
```

Record the exact URL, timestamp, response hash, and HTTP status. Missing
records or service failure are `blocked_resources`; never fabricate properties.
