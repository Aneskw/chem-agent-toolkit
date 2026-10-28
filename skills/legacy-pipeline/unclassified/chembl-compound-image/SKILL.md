---
name: chembl-compound-image
description: "Fetch a ChEMBL compound depiction as SVG with explicit image dimensions; use when an existing ChEMBL structure needs a rendered image."
license: undetermined
---


# Retrieve a ChEMBL structure image

Requires network access and a compound ChEMBL ID or a Standard InChIKey already present in ChEMBL. No model or local chemistry package is needed.

```python
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import urlopen

identifier = "CHEMBL25"
query = urlencode({"format": "svg", "dimensions": 300, "ignoreCoords": 0})
url = "https://www.ebi.ac.uk/chembl/api/data/image/" + quote(identifier, safe="") + "?" + query
with urlopen(url, timeout=30) as response:
    image = response.read()
Path("compound.svg").write_bytes(image)
```

`dimensions`: square side **1–500 pixels**, default 500. `ignoreCoords=0` uses stored coordinates; `1` requests new depiction coordinates. Use SVG explicitly rather than guessing a format from a returned file name. Image requests have no list pagination.

Keep the identifier and URL with the image. HTTP failure is not an empty depiction; do not save an error page as SVG. Depiction does not establish stereochemical assignment or experimental identity of a supplied sample.

[Official image options](https://github.com/chembl/GLaDOS-docs/blob/4f41ab17ef202999ece407aa6003a27cf7840e71/web-services/chembl-data-web-services.md#molecule-images).
