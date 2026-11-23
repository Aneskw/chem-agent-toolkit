"""Generate a shared-environment input without downloading sources or invoking models."""
import json
import os
from pathlib import Path
import re

from creation_pipeline.paths import ROOT
from creation_pipeline.records import has_link,redact


def initialize(output, model):
    if not isinstance(model,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}',model) or redact(model)!=model:
        raise ValueError('model: expected your own accessible plain model identifier; credentials are not accepted')
    output=Path(output).absolute()
    if output.suffix.lower()!='.json':raise ValueError('Configuration destination must use .json')
    if has_link(output) or output.exists():
        raise ValueError('Configuration destination must be new and unlinked: '+str(output))
    try:
        tools_path=Path(os.path.relpath(ROOT/'tools',output.parent)).as_posix()
    except ValueError as exc:
        raise ValueError('Configuration and tools library must share a filesystem root for relative paths') from exc
    raw={
        'workflow':'shared-environments',
        'prompt':'Discover source-grounded RDKit tool Skills with clear inputs and outputs.',
        'model':{'backend':'codex_cli','name':model},
        'resource_groups':[{'id':'rdkit','sources':[
            {'id':'guide','url':'https://www.rdkit.org/docs/GettingStartedInPython.html'},
            {'id':'api','url':'https://www.rdkit.org/docs/source/rdkit.Chem.Descriptors.html','related_to':['guide']}
        ]}],
        'research_access':'supplement','network':True,
        'environments':{'root':tools_path,'repository':'ghcr.io/your-account/chem-tools'}
    }
    output.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation never replaces another operator's configuration.
    with output.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
    return {'status':'configuration_created','path':str(output),'model':model,'backend':'codex_cli',
            'model_calls':0,'build_calls':0,'qualification':'not_granted',
            'next':'Set environments.repository to your publishing namespace; run readiness CONFIG, then build CONFIG'}
