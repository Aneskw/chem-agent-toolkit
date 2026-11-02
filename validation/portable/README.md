# Portable-startup infrastructure checks

These controllers never request a model or grant qualification. Run from the repository root.
Every round uses a new evidence directory; failures are retained.

`verify_checkout.py NEW_EVIDENCE_ROOT ISOLATED_CODEX_NPM_PREFIX` exports the candidate source
(tracked plus nonignored untracked files), creates a Windows checkout with spaces, bootstraps
an independent venv, removes installed Codex from PATH and credentials from the child environment,
then checks the ordinary init/preflight/doctor CLI, the full offline suite and contracts. Finally
it adds an independently installed official client prefix to PATH for help/version/feature-only
diagnosis against the current local Docker daemon. It does not authenticate or generate Skills.
The source-inputs manifest identifies the exact tested bytes; this is not a public GitHub clone.

`linux_smoke.py` runs **inside a disposable Linux container**, with candidate source mounted
read-only at `/input` and a new writable evidence directory at `/evidence`. It copies source to
`/workspace`, explicitly installs Git in that disposable container, bootstraps a venv, runs CLI
and offline checks without Codex or a Docker socket, then installs the original pinned chemistry
dependencies and executes five original source inputs. Those executions are infrastructure
workload checks, not Skill qualification. The actual `docker run` command/image ID is recorded
in each round's `command.json`. Any proxy is supplied only by the experiment operator.

The optional YAML dependency is installed for the full suite; a separate default-bootstrap
JSON-only venv check proves initialization/preflight without PyYAML. Test model names are plain
placeholders, never claims about account access.

See [the report](../../docs/integration/portable-startup-20261102.md) and
[evidence index](results-20261102.json). Published evidence contains redacted logs and hashes,
not author credentials, venvs, operational libraries or Docker images.
Run `python validation/portable/verify_evidence.py` to verify the published evidence hashes
without accessing the original absolute evidence directories. This verifies historical bytes,
not current Docker availability or qualification; Git attributes preserve those evidence bytes.
