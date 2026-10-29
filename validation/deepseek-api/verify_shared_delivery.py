"""Install/import/relocate a shared-stage tool without inheriting approval."""
import argparse
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

repo=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(repo))
from creation_pipeline.artifacts import store
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.records import read_json,write_json,file_digest
from creation_pipeline.runtime import local
from creation_pipeline.runtime.recovery import import_candidate,inspect_candidate,relocate
from creation_pipeline.runtime.service import resume_build

parser=argparse.ArgumentParser()
parser.add_argument('evidence',type=Path)
parser.add_argument('--library',type=Path,default=repo.parent/'acceptance-openbabel-run74-20261029/library')
parser.add_argument('--name',default='chem-openbabel-convert')
args=parser.parse_args()
root=args.evidence.resolve(); source=args.library.resolve(); name=args.name
if root.exists() or root.is_relative_to(source) or source.is_relative_to(root):
    raise ValueError('Use a fresh evidence root separate from the source library')
root.mkdir(parents=True)
cache=repo/'.pipeline/shared-environments'
cache_before={p.name:file_digest(p) for p in cache.glob('*.json')}
commands=[]
original_process=local.process
def observed(command,timeout):
    if command[:2]==['docker','build']:
        raise AssertionError('A new image build is forbidden in this reuse trial')
    result=original_process(command,timeout)
    commands.append({'command':command,'result':result})
    write_json(root/'metadata-commands.json',commands)
    return result

def verify(lib,revision,freeze,image):
    state=inspect_candidate(lib,name)
    write_json(lib.parent/(lib.name+'-inspection.json'),state)
    assert state['qualification']['accepted'] and state['zone']=='accepted'
    entry=store.get(lib,name,include_candidates=True)
    assert entry['revision_id']==revision and entry['freeze_sha256']==freeze
    attempt=lib/entry['runtime']['path']
    receipt=read_json(attempt/'receipt.json')
    report=read_json(attempt/'execution/report.json')
    assert receipt['image_id']==image
    assert report['cases'] and all(c['status']=='passed' for c in report['cases'])
    return {'library':str(lib),'revision_id':revision,'freeze_sha256':freeze,'image_id':image,
            'fresh_passed_cases':len(report['cases']),'report':str(attempt/'execution/report.json')}

try:
    with patch('creation_pipeline.runtime.model_call.call',side_effect=AssertionError('No model calls allowed')), \
         patch('creation_pipeline.agent.backend.NativeSession.stage',side_effect=AssertionError('No native model stages allowed')), \
         patch.object(local.LocalExecutor,'build',side_effect=AssertionError('No new build allowed')), \
         patch.object(local,'process',side_effect=observed):
        old=store.get(source,name,include_candidates=True)
        assert old['zone']=='accepted' and old['current_qualification']['accepted']
        package_before=manifest(source/old['path'])
        revision,freeze,image=old['revision_id'],old['freeze_sha256'],old['runtime']['image_id']
        installed=store.install_from_library(source,name,root/'installed')
        assert manifest(Path(installed['installed']))==package_before
        envelope=root/'installed/.runtime'/name
        assert (envelope/'frozen').is_dir() and (envelope/'attempt').is_dir()
        imported=root/'imported-library'
        import_result=import_candidate(envelope,imported,name)
        write_json(root/'import-result.json',import_result)
        before=inspect_candidate(imported,name)
        write_json(root/'import-before-validation.json',before)
        assert before['zone']=='candidates' and not before['qualification']['accepted']
        resume_build(imported,name,reuse_image=True)
        imported_result=verify(imported,revision,freeze,image)
        assert not (imported/'.catalog.lock').exists()
        moved=root/'moved-library'
        shutil.copytree(imported,moved)
        before_move=inspect_candidate(moved,name)
        write_json(root/'moved-before-relocation.json',before_move)
        assert not before_move['qualification']['accepted']
        relocate(moved,name,revalidate=False)
        withdrawn=inspect_candidate(moved,name)
        write_json(root/'moved-after-withdrawal.json',withdrawn)
        assert not withdrawn['qualification']['accepted']
        resume_build(moved,name,reuse_image=True)
        moved_result=verify(moved,revision,freeze,image)
        reinstalled=store.install_from_library(moved,name,root/'reinstalled')
        assert manifest(Path(reinstalled['installed']))==package_before
        old_after=inspect_candidate(source,name)
        assert old_after['qualification']['accepted']
        assert manifest(source/old['path'])==package_before
        assert {p.name:file_digest(p) for p in cache.glob('*.json')}==cache_before
        result={'passed':True,'scope':'real Docker install/import/relocation compatibility, not fresh skill generation',
                'model_calls':0,'image_builds':0,'original_qualification_preserved':True,
                'import_did_not_inherit_qualification':True,'move_did_not_inherit_qualification':True,
                'shared_registry_unchanged':True,'installed_package_bytes_unchanged':True,
                'fresh_execution_records':imported_result['fresh_passed_cases']+moved_result['fresh_passed_cases'],
                'observations':[imported_result,moved_result]}
        write_json(root/'result.json',result)
        print({k:v for k,v in result.items() if k!='observations'})
except BaseException as exc:
    write_json(root/'failure.json',{'error_type':type(exc).__name__,'error':str(exc),
                                  'scope':'failed compatibility trial; evidence retained, no restart'})
    raise
