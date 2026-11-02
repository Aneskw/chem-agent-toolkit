"""Read-only current qualification and isolated exact-match probes; no model calls."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
from creation_pipeline.records import read_json,write_json,sanitized,file_digest
from creation_pipeline.artifacts.package import manifest,verify_bundle
from creation_pipeline.contracts import qualify
from creation_pipeline.runtime import shared_tool as st,local
from creation_pipeline.runtime.recovery import inspect_candidate


def audit(root,labels,b_root=None,output_root=None):
    if b_root is not None:
        for name in ('production-code.json','source-before.json','old-bindings-before.json'):
            assert read_json(root/name)==read_json(b_root/name),name
    for item in read_json(root/'production-code.json'):
        assert file_digest(REPO/item['path'])==item['sha256'],item['path']
    original=read_json(root/'source-before.json');assert manifest(original['path'])==original['files']
    if (root/'additional-source-before.json').is_file():
        extra=read_json(root/'additional-source-before.json');assert manifest(extra['path'])==extra['files']
    legacy=REPO.parent/'chem-agent-toolkit_newpipeline/tools-skills/rdkit/chem-rdkit-descriptors'
    for path in ('scripts/calc_descriptors.py','requirements.txt'):
        assert file_digest(Path(original['path'])/path)==file_digest(legacy/path)
    out=[]
    for label in labels:
        run_root=b_root if label=='b' and b_root is not None else root
        outputs=list((run_root/label/'state/outputs').iterdir());assert len(outputs)==1
        directory=outputs[0];summary,_=verify_bundle(directory);assert summary['status']=='ready'
        name=summary['entities'][0]['name'];record=read_json(directory/'records'/(name+'.json'))
        frozen=directory/record['durable_evidence']['path'];rt=directory/record['runtime']['path']
        receipt=read_json(rt/'receipt.json');report=read_json(rt/'execution/report.json')
        assert receipt['tool_artifact']['abi']=='shared_tool_image_v3'
        accepted,reason=qualify(record['delivery'],runtime_root=directory,runtime_ref=record['runtime'],
            frozen_directory=frozen,freeze_sha256=record['durable_evidence']['freeze_sha256']);assert accepted,reason
        current=inspect_candidate(run_root/label/'library',name);assert current['qualification']['accepted']
        for path in ('scripts/triage.py','scripts/calc_descriptors.py','scripts/data/rules.json','requirements.txt'):
            assert file_digest(frozen/'package'/path)==file_digest(Path(original['path'])/path),path
        session=read_json(run_root/label/'state/runs'/summary['build_id']/'agent-state.json')['sessions']
        assert session['review:'+name]!=session['build:'+name]
        seen={}
        for c in report['cases']:
            command=c.get('command',[])
            if receipt['image_id'] not in command:continue
            args=command[command.index(receipt['image_id'])+1:]
            if len(args)!=2 or args[0]!='--smiles':continue
            value=args[1]
            try:r=json.loads(c['stdout'])
            except ValueError:continue
            if value in ('CCO','c1ccccc1O'):
                assert c['exit_code']==0 and r['ok'] is True
                assert r['selected'] is (value=='CCO') and r['input']==value
                assert r['policy_id']=='demonstration-screen-50-v1' and r['maximum_molecular_weight']==50.0
                assert r['descriptors']['molecular_weight']==(46.069 if value=='CCO' else 94.113)
                if value=='CCO':assert r['descriptors']['h_bond_donors']==r['descriptors']['h_bond_acceptors']==1
            elif value in ('','not-a-smiles'):
                assert c['exit_code']==2 and r['ok'] is False and r['input']==value
                assert r['error']=='Invalid or empty SMILES'
            else:continue
            seen[value]=c['name']
        assert set(seen)=={'CCO','c1ccccc1O','','not-a-smiles'},seen
        assert all(c['status']=='passed' for c in report['cases'])
        config=read_json(run_root/('skill-'+label+'.json'))
        assert config==read_json(root/('skill-'+label+'.json'))
        assert not {'plan','acceptance_plan','tool_artifact'}&set(config['runtime_defaults'])
        assert len(summary['model_calls'])<=config['limits']['model_calls']
        out.append({'label':label,'output':str(directory),'build_id':summary['build_id'],'name':name,
            'revision_id':record['delivery']['revision_id'],'cases':len(report['cases']),
            'current_qualification':current['qualification'],'independent_review':True,'direct_business_cases':seen,
            'author_session':session['build:'+name],'review_session':session['review:'+name],
            'attempt_directory':str(rt),'execution_report_sha256':file_digest(rt/'execution/report.json'),
            'acceptance_sha256':record['delivery']['inputs']['acceptance']['sha256'],
            'skill_sha256':file_digest(frozen/'package/SKILL.md'),'artifact_id':receipt['shared_tool']['artifact_id'],
            'image_id':receipt['image_id'],'build_calls':receipt['build_calls'],'preparation':record['runtime_preparation'],
            'model_calls':summary['model_calls']})
    for item in read_json(root/'old-bindings-before.json'):
        assert manifest(item['path'])==item['files']
        assert inspect_candidate(Path(item['path'])/'library','chem-rdkit-descriptors')['qualification']['accepted']
    if labels==['a','b']:
        a,b=out;assert a['artifact_id']==b['artifact_id'] and a['skill_sha256']!=b['skill_sha256']
        assert a['revision_id']!=b['revision_id']
        assert a['author_session']!=b['author_session'] and a['review_session']!=b['review_session']
        assert a['attempt_directory']!=b['attempt_directory']
        before=read_json(root/'audit-a.json')['observations'][0]
        for field in ('revision_id','skill_sha256','artifact_id','image_id'):
            assert a[field]==before[field],field
        assert b['build_calls']=={'environment':0,'tool':0}
        assert b['preparation']['environment_planning_calls']==0 and b['preparation']['acceptance_planning_calls']>0
    write_json((output_root or root)/('audit-'+''.join(labels)+'.json'),sanitized({'passed':True,'observations':out,'old_bindings_unchanged':True}))
    print({'passed':True,'cases':sum(x['cases'] for x in out),'labels':labels})


def negatives(root,output_root=None):
    destination=output_root or root
    a=read_json(root/'audit-a.json')['observations'][0];directory=Path(a['output'])
    record=read_json(directory/'records'/(a['name']+'.json'));frozen=directory/record['durable_evidence']['path']
    artifact=read_json(directory/record['runtime']['path']/'receipt.json')['tool_artifact']
    reference={k:artifact[k] for k in ('request_key','artifact_id')};host=local.LocalExecutor().host()
    before=manifest(root/'shared-tools');results=[]
    for mode in ('module','data','dependency','interface'):
        context=destination/'negative-probes'/mode;shutil.copytree(frozen/'runtime/context',context)
        d=copy.deepcopy(artifact['request']['declaration'])
        if mode=='module':
            p=context/'package/scripts/calc_descriptors.py';p.write_bytes(p.read_bytes()+b'\n# independent new module version\n')
        elif mode=='data':
            p=context/'package/scripts/data/rules.json';p.write_text('{"policy_id":"demonstration-screen-50-v1","maximum_molecular_weight":51.0}',encoding='utf-8')
            d['bundled_data'][0]['sha256']=file_digest(p)
        elif mode=='dependency':d['requirements']['imports']['rdkit']='2025.3.1'
        else:d['interface']['entrypoint'][0]='python3'
        binding=record['delivery']['inputs']['bindings']['payload']
        req=st.describe(context,binding,d,artifact['request']['requirements'],artifact['request']['constraints'],artifact['request']['runtime_limits'])
        found,obs=st.select(req,reference,host,local.process,root/'shared-tools')
        assert found is None and obs['reason']=='selected_request_mismatch',obs
        assert obs['mismatches'];results.append({'mutation':mode,'observation':obs})
    assert manifest(root/'shared-tools')==before
    assert inspect_candidate(root/'a/library',a['name'])['qualification']['accepted']
    write_json(destination/'negative-probes.json',sanitized({'passed':True,'scope':'isolated request parsing against real registered version; not new generation','models':0,'builds':0,'old_binding_preserved':True,'observations':results}))
    print({'negative_probes':len(results),'passed':True})


def original_package_check(root, label, output_root=None):
    """Recheck the unchanged failed assertion on the correct current Skill object.

    Separate infrastructure audit only. No edits to the failed round, its contract,
    new acceptance plans or qualifications. Only the directory argv is rebound to
    a read-only mount of the complete current frozen Skill package.
    """
    import uuid
    from creation_pipeline.runtime import runner
    previous=root.parent/'bundled-json-cli-20261101-02'
    old=next((previous/'a/state/outputs').iterdir());summary=read_json(old/'summary.json')
    old_record=read_json(old/'records'/(summary['entities'][0]['name']+'.json'))
    old_cases=read_json(old/old_record['durable_evidence']['path']/'runtime/locked-tests.json')['cases']
    case=next(c for c in old_cases if c['name']=='check-generated-source-bytes-and-bundled-policy')
    observed=next(c for c in read_json(old/old_record['runtime']['path']/'execution/report.json')['cases'] if c['name']==case['name'])
    assert observed['status']=='failed'
    current=next((root/label/'state/outputs').iterdir());s=read_json(current/'summary.json')
    record=read_json(current/'records'/(s['entities'][0]['name']+'.json'))
    package=current/record['durable_evidence']['path']/'package'
    receipt=read_json(current/record['runtime']['path']/'receipt.json')
    args=list(case['args']);assert args[0]=='-c' and args[2]=='/opt/skill/package'
    args[2]='/input'
    expected=json.loads(args[3]);assert set(expected)=={'scripts/triage.py','scripts/calc_descriptors.py','scripts/data/rules.json','requirements.txt'}
    for path,sha in expected.items():assert file_digest(package/path)==sha
    tool={'limits':{'memory':'512m','cpus':'1','pids':64},'behavior':{'file_io':True},
          'runtime_network':False,'execution_scope':'p2-package-audit-'+uuid.uuid4().hex}
    result=runner.run(tool,receipt['image_id'],args,input_dir=package,entrypoint='python',timeout=30)
    write_json((output_root or root)/('original-package-check-'+label+'.json'),sanitized({'scope':'separate read-only Docker infrastructure check, not generation qualification',
        'original_case':case,'original_failed_observation':observed,'program_and_expected_hashes_unchanged':True,
        'directory_argument':{'expected_object':'current frozen Skill package','old':'/opt/skill/package','actual':'/input'},
        'current_package':str(package),'complete_package_files':manifest(package),'actual_argv':args,'result':result}))
    assert result['exit_code']==0 and 'source-bytes-and-policy-verified' in result['stdout'],result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path)
    parser.add_argument('--labels',nargs='+',default=['a','b']);parser.add_argument('--negatives',action='store_true')
    parser.add_argument('--original-package-check',action='store_true')
    parser.add_argument('--b-root',type=Path,help='Fresh B directory after an interrupted run; no state is copied')
    parser.add_argument('--output-root',type=Path,help='Write new audit evidence here; preserve earlier experiment directories')
    args=parser.parse_args();audit(args.root.resolve(),args.labels,args.b_root.resolve() if args.b_root else None,
                                 args.output_root.resolve() if args.output_root else None)
    if args.negatives:negatives(args.root.resolve(),args.output_root.resolve() if args.output_root else None)
    if args.original_package_check:
        for label in args.labels:original_package_check(args.b_root.resolve() if label=='b' and args.b_root else args.root.resolve(),label,
                                                      args.output_root.resolve() if args.output_root else None)
