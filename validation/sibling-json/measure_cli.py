"""Observational real-generation timings; no new models/builds/qualification."""
from datetime import datetime
import importlib.util
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from creation_pipeline.records import read_json,write_json,now
from creation_pipeline.artifacts.package import manifest


def main():
    root=Path(sys.argv[1]).resolve();audit=read_json(root/'audit-ab.json');observations=[]
    sampler=REPO/'validation/deepseek-api/measure_shared_tool_paths.py'
    spec=importlib.util.spec_from_file_location('read_only_storage_sampler',sampler);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    endpoint=read_json(root/'storage-endpoint.json')['endpoint']
    after=m.snapshot(root/'storage-after-b',endpoint);before=read_json(root/'storage-before-b/summary.json')
    delta=m.storage_delta(before,after);df=read_json(root/'storage-after-b/engine-df.json')
    for item in audit['observations']:
        output=Path(item['output']);record=read_json(output/'records'/(item['name']+'.json'))
        attempt=Path(item['attempt']);receipt=read_json(attempt/'receipt.json');report=read_json(attempt/'execution/report.json')
        stages={}
        for call in item['model_calls']:
            phase=call.get('phase','unknown');stages.setdefault(phase,{'calls':0,'seconds':0})
            stages[phase]['calls']+=1;stages[phase]['seconds']+=call.get('elapsed_seconds',0)
        commands=[]
        for command in read_json(attempt/'build-log.json'):
            if command.get('command',[])[:2]!=['docker','build']:continue
            text=command.get('stdout','')+'\n'+command.get('stderr','')
            commands.append({'kind':'environment' if any(str(a).startswith('chem.shared.recipe=') for a in command['command']) else 'tool',
                'exit_code':command['exit_code'],'cache_evidence':[s for s in text.splitlines() if 'CACHED' in s or 'RUN ' in s],
                'timing_scope':'BuildKit step timings in original log; separate subprocess wall times not instrumented'})
        actual={key:sum(c['kind']==key for c in commands) for key in ('environment','tool')}
        assert actual==item['build_calls']
        image=next(i for i in df['Images'] if i['Id']==item['image_id'])
        direct=[]
        for case in report['cases']:
            command=case.get('command',[])
            if item['image_id'] not in command:continue
            args=command[command.index(item['image_id'])+1:]
            if args[:1]==['/opt/skill/package/scripts/screen.py']:args=args[1:]
            if len(args)==2 and args[0]=='--smiles':direct.append(case['name'])
        wall=report.get('case_wall_seconds',{})
        observations.append({'label':item['label'],'cases':item['cases'],'model_stages':stages,'model_calls':len(item['model_calls']),
            'runtime_model_stages':item['preparation']['model_calls_by_stage'],
            'environment_planning_calls':item['preparation']['environment_planning_calls'],
            'acceptance_planning_calls':item['preparation']['acceptance_planning_calls'],'build_calls':actual,'build_commands':commands,
            'hit':item['preparation']['shared_tool'],'environment':receipt['shared_environment'],
            'seconds':{'public_cli_total':item['cli_seconds'],'build_or_bind_including_identity_checks':m.elapsed(receipt['started_at'],receipt['finished_at']),
                'validation_including_checks':m.elapsed(report['started_at'],report['finished_at']),
                'all_current_case_wall':sum(wall.values()),'direct_smiles_case_wall':sum(wall.get(n,0) for n in direct)},
            'direct_smiles_cases':direct,
            'storage':{'frozen_files_logical_bytes':sum(f['bytes'] for f in manifest(output/record['durable_evidence']['path'])),
                'image_virtual_bytes':image.get('Size'),'image_shared_bytes':image.get('SharedSize'),
                'image_unique_bytes':image['Size']-image['SharedSize'] if isinstance(image.get('SharedSize'),int) and image['SharedSize']>=0 else None,
                'daemon_and_desktop_delta':delta if item['label']=='b' else None}})
    write_json(root/'measurements.json',{'version':1,'at':now(),'scope':'two real generation invocations; independent current contracts, not fixed-workload causal benchmarking',
        'observations':observations,'new_models_in_measurement':0,'new_builds_in_measurement':0,
        'limitations':['Single sequential A/B sample; current contract case counts and model latency differ.',
            'Existing Docker/BuildKit and dependency image cache retained; fresh registries are not cold Docker.',
            'Environment build invocation is not an installation count: A pip RUN was CACHED in original BuildKit log.',
            'A storage-before is human-readable docker system df -v only; no fabricated exact physical/byte delta for A.',
            'B Engine /system/df and Desktop df -B1 are raw byte observations for the whole daemon/filesystem, not Windows VHD allocation or attributable single-tool bytes.',
            'Image virtual sizes are never summed; image/cache usage overlap. Logical frozen file sizes are another separate scope.',
            'build_or_bind includes identity checks, not isolated build subprocess wall time; direct_smiles_case_wall covers only observed direct default/explicit Python entry calls, not opaque inline wrappers.',
            'Only miss and complete-hit generation paths measured here; earlier three-path fixed-contract measurements remain separately labeled infrastructure evidence.']})
    print({'passed':True,'observations':len(observations),'b_storage_delta':delta})


if __name__=='__main__':main()
