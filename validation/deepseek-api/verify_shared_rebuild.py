"""Rebuild from a relocated frozen package while retaining its shared environment."""
from pathlib import Path
import argparse
import shutil
import sys
from unittest.mock import patch

repo=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(repo))
from creation_pipeline.artifacts import store
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.records import read_json,write_json,file_digest
from creation_pipeline.runtime import local
from creation_pipeline.runtime.recovery import inspect_candidate,relocate
from creation_pipeline.runtime.service import resume_build

parser=argparse.ArgumentParser()
parser.add_argument('evidence',type=Path)
parser.add_argument('--library',type=Path,default=repo.parent/'shared-runtime-install-compatibility-20261029-01/moved-library')
parser.add_argument('--name',default='chem-openbabel-convert')
args=parser.parse_args()
root=args.evidence.resolve()
source=args.library.resolve()
if root.exists() or root.is_relative_to(source) or source.is_relative_to(root):
    raise ValueError('Fresh independent root required')
root.mkdir(parents=True)
name=args.name
cache=repo/'.pipeline/shared-environments'
cache_before={p.name:file_digest(p) for p in cache.glob('*.json')}
commands=[]
original=local.process
def observed(command,timeout):
    result=original(command,timeout)
    commands.append({'command':command,'result':result})
    write_json(root/'commands.json',commands)
    return result
try:
    with patch('creation_pipeline.runtime.model_call.call',side_effect=AssertionError('No models allowed')), \
         patch('creation_pipeline.agent.backend.NativeSession.stage',side_effect=AssertionError('No native models allowed')), \
         patch.object(local,'process',side_effect=observed):
        old=store.get(source,name,include_candidates=True)
        assert old['current_qualification']['accepted']
        previous=read_json(source/old['runtime']['path']/'receipt.json')
        expected_recipe=previous['shared_environment']['recipe_key']
        before=manifest(source/old['path'])
        destination=root/'rebuilt-library'
        assert not (source/'.catalog.lock').exists()
        shutil.copytree(source,destination)
        relocate(destination,name,revalidate=False)
        assert not inspect_candidate(destination,name)['qualification']['accepted']
        resume_build(destination,name,reuse_image=False)
        state=inspect_candidate(destination,name)
        write_json(root/'inspection.json',state)
        assert state['zone']=='accepted' and state['qualification']['accepted']
        entry=store.get(destination,name,include_candidates=True)
        attempt=destination/entry['runtime']['path']
        receipt=read_json(attempt/'receipt.json')
        report=read_json(attempt/'execution/report.json')
        assert receipt['shared_environment']['status']=='hit'
        assert receipt['shared_environment']['recipe_key']==expected_recipe
        assert report['cases'] and all(c['status']=='passed' for c in report['cases'])
        builds=[c for c in commands if c['command'][:2]==['docker','build']]
        assert len(builds)==1
        assert not any(any('chem.shared.recipe=' in item for item in c['command']) for c in builds)
        assert entry['revision_id']==old['revision_id'] and entry['freeze_sha256']==old['freeze_sha256']
        assert manifest(destination/entry['path'])==before==manifest(source/old['path'])
        assert {p.name:file_digest(p) for p in cache.glob('*.json')}==cache_before
        assert inspect_candidate(source,name)['qualification']['accepted']
        result={'passed':True,'scope':'real Docker rebuild of relocated frozen delivery; not new skill generation',
                'model_calls':0,'environment_build_invocations':0,'thin_tool_build_invocations':1,
                'shared_environment_status':'hit','fresh_passed_cases':len(report['cases']),
                'revision_and_freeze_unchanged':True,'source_library_qualification_preserved':True,
                'package_and_registry_bytes_unchanged':True,'image_id':receipt['image_id'],
                'report':str(attempt/'execution/report.json'),
                'cache_note':'A build invocation may use Docker layer cache; no install-rerun or performance saving claimed'}
        write_json(root/'result.json',result)
        print({k:v for k,v in result.items() if k!='report'})
except BaseException as exc:
    write_json(root/'failure.json',{'type':type(exc).__name__,'error':str(exc),
                                  'scope':'failed independent rebuild trial; retained without restart'})
    raise
