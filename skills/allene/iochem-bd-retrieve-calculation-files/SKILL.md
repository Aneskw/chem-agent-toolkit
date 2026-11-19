---
name: iochem-bd-retrieve-calculation-files
description: Retrieve published calculation metadata and files from an identified ioChem-BD Browse collection using its REST API.
---

# Retrieve published ioChem-BD calculation files

## Service and inputs

Use the hosted [ioChem-BD Browse REST API 1.0.0](https://docs.iochem-bd.org/api/browse.html), with response fields checked against [ioChem-BD 4.0.0](https://gitlab.com/ioChem-BD/iochem-bd/-/releases/4.0.0). Institutional services can run different releases; confirm that the selected node returns the documented JSON structure.

Obtain the institutional Browse address from the dataset landing page or the official [instance links](https://www.iochem-bd.com/aboutus.html). Its API base is `https://HOST/rest`; documented examples include `https://iochem-bd.iciq.es/rest` and `https://iochem-bd.urv.es/rest`. Public, readable records need no login. Restricted or embargoed records require a separate authorized access path.

The example uses [Python 3](https://www.python.org/downloads/) with its standard library. Supply:

| Input | Meaning |
| --- | --- |
| API base | The institutional endpoint serving the collection |
| Collection ID | The node's API `id`, not a DOI or the numeric tail of a Handle |
| Item and file selection | Choose a calculation, then the required file from its returned records |
| Output directory | A new local directory for the downloaded bytes and provenance |

If only a collection landing URL is supplied, inspect `GET /collections?limit=100&offset=0` and subsequent pages to match the collection's `name` and `handle` and obtain its `id`. Keep IDs tied to their originating node.

Browse maps a research project to a collection and each calculation to an item. An item can contain input files, output files and associated documents; the bitstreams are its individual files.

## Retrieve one selected file

Run the following as one Python session after supplying the API base and collection ID. The prompts deliberately leave scientific selection to the task: do not select the first calculation or file merely because it exists.

Collection item pages default to 100 records with offset 0. The example requests those values explicitly and advances the offset by the requested page size. For file enumeration it uses `GET /items/{id}?expand=bitstreams`, which returns all readable bitstreams without pagination in 4.0.0. The separate `/items/{id}/bitstreams` endpoint defaults to only 20 files.

```python
import json
import shutil
from pathlib import Path
from urllib.request import Request, urlopen

base = input("Institutional API base (https://HOST/rest): ").rstrip("/")
collection_id = int(input("Collection API id: "))
out = Path(input("New output directory: "))
out.mkdir(parents=True, exist_ok=False)

def get_json(path):
    with urlopen(Request(base + path, headers={
        "Accept": "application/json"
    }), timeout=60) as response:
        if "json" not in response.headers.get("Content-Type", "").lower():
            raise RuntimeError("Expected API JSON; inspect the service response.")
        return json.load(response)

limit, offset = 100, 0
while True:
    page = get_json(
        f"/collections/{collection_id}/items?limit={limit}&offset={offset}"
    )
    for item in page:
        print(item["id"], item["name"], item.get("handle"))
    if not page:
        raise RuntimeError("No visible items at this offset; check access and ID.")
    selected = input("Item id from this page, or Enter for next page: ").strip()
    if selected:
        item = next(x for x in page if x["id"] == int(selected))
        break
    offset += limit

item_id = item["id"]
metadata = get_json(f"/items/{item_id}/metadata")
expanded = get_json(f"/items/{item_id}?expand=bitstreams")
files = expanded["bitstreams"]
for file in files:
    print(file["id"], file["name"], file.get("bundleName"),
          file.get("mimeType"), file.get("sizeBytes"))
if not files:
    raise RuntimeError("This item exposes no readable bitstreams.")
file_id = int(input("Required bitstream id from this list: "))
file = next(x for x in files if x["id"] == file_id)

path = f"/bitstreams/{file_id}/retrieve"
destination = out / f"bitstream-{file_id}.bin"
with urlopen(base + path, timeout=60) as response:
    media_type = response.headers.get("Content-Type")
    with destination.open("xb") as target:
        shutil.copyfileobj(response, target)

record = {
    "api_base": base, "collection_id": collection_id,
    "item": expanded, "metadata": metadata,
    "selected_bitstream": file, "download_url": base + path,
    "local_file": destination.name, "response_content_type": media_type
}
(out / "provenance.json").write_text(
    json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(destination, destination.stat().st_size, "bytes")
```

The local `.bin` file preserves the response bytes without assuming a format. Its original filename, MIME type, expected `sizeBytes`, item Handle and calculation metadata are retained in `provenance.json`. Inspect the downloaded content and compare its size with `sizeBytes` before handing it to another tool; copy or rename it to the recorded original extension when that tool requires one.

## Interpret the result

Choose files by their name, description, bundle and format. An associated report is a different artifact from a program input or output; inspect the record and file content to determine what is actually available.

An empty collection page means no visible items at that offset. Permissions can filter results, so neither an empty nor a short page proves the underlying collection is empty or complete. An empty expanded bitstream list means no files are readable in the current access context.

HTTP errors stop the example: 404 indicates a missing resource or incorrect ID; 401/403 indicates an access problem. An HTML verification/login page is an access obstacle, even if HTTP status is 200. Treat it as a failed retrieval rather than a calculation artifact.

Successful download establishes access to a published file. It does not establish convergence, computational correctness or agreement with experimental measurements; use the retained metadata and program output for those assessments.
