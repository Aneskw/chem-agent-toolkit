# Codex planner profile

These ordinary CLI configurations select the existing `codex_cli` runtime backend.
They retain the P2 real RDKit module, JSON resource, explicit requirements, native
discovery/author/review settings and 16-stage/600-second call envelope. The original
DeepSeek configurations remain available under `validation/deepseek-api/`.

```powershell
python -m creation_pipeline build validation/codex-planner/skill-a.json --preflight
python -m creation_pipeline build validation/codex-planner/skill-a.json --state-dir "$root/a/state" --library-dir "$root/a/library" --keep-debug
python -m creation_pipeline build validation/codex-planner/skill-b.json --state-dir "$root/b/state" --library-dir "$root/b/library" --keep-debug
```

Before real runs, verify Docker and choose a fresh `$root`. Set
`CHEM_AGENT_SHARED_TOOLS="$root/shared-tools"` and
`CHEM_AGENT_SHARED_ENVIRONMENTS="$root/shared-environments"` for both invocations.
No acceptance plan, artifact selection or qualification is supplied by this profile.

The runtime selector is `runtime_defaults.options.backend="codex_cli"`, with
`model="gpt-6-astra"` and `transport="https"`, matching the already configured native
Codex identity and transport. DeepSeek-only `api_*` options are removed: their token
and retry controls do not apply to `codex exec`. Call/time envelopes stay unchanged;
this does not claim identical provider token limits or pricing. Runtime association
and diagnosis use the same options when needed; they are not separately selectable
by this profile. Native discovery, authoring and independent review are unchanged.

On the tested Windows host, PATH resolves the desktop-bundled executable at
`C:/Users/27343/AppData/Local/OpenAI/Codex/bin/22cfb1d302613eae/codex.exe`.
No standalone CLI was installed. This is still an executable child process using
normal existing client authentication, not an API exposed by the ChatGPT chat window.
Do not read or copy authentication files. Other desktops are not guaranteed to have
the same binary/path; a normal terminal must be able to resolve `codex` on its own
process PATH. The version check alone does not establish login or model entitlement.

Official [non-interactive mode documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
describes `codex exec`, saved authentication and `--output-schema`. The planner
retains its isolated read-only/no-tools contract, validates the actual answer and
records prompt/schema identities, usage and process lifecycle. A failed Codex call
never falls back to DeepSeek or grants business qualification.

Codex strict output uses the existing JSON-text alternative for acceptance/case
payloads and requires all declared fixed properties on the wire. Logical schemas,
DeepSeek object compatibility and downstream business checks remain unchanged.
Unknown open objects without a text alternative are refused before inference.
Receipts distinguish logical and wire schema identities; terminal schema errors
retain the actual server field diagnostic rather than an unrelated stderr warning.

Real results and limitations: [verification report](../../docs/integration/codex-planner-desktop-20261102.md).
