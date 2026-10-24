# Resources and known supplements

Sources are retained independently of parser support. Unknown formats and large data/weights are not discarded just because the program cannot interpret them. Default snapshots exclude only narrow internal/environment/cache/credential categories. No general web search, dependency installation or recursive link crawling is provided.

## Preparation

Local snapshots preserve selected files and provenance; explicit single-file reference storage avoids copying large originals. Repository archives and downloads stream to disk, and file hashes are computed incrementally. No default byte/file-count cutoff. Explicit development limits report their effect.

Excluded: .git, installed .venv/venv/node_modules, __pycache__ and common test/lint caches, .pipeline, .aws/.ssh credential stores, system/editor junk and known secret files. Hidden research directories such as .github, output/results examples, credential documentation and .env.example templates survive. Links are recorded but not followed automatically. Git submodules and LFS payloads are not automatically resolved; archive limitations are recorded. Exclusions are not a complete secret-detection service.

resources.json maps file locators to originals, hashes, optional views and helper commands. eN identifies a source file, not proof the Agent read it correctly. Claims identify concrete passages/functions/pages. resource-state.json retains the full source registry, config and acquisition failures for supplements/recovery. A concise initial context points to the index; it does not inject all files into the model.

## Views

| Format | Auxiliary support / limit |
| --- | --- |
| Code/text | Direct Agent search/read; no duplicate view needed |
| PDF | Poppler text when available, pypdf fallback; page renderer is on demand |
| PNG/JPEG/WebP | Native image tool reads original |
| DOCX | Paragraph text; layout and embedded diagrams not fully represented |
| XLSX | First worksheet values; no automatic chart/visual interpretation |
| Notebook | Markdown/code view; outputs remain in original JSON |
| SQLite | Schema-only view, not automatic table extraction |
| Other formats | Original retained, Agent may inspect or use an appropriate installed processor |

Views are cached with hashes and never replace originals. Structured converters run in a separate process with an optional converter timeout. HTML views retain link addresses to support targeted supplements. Parse failures are warnings with locations, not blanket source rejection. Individual PDF pages render with pdftoppm, at 1600-pixel longest edge, with a 60-second converter timeout. There is no separate OCR service. Merely passing an image path is not vision; best-effort current-session image audits count actual native image returns without copying base64 or private reasoning.

## Supplemental acquisition

The Agent uses the helper listed in resources.json: supplement --run RUN --url URL (or --repo URL / --paper DOI) --reason WHY [--ref REVISION]. It identifies a concrete missing fact, not a vague wish for more background. Success updates provenance, source locators, views and durable registry, and the Agent continues in the same conversation. Duplicate supplements reuse registered material; failures preserve existing sources. Metadata is not a substitute for a PDF that was not obtained.

Known links/identifiers are supported in discovery, authoring and review. Searching for unknown papers/sites remains out of scope. Protected/unavailable resources become localized gaps, not a reason to stop unrelated candidates.
