"""Offline cross-check of documented local seams; no platform/Docker/model calls."""
import ast
from dataclasses import fields
import importlib
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
from creation_pipeline import contracts
from creation_pipeline.runtime import shared_tool, external_tool, bundled_data, request_contracts
from creation_pipeline.runtime.interface import RuntimeRequest


def check(value):
    issues=[]
    def equal(name,expected,actual):
        if expected!=actual:issues.append({'field':name,'expected':expected,'actual':actual})
    equal('versions.delivery',contracts.PROTOCOL,value['versions']['delivery'])
    equal('versions.binding_envelope',contracts.versioned(None)['version'],value['versions']['binding_envelope'])
    env_tree=ast.parse((REPO/'creation_pipeline/runtime/shared_environment.py').read_text(encoding='utf-8'))
    describe=next(n for n in env_tree.body if isinstance(n,ast.FunctionDef) and n.name=='describe')
    recipe=next(n.value for n in ast.walk(describe) if isinstance(n,ast.Return) and isinstance(n.value,ast.Dict))
    abi=next(ast.literal_eval(v) for k,v in zip(recipe.keys,recipe.values) if ast.literal_eval(k)=='abi')
    equal('versions.environment_recipe',abi,value['versions']['environment_recipe'])
    equal('versions.tool_abis',[shared_tool.ABI,external_tool.ABI,*bundled_data.PROFILES.values(),request_contracts.ABI],value['versions']['tool_abis'])
    for name,expected in (('tool_request',request_contracts.REQUEST_PROTOCOL),('tool_compatibility',request_contracts.VERSION),('skill_contract',request_contracts.VERSION)):
        equal('versions.'+name,expected,value['versions'].get(name))
    equal('versions.policies',[shared_tool.POLICY,external_tool.POLICY,*bundled_data.PROFILES],value['versions']['policies'])
    equal('runtime_request_fields',[f.name for f in fields(RuntimeRequest)],value['runtime_request_fields'])
    equal('execution_states',sorted(contracts.EXECUTION_STATES),sorted(value['execution_states']))
    source=REPO/'creation_pipeline/runtime/shared_tool.py'
    function=next(n for n in ast.parse(source.read_text(encoding='utf-8')).body
                  if isinstance(n,ast.FunctionDef) and n.name=='validate_record')
    expected=ast.literal_eval(function.body[0].value)
    equal('tool_record_v1_fields',sorted(expected),sorted(value['tool_record_v1_fields']))
    request_fields=next(n.comparators[0] for n in ast.walk(function) if isinstance(n,ast.Compare)
        and isinstance(n.left,ast.Call) and isinstance(n.left.func,ast.Name) and n.left.func.id=='set'
        and len(n.left.args)==1 and isinstance(n.left.args[0],ast.Name) and n.left.args[0].id=='req')
    equal('tool_request_v2_fields',sorted(ast.literal_eval(request_fields)),sorted(value['tool_request_v2_fields']))
    extra=next(n for n in ast.walk(function) if isinstance(n,ast.Call)
               and isinstance(n.func,ast.Attribute) and n.func.attr=='add')
    equal('tool_v2_extra_fields',[ast.literal_eval(extra.args[0])],value['tool_v2_extra_fields'])
    for module,names in value['existing_entrypoints'].items():
        imported=importlib.import_module(module)
        for name in names:
            if not callable(getattr(imported,name,None)):
                issues.append({'field':module+'.'+name,'expected':'callable','actual':'missing'})
    for path,anchors in value['error_anchors'].items():
        text=(REPO/path).read_text(encoding='utf-8')
        for anchor in anchors:
            if anchor not in text:issues.append({'field':path,'expected':anchor,'actual':'anchor missing'})
    try:shared_tool.validate_reference(value['examples']['selected_reference'])
    except ValueError as exc:issues.append({'field':'selected_reference','actual':str(exc)})
    for name in ('proposed_resolve','proposed_qualification'):
        example=value['examples'][name]
        equal(name+'.implementation','proposed',example['implementation'])
        equal(name+'.request_id',example['request']['request_id'],example['response']['request_id'])
    return issues


if __name__=='__main__':
    value=json.loads((Path(__file__).with_name('skillnet-contract.json')).read_text(encoding='utf-8'))
    issues=check(value)
    print(json.dumps({'passed':not issues,'scope':'offline local contract inventory, not platform integration acceptance',
                      'models':0,'docker_calls':0,'issues':issues},ensure_ascii=False,indent=2))
    raise SystemExit(bool(issues))
