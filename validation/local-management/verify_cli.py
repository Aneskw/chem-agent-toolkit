"""Public management CLI against real frozen Skills; no internal state injection."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from creation_pipeline.management import API_VERSION
from creation_pipeline.records import read_json,write_json,redact,now,file_digest
from creation_pipeline.artifacts.package import manifest


def main():
    root=Path(sys.argv[1]).resolve();root.mkdir(exist_ok=False)
    original=Path(sys.argv[2]).resolve();registry=original/'shared-tools'
    before={label:manifest(original/label/'library') for label in ('a','b')};registered=manifest(registry)
    write_json(root/'implementation.json',{p.as_posix():file_digest(p) for p in sorted((REPO/'creation_pipeline').rglob('*.py'))})
    guard=root/'guard';guard.mkdir()
    p=subprocess.run(['C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe','/nologo','/out:'+str(guard/'docker.exe'),str(REPO/'validation/v3-delivery/CliGuard.cs')],capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    shutil.copyfile(guard/'docker.exe',guard/'codex.exe')
    env=os.environ.copy();env['CHEM_PROBE_REAL_DOCKER']=shutil.which('docker');env['PATH']=str(guard)+os.pathsep+env['PATH']
    operations=[];executions=[]
    def cli(label,argv,expected=0,missing=None):
        dest=root/'operations'/label;dest.mkdir(parents=True,exist_ok=False)
        e=env.copy();e['CHEM_PROBE_COUNTER']=str(dest/'counter.txt')
        if missing:e['CHEM_PROBE_MISSING_IMAGE']=missing
        command=[sys.executable,'-m','creation_pipeline',*map(str,argv)]
        started=time.monotonic();p=subprocess.run(command,cwd=REPO,env=e,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (dest/'stdout.json').write_text(redact(p.stdout),encoding='utf-8');(dest/'stderr.log').write_text(redact(p.stderr),encoding='utf-8')
        answer=json.loads(p.stdout or p.stderr);marks=(dest/'counter.txt').read_text() if (dest/'counter.txt').exists() else ''
        result={'command':command,'seconds':time.monotonic()-started,'exit_code':p.returncode,'response':answer,
                'models':marks.count('M'),'builds':marks.count('B'),'docker_commands':marks.count('D'),'injected_image_observations':marks.count('F')}
        write_json(dest/'result.json',result);operations.append({'label':label,**result})
        assert p.returncode==expected and 'M' not in marks and 'B' not in marks,(label,result)
        return answer
    def manage(label,operation,params,expected=0,missing=None,request_id=None):
        path=root/'requests'/(label+'.json')
        write_json(path,{'api_version':API_VERSION,'request_id':request_id or label,'operation':operation,'params':params})
        answer=cli(label,['manage',path],expected,missing)
        assert answer['api_version']==API_VERSION and answer['request_id']==(request_id or label)
        assert answer['ok'] is (expected==0)
        return answer
    def entry(library,name):return next(i for i in read_json(library/'catalog.json')['skills'] if i['name']==name)
    first=None
    for label in ('a','b'):
        out=next((original/label/'state/outputs').iterdir());summary=read_json(out/'summary.json');name=summary['entities'][0]['name']
        record=read_json(out/'records'/(name+'.json'));frozen=out/record['durable_evidence']['path'];receipt=read_json(out/record['runtime']['path']/'receipt.json')
        request=receipt['tool_artifact']['request'];scope=request['tool_compatibility'];opaque=scope['unclassified']
        descriptor={'context':str(frozen/'runtime/context'),'entry':request['entry'],'declaration':request['declaration'],
            'runtime_limits':request['runtime_limits'],'requirements':opaque['requirements'],'constraints':opaque['constraints'],
            'tool_compatibility':{k:v for k,v in scope.items() if k!='unclassified'},'caller_constraints':opaque['caller_constraints']}
        described=manage(label+'-describe','tool.describe',descriptor)
        assert described['data']['request']==request
        reference={k:receipt['tool_artifact'][k] for k in ('request_key','artifact_id')}
        params={'descriptor':descriptor,'request_key':reference['request_key'],'registry':str(registry)}
        resolved=manage(label+'-resolve','tool.resolve',params)
        selected=manage(label+'-select','tool.select',dict(params,reference=reference))
        assert resolved['data']['artifact']==selected['data']['artifact']==receipt['tool_artifact']
        assert selected['data']['accepted'] is None and not selected['data']['binding_persisted']
        online=manage(label+'-available','tool.availability',{'registry':str(registry),'reference':reference})
        assert online['data']['available'] and online['data']['passed'] is None
        offline=manage(label+'-offline-available','tool.availability',{'registry':str(registry),'reference':reference,'offline':True})
        assert offline['data']['available'] is None and operations[-1]['docker_commands']==0
        library=root/label/'library'
        cli(label+'-import',['runtime-import',out,library,'--candidate',name],1)
        observed=manage(label+'-unqualified','skill.qualification',{'library':str(library),'name':name})
        assert not observed['data']['qualification']['accepted']
        historical=manage(label+'-historical','skill.qualification',{'library':str(library),'name':name,'offline':True})
        assert historical['data']['qualification']['accepted'] is None and operations[-1]['docker_commands']==0
        current=entry(library,name)
        execute={'library':str(library),'name':name,'expected_revision':current['revision_id'],'expected_freeze_sha256':current['freeze_sha256']}
        stale=manage(label+'-stale-revision','skill.execute',dict(execute,expected_revision='rev-'+'0'*64),1)
        assert stale['error']['code']=='revision_changed' and stale['error']['expected']=='rev-'+'0'*64
        response=manage(label+'-execute','skill.execute',execute,request_id='same-correlation')
        assert response['data']['passed'] and response['data']['accepted']
        def audit_execution(tag,response):
            item=entry(library,name);attempt=library/item['runtime']['path'];report=read_json(attempt/'execution/report.json')
            assert report['acceptance']['complete'] and all(c['status']=='passed' for c in report['cases'])
            assert str(attempt/'receipt.json') in [r['path'] for r in response['evidence']]
            assert response['data']['native']['evidence_snapshot']['runtime']['path']==item['runtime']['path']
            executions.append({'label':tag,'attempt':str(attempt),'cases':len(report['cases']),'execution_sha256':file_digest(attempt/'execution/report.json')})
            return item['runtime']['path']
        path=audit_execution(label,response)
        if label=='a':
            repeated=manage('a-repeat-correlation','skill.execute',execute,request_id='same-correlation')
            assert audit_execution('a-repeat',repeated)!=path
        assert manage(label+'-qualified','skill.qualification',{'library':str(library),'name':name})['data']['qualification']['accepted']
        old_cli=cli(label+'-old-inspect',['runtime-inspect',library,'--candidate',name])
        assert old_cli['qualification']['accepted'] and 'api_version' not in old_cli
        if first is None:first=(out,name,descriptor,params,reference,receipt['image_id'])
    out,name,descriptor,params,reference,image=first
    changed=copy.deepcopy(descriptor);changed['constraints'].append('changed opaque requirement')
    new=manage('changed-description','tool.describe',changed)['data']
    mismatch=manage('selected-mismatch','tool.select',dict(params,descriptor=changed,request_key=new['request_key'],reference=reference),1)
    assert mismatch['error']['raw']['observation']['reason']=='selected_request_mismatch' and mismatch['evidence']
    invalid=root/'requests/invalid.json';write_json(invalid,{'api_version':'unknown','request_id':'invalid','operation':'tool.describe','params':{}})
    assert cli('invalid-version',['manage',invalid],2)['error']['code']=='request_invalid'
    fault=root/'missing-image-library';cli('fault-import',['runtime-import',out,fault,'--candidate',name],1)
    item=entry(fault,name)
    failed=manage('missing-image-execute','skill.execute',{'library':str(fault),'name':name,'expected_revision':item['revision_id'],
        'expected_freeze_sha256':item['freeze_sha256']},1,missing=image)
    assert failed['error']['code'] in {'execution_failed','execution_blocked'} and failed['error']['source_refs']
    item=entry(fault,name);report=read_json(fault/item['runtime']['path']/'execution/report.json')
    assert report.get('cases',[])==[] and not item['current_qualification']['accepted']
    assert any(i['injected_image_observations'] for i in operations)
    assert manifest(registry)==registered
    assert all(manifest(original/label/'library')==before[label] for label in ('a','b'))
    assert len({x['attempt'] for x in executions})==len(executions)
    write_json(root/'results.json',{'at':now(),'passed':True,'models':0,'actual_builds':0,'new_generation_batches':0,
        'cases':sum(x['cases'] for x in executions),'executions':executions,'original_libraries_and_registry_unchanged':True,
        'fault_scope':'exact image inspect boundary injection; real image retained; failed library never rerun', 'operations':operations})
    print({'passed':True,'cases':sum(x['cases'] for x in executions),'operations':len(operations),'models':0,'builds':0})


if __name__=='__main__':main()
