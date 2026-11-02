"""Read-only scoped-contract CLI evidence audit; no model/state injection."""
import argparse
import copy
from pathlib import Path
import shutil
import sys
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from creation_pipeline.artifacts.package import manifest,verify_bundle
from creation_pipeline.records import read_json,write_json,file_digest,now
from creation_pipeline.runtime import shared_tool as st,local
from creation_pipeline.runtime.recovery import inspect_candidate
from creation_pipeline.contracts import fingerprint


def observe(root,label):
    output=next((root/label/'state/outputs').iterdir());summary=read_json(output/'summary.json')
    assert summary['status']=='ready',summary['errors']
    name=summary['entities'][0]['name'];record=read_json(output/'records'/(name+'.json'))
    verify_bundle(output)
    rt=output/record['runtime']['path'];receipt=read_json(rt/'receipt.json');report=read_json(rt/'execution/report.json')
    current=inspect_candidate(root/label/'library',name);assert current['qualification']['accepted'],current
    frozen=output/record['durable_evidence']['path'];sessions=read_json(next((root/label/'state/runs').iterdir())/'agent-state.json')['sessions']
    assert sessions['build:'+name]!=sessions['review:'+name]
    assert receipt['tool_artifact']['abi']=='shared_tool_image_v5'
    from creation_pipeline.runtime import request_contracts as rc
    inputs=record['delivery']['inputs'];rc.verify_inputs(inputs)
    assert receipt['tool_artifact']['request']['request_protocol']==2
    assert receipt['tool_artifact']['request']['implementation_abi']=='shared_tool_image_v4'
    scoped_tool=inputs['environment']['payload']['tool_compatibility']
    scoped_skill=inputs['acceptance']['payload']['skill_contract']
    assert scoped_tool['payload']==receipt['tool_artifact']['request']['tool_compatibility']
    assert not {'requirements','constraints','skill_contract'}&receipt['tool_artifact']['request'].keys()
    assert report['status']=='execution_passed' and report['acceptance']['complete']
    assert all(c['status']=='passed' for c in report['cases'])
    seen={}
    for case in report['cases']:
        argv=case.get('command',[])
        if receipt['image_id'] not in argv:continue
        args=argv[argv.index(receipt['image_id'])+1:]
        if args[:1]==['/opt/skill/package/scripts/screen.py']:args=args[1:]
        if len(args)!=2 or args[0]!='--smiles':continue
        import json
        try:result=json.loads(case['stdout'])
        except ValueError:continue
        value=args[1]
        if value in ('CCO','c1ccccc1O'):
            assert case['exit_code']==0 and result['ok'] is True
            assert result['selected'] is (value=='CCO')
            assert result['policy_id']=='demonstration-screen-50-v1' and result['maximum_molecular_weight']==50.0
            assert result['descriptors']['molecular_weight']==(46.069 if value=='CCO' else 94.113)
            if value=='CCO':assert result['descriptors']['h_bond_donors']==result['descriptors']['h_bond_acceptors']==1
        elif value in ('','not-a-smiles'):
            assert case['exit_code']==2 and result['ok'] is False and result['error']=='Invalid or empty SMILES'
        else:continue
        seen[value]=case['name']
    assert set(seen)=={'CCO','c1ccccc1O','','not-a-smiles'},seen
    config=read_json(Path(__file__).with_name('skill-'+label+'.json'))
    assert not {'plan','acceptance_plan','tool_artifact'}&config['runtime_defaults'].keys()
    assert not {'requirements','constraints'}&config['runtime_defaults'].keys()
    from creation_pipeline.models import load_config
    expected=rc.skill_payload(config['runtime_defaults'],rc.caller_context(load_config(Path(__file__).with_name('skill-'+label+'.json'))))
    assert scoped_skill['payload']==expected
    assert len(summary['model_calls'])<=config['limits']['model_calls']
    return {'label':label,'output':str(output),'name':name,'build_id':summary['build_id'],'cases':len(report['cases']),
        'qualification':current['qualification'],'tool_compatibility_sha256':scoped_tool['sha256'],'skill_contract_sha256':scoped_skill['sha256'],'skill_requirements':scoped_skill['payload']['requirements'],'skill_constraints':scoped_skill['payload']['constraints'],'revision_id':record['delivery']['revision_id'],
        'artifact_id':receipt['tool_artifact']['artifact_id'],'request_key':receipt['tool_artifact']['request_key'],
        'image_id':receipt['image_id'],'build_calls':receipt['build_calls'],'preparation':record['runtime_preparation'],
        'attempt':str(rt),'author_session':sessions['build:'+name],'review_session':sessions['review:'+name],
        'skill_sha256':file_digest(frozen/'package/SKILL.md'),'execution_sha256':file_digest(rt/'execution/report.json'),
        'acceptance_sha256':record['delivery']['inputs']['acceptance']['sha256'],
        'locked_cases_sha256':fingerprint(record['delivery']['inputs']['acceptance']['payload']['cases']),'actual_entry_cases':seen,
        'model_calls':summary['model_calls'],'cli_seconds':read_json(root/'operations'/('skill-'+label)/'result.json')['seconds']}


