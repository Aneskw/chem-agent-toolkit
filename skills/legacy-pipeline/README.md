# Legacy Skill collection

Migration status: **66 retained; 20 removed or excluded**, from 86 unique historical packages at main commit `1e7cada4f693501b35e69b99676cdcbcc801c29c`.

- Original tool/model/database classifications are retained; previously unclassified packages are under `unclassified/`.
- Retained packages have received content and support-file review. External tools, weights and datasets remain prerequisites where specified; full runtime correctness and Agent benefit are not established.
- [catalog.json](catalog.json) records source revisions, imported/current file hashes and changes.

## Retained packages

| Classification | Packages |
| --- | --- |
| databases-skills | 4 |
| models-skills | 7 |
| tools-skills | 13 |
| unclassified | 42 |

| Skill | Classification |
| --- | --- |
| [aggregate-augmented-reaction-predictions](unclassified/aggregate-augmented-reaction-predictions/SKILL.md) | unclassified |
| [augment-and-rank-retrosynthesis-predictions](models-skills/open-models/augment-and-rank-retrosynthesis-predictions/SKILL.md) | models-skills |
| [bond-cleavage-mechanism-ranking](unclassified/bond-cleavage-mechanism-ranking/SKILL.md) | unclassified |
| [check-mismatched-retrosynthesis-with-forward-prediction](unclassified/check-mismatched-retrosynthesis-with-forward-prediction/SKILL.md) | unclassified |
| [chem-ase-geometry](tools-skills/ASE/chem-ase-geometry/SKILL.md) | tools-skills |
| [chem-chembl-activity](databases-skills/chembl/chem-chembl-activity/SKILL.md) | databases-skills |
| [chem-idpp-path](tools-skills/ASE/chem-idpp-path/SKILL.md) | tools-skills |
| [chem-openbabel-convert](tools-skills/openbabel/chem-openbabel-convert/SKILL.md) | tools-skills |
| [chem-pubchem-query](databases-skills/pubchem/chem-pubchem-query/SKILL.md) | databases-skills |
| [chem-rdkit-compound-filter](tools-skills/rdkit/chem-rdkit-compound-filter/SKILL.md) | tools-skills |
| [chem-rdkit-descriptors](tools-skills/rdkit/chem-rdkit-descriptors/SKILL.md) | tools-skills |
| [chem-reaction-atommap-audit](tools-skills/rdkit/chem-reaction-atommap-audit/SKILL.md) | tools-skills |
| [chem-reaction-stage-audit](unclassified/chem-reaction-stage-audit/SKILL.md) | unclassified |
| [chem-retro-candidate-evaluation](tools-skills/rdkit/chem-retro-candidate-evaluation/SKILL.md) | tools-skills |
| [chem-structure-check](tools-skills/ASE/chem-structure-check/SKILL.md) | tools-skills |
| [chem-uspto50k-split](databases-skills/uspto50k/chem-uspto50k-split/SKILL.md) | databases-skills |
| [chem-vasp-calculation](tools-skills/VASP/chem-vasp-calculation/SKILL.md) | tools-skills |
| [chem-vasp-neb](tools-skills/VASP/chem-vasp-neb/SKILL.md) | tools-skills |
| [chem-vasp-neb-validation](tools-skills/VASP/chem-vasp-neb-validation/SKILL.md) | tools-skills |
| [chem-vasp-ts-validation](tools-skills/VASP/chem-vasp-ts-validation/SKILL.md) | tools-skills |
| [chem-xtb-ts-validation](tools-skills/chem-xtb-ts-validation/SKILL.md) | tools-skills |
| [chembl-compound-image](unclassified/chembl-compound-image/SKILL.md) | unclassified |
| [chembl-molecule-flexmatch](unclassified/chembl-molecule-flexmatch/SKILL.md) | unclassified |
| [chembl-similarity-request](unclassified/chembl-similarity-request/SKILL.md) | unclassified |
| [chembl-target-text-search](unclassified/chembl-target-text-search/SKILL.md) | unclassified |
| [choose-retrosynthesis-evaluation-scope](unclassified/choose-retrosynthesis-evaluation-scope/SKILL.md) | unclassified |
| [committee-force-disagreement](unclassified/committee-force-disagreement/SKILL.md) | unclassified |
| [conformer-ensemble-population](unclassified/conformer-ensemble-population/SKILL.md) | unclassified |
| [construct-retrosynthetic-route-benchmark](unclassified/construct-retrosynthetic-route-benchmark/SKILL.md) | unclassified |
| [context-aware-retrosynthetic-planning](unclassified/context-aware-retrosynthetic-planning/SKILL.md) | unclassified |
| [convex-hull-reference-scale](unclassified/convex-hull-reference-scale/SKILL.md) | unclassified |
| [defect-formation-reference](unclassified/defect-formation-reference/SKILL.md) | unclassified |
| [delaney-esol-scaffold-evaluation](databases-skills/delaney-esol/delaney-esol-scaffold-evaluation/SKILL.md) | databases-skills |
| [derive-local-reaction-template-library](unclassified/derive-local-reaction-template-library/SKILL.md) | unclassified |
| [electrochemical-stability-window](unclassified/electrochemical-stability-window/SKILL.md) | unclassified |
| [evaluate-planning-with-depth-pruning-and-set-matching](unclassified/evaluate-planning-with-depth-pruning-and-set-matching/SKILL.md) | unclassified |
| [gln-constrained-retrosynthesis-search](unclassified/gln-constrained-retrosynthesis-search/SKILL.md) | unclassified |
| [identify-reaction-centers-and-extract-synthons](unclassified/identify-reaction-centers-and-extract-synthons/SKILL.md) | unclassified |
| [ir-spectrum-candidate-ranking](unclassified/ir-spectrum-candidate-ranking/SKILL.md) | unclassified |
| [localretro-single-step-retrosynthesis](models-skills/open-models/localretro-single-step-retrosynthesis/SKILL.md) | models-skills |
| [localretro-template-library-preflight](models-skills/open-models/localretro-template-library-preflight/SKILL.md) | models-skills |
| [microstate-aware-virtual-screening](unclassified/microstate-aware-virtual-screening/SKILL.md) | unclassified |
| [mlip-unit-consistent-error-audit](unclassified/mlip-unit-consistent-error-audit/SKILL.md) | unclassified |
| [nmr-kinetics-deconvolution](unclassified/nmr-kinetics-deconvolution/SKILL.md) | unclassified |
| [parent-analog-stereo-audit](unclassified/parent-analog-stereo-audit/SKILL.md) | unclassified |
| [parent-standardized-lead-triage](unclassified/parent-standardized-lead-triage/SKILL.md) | unclassified |
| [polymorph-free-energy-comparison](unclassified/polymorph-free-energy-comparison/SKILL.md) | unclassified |
| [pose-geometry-validity-gate](unclassified/pose-geometry-validity-gate/SKILL.md) | unclassified |
| [potential-consistent-thermochemistry](unclassified/potential-consistent-thermochemistry/SKILL.md) | unclassified |
| [predict-class-conditioned-local-retrosynthesis](unclassified/predict-class-conditioned-local-retrosynthesis/SKILL.md) | unclassified |
| [predict-reactants-through-reaction-centers](unclassified/predict-reactants-through-reaction-centers/SKILL.md) | unclassified |
| [predict-reaction-products-with-confidence-abstention](unclassified/predict-reaction-products-with-confidence-abstention/SKILL.md) | unclassified |
| [prepare-single-product-reaction-sequences](unclassified/prepare-single-product-reaction-sequences/SKILL.md) | unclassified |
| [quasi-harmonic-volume-scan](unclassified/quasi-harmonic-volume-scan/SKILL.md) | unclassified |
| [reaction-center-guided-retrosynthesis](models-skills/open-models/reaction-center-guided-retrosynthesis/SKILL.md) | models-skills |
| [replicate-ligand-md-stability](unclassified/replicate-ligand-md-stability/SKILL.md) | unclassified |
| [retro-star-retrosynthetic-planning](models-skills/open-models/retro-star-retrosynthetic-planning/SKILL.md) | models-skills |
| [retroprime-inference-preflight](models-skills/open-models/retroprime-inference-preflight/SKILL.md) | models-skills |
| [retroprime-two-stage-inference-check](models-skills/open-models/retroprime-two-stage-inference-check/SKILL.md) | models-skills |
| [select-and-evaluate-graph2smiles-predictions](unclassified/select-and-evaluate-graph2smiles-predictions/SKILL.md) | unclassified |
| [select-reaction-smiles-augmentation](unclassified/select-reaction-smiles-augmentation/SKILL.md) | unclassified |
| [symmetry-aware-redocking-control](unclassified/symmetry-aware-redocking-control/SKILL.md) | unclassified |
| [synthesis-precursor-evidence](unclassified/synthesis-precursor-evidence/SKILL.md) | unclassified |
| [template-guided-docking-box](unclassified/template-guided-docking-box/SKILL.md) | unclassified |
| [widom-sorbent-screening](unclassified/widom-sorbent-screening/SKILL.md) | unclassified |
| [xrd-mixture-phase-quantification](unclassified/xrd-mixture-phase-quantification/SKILL.md) | unclassified |

