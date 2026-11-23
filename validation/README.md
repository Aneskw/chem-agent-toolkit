# Developer verification

Automated test cases live in `tests/`. This directory contains their runners and fixed inputs,
plus integration checks that developers run explicitly.

| Directory | Purpose |
| --- | --- |
| checks/ | Offline checks, contract audits and helpers exercised by tests |
| fixtures/ | Minimal fixed inputs, prompt/schema baselines and recovery artifacts required by checks |
| integration/ | Explicit Docker and isolated-installation checks |

Run from the repository root:

```bash
python validation/checks/run_offline_suite.py
python validation/checks/verify_prompt_contract.py
python validation/checks/verify_acceptance_prompt.py check
python validation/checks/verify_planner.py check
python validation/checks/verify_skillnet_contract.py
```

The offline commands above do not call models. The planner's run mode is an explicit live provider check; its output goes under `.pipeline/validation/`.

Integration scripts require the infrastructure named by each script and a fresh output directory. Docker checks cover dependency sharing, contention, cross-checkout reuse and owned-resource recovery. Installation checks are verify_checkout.py and linux_smoke.py; neither publishes images nor calls models. Run them deliberately rather than as part of ordinary Skill generation.

Fixture bytes participate in regression identities. Preserve frozen manifests, prompts, source files and execution artifacts when changing directory layout. Update fixtures only with the corresponding reviewed behavior change. New run logs, measurements and operational libraries belong under `.pipeline/` or an explicit external output directory.
