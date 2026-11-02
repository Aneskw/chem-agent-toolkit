"""Local example initialization; no inference, credentials or artifact state."""
import copy
import json
import os
from pathlib import Path
import re

from creation_pipeline.models import load_config
from creation_pipeline.paths import ROOT
from creation_pipeline.records import has_link,read_json,redact


def initialize(output, model):
    if not isinstance(model,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}',model) or redact(model)!=model:
        raise ValueError('model: expected your own accessible plain model identifier; credentials are not accepted')
    output=Path(output).absolute()
    if output.suffix.lower()!='.json':raise ValueError('Configuration destination must use .json (no YAML dependency required)')
    if has_link(output) or output.exists():
        raise ValueError('Configuration destination must be new and unlinked: '+str(output))
    template=ROOT/'examples/descriptor-screening/input.json'
    load_config(template)  # Use the ordinary configuration validator.
    raw=copy.deepcopy(read_json(template))
    for source in raw['sources']:
        for key in ('path','table'):
            if key in source:
                target=(template.parent/source[key]).resolve()
                try: source[key]=Path(os.path.relpath(target,output.parent)).as_posix()
                except ValueError as exc:
                    raise ValueError('Configuration and example sources must share a filesystem root for relative paths') from exc
    raw['model']['name']=model
    raw['runtime_defaults']['options']['model']=model
    output.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation never replaces another operator's configuration.
    with output.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
    return {'status':'configuration_created','path':str(output),'model':model,'backend':'codex_cli',
            'model_calls':0,'build_calls':0,'qualification':'not_granted',
            'next':'Run doctor CONFIG, then build CONFIG with your own state/library paths'}
