"""Read-only audit of fresh public-CLI batches; never creates pipeline state.

Run build through the ordinary CLI first. This verifier only reads its existing
records/receipts and checks current qualification; it never prepares or seals them.
"""
import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.contracts import fingerprint, qualify
from creation_pipeline.records import read_json, write_json, sanitized, file_digest
from creation_pipeline.runtime import external_tool
from creation_pipeline.runtime.coverage import business_args
from audit_openbabel_acceptance import ethanol_sdf
from audit_extended_acceptance import rows


def audit(root, labels, previous_a=None):
    original = read_json(root/'source-before.json')
    for source in original:
        assert manifest(Path(source['path'])) == source['files'], 'Original source changed: '+source['path']
    origins = {'a':previous_a or root,'b':root}
    for item in read_json(root/'code-before.json'):
        assert file_digest(REPO/item['path']) == item['sha256'], 'Runtime code changed during current batch: '+item['path']
    if previous_a:
        assert read_json(previous_a/'source-before.json') == original
    baseline = read_json(REPO/'validation/deepseek-api/acceptance-openbabel-input.json')
    observations = []
    for label in labels:
        origin = origins[label]
        config = read_json(origin/('openbabel-'+label+'.json'))
        assert config['model'] == baseline['model'] and config['limits'] == baseline['limits']
        assert config['runtime_defaults']['options'] == baseline['runtime_defaults']['options']
        assert not set(config['runtime_defaults']) & {'plan', 'acceptance_plan', 'tool_artifact'}
        summaries = list((origin/label/'state/outputs').glob('*/summary.json'))
        assert len(summaries) == 1, 'Require one fresh CLI output per batch, no resume/restart'
        output = summaries[0].parent
        summary = read_json(summaries[0])
        assert summary['status'] == 'ready', str(summaries[0])
        assert len(summary['entities']) == 1
        name = summary['entities'][0]['name']
        record = read_json(output/'records'/(name+'.json'))
        ref = record['durable_evidence']
        attempt = output/record['runtime']['path']
        receipt = read_json(attempt/'receipt.json')
        report = read_json(attempt/'execution/report.json')
        accepted, reason = qualify(record['delivery'], runtime_root=output, runtime_ref=record['runtime'],
            frozen_directory=output/ref['path'], freeze_sha256=ref['freeze_sha256'])
        assert accepted, reason
        assert report['cases'] and all(c['status']=='passed' for c in report['cases'])
        phases = Counter(c['phase'] for c in summary['model_calls'])
        assert all(phases[p] for p in ('discovery','author','review')), phases
        assert len(summary['model_calls']) <= baseline['limits']['model_calls']
        artifact = receipt['tool_artifact']
        assert artifact['abi'] == external_tool.ABI
        external_tool.validate_identity(artifact['external_identity'])
        locked = read_json(output/ref['path']/'runtime/locked-tests.json')['cases']
        by_name = {c['name']:c for c in locked}
        direct = [c for c in report['cases'] if business_args({'entrypoint':artifact['plan']['entrypoint']},
                                                            by_name[c['name']]) is not None]
        normal = [c['name'] for c in direct if c.get('exit_code')==0 and ethanol_sdf(c.get('persisted_output',''))
                  and any(v.get('ok') is True and v.get('input_format')=='smi' and v.get('output_format')=='sdf'
                          for v in rows(c.get('stdout','')))]
        rejected = [c['name'] for c in direct if c.get('exit_code')==2
                    and any(arg in {'nonexistent_format_xyz','--output-format=nonexistent_format_xyz'}
                            for arg in c.get('command',[]))
                    and any(v.get('ok') is False and v.get('exit_code')==1
                            and v.get('error')=='obabel: cannot write output format!'
                            for v in rows(c.get('stdout','')))]
        assert normal, 'Missing actual retained C-C-O SDF (atoms, bonds, topology and terminator)'
        assert rejected, 'Missing actual unknown-format exit 2 and exact upstream JSON rejection fields'
        package = output/'bundle/skills'/name
        source = Path(original[0]['path'])
        assert file_digest(package/'scripts/convert_molecule.py') == file_digest(source/'scripts/convert_molecule.py')
        inputs = [p for p in package.rglob('input.smi') if p.is_file()]
        assert len(inputs)==1 and file_digest(inputs[0])==file_digest(source/'examples/input.smi')
        observations.append({'label':label,'output':str(output),'attempt':str(attempt),'name':name,
            'generation_root':str(origin),'new_generation_in_current_root':origin==root,
            'code_at_generation':read_json(origin/'code-before.json'),
            'qualified_now':accepted,'cases':len(report['cases']),'preparation':record['runtime_preparation'],
            'retained_ethanol_sdf_cases':normal,'unknown_format_rejection_cases':rejected,
            'build_calls':receipt['build_calls'],'tool':receipt['shared_tool'],
            'external_identity':artifact['external_identity'],'model_calls':len(summary['model_calls']),
            'phases':dict(phases),'model_receipts':summary['model_calls'],
            'seconds':{
                'batch':(datetime.fromisoformat(summary['finished_at'])-datetime.fromisoformat(summary['started_at'])).total_seconds(),
                'build_or_bind':(datetime.fromisoformat(receipt['finished_at'])-datetime.fromisoformat(receipt['started_at'])).total_seconds(),
                'case_wall':report.get('case_wall_seconds',{})},
            'skill_sha256':file_digest(package/'SKILL.md'),
            'acceptance_sha256':record['delivery']['inputs']['acceptance']['sha256'],
            'package_files':manifest(package),'source_input_sha256':file_digest(inputs[0])})
    if labels == ['a','b']:
        a,b = observations
        assert a['tool']['artifact_id']==b['tool']['artifact_id']
        assert a['external_identity']==b['external_identity']
        assert a['skill_sha256']!=b['skill_sha256'] and a['acceptance_sha256']!=b['acceptance_sha256']
        assert b['preparation']['shared_tool']['status']=='hit'
        assert b['preparation']['environment_planning_calls']==0
        assert b['preparation']['acceptance_planning_calls']>0
        assert b['build_calls']=={'environment':0,'tool':0}
        assert b['phases'].get('runtime_planning',0)==0 and b['phases']['runtime_acceptance_planning']>0
        ca=read_json(origins['a']/'openbabel-a.json')['runtime_defaults']
        cb=read_json(root/'openbabel-b.json')['runtime_defaults']
        assert ca==cb, 'Independent runtime requirements must be identical'
    result={'passed':True,'scope':'public CLI independent full generation; read-only current qualification audit',
            'manual_acceptance_plan':False,'internal_state_injection':False,'labels':labels,
            'previous_successful_a':str(previous_a) if previous_a else None,
            'cases':sum(o['cases'] for o in observations),'original_sources_unchanged':True,
            'observations':observations}
    write_json(root/('audit-'+''.join(labels)+'.json'),sanitized(result))
    print({k:result[k] for k in ('passed','labels','cases')})


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    parser.add_argument('--labels',nargs='+',choices=['a','b'],default=['a','b'])
    parser.add_argument('--previous-a',type=Path,help='Read an already successful A; never resume a failed batch or copy its tests')
    args=parser.parse_args()
    audit(args.evidence.resolve(),args.labels,args.previous_a.resolve() if args.previous_a else None)
