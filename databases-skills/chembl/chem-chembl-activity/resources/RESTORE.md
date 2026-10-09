# ChEMBL activity resource contract

The query wrapper and examples are included in this Skill. Activity records
are fetched at runtime; no database snapshot is bundled.

- Source: `scripts/query_activity.py`
- API documentation: https://www.ebi.ac.uk/chembl/api/data/docs
- Direct endpoint: https://www.ebi.ac.uk/chembl/api/data/activity.json

Example:

```bash
curl -L 'https://www.ebi.ac.uk/chembl/api/data/activity.json?molecule_chembl_id=CHEMBL25&limit=20'
```

Record the exact URL, retrieval timestamp, response hash, and HTTP status.
Unavailable API access is `blocked_resources`, not an empty dataset.