def negatives(root,original):
    output=Path(original['output']);record=read_json(output/'records'/(original['name']+'.json'))
    artifact=read_json(Path(original['attempt'])/'receipt.json')['tool_artifact'];request=artifact['request']
    frozen=output/record['durable_evidence']['path'];reference={k:artifact[k] for k in ('request_key','artifact_id')}
    host=local.LocalExecutor().host();before=manifest(root/'shared-tools');results=[]
    for mode in ('module','resource','dependency','interface'):
        context=root/'negative-probes'/mode;shutil.copytree(frozen/'runtime/context',context)
        d=copy.deepcopy(request['declaration'])
        if mode=='module':
            path=context/'package/scripts/calc_descriptors.py';path.write_bytes(path.read_bytes()+b'\n# new implementation version\n')
        elif mode=='resource':
            path=context/'package/scripts/rules.json';path.write_text('{"policy_id":"demonstration-screen-50-v1","maximum_molecular_weight":51.0}',encoding='utf-8')
            d['bundled_data'][0]['sha256']=file_digest(path)
        elif mode=='dependency':d['requirements']['imports']['rdkit']='2025.3.1'
        else:d['interface']['entrypoint'][0]='python3'
        opaque=request['tool_compatibility']['unclassified']
        req=st.describe(context,record['delivery']['inputs']['bindings']['payload'],d,opaque['requirements'],opaque['constraints'],request['runtime_limits'],tool_compatibility=request['tool_compatibility'])
        found,obs=st.select(req,reference,host,local.process,root/'shared-tools')
        assert found is None and obs['reason']=='selected_request_mismatch' and obs['mismatches'],obs
        automatic=st.resolve(req,host,local.process,root/'shared-tools')[1]
        assert automatic['status']=='miss'
        results.append({'mutation':mode,'selected':obs,'automatic':automatic})
    assert manifest(root/'shared-tools')==before
    assert inspect_candidate(root/'a/library',original['name'])['qualification']['accepted']
    write_json(root/'negative-probes.json',{'passed':True,'models':0,'builds':0,'scope':'isolated copies of real frozen contexts; not new generation or qualification',
        'old_binding_unchanged':True,'observations':results})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--pair',action='store_true');p.add_argument('--negatives',action='store_true');p.add_argument('--output',type=Path)
    args=p.parse_args();root=args.root.resolve();out=[observe(root,'a')]
    if args.pair:
        out.append(observe(root,'b'));a,b=out
        for field in ('artifact_id','request_key','image_id','tool_compatibility_sha256'):assert a[field]==b[field],field
        for field in ('skill_sha256','revision_id','author_session','review_session','attempt','acceptance_sha256','locked_cases_sha256','skill_contract_sha256','skill_requirements','skill_constraints'):assert a[field]!=b[field],field
        assert b['build_calls']=={'environment':0,'tool':0}
        assert b['preparation']['environment_planning_calls']==0 and b['preparation']['acceptance_planning_calls']>0
        prior=read_json(root/'audit-a.json')['observations'][0]
        for field in ('revision_id','skill_sha256','artifact_id','image_id'):assert a[field]==prior[field]
    assert manifest(REPO/'validation/sibling-json/source')==read_json(root/'source-before.json')
    if args.negatives:negatives(root,out[0])
    destination=args.output or root/('audit-ab.json' if args.pair else 'audit-a.json')
    if destination.exists():raise FileExistsError('Use a fresh read-only audit evidence file: '+str(destination))
    write_json(destination,{'passed':True,'at':now(),'observations':out})
    print({'passed':True,'cases':sum(i['cases'] for i in out),'labels':[i['label'] for i in out]})
