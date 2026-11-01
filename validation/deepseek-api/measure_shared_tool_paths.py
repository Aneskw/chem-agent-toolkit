"""Warm-cache, fixed-contract real chemistry measurements; no model calls.

Registry misses are controlled by NEW directories, never by deleting caches.
Windows Docker Desktop storage measurements use its current local named pipe.
"""
import argparse
import copy
import http.client
import io
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.artifacts.evidence import seal
from creation_pipeline.contracts import qualify, fingerprint
from creation_pipeline.records import read_json, write_json, sanitized, file_digest, now
from creation_pipeline.runtime import local, shared_tool
from creation_pipeline.runtime.preparation import prepare, rebind
from creation_pipeline.runtime.service import execute_prepared


def engine_df(endpoint):
    prefix = 'npipe:////./pipe/'
    if not endpoint.startswith(prefix) or not re.fullmatch(r'[A-Za-z0-9_.-]+', endpoint[len(prefix):]):
        raise ValueError('Storage sampler supports the current local Windows Docker named pipe only')
    stream = open('\\\\.\\pipe\\' + endpoint[len(prefix):], 'r+b', buffering=0)
    class Pipe:
        def makefile(self, mode):
            # Raw named-pipe reads may be short; HTTP chunk parsing needs buffering.
            return io.BufferedReader(stream)
    try:
        stream.write(b'GET /system/df HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response = http.client.HTTPResponse(Pipe()); response.begin()
        with response:
            if response.status != 200:
                raise ValueError('Docker /system/df HTTP ' + str(response.status))
            return json.loads(response.read())
    finally:
        if not stream.closed: stream.close()


def storage_summary(data):
    # Unknown/negative values remain unknown; never invent zero disk usage.
    size = data.get('LayersSize')
    def usage(key):
        value=data.get(key)
        return {k:v for k,v in value.items() if v is None or isinstance(v,(int,float,bool,str))} if isinstance(value,dict) else None
    return {'image_layers_bytes': size if isinstance(size,int) and size >= 0 else None,
            'image_ids': sorted(i['Id'] for i in data.get('Images') or []),
            'build_cache_records': len(data.get('BuildCache') or []),
            'build_cache_usage': usage('BuildCacheUsage'),
            'image_usage': usage('ImageUsage'),
            'container_usage': usage('ContainerUsage'), 'volume_usage': usage('VolumeUsage')}


def storage_delta(before, after):
    a,b = before['summary'],after['summary']
    cache_a=(a.get('build_cache_usage') or {}).get('TotalSize')
    cache_b=(b.get('build_cache_usage') or {}).get('TotalSize')
    return {'image_layers_bytes': (b['image_layers_bytes']-a['image_layers_bytes']
                                  if a['image_layers_bytes'] is not None and b['image_layers_bytes'] is not None else None),
            'new_image_ids': sorted(set(b['image_ids'])-set(a['image_ids'])),
            'removed_image_ids': sorted(set(a['image_ids'])-set(b['image_ids'])),
            'build_cache_records': b['build_cache_records']-a['build_cache_records'],
            'build_cache_reported_bytes': cache_b-cache_a if isinstance(cache_a,int) and isinstance(cache_b,int) else None,
            'desktop_filesystem_used_bytes': (after['filesystem_used_bytes']-before['filesystem_used_bytes']
                if after['filesystem_used_bytes'] is not None and before['filesystem_used_bytes'] is not None else None)}


def snapshot(directory, endpoint):
    started = time.monotonic(); directory.mkdir(parents=True)
    response = subprocess.run([sys.executable, __file__, '--engine-df', endpoint],
                              capture_output=True, timeout=60)
    if response.returncode:
        raise ValueError('Read-only Engine storage sampling failed: ' + response.stderr.decode('utf-8',errors='replace')[-1000:])
    data = json.loads(response.stdout); write_json(directory/'engine-df.json', sanitized(data))
    fs = subprocess.run(['wsl.exe','-d','docker-desktop','--','df','-B1','/mnt/docker-desktop-disk'],
                        capture_output=True,timeout=30)
    text = fs.stdout.decode('utf-8',errors='replace')
    lines = [line.split() for line in text.splitlines() if line.startswith('/dev/')]
    used = int(lines[-1][2]) if fs.returncode==0 and lines and lines[-1][2].isdigit() else None
    write_json(directory/'filesystem.json', sanitized({'command':['wsl.exe','-d','docker-desktop','--','df','-B1','/mnt/docker-desktop-disk'],
        'exit_code':fs.returncode,'stdout':text,
        'stderr':fs.stderr.decode('utf-16le' if b'\x00' in fs.stderr else 'utf-8',errors='replace'),
        'used_bytes':used,'scope':'entire Docker Desktop data filesystem, includes unrelated data and metadata; not Windows VHD allocation'}))
    result = {'at':now(),'directory':str(directory),'summary':storage_summary(data),
              'filesystem_used_bytes':used,'sampling_seconds':time.monotonic()-started}
    write_json(directory/'summary.json',sanitized(result)); return result


def elapsed(start, end):
    return (datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds()


def case_timings(report):
    """These fixed atom-map workloads have business checks in both origins.

Authored chemical checks are mapped to interface-layer cases by the pipeline;
they must not disappear from the business-time total just because of that label.
"""
    wall=report.get('case_wall_seconds',{})
    behavior=sum(wall.get(c['name'],0) for c in report['cases'] if c['layer']=='behavior')
    authored=sum(wall.get(c['name'],0) for c in report['cases'] if c.get('origin')=='authored_check' and c['layer']!='behavior')
    return {'model_behavior_cases':behavior,'authored_business_checks':authored,
            'business_cases':behavior+authored,'all_cases':sum(wall.values())}


def fixture(saved, original, config):
    """Retain real content approval; discard environment/execution for preparation."""
    sources=[dict(copy.deepcopy(s),path=str(original/'sources'/s['id'])) for s in saved['delivery']['inputs']['sources']]
    record=copy.deepcopy(saved)
    for field in ('runtime','durable_evidence','execution_location','runtime_history_records','runtime_preparation'):
        record.pop(field,None)
    assert record['delivery']['content']['status']=='passed'
    rebind(record,None,None,copy.deepcopy(saved['delivery']['inputs']['acceptance']['payload']['author_tests']))
    assert not record['delivery']['qualification']['accepted']
    spec=copy.deepcopy(config['runtime_defaults'])
    spec['plan']=copy.deepcopy(saved['delivery']['inputs']['environment']['payload']['plan'])
    spec['acceptance_plan']={k:copy.deepcopy(spec['plan'][k]) for k in shared_tool.ACCEPTANCE}
    spec['locked_cases']=copy.deepcopy(saved['delivery']['inputs']['acceptance']['payload']['cases'])
    return record,sources,spec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('evidence',type=Path)
    parser.add_argument('--repetitions',type=int,default=3)
    parser.add_argument('--offline',action='store_true')
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 3: raise ValueError('Use 1 to 3 repetitions; no unbounded runs')
    root = args.evidence.resolve(); root.mkdir(parents=True,exist_ok=False)
    index = read_json(REPO/'validation/deepseek-api/shared-tool-acceptance-model-results-20261101.json')
    selected = [o for o in index['observations'] if o['qualified_now']]
    fixtures = []
    for item in selected:
        output = Path(item['output']); outer = read_json(next((output/'records').glob('*.json')))
        frozen = output/outer['durable_evidence']['path']; saved = read_json(frozen/'record.json')
        config = read_json(output.parents[3]/('input-'+item['label']+'.json'))
        fixtures.append((item['label'],frozen,saved,config,manifest(frozen)))
    assert len(fixtures)==2
    write_json(root/'method.json',sanitized({'scope':'fixed original contracts, real Docker, no new content review or model generation',
        'repetitions':args.repetitions,'paths':['environment_miss','environment_hit_tool_miss','tool_hit'],
        'control':'same source bytes, plan, platform, dependency requirements and locked workload within each Skill',
        'cache':'existing Docker/BuildKit images/cache retained; fresh registry is not cold Docker',
        'model_calls':0,'model_policy':'original budgets/backends retained; model entrypoints fail if called',
        'storage':'Engine /system/df byte snapshots and Docker Desktop filesystem used bytes, sampled outside timed phases',
        'historical_model_evidence':'shared-tool-acceptance-model-results-20261101.json; not new calls',
        'source_fingerprints':[{'label':l,'frozen':str(f),'manifest_sha256':fingerprint(m)} for l,f,s,c,m in fixtures]}))
    if args.offline:
        os.environ['CHEM_AGENT_SHARED_TOOLS']=str(root/'empty-offline-registry')
        for label,original,saved,config,_ in fixtures:
            record,sources,spec=fixture(saved,original,config)
            executor=local.LocalExecutor()
            with patch.object(local.LocalExecutor,'host',return_value={'status':'available','gaps':[],'engine_id':'offline'}), \
                 patch.object(local.LocalExecutor,'resolve_base_image',return_value=saved['delivery']['inputs']['environment']['payload']['base_image']), \
                 patch.object(local,'process',side_effect=AssertionError('Offline preflight must not call Docker')), \
                 patch('creation_pipeline.runtime.model_call.call',side_effect=AssertionError('Offline preflight must not call models')):
                materials=prepare(record,original/'package',sources,root/label,spec,executor)
            write_json(root/(label+'-preparation.json'),sanitized(record))
            assert materials and record['runtime_preparation']['status']=='prepared',record['runtime_preparation']
            assert record['delivery']['inputs']['acceptance']['payload']==saved['delivery']['inputs']['acceptance']['payload']
        print({'offline':'passed','skills':2,'model_calls':0}); return
    context = local.process(['docker','context','inspect','--format','{{json .Endpoints.docker}}'],30)
    assert context['exit_code']==0
    endpoint = json.loads(context['stdout'])['Host']
    host = local.LocalExecutor().host(); assert host['status']=='available',host
    write_json(root/'host.json',sanitized(host))
    results = []; current = {'commands':[]}; process = local.process
    def observe(command, timeout):
        start=time.monotonic(); out=process(command,timeout)
        if command[:2]==['docker','build']:
            current['commands'].append({'argv':command,'elapsed_seconds':time.monotonic()-start,
                'kind':'environment' if any(str(v).startswith('chem.shared.recipe=') for v in command) else 'tool',
                'result':sanitized(out)})
        return out
    with patch('creation_pipeline.runtime.model_call.call',side_effect=AssertionError('No new model calls in fixed-plan control')), \
         patch('creation_pipeline.agent.backend.NativeSession.stage',side_effect=AssertionError('No native models')), \
         patch.object(local,'process',side_effect=observe):
        for label,original,saved,config,original_manifest in fixtures:
            for repetition in range(1,args.repetitions+1):
                series=root/(label+'-'+str(repetition)); series.mkdir()
                os.environ['CHEM_AGENT_SHARED_ENVIRONMENTS']=str(series/'environment-registry')
                before=snapshot(series/'storage-before',endpoint)
                pair=[]
                for number,path in enumerate(('environment_miss','environment_hit_tool_miss','tool_hit')):
                    os.environ['CHEM_AGENT_SHARED_TOOLS']=str(series/('tool-registry-first' if number==0 else 'tool-registry-second'))
                    run=series/path; run.mkdir(); package=run/'package'; shutil.copytree(original/'package',package)
                    record,sources,spec=fixture(saved,original,config)
                    assert manifest(package)==record['delivery']['inputs']['files']
                    executor=local.LocalExecutor(); pin=executor._local_base_image(spec['plan']['base_image'],30)
                    assert pin and pin['repo_digest']==saved['delivery']['inputs']['environment']['payload']['base_image']['repo_digest']
                    executor.resolve_base_image=lambda reference,timeout=120,pin=pin:dict(pin,resolved_from='local_cache')
                    current['commands']=[]; start=time.monotonic()
                    materials=prepare(record,package,sources,run/'work',spec,executor)
                    prepared=time.monotonic()
                    assert materials and record['runtime_preparation']['status']=='prepared',record.get('runtime_preparation')
                    assert record['delivery']['inputs']['acceptance']['payload']==saved['delivery']['inputs']['acceptance']['payload']
                    seal_start=time.monotonic(); freeze=seal(run/'evidence/frozen',package,record,sources,materials)
                    record['durable_evidence']={'path':'evidence/frozen','freeze_sha256':freeze}
                    sealed=time.monotonic(); receipt=execute_prepared(run,record,executor)
                    executed=time.monotonic()
                    accepted,reason=qualify(record['delivery'],runtime_root=run,runtime_ref=record['runtime'],
                        frozen_directory=run/'evidence/frozen',freeze_sha256=freeze,executor=executor)
                    end=time.monotonic(); assert accepted,reason
                    write_json(run/'record.json',sanitized(record));write_json(run/'build-commands.json',sanitized(current['commands']))
                    expected=({'environment':1,'tool':1},{'environment':0,'tool':1},{'environment':0,'tool':0})[number]
                    assert receipt['build_calls']==expected,receipt['build_calls']
                    assert {k:sum(c['kind']==k for c in current['commands']) for k in expected}==expected
                    expected_status=('built','hit','not_requested_tool_hit')[number]
                    assert receipt['shared_environment']['status']==expected_status
                    assert receipt['shared_tool']['status']==('hit' if number==2 else 'built')
                    report=receipt['execution']; assert all(c['status']=='passed' for c in report['cases'])
                    after=snapshot(series/('storage-after-'+str(number)),endpoint)
                    data=read_json(Path(after['directory'])/'engine-df.json')
                    image=next(i for i in data['Images'] if i['Id']==receipt['image_id'])
                    shared=image.get('SharedSize'); size=image.get('Size')
                    timing={'preparation':prepared-start,'freeze':sealed-seal_start,'build_and_execution':executed-sealed,
                        'qualification':end-executed,'total':end-start,
                        'build_or_bind':elapsed(receipt['started_at'],receipt['finished_at']),
                        'validation':elapsed(report['started_at'],report['finished_at']),
                        **case_timings(report),
                        'environment_build_commands':sum(c['elapsed_seconds'] for c in current['commands'] if c['kind']=='environment'),
                        'tool_build_commands':sum(c['elapsed_seconds'] for c in current['commands'] if c['kind']=='tool')}
                    observation={'skill':label,'repetition':repetition,'path':path,'accepted':accepted,'cases':len(report['cases']),
                        'run':str(run),'attempt':record['runtime']['path'],'model_calls':record['runtime_preparation']['model_calls'],
                        'model_stages':{'discovery':0,'author':0,'review':0,'environment_planning':0,'acceptance_planning':0},
                        'model_count_reason':'caller supplied existing frozen plan/locked acceptance; no new generation',
                        'build_calls':receipt['build_calls'],'preparation':record['runtime_preparation'],
                        'tool':receipt['shared_tool'],'environment':receipt['shared_environment'],'image_id':receipt['image_id'],
                        'acceptance_sha256':saved['delivery']['inputs']['acceptance']['sha256'],'source_manifest_sha256':fingerprint(original_manifest),
                        'timing_seconds':timing,'storage_before':before['directory'],'storage_after':after['directory'],
                        'storage_delta':storage_delta(before,after),
                        'image_storage':{'size_bytes_virtual':size,'shared_bytes':shared,
                            'unique_bytes':size-shared if isinstance(size,int) and isinstance(shared,int) and shared>=0 else None},
                        'build_cached_lines':[line for c in current['commands'] for line in (c['result'].get('stdout','')+'\n'+c['result'].get('stderr','')).splitlines() if 'CACHED' in line],
                        'run_files_logical_bytes':sum(f['bytes'] for f in manifest(run)),
                        'registry_files_logical_bytes':sum(p.stat().st_size for directory in
                            ('environment-registry','tool-registry-first','tool-registry-second') for p in (series/directory).glob('*.json'))}
                    results.append(observation);pair.append(observation); before=after
                    write_json(root/'observations.json',sanitized(results))
                    print({'skill':label,'repeat':repetition,'path':path,'cases':len(report['cases']),'seconds':round(timing['total'],3)},flush=True)
                assert pair[1]['tool']['artifact_id']==pair[2]['tool']['artifact_id']
                assert len({o['tool']['request_key'] for o in pair})==1
                assert len({o['acceptance_sha256'] for o in pair})==1
            assert manifest(original)==original_manifest
    medians=[]
    for label,_,_,_,_ in fixtures:
        for path in ('environment_miss','environment_hit_tool_miss','tool_hit'):
            rows=[r for r in results if r['skill']==label and r['path']==path]
            medians.append({'skill':label,'path':path,'samples':len(rows),
                'timing_seconds':{k:{'median':statistics.median(r['timing_seconds'][k] for r in rows),
                    'min':min(r['timing_seconds'][k] for r in rows),'max':max(r['timing_seconds'][k] for r in rows)} for k in rows[0]['timing_seconds']}})
    write_json(root/'result.json',sanitized({'passed':True,'scope':'controlled fixed-plan warm-cache infrastructure benchmark',
        'model_calls':0,'new_generation_batches':0,'repetitions':args.repetitions,
        'cases':sum(r['cases'] for r in results),'observations':results,'statistics':medians,
        'limitations':['Fixed plan bypasses models in all paths: no current model speedup measurement',
            'Fresh registries deliberately cause misses; Docker/BuildKit remain warm',
            'Sequential path order, three samples per path at most, not randomized causal benchmarking',
            'Daemon and Desktop filesystem totals include unrelated activity; not Windows physical VHD allocation',
            'Image virtual sizes are not summed; cache usage overlaps image layers',
            'A/B contracts differ; compare within each Skill only']}))


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--engine-df':
        print(json.dumps(engine_df(sys.argv[2])));sys.exit(0)
    try: main()
    except BaseException as exc:
        if len(sys.argv)>1 and Path(sys.argv[1]).is_dir():
            write_json(Path(sys.argv[1])/'failure.json',sanitized({'type':type(exc).__name__,'error':str(exc)}))
        raise
