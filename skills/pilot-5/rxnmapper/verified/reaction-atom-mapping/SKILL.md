---
name: reaction-atom-mapping
description: Assign atom correspondences to prepared reaction SMILES with RXNMapper, including batched inference, failed-record tracking and confidence interpretation.
---

# Map reaction atoms with RXNMapper

Use RXNMapper 0.4.3's pretrained attention-guided model to label corresponding precursor and product atoms. Start with prepared reaction SMILES; document extraction, model training, template extraction and experimental validation are separate tasks.

## Preparation

Supply strings in `precursor1.precursor2>>product1.product2` form, keeping reactants and reagents together on the left. Retain a stable record identifier and the original string. Mapping produces a new string; canonicalization can change component and atom order and removes existing atom-map labels. Do not join results back by string equality or assume output atom order matches the input.

The preconfigured environment includes the pretrained ALBERT model and tokenizer bundled with the [official RXNMapper 0.4.3 package](https://pypi.org/project/rxnmapper/0.4.3/). For local setup, the official [installation instructions](https://github.com/rxn4chemistry/rxnmapper/tree/v0.4.3#installation) support `python -m pip install "rxnmapper[rdkit]==0.4.3"`; use compatible dependencies from runtime.json, including Transformers below 5 and setuptools with `pkg_resources`. The supplied runtime uses CPU and requires no credentials or separate model download.

## Runtime environment

Use the preconfigured Docker image:

```bash
docker pull ghcr.io/jinselw/chem-tools:rxnmapper-v1
```

Execution example (Bash; replace the example filename or arguments for the task):

```bash
docker run --rm \
  --mount "type=bind,source=$(pwd),target=/work" \
  --workdir /work \
  ghcr.io/jinselw/chem-tools:rxnmapper-v1 \
  python map_reactions.py
```

Files written under `/work` persist in the mounted local directory. Adjust the example filename and mount directory as needed. With a compatible local environment, run the same code directly; tool versions, dependencies and external resource requirements are listed in [runtime.json](runtime.json).

## Map and save records

This example uses an illustrative batch size of 32 and explicitly enables canonicalization. Replace `records` with prepared records from the caller; keep the same order while pairing inputs and results.

```python
import json
from rxnmapper import BatchedMapper

records = [
    {"id": "rxn-001", "reaction": "CC[O-]~[Na+].BrCC>>CCOCC"},
    {"id": "rxn-002", "reaction": "invalid>>reaction"},
]
mapper = BatchedMapper(batch_size=32, canonicalize=True)
results = mapper.map_reactions_with_info([r["reaction"] for r in records])

with open("mapped_reactions.jsonl", "w", encoding="utf-8") as out:
    for record, result in zip(records, results, strict=True):
        row = dict(record)
        row["status"] = "mapped" if result else "failed"
        row["mapped_rxn"] = result["mapped_rxn"] if result else None
        row["confidence"] = float(result["confidence"]) if result else None
        out.write(json.dumps(row) + "\n")
```

`mapped_reactions.jsonl` contains one JSON object per input, including failures. The invalid example demonstrates failure tracking; it is not an acceptable reaction input. For larger datasets, feed successive record chunks through the same mapper and write each chunk before proceeding.

| Field or setting | Meaning |
| --- | --- |
| `mapped_rxn` | Reaction string with bracket atom-map labels such as `:1`; matching labels identify the predicted correspondence. Labels are identifiers, not atom-array indices or physical quantities. |
| `confidence` | Unitless product of the per-product-atom mapping scores. It is a model score, not a calibrated probability that the whole reaction is correct or experimental confirmation. |
| `{}` | A record that still failed after individual retry; it has no mapped reaction or confidence. |
| `canonicalize=True` | Explicit example choice. `BatchedMapper` defaults to `False`; the direct `RXNMapper` API defaults to canonicalization. |

A failed batch is retried individually, preserving one result position per input. Invalid SMILES and excessive token length can cause failures. The bundled model supports at most 512 encoded tokens, including special tokens; this is not a character or atom limit. Reduce batch size for memory pressure; it does not resolve an overlength individual reaction. Enable Python logging when diagnosing failures. Constructor/model-loading failures can still raise exceptions.

If only strings are needed, `mapper.map_reactions(rxns)` yields mapped strings and substitutes `>>` on failure by default (`placeholder_for_invalid` changes that placeholder). Keep the dictionary interface when identifiers, scores or explicit failure status matter. Do not interpret `>>` as a successful empty transformation.

## Inspect a correspondence when needed

Use the direct API on a small set of valid reactions for detailed inspection. It raises on input errors rather than supplying batched failure placeholders.

```python
from rxnmapper import RXNMapper

inspection = RXNMapper().get_attention_guided_atom_maps(
    [records[0]["reaction"]], canonicalize_rxns=True, detailed_output=True
)[0]
print(inspection["mapped_rxn"], inspection["confidence"])
print(inspection["mapping_tuples"])
# Preserve numeric arrays without treating them as JSON-native values:
import numpy as np
np.savez_compressed(
    "mapping_attention.npz",
    tokensxtokens_attns=inspection["tokensxtokens_attns"],
    pxrrxp_attns=inspection["pxrrxp_attns"],
)
with open("mapping_tokens.json", "w", encoding="utf-8") as out:
    json.dump(inspection["tokens"], out)
```

With the default `absolute_product_inds=False`, `mapping_tuples` contains `(product_atom_index, reactant_atom_index, score)`: zero-based atom indices on the respective sides of the model input and a unitless per-atom score. These refer to the processed input, not the original string or map-label numbers. `tokens` records the actual model tokens. `tokensxtokens_attns` is the square token-by-token attention array; `pxrrxp_attns` is the combined normalized product-by-reactant atom attention matrix used to begin assignment. Use arrays and tuples to inspect predictions; they do not establish a reaction mechanism. Save them with their record identifier and tokens if retaining an audit artifact.

The [versioned core interface](https://github.com/rxn4chemistry/rxnmapper/blob/v0.4.3/rxnmapper/core.py) documents detailed fields. Review ambiguous or chemically consequential mappings in context; no universal confidence acceptance threshold is supplied by this workflow.