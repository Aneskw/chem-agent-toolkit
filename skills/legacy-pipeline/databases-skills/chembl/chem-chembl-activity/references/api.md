# ChEMBL activity page

`GET https://www.ebi.ac.uk/chembl/api/data/activity.json` with exactly one `molecule_chembl_id` or `target_chembl_id`, plus `limit` and `offset`.

Read `activities` and `page_meta` together. The latter contains `next`, `previous`, `limit`, `offset` and `total_count`. A wrapper success is successful retrieval, not scientific validation.

[Official reference](https://github.com/chembl/GLaDOS-docs/blob/master/web-services/chembl-data-web-services.md).
