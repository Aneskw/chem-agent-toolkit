"""Lossless rule abstraction: deduplicate only identical bounded policies."""
import hashlib
import json
import re
from difflib import SequenceMatcher

FIELDS=('when','requires','choose','avoid','because','check','stop_or_fallback','scope','support')


def canonical(rule):
    # Preserve case, punctuation, score direction and chemical notation.
    return {k:re.sub(r'\s+',' ',rule[k]).strip() for k in FIELDS}


def build_library(responses,origins=None):
    groups={};related=[]
    for response_index,response in enumerate(responses):
        for candidate in response['candidates']:
            for i,rule in enumerate(candidate.get('decisions',[])):
                policy=canonical(rule)
                key=hashlib.sha256(json.dumps(policy,sort_keys=True).encode()).hexdigest()
                group=groups.setdefault(key,{'rule_id':key,'policy':policy,'origins':[]})
                group['origins'].append({'paper_id':response['paper_id'],'candidate':candidate['name'],
                                         'decision_index':i,'citations':rule['citations'],
                                         **(origins[response_index] if origins else {})})
    values=list(groups.values())
    for i,a in enumerate(values):
        for b in values[i+1:]:
            ratio=SequenceMatcher(None,a['policy']['choose'],b['policy']['choose']).ratio()
            if ratio>=0.7:
                related.append({'a':a['rule_id'],'b':b['rule_id'],'action':'retain_scoped_variants',
                                'reason':'Similar action is not evidence of equivalent triggers, scope or mechanism.'})
    return {'version':1,'rules':values,'related':related,
            'abstraction':'A portable conditional policy with original scope and evidence; no invented parent rule.',
            'input_rules':sum(len(c.get('decisions',[])) for r in responses for c in r['candidates']),
            'unique_rules':len(values),'utility':'not_evaluated'}


def render_rules(candidate):
    lines=[]
    for r in candidate.get('decisions',[]):
        lines.append('\n'.join(f'- **{label}**: {r[key]}' for label,key in (
            ('When','when'),('Requires','requires'),('Choose','choose'),('Avoid','avoid'),
            ('Why','because'),('Check','check'),('Stop / fallback','stop_or_fallback'),('Scope','scope'))))
        refs=', '.join(f"{c['source_id']}:L{c['start']}-L{c['end']}" for c in r['citations'])
        lines.append(f"Support: {r['support']}; {refs}.\n")
    return '\n\n'.join(lines)


def main():
    import argparse
    from pathlib import Path
    from core.creation_schema import validate
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,action='append',required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();responses=[];origins=[]
    for run in a.run:
        paths=sorted((run/'import_results').glob('*/validated.json'))
        if not paths:raise ValueError('No citation-validated responses in '+str(run))
        for path in paths:
            response=json.loads(path.read_text());bundle_path=run/'jobs'/response['paper_id']/'bundle.json'
            bundle=json.loads(bundle_path.read_text());validate(response,bundle)
            responses.append(response);origins.append({'run_id':run.name,
                'bundle_sha256':hashlib.sha256(bundle_path.read_bytes()).hexdigest()})
    if a.out.exists():raise ValueError('Library output already exists')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(build_library(responses,origins),indent=2)+'\n')

if __name__=='__main__':main()
