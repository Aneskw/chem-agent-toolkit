---
name: chembl-target-text-search
description: "Search ChEMBL target records by text and inspect target IDs, organism and components before selecting an assay target."
license: undetermined
---


# Search ChEMBL targets

Python standard library and network access are sufficient:

```python
import json
from urllib.parse import urlencode, urljoin
from urllib.request import urlopen

url = "https://www.ebi.ac.uk/chembl/api/data/target/search.json?" + urlencode({"q": "lipoxygenase", "limit": 20})
with urlopen(url, timeout=30) as response:
    page = json.load(response)
for target in page["targets"]:
    print(target["target_chembl_id"], target.get("pref_name"), target.get("organism"), target.get("target_type"))
next_url = urljoin(url, page["page_meta"]["next"]) if page["page_meta"].get("next") else None
```

Replace `q` with the user's search text. Retain `target_chembl_id`, organism, target type and `target_components`; use component accessions when a specific protein is intended. Text relevance is not proof of a unique biological target. A complex, family or organism-level target is not interchangeable with a single protein.

`targets: []` is a valid no-hit page. Follow `page_meta.next` only when more results are needed; the first page is not an exhaustive search. Keep the query URL and retrieval date. Handle HTTP/schema errors separately from no hits.

[Official filtering/search and pagination contract](https://github.com/chembl/GLaDOS-docs/blob/4f41ab17ef202999ece407aa6003a27cf7840e71/web-services/chembl-data-web-services.md).
