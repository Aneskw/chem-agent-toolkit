"""Compile the dated evidence index, preserving raw measurements and source identities."""
import copy
import importlib.util
import re
import statistics
import sys
from pathlib import Path
repo=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(repo))
from creation_pipeline.records import read_json,write_json,sanitized,file_digest
from creation_pipeline.contracts import fingerprint,qualify
from creation_pipeline.artifacts.package import manifest
spec=importlib.util.spec_from_file_location('metrics',repo/'validation/deepseek-api/measure_shared_tool_paths.py')
metrics=importlib.util.module_from_spec(spec);spec.loader.exec_module(metrics)
import argparse
parser=argparse.ArgumentParser(description='Read-only audit of the dated fixed-contract benchmark; writes a sanitized index, never reruns cases')
parser.add_argument('evidence',type=Path)
args=parser.parse_args()
base=repo.parent;root=args.evidence.resolve()
regression=(base/'shared-paths-regression-final-20261101.log').read_text(encoding='utf-8',errors='replace')
assert 'Ran 681 tests' in regression and 'OK (skipped=3)' in regression
raw=read_json(root/'result.json');assert raw['passed'] and raw['cases']==369
rows=copy.deepcopy(raw['observations']); assert len(rows)==18
files=[root/n for n in ('result.json','observations.json','method.json','host.json','measurement-code.json','measurement-script.py')]
installs=[];storage_rows=[];metadata=[]
for row in rows:
    run=Path(row['run']);attempt=run/row['attempt'];report=read_json(attempt/'execution/report.json')
    assert len(report['cases'])==row['cases'] and all(c['status']=='passed' for c in report['cases'])
    row['timing_seconds'].update(metrics.case_timings(report))
    assert row['model_calls']==0
    counts={'environment':0,'tool':0}
    for command in read_json(run/'build-commands.json'):
        counts[command['kind']]+=1
        if command['kind']=='environment':
            lines=(command['result'].get('stdout','')+'\n'+command['result'].get('stderr','')).splitlines()
            steps=[re.match(r'^(#\d+)',line).group(1) for line in lines if re.match(r'^#\d+ .*RUN python -m pip install',line)]
            cached=bool(steps) and all(any(line.startswith(step+' CACHED') for line in lines) for step in steps)
            assert cached
            installs.append({'run':str(run),'steps':steps,'buildkit_cached':True,'pip_step_executed':False})
    assert counts==row['build_calls']
    expected={row['image_id']}
    if row['path']!='tool_hit':expected.add(row['environment']['image_id'])
    assert set(row['storage_delta']['new_image_ids'])<=expected
    assert not row['storage_delta']['removed_image_ids']
    if row['path']=='tool_hit':
        assert all(row['storage_delta'][k]==0 for k in ('image_layers_bytes','build_cache_reported_bytes','desktop_filesystem_used_bytes'))
        assert not row['storage_delta']['new_image_ids']
    files += [run/'build-commands.json',run/'record.json',attempt/'receipt.json',attempt/'execution/report.json']
    for directory in (row['storage_before'],row['storage_after']):
        files += [Path(directory)/n for n in ('engine-df.json','filesystem.json','summary.json')]
assert len({r['tool']['request_key'] for r in rows})==1
assert len({fingerprint(read_json(p)['recipe']) for p in root.glob('*/environment-registry/*.json')})==1
stats=[]
for label in ('a','b'):
    for path in ('environment_miss','environment_hit_tool_miss','tool_hit'):
        group=[r for r in rows if r['skill']==label and r['path']==path]
        assert len(group)==3
        stats.append({'skill':label,'path':path,'samples':3,'timing_seconds':{
            k:{'median':statistics.median(o['timing_seconds'][k] for o in group),
               'min':min(o['timing_seconds'][k] for o in group),'max':max(o['timing_seconds'][k] for o in group)}
            for k in group[0]['timing_seconds']}})
        storage_rows.append({'skill':label,'path':path,'samples':[
            {'repetition':o['repetition'],'delta':o['storage_delta'],'image':o['image_storage'],
             'run_files_logical_bytes':o['run_files_logical_bytes'],'cumulative_registry_files_logical_bytes':o['registry_files_logical_bytes']}
            for o in group]})
original=read_json(repo/'validation/deepseek-api/shared-tool-acceptance-model-results-20261101.json')
for o in original['observations'][:2]:
    output=Path(o['output']);record=read_json(next((output/'records').glob('*.json')))
    ref=record['durable_evidence'];frozen=output/ref['path']
    accepted,reason=qualify(record['delivery'],runtime_root=output,runtime_ref=record['runtime'],frozen_directory=frozen,freeze_sha256=ref['freeze_sha256'])
    assert accepted
    m=next(m for m in read_json(root/'method.json')['source_fingerprints'] if m['label']==o['label'])
    assert fingerprint(manifest(frozen))==m['manifest_sha256']
    metadata.append({'skill':o['label'],'qualified_now':True,'original_frozen_unchanged':True,'reason':reason,
                     'historical_model_calls':o['model_calls'],'current_model_calls':0})
    files += [frozen/'freeze.json',frozen/'record.json']
files += [base/('shared-paths-'+n+'-20261101.log') for n in ('regression-final','prompt-contract','acceptance-prompt','planner')]
files += [base/'shared-paths-measurement-20261101-01/diagnosis.json',base/'shared-paths-measurement-20261101-01/failure.json']
first=read_json(Path(rows[0]['storage_before'])/'summary.json');last=read_json(Path(rows[-1]['storage_after'])/'summary.json')
result={'date':'2026-11-01','base_commit':'ffa00a18f5ed4d6d6c4c7e01c5b13266231b764e','passed':True,
 'scope':raw['scope'],'cases':369,'new_generation_batches':0,'model_calls':0,
 'build_calls':{k:sum(o['build_calls'][k] for o in rows) for k in ('environment','tool')},
 'regression':{'total':681,'passed':678,'skipped':3,'failed':0,'errors':0},'prompt_checks':'all three passed; unchanged prompts/schema',
 'observations':rows,'statistics':stats,'storage':storage_rows,'aggregate_storage_delta':metrics.storage_delta(first,last),
 'installation_cache_observations':installs,'originals':metadata,'limitations':raw['limitations'],
 'metric_correction':'Raw business_cases included model behavior only; published business_cases adds original authored chemistry checks mapped as interface. Recomputed from preserved case_wall_seconds; no reruns or changed assertions.',
 'evidence_root':str(root),'evidence_files':[{'path':str(p.resolve()),'sha256':file_digest(p)} for p in sorted(set(files))],
 'code_files':[{'path':n,'sha256':file_digest(repo/n)} for n in ('validation/deepseek-api/measure_shared_tool_paths.py','tests/pipeline/test_shared_path_metrics.py','validation/deepseek-api/audit_shared_path_metrics.py')]}
write_json(root/'audited-result.json',sanitized(result))
write_json(repo/'validation/deepseek-api/shared-path-metrics-results-20261101.json',sanitized(result))
print('builds',result['build_calls'],'storage deltas',{k:v for k,v in result['aggregate_storage_delta'].items() if k not in ('new_image_ids','removed_image_ids')})
for s in stats:print(s['skill'],s['path'],{k:round(s['timing_seconds'][k]['median'],3) for k in ('total','build_or_bind','business_cases','all_cases')})
