# Validation report

Reviewed on 2026-10-22. Local live builds used Python 3.11, installed RDKit 2026.03.6 and the authenticated Codex CLI with its configured `gpt-6-luna` model. They used HTTP transport through that CLI. No standalone paid model API or Agent efficacy benchmark was run.

## Engineering verification

`python -m unittest discover -s tests -v`: **60 tests passed**. Coverage includes resource-only input, candidate selection, zero candidates, discovery repair, source snapshots, plan continuation, shared-tool ordering, actual shared interfaces reaching authors, independent failures, hash-checked installation, execution assertions, explicit working directories, failed-oracle retention and model-backend failure handling.

Document tests cover DOCX, notebook, HTML/XML, SQLite schema and XLSX catalog parsing. Network/provider fixtures cover pinned GitHub export, limits, compatible chat and Ollama message protocols. Fixtures are explicitly replay, not fresh model evidence.

CLI help/configuration preflight, static bundle checks and installation into a new directory were also exercised. Detailed development validation is maintained outside user documentation.

## Resource-driven live builds

No concrete task, desired candidate names, hand-written per-candidate checks or expected file sets were supplied in these inputs. Candidate counts differ across runs; limits did not require filling a quota.

| Case | Build ID | Actual result |
| --- | --- | --- |
| RDKit BRICS and RECAP upstream source modules | `20261022T010315-9a56d084` | Two ready skills; 11 model calls; five generated result checks passed |
| Independent discovery from the same modules | `20261022T011009-1672caa8` | Two candidates, one selected and ready; six calls |
| Continue that saved plan | `20261022T011725-08658ec8` | Ready; two authoring-related calls and no discovery; installation and example execution succeeded |
| Dimorphite-DL paper plus v1.2.5 code | `20261022T012135-f9f8381f` | Draft; source pair acquired, required runtime dependency unavailable |
| Same paper plus paper-era implementation | `20261022T012305-7e1fbb34` | Ready; 11 calls; two source-grounded CLI result checks passed |
| Continue the paper-era plan | `20261022T012818-bc6cad6e` | Ready; one authoring call and no discovery |
| Final repository-code review and upstream suite | `20261022T085347-22c804de` | Ready; source plan reused; upstream `--test` executed with explicit source cwd and content review passed |
| Final unchanged-output reuse | `20261022T085642-22f7a5ae` | Ready; zero model calls; installation and Python example in relocated bundle verified |
| Reuse unchanged ready paper output | `20261022T012937-022fbeae` | Ready; zero model calls; reused files, not new generation or new execution evidence |

Packages and detailed records remain under `.pipeline/outputs/<id>/`, excluded from Git. The BRICS and RECAP main-file Python examples were separately executed. Complete bundles were installed outside their output directories and verified.

### Sources and interpretation

RDKit input consisted of the actual installed `Chem/BRICS.py` and `Chem/Recap.py`, including upstream docstrings, implementation and embedded examples/tests. The model chose related operations and explained hierarchy/fragment handling without generating unnecessary wrappers.

The paper input is the public Dimorphite-DL full text, DOI `10.1186/s13321-019-0336-9`, obtained as Europe PMC XML for `PMC6689865`. Code came from the official `durrantlab/dimorphite_dl` repository:

- `v1.2.5` resolved to `9008e12b43419d596b96c0f85dfced3def340f8d`.
- The paper-era implementation was pinned to `155a5c6bbbc6664e05eec8a470a4998d7909e019` (2019-08-13).

GitHub source acquisition uses commit metadata and an official pinned archive, exporting eligible text only. Snapshots record actual file hashes. The paper and software versions are not treated as interchangeable.

The older implementation's passing checks assert documented protonated/deprotonated outputs under deliberately extreme pH values from upstream tests. They verify those program branches, not scientific validity at those pH values, experimental populations, pKa accuracy or general predictive performance.

The final paper-era package also passed the upstream test entrypoint using its required source working directory. Its installed main-file Python example returned ionization states and preserved properties when the pinned source directory was on the import path. The legacy API reads ambient `sys.argv` and prints a banner: embedding it in a larger CLI/notebook/service requires separate attention; the example was tested as a standalone script.

The v1.2.5 case lacked `loguru` in the existing interpreter. No dependency was installed to make it pass. It remained draft. This demonstrates missing-runtime evidence handling, not that every modern interface was executed.

## Scope of confidence

Generated main files identify useful API distinctions and supply real calls. The examples support engineering usability in the tested scope. Their optimal granularity, selection stability and benefit for an Agent remain unmeasured. Small or overly broad candidates can still occur; model review is not an independent correctness proof.

Shared tool generation, dependency ordering, interface propagation, failure handling and relocation have deterministic end-to-end tests. A genuinely valuable shared adapter autonomously discovered in a real research project has not yet been established by these samples; no adapter was forced merely to populate the tool layer.

API/Ollama protocols were tested with local fixtures, not live external credentials/services. Generic non-GitHub Git acquisition has not been fully validated in this network. DOI/arXiv resolution is implemented but these live cases used a direct XML article address. The normal interpreter lacks pypdf, so no live PDF case is claimed. No OCR, visual input, unrestricted search, automatic environment setup, GPU/service deployment or Agent benchmark was exercised.

`ready` means applicable recorded checks passed. It does not imply exhaustive API coverage, universal runtime compatibility, scientific correctness or Agent benefit. Plan reuse with zero model calls is reuse of past scoped evidence, not a new independent validation.
