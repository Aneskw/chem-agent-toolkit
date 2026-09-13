# PubChem PUG REST API

The script calls the compound property endpoint:

`GET /rest/pug/compound/name/{identifier}/property/CanonicalSMILES,MolecularFormula,MolecularWeight/JSON`

The response is accepted only when `PropertyTable.Properties` contains a row with a `CID`.