## Removed or excluded packages (20)

Exclusions reflect missing essentials for the promised capability or limited independent value. External dependencies and lack of runtime tests alone were not grounds for removal.

| Package | Specific reason |
| --- | --- |
| `attach-semi-template-residuals` | Template representation and attachment operations are undefined; map/match/replace alone does not specify a reliable graph rewrite. |
| `chem-diffdock-nim` | Only checks two files exist and the endpoint string is nonempty; little DiffDock-specific preparation value. |
| `chem-genmol` | Only checks a repository directory and checkpoint file exist; no SAFE or task-configuration guidance. |
| `chem-openmm-md` | Only enumerates available platforms; better as a preparation step than a standalone simulation Skill. |
| `chem-reinvent` | Claims to check the configuration path, but only checks executable availability; little task-specific help. |
| `construct-leaving-group-vocabulary` | Attachment-marker encoding and ambiguous component alignment are undefined; source references point to an old local workspace. |
| `correct-and-filter-semi-template-pairs` | No usable paired predictor contract, template vocabulary or pair-prior construction is established. |
| `experience-guided-retrosynthetic-search` | The core PUCT expression is damaged, with no definite implementation entrypoint to resolve selection behavior. |
| `generate-and-filter-chemical-reasoning-examples` | Requires a score of at least 4/5 but supplies no scoring rubric, leaving the main acceptance rule undefined. |
| `generate-reactant-graphs-with-valid-action-beam-search` | Valid-action rules and atom/bond vocabularies are neither defined nor tied to a usable predictor. |
| `gln-support-restricted-training` | The required gradient equation and weighting for the uniform-sampling approximation are missing. |
| `graph-aware-molecular-attention` | Distance buckets are specified, but the attention equation needed to produce the promised representations is not. |
| `graphretro-beam-search-retrosynthesis` | Final attachment and stereochemistry rules depend on a missing appendix; references use old local paths. |
| `localretro-extract-local-template` | The documented scripts/extract_template.py entrypoint is not included. |
| `localtransform-forward-prediction` | Mostly generic file/commit checks; the command depends on the old repository/evidence layout. |
| `rdkit-descriptor-result-triage` | Duplicates the existing descriptor calculator and interpretation boundary with substantially more template text. |
| `robustify-rgn-against-synthon-errors` | Does not define target alignment when erroneous synthons change component counts or correspondence, the core augmentation case. |
| `retroxpert-evaluate-bond-disconnection` | No inference adapter is delivered; documented command only tests a checkpoint path in an old evidence workspace. |
| `wln-build-molecular-graph` | Documented executable run.py is not delivered; command requires an old virtual environment and batch workspace. |
| `retroprime-two-stage-retrosynthesis` | Resource recovery instructions depend on another Skill package through an incorrect relative link; package is not independently self-contained. |
