"""Revalidate two real generated Skills through delivery/recovery, without models.

Successful paths use real Docker. Negative image/daemon observations and an
interruption are explicitly injected; no user image, source or cache is removed.
"""
import argparse
import copy
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from creation_pipeline.artifacts import store
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.records import read_json, write_json, sanitized, file_digest
from creation_pipeline.runtime import local
from creation_pipeline.runtime.recovery import import_candidate, inspect_candidate, relocate
from creation_pipeline.runtime.service import resume_build


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    root = args.evidence.resolve(); root.mkdir(parents=True, exist_ok=False)
    index = read_json(REPO/'validation/deepseek-api/shared-tool-acceptance-model-results-20261101.json')
    sources = [o for o in index['observations'] if o['qualified_now']]
    assert len(sources) == 2
    originals = []
    for source in sources:
        output = Path(source['output']); library = output.parents[2]/'library'
        record = read_json(next((output/'records').glob('*.json')))
        assert record['delivery']['inputs']['environment']['payload']['shared_tool']
        assert not root.is_relative_to(library) and not library.is_relative_to(root)
        originals.append((source['label'], output, library, record['name'], manifest(library)))
    registry = REPO.parent/'acceptance-only-e2e-20261101-01/shared-tools'
    registry_before = manifest(registry)
    write_json(root/'source-snapshots.json', sanitized([
        {'label':label,'output':str(output),'library':str(lib),'name':name,'manifest':before}
        for label,output,lib,name,before in originals]))
    if args.offline:
        print({'offline':'passed','real_generated_skills':2,'model_calls':0}); return
    # Existing pinned receipts must suffice; no registry discovery or author path.
    os.environ['CHEM_AGENT_SHARED_TOOLS'] = str(root/'empty-tool-registry')
    os.environ['CHEM_AGENT_SHARED_ENVIRONMENTS'] = str(root/'empty-environment-registry')
    host = local.LocalExecutor().host(); write_json(root/'host.json', sanitized(host))
    assert host['status'] == 'available', host
    observations = []; negatives = []; commands = []; fault = {'mode':None,'image':None}
    process = local.process; host_call = local.LocalExecutor.host

    def observed(command, timeout):
        assert command[:2] != ['docker','build'], 'No new build is allowed in pinned recovery'
        injected = fault['mode']=='missing_image' and command[:3]==['docker','image','inspect'] and fault['image'] in command
        result = ({'exit_code':1,'stdout':'','stderr':'Injected absent concrete image (no real image removed)'}
                  if injected else process(command, timeout))
        commands.append({'command':command,'injected':injected,'exit_code':result['exit_code']})
        return result

    def observed_host(executor):
        result = host_call(executor)
        if fault['mode']=='different_daemon':
            result = dict(result, engine_id='injected-other-daemon')
        return result

    def save():
        write_json(root/'observations.json', sanitized(observations))
        write_json(root/'negative-observations.json', sanitized(negatives))
        write_json(root/'metadata-commands.json', sanitized(commands))

    def withdrawn(lib, name, label):
        state = inspect_candidate(lib, name)
        write_json(root/(label+'-before.json'), sanitized(state))
        assert not state['qualification']['accepted'], state
        try:
            store.install_from_library(lib, name, root/(label+'-forbidden-install'))
        except ValueError as exc:
            assert 'qualified' in str(exc), str(exc)
        else:
            raise AssertionError('Unqualified import/migration was installable')

    def execute(lib, name, old, label, mode=True):
        previous = store.get(lib,name,include_candidates=True)
        ref = previous.get('pending_runtime') or previous.get('runtime')
        history = manifest(lib/ref['path']) if ref else None
        result = resume_build(lib,name,reuse_image=mode)
        entry = store.get(lib,name,include_candidates=True)
        assert entry['zone']=='accepted' and entry['current_qualification']['accepted'], result
        assert entry['revision_id']==old['revision_id'] and entry['freeze_sha256']==old['freeze_sha256']
        assert entry['delivery']==old['delivery']
        attempt = lib/entry['runtime']['path']; report = read_json(attempt/'execution/report.json')
        receipt = read_json(attempt/'receipt.json')
        assert receipt['image_id']==old['runtime']['image_id']
        assert all(c['status']=='passed' for c in report['cases']) and report['cases']
        assert not ref or entry['runtime']['path'] != ref['path']
        assert not ref or manifest(lib/ref['path'])==history
        observations.append({'scenario':label,'library':str(lib),'accepted':True,'cases':len(report['cases']),
            'attempt':str(attempt),'revision_id':entry['revision_id'],'freeze_sha256':entry['freeze_sha256'],
            'acceptance_sha256':entry['delivery']['inputs']['acceptance']['sha256'],
            'tool':receipt['shared_tool'],'image_id':receipt['image_id'],'recovery':result['recovery'],
            'current_build_calls':{'environment':0,'tool':0},
            'historical_receipt_build_calls':receipt['build_calls'],
            'report_sha256':file_digest(attempt/'execution/report.json'),'previous_attempt_unchanged':True})
        save(); print({'scenario':label,'cases':len(report['cases']),'accepted':True},flush=True)

    with patch('creation_pipeline.runtime.model_call.call', side_effect=AssertionError('No model calls')), \
         patch('creation_pipeline.agent.backend.NativeSession.stage', side_effect=AssertionError('No native model calls')), \
         patch.object(local.LocalExecutor,'build',side_effect=AssertionError('Pinned recovery must not build')), \
         patch.object(local,'process',side_effect=observed), \
         patch.object(local.LocalExecutor,'host',observed_host):
        for label,output,source,name,before in originals:
            old = store.get(source,name,include_candidates=True)
            assert old['current_qualification']['accepted']
            target = root/label; target.mkdir()
            installed = store.install_from_library(source,name,target/'installed')
            assert manifest(Path(installed['installed']))==old['delivery']['inputs']['files']
            envelope = target/'installed/.runtime'/name
            imported = target/'imported'
            import_candidate(envelope,imported,name); withdrawn(imported,name,label+'-import')
            execute(imported,name,old,label+'-envelope-import')
            moved = target/'moved'; shutil.copytree(imported,moved)
            withdrawn(moved,name,label+'-move')
            relocate(moved,name,revalidate=False); withdrawn(moved,name,label+'-relocate')
            execute(moved,name,old,label+'-migration')
            # --rebuild in shared mode is explicitly a pinned-version revalidation.
            execute(moved,name,old,label+'-explicit-rebuild',mode=False)
            store.install_from_library(moved,name,target/'reinstalled')
            native = target/'native-output-import'
            import_candidate(output,native,name); withdrawn(native,name,label+'-native-import')
            execute(native,name,old,label+'-native-output-import',mode=None)
            interrupted = target/'interrupted'
            import_candidate(envelope,interrupted,name)
            with patch.object(local.LocalExecutor,'validate',side_effect=KeyboardInterrupt('Injected interruption before execution')):
                try:
                    resume_build(interrupted,name,reuse_image=True)
                except KeyboardInterrupt:
                    pass
                else:
                    raise AssertionError('Expected interruption')
            pending = store.get(interrupted,name,include_candidates=True)
            assert pending['pending_runtime'] and not pending['current_qualification']['accepted']
            interrupted_before = manifest(interrupted)
            recovered = target/'recovered-copy'; shutil.copytree(interrupted,recovered)
            execute(recovered,name,old,label+'-interrupted-copy-recovery',mode=None)
            assert manifest(interrupted)==interrupted_before
            assert not (interrupted/'.catalog.lock').exists()
            # Real filesystem corruption, isolated from originals and successful paths.
            broken = target/'broken-envelope'; shutil.copytree(envelope,broken)
            script = broken/'frozen/package/scripts/audit_atom_maps.py'
            script.write_bytes(script.read_bytes()+b'\n# deliberate isolated corruption\n')
            try:
                import_candidate(broken,target/'broken-import',name)
            except ValueError as exc:
                negatives.append({'scenario':label+'-corrupt-envelope','rejected':True,'reason':str(exc)})
            else:
                raise AssertionError('Corrupt frozen source imported')
            assert not (target/'broken-import').exists()
            for mode in ('missing_image','different_daemon'):
                bad = target/mode; import_candidate(envelope,bad,name)
                fault.update(mode=mode,image=old['runtime']['image_id'])
                try:
                    result = resume_build(bad,name,reuse_image=False)
                    entry = store.get(bad,name,include_candidates=True)
                    assert not entry['current_qualification']['accepted'] and not result['accepted'], result
                    report = read_json(bad/entry['runtime']['path']/'execution/report.json')
                    assert not report['cases'], report
                    negatives.append({'scenario':label+'-'+mode,'fault_injection':True,'accepted':False,
                        'result':result,'report':str(bad/entry['runtime']['path']/'execution/report.json')})
                finally:
                    fault.update(mode=None,image=None)
                assert not store.get(bad,name,include_candidates=True)['current_qualification']['accepted']
                save()
            for path in (Path(installed['installed']), target/'unsupported-oci.tar'):
                if path.suffix=='.tar': path.write_bytes(b'unsupported archive fixture')
                try:
                    import_candidate(path,target/'unsupported-import',name)
                except ValueError as exc:
                    negatives.append({'scenario':label+'-unsupported-import','path':str(path),'reason':str(exc)})
                else:
                    raise AssertionError('Unsupported import admitted')
            assert manifest(source)==before
            assert store.get(source,name,include_candidates=True)['current_qualification']['accepted']
            save()
        assert manifest(registry)==registry_before
        assert len({o['tool']['artifact_id'] for o in observations})==1
        assert not any(c['command'][:2]==['docker','build'] for c in commands)
        for _,_,lib,name,before in originals:
            assert store.get(lib,name,include_candidates=True)['current_qualification']['accepted']
            assert manifest(lib)==before
        write_json(root/'result.json',sanitized({'passed':True,'scope':'existing real-generated contracts delivery revalidation',
            'new_generation_batches':0,'model_calls':0,'current_environment_build_calls':0,'current_tool_build_calls':0,
            'fresh_case_executions':sum(o['cases'] for o in observations),'observations':observations,'negatives':negatives,
            'original_libraries_unchanged':True,'shared_registry_unchanged':True,
            'empty_registry_recovery_supported':True,'faults':'missing image/daemon/interruption injected, no original image removed'}))
        save()
        print({'passed':True,'fresh_case_executions':sum(o['cases'] for o in observations)},flush=True)


if __name__=='__main__':
    try:
        main()
    except BaseException as exc:
        if len(sys.argv)>1 and Path(sys.argv[1]).is_dir():
            write_json(Path(sys.argv[1])/'failure.json',sanitized({'type':type(exc).__name__,'error':str(exc)}))
        raise
