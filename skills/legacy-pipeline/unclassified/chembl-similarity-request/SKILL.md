---
name: chembl-similarity-request
description: "Search ChEMBL molecules using a declared percentage similarity cutoff, then interpret returned scores and pagination without treating similarity as identity or activity."
license: undetermined
---


# Query ChEMBL similarity

Input: SMILES, a ChEMBL molecule ID, or a Standard InChIKey already in ChEMBL, plus the requested cutoff. The service documents a **Tanimoto percentage cutoff**: use `80` for 80%, not `0.8`.

```python
import json
from urllib.parse import quote, urlencode
from urllib.request import urlopen

query_structure, cutoff = "CHEMBL25", 80
url = ("https://www.ebi.ac.uk/chembl/api/data/similarity/"
       + quote(query_structure, safe="") + "/" + str(cutoff) + ".json?"
       + urlencode({"limit": 20}))
with urlopen(url, timeout=30) as response:
    page = json.load(response)
for molecule in page["molecules"]:
    print(molecule["molecule_chembl_id"], molecule.get("similarity"))
```

Requires only network access and Python's standard library. Use an integer percentage supported by the service; the example is a task choice, not a scientifically universal cutoff. Preserve returned structures, scores, query and database release when comparing runs.

Read `page_meta.next` before assuming the list is complete. Invalid input/HTTP failure differs from an empty `molecules` list. ChEMBL's server-side similarity is not automatically the same as a locally chosen Morgan fingerprint; 100% similarity is not proof of stereo identity, shared activity or experimental equivalence.

[Official examples](https://github.com/chembl/GLaDOS-docs/blob/4f41ab17ef202999ece407aa6003a27cf7840e71/web-services/chembl-data-web-services.md#chemical-searching) and [parent-structure search caveat](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/drug-and-compound-questions).
