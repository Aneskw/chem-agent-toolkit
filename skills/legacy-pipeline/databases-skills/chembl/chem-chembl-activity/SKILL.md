---
name: chem-chembl-activity
description: "Retrieve a page of ChEMBL activity records for a molecule or target, with assay context and pagination preserved."
license: Apache-2.0
---


# Retrieve ChEMBL activities

Requires Python 3.10+ and access to the public ChEMBL REST service; the wrapper uses the standard library.

```bash
python <skill-dir>/scripts/query_activity.py --molecule-id CHEMBL25 --limit 100
# Or query by target; these selectors are mutually exclusive:
python <skill-dir>/scripts/query_activity.py --target-id CHEMBL203 --limit 100 --offset 0
```

Input: one ChEMBL molecule or target ID, `limit` **1–1000** and nonnegative `offset`. Output JSON includes `activities`, `page_meta`, query URL and retrieval time. Require exit **0** / `ok:true`; an empty activities list is a valid no-record page. Exit **2** reports an input, network or response error.

For interpretation, retain `activity_id`, `assay_chembl_id`, `document_chembl_id`, `standard_type`, `standard_relation`, `standard_value` and `standard_units` when available. Null values remain unknown; a '<' or '>' relation is not an exact measurement. Do not pool heterogeneous assays/endpoints merely because they share a molecule or target.

This is **one page**, not the whole dataset. Use `page_meta.next` to determine whether more records exist. For another wrapper call, advance offset by the returned page limit; keep the same selector. Preserve page URLs if collecting a complete set. Check assay context before comparing values.

[Official service and pagination reference](https://github.com/chembl/GLaDOS-docs/blob/master/web-services/chembl-data-web-services.md). Results depend on the live database release.
