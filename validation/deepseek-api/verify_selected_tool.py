"""Compare automatic and explicitly selected full-tool hits on real frozen Skills.

No model calls: these are original-contract revalidations, not new generation.
"""
import argparse
import copy
import importlib.util
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
from creation_pipeline.records import read_json,write_json,sanitized,file_digest
from creation_pipeline.contracts import qualify
from creation_pipeline.artifacts.evidence import seal
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.runtime import local,shared_tool
from creation_pipeline.runtime.preparation import prepare,handoff,bind
from creation_pipeline.runtime.service import execute_prepared
loader=importlib.util.spec_from_file_location('path_metrics',Path(__file__).with_name('measure_shared_tool_paths.py'))
metrics=importlib.util.module_from_spec(loader);loader.loader.exec_module(metrics)


def main():
    p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);p.add_argument('--offline',action='store_true');args=p.parse_args()
    root=args.evidence.resolve();root.mkdir(parents=True,exist_ok=False)
    previous=read_json(Path(__file__).with_name('shared-tool-acceptance-model-results-20261101.json'))
    registry=REPO.parent/'acceptance-only-e2e-20261101-01/shared-tools'
    reference={k:previous['artifact'][k] for k in ('request_key','artifact_id')}
    artifact=shared_tool.read_record(registry/(reference['request_key']+'-'+reference['artifact_id']+'.json'))
    registry_before=manifest(registry)
    os.environ['CHEM_AGENT_SHARED_TOOLS']=str(registry)
    fixtures=[]
    for item in previous['observations'][:2]:
        output=Path(item['output']);outer=read_json(next((output/'records').glob('*.json')))
        frozen=output/outer['durable_evidence']['path'];saved=read_json(frozen/'record.json')
        config=read_json(output.parents[3]/('input-'+item['label']+'.json'))
        record,sources,spec=metrics.fixture(saved,frozen,config)
        source=root/(item['label']+'-offline-handoff');handoff(frozen/'package',sources,source)
        request=shared_tool.describe(source,bind(frozen/'package',sources),spec['shared_tool'],spec['requirements'],spec['constraints'],saved['delivery']['inputs']['environment']['payload']['limits'])
        assert request==artifact['request']
        fixtures.append((item['label'],frozen,saved,config,manifest(frozen),output,outer))
    write_json(root/'scope.json',sanitized({'scope':'original real Skill contracts; no fresh model generation','reference':reference,
        'model_calls':0,'budget':'unchanged runtime_defaults; no model entry allowed','registry':str(registry),
        'cases_per_skill':{'a':21,'b':20},'measurement':'one paired automatic/explicit sample per Skill; warm caches; not a speedup estimate'}))
    if args.offline:
        print({'offline':'passed','reference':reference});return
    host=local.LocalExecutor().host();assert host['status']=='available';write_json(root/'host.json',sanitized(host))
    endpoint=__import__('json').loads(local.process(['docker','context','inspect','--format','{{json .Endpoints.docker}}'],30)['stdout'])['Host']
    before=metrics.snapshot(root/'storage-before',endpoint);observations=[];negative=[]
    process=local.process
    def observed(command,timeout):
        assert command[:2]!=['docker','build'],'Direct reuse must not build'
        return process(command,timeout)
    with patch('creation_pipeline.runtime.model_call.call',side_effect=AssertionError('No model calls')), \
         patch('creation_pipeline.agent.backend.NativeSession.stage',side_effect=AssertionError('No native calls')), \
         patch.object(local.LocalExecutor,'resolve_base_image',side_effect=AssertionError('No environment planning/pull')), \
         patch.object(local,'process',side_effect=observed):
        for label,frozen,saved,config,original,output,outer in fixtures:
            for mode in ('automatic','selected'):
                run=root/(label+'-'+mode);run.mkdir()
                record,sources,spec=metrics.fixture(saved,frozen,config)
                if mode=='selected':spec['tool_artifact']=reference
                executor=local.LocalExecutor();start=time.monotonic()
                materials=prepare(record,frozen/'package',sources,run/'work',spec,executor);prepared=time.monotonic()
                assert materials and record['runtime_preparation']['status']=='prepared',record.get('runtime_preparation')
                assert record['delivery']['inputs']['acceptance']['payload']==saved['delivery']['inputs']['acceptance']['payload']
                selection=record['delivery']['inputs']['environment']['payload']['shared_tool'].get('selection')
                assert selection==(reference if mode=='selected' else None)
                freeze=seal(run/'evidence/frozen',frozen/'package',record,sources,materials)
                record['durable_evidence']={'path':'evidence/frozen','freeze_sha256':freeze}
                sealed=time.monotonic();receipt=execute_prepared(run,record,executor)
                accepted,reason=qualify(record['delivery'],runtime_root=run,runtime_ref=record['runtime'],
                    frozen_directory=run/'evidence/frozen',freeze_sha256=freeze,executor=executor);end=time.monotonic()
                assert accepted,reason
                assert receipt['build_calls']=={'environment':0,'tool':0}
                assert receipt['shared_tool']['artifact_id']==reference['artifact_id']
                report=receipt['execution'];assert all(c['status']=='passed' for c in report['cases'])
                write_json(run/'record.json',sanitized(record))
                after=metrics.snapshot(root/('storage-after-'+label+'-'+mode),endpoint)
                observations.append({'skill':label,'mode':mode,'accepted':accepted,'cases':len(report['cases']),
                    'preparation':record['runtime_preparation'],'selection':selection,'tool':receipt['shared_tool'],
                    'build_calls':receipt['build_calls'],'model_calls':0,'run':str(run),'attempt':record['runtime']['path'],
                    'seconds':{'prepare':prepared-start,'freeze':sealed-prepared,'build_or_bind':metrics.elapsed(receipt['started_at'],receipt['finished_at']),
                        'validation':metrics.elapsed(report['started_at'],report['finished_at']),'total':end-start,**metrics.case_timings(report)},
                    'storage_delta':metrics.storage_delta(before,after),'storage_before':before['directory'],'storage_after':after['directory'],
                    'run_files_logical_bytes':sum(f['bytes'] for f in manifest(run))})
                before=after;write_json(root/'observations.json',sanitized(observations))
                print({'skill':label,'mode':mode,'cases':len(report['cases']),'accepted':accepted},flush=True)
            for failure in ('missing_version','changed_requirement','conflicting_plan','corrupt_record'):
                record,sources,spec=metrics.fixture(saved,frozen,config);spec['tool_artifact']=copy.deepcopy(reference)
                if failure=='missing_version':spec['tool_artifact']['artifact_id']='0'*64
                elif failure=='changed_requirement':spec['requirements'].append('Additional current runtime requirement')
                elif failure=='conflicting_plan':spec['plan']['environment'].append({'name':'NEW_REQUIREMENT','value':'required'})
                else:
                    corrupt=root/(label+'-corrupt-registry');corrupt.mkdir()
                    (corrupt/(reference['request_key']+'-'+reference['artifact_id']+'.json')).write_text('{broken',encoding='utf-8')
                    os.environ['CHEM_AGENT_SHARED_TOOLS']=str(corrupt)
                try:
                    prepare(record,frozen/'package',sources,root/(label+'-'+failure),spec,local.LocalExecutor())
                    assert record['runtime_preparation']['status']=='runtime_blocked',record['runtime_preparation']
                    assert not record['delivery']['qualification']['accepted']
                    negative.append({'skill':label,'failure':failure,'preparation':record['runtime_preparation'],'accepted':False})
                finally:os.environ['CHEM_AGENT_SHARED_TOOLS']=str(registry)
                write_json(root/'negatives.json',sanitized(negative))
            assert manifest(frozen)==original
            assert qualify(outer['delivery'],runtime_root=output,runtime_ref=outer['runtime'],frozen_directory=frozen,
                           freeze_sha256=outer['durable_evidence']['freeze_sha256'])[0]
    assert manifest(registry)==registry_before
    write_json(root/'result.json',sanitized({'passed':True,'scope':'real original-contract direct-version reuse and fail-closed selection',
        'observations':observations,'negatives':negative,'cases':sum(o['cases'] for o in observations),
        'model_calls':0,'new_generation_batches':0,'build_calls':{'environment':0,'tool':0},
        'originals_unchanged_and_qualified':True,'registry_unchanged':True}))


if __name__=='__main__':
    try:main()
    except BaseException as exc:
        if len(sys.argv)>1 and Path(sys.argv[1]).is_dir():
            write_json(Path(sys.argv[1])/'failure.json',sanitized({'type':type(exc).__name__,'error':str(exc)}))
        raise
