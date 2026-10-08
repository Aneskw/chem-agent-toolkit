#!/usr/bin/env python3
"""Render cited extraction candidates as low-confidence, unpublished v0.3 drafts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from decision_library import render_rules


def references(claims: list[dict]) -> str:
    output = []
    for claim in claims:
        refs = ", ".join(f"{c['source_id']}:L{c['start']}-L{c['end']}" for c in claim["citations"])
        output.append(f"- {claim['text']} ({refs})")
    return "\n".join(output)


def render(candidate: dict, bundle: dict, check: dict, packaged_resources=()) -> str:
    name = candidate["name"]
    description=' '.join(candidate['description'].split())
    operation=' '.join(candidate['operation'].split())
    claims=candidate['inputs']+candidate['outputs']+candidate['steps']+candidate.get('decisions',[])
    claims += [item['reason'] for item in candidate['requirements']]
    cited={c['source_id'] for claim in claims for c in claim['citations']}
    grouped={}
    for source in bundle['sources']:
        if source['id'] in cited:
            key=(source['role'],source['url'] or source['path'])
            grouped.setdefault(key,[]).append(source['id'])
    source_lines=[f"- {role}: {url} (sources {', '.join(ids)})." for (role,url),ids in grouped.items()]
    requirements = [f"- {item['kind']}: {item['path']} — {item['reason']['text']}"
                    for item in candidate["requirements"]]
    resources = [
        f"- {item['kind']}: `{item['path']}` — status `{item['status']}`; "
        f"source: {item['source_url'] or 'not supplied'}; revision: {item['source_revision'] or 'not supplied'}; "
        f"sha256: {item['sha256'] or 'not verified'}; "
        f"restore: `{('included at resources/' + item['path']) if item['path'] in packaged_resources else (item['restore_command'] or 'not supplied')}`"
        for item in candidate.get('resource_manifest', [])
    ]
    unknowns = [f"- {item}" for item in candidate["unknowns"]]
    if check.get('missing_model_resources'):
        unknowns.append('- Missing model acquisition contracts: '+', '.join(check['missing_model_resources'])+'.')
    state = check["state"]
    manifest=candidate.get('resource_manifest',[])
    bundled=sum(item['path'] in packaged_resources for item in manifest)
    external=sum(item['status']=='download_required' for item in manifest)
    compatibility=f'Bundled resources: {bundled}; external acquisitions: {external}; runtime not validated'
    allowed_tools='Read, Bash' if any(item['kind'] in {'source_code','preprocessing','dataset'} for item in manifest) else 'Read'
    return (
        "---\n"
        f"name: {name}\n"
        "description: >\n"
        f"  {description} Invoke for: {operation} Do not use as evidence of successful execution.\n"
        "license: undetermined\n"
        f"compatibility: \"{compatibility}\"\n"
        f"allowed-tools: {allowed_tools}\n"
        "---\n\n"
        f"# {name.replace('-', ' ').title()}\n\n"
        f"Use this cited draft to {operation}. Apply it only when the listed inputs and rule preconditions hold. "
        "Do not apply it outside the stated scope or treat computed outputs as experimental evidence. "
        "It is a `source_validated_candidate`, not an execution-validated package.\n\n"
        "## Credibility\n\n"
        f"**Low confidence (Highly flexible)**. State: `{state}`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.\n\n"
        "## Reference\n\nUse the cited primary text to check scientific scope; use pinned code to check implementation behavior. "
        "README statements alone do not establish chemistry or execution. Inspect [the evidence index](references/evidence.json) "
        "for each rule's quotes, source hashes and declared assumptions.\n\n" + "\n".join(source_lines) + "\n\n"
        "## Input & Output\n\nInputs:\n\n" + references(candidate["inputs"]) +
        "\n\nOutputs:\n\n" + references(candidate["outputs"]) + "\n\n"
        "## Procedure Guidance\n\n" + (render_rules(candidate)+'\n\n' if candidate.get('decisions') else '') + references(candidate["steps"]) + "\n\n"
        "## Matters & Troubleshooting\n\nDeclared requirements:\n\n" + ("\n".join(requirements) or "- None identified.") +
        "\n\nResource recovery manifest:\n\n" + ("\n".join(resources) or "- No external resource manifest supplied; this draft is not executable.") +
        "\n\nUnknowns and limits:\n\n" + ("\n".join(unknowns) or "- No explicit unknowns recorded.") + "\n"
    )


def copy_present_resources(candidate: dict, bundle: dict, destination: Path) -> set[str]:
    root=Path(bundle['repo_root']).resolve()
    copied=set()
    for item in candidate.get('resource_manifest',[]):
        if item['status']!='present':continue
        source=(root/item['path']).resolve()
        try:source.relative_to(root)
        except ValueError:raise ValueError('Resource escapes source root: '+item['path'])
        if not source.is_file():raise ValueError('Present resource missing from intake: '+item['path'])
        if hashlib.sha256(source.read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('Present resource changed after source lock: '+item['path'])
        target=destination/'resources'/item['path']
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        copied.add(item['path'])
    return copied


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--paper-id", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    run = args.run
    result = run / "import_results" / args.paper_id
    response = json.loads((result / "validated.json").read_text())
    bundle = json.loads((run / "jobs" / args.paper_id / "bundle.json").read_text())
    summary = json.loads((run / "import_results" / "summary.json").read_text())
    checks = next(item["checks"] for item in summary["jobs"] if item["paper_id"] == args.paper_id)
    args.out.mkdir(parents=True, exist_ok=True)
    for candidate, check in zip(response["candidates"], checks):
        path = args.out / candidate["name"]
        path.mkdir(exist_ok=False)
        packaged=copy_present_resources(candidate,bundle,path)
        (path / "SKILL.md").write_text(render(candidate, bundle, check, packaged), encoding="utf-8")
        refs=path/'references';refs.mkdir()
        (refs/'evidence.json').write_text(json.dumps({'candidate':candidate,'audit':check,
            'sources':[{k:v for k,v in s.items() if k!='lines'} for s in bundle['sources']]},indent=2)+'\n')
    print(json.dumps({"paper_id": args.paper_id, "drafts": len(response["candidates"]), "out": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
