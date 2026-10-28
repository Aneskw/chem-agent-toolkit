---
name: chembl-molecule-flexmatch
description: "Retrieve ChEMBL candidates using the flexmatch structure operator, while distinguishing server matches from exact textual or stereochemical identity."
license: undetermined
---


# ChEMBL flexible structure lookup

Use for server-side lookup of molecules matching a query structure. The official molecule resource distinguishes `flexmatch` from exact canonical-SMILES equality. It must not be used as an unqualified stereo-identity test.

```python
import json
from urllib.parse import urlencode
from urllib.request import urlopen

smiles = "CC(=O)Oc1ccccc1C(=O)O"
url = "https://www.ebi.ac.uk/chembl/api/data/molecule.json?" + urlencode({
    "molecule_structures__canonical_smiles__flexmatch": smiles,
    "limit": 20,
})
with urlopen(url, timeout=30) as response:
    page = json.load(response)
matches = [(m["molecule_chembl_id"], m.get("molecule_structures")) for m in page["molecules"]]
```

Python standard library and network access suffice. Preserve each ID and returned structure. If the task needs exact stereochemistry, charge, isotopes or tautomer equivalence, compare returned structures under that explicitly declared policy; do not assume the server operator enforces every aspect. In particular, do not infer a universal salt/tautomer policy from the word “flexible.”

Follow `page_meta.next` if a complete match set is required. An empty list is no match; HTTP/schema errors are not. URL-encode SMILES as a query value, including `+`, `#`, brackets and slashes.

[Inspected official operator definition](https://github.com/chembl/chembl_webservices_2/blob/59fb52665cc1fc09a495d9a8c118687ddd0ad781/chembl_webservices/resources/molecule.py) and [service format/pagination](https://github.com/chembl/GLaDOS-docs/blob/4f41ab17ef202999ece407aa6003a27cf7840e71/web-services/chembl-data-web-services.md).
