"""Explicit old version + changed source/requirements must fail before inference."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from creation_pipeline.records import read_json,write_json,file_digest,redact
from creation_pipeline.artifacts.package import manifest


def main():
    root=Path(sys.argv[1]).resolve();audit=read_json(root/'audit-a.json')['observations'][0]
    reference={k:audit[k] for k in ('request_key','artifact_id')}
    directory=root/'mutation-cli';directory.mkdir(exist_ok=False);guard=directory/'guard';guard.mkdir()
    compiler='C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    r=subprocess.run([compiler,'/nologo','/out:'+str(guard/'docker.exe'),str(REPO/'validation/v3-delivery/CliGuard.cs')],capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    shutil.copyfile(guard/'docker.exe',guard/'codex.exe')
    env=os.environ.copy();env['CHEM_PROBE_REAL_DOCKER']=shutil.which('docker');env['PATH']=str(guard)+os.pathsep+env['PATH']
    env['CHEM_AGENT_SHARED_TOOLS']=str(root/'shared-tools')
    before=manifest(root/'a/library');registry=manifest(root/'shared-tools');results=[]
    base=read_json(Path(__file__).with_name('skill-a.json'))
    for mode in ('module','resource','dependency','interface','platform','resource-capability','base-image','unknown-field','unclassified','source-document','caller-constraint'):
        d=directory/mode;d.mkdir();source=d/'source';shutil.copytree(base['sources'][0]['path'],source)
        config=copy.deepcopy(base);config['sources'][0]['path']=str(source)
        spec=config['runtime_defaults'];spec['tool_artifact']=reference
        if mode=='module':
            p=source/'scripts/calc_descriptors.py';p.write_bytes(p.read_bytes()+b'\n# new source version\n')
        elif mode=='resource':
            p=source/'scripts/rules.json';p.write_text('{"policy_id":"demonstration-screen-50-v1","maximum_molecular_weight":51.0}',encoding='utf-8')
            spec['shared_tool']['bundled_data'][0]['sha256']=file_digest(p)
        elif mode=='dependency':spec['shared_tool']['requirements']['imports']['rdkit']='2025.3.1'
        elif mode=='interface':spec['shared_tool']['interface']['entrypoint'][0]='python3'
        elif mode=='platform':spec['shared_tool']['platform']='linux/arm64'
        elif mode=='resource-capability':spec['shared_tool']['interface']['resources']=['undeclared GPU']
        elif mode=='base-image':spec['tool_compatibility']['requirements']['base_image']='python:3.12-slim'
        elif mode=='unknown-field':spec['tool_compatibility']['requirements']['unknown_runtime_requirement']='value'
        elif mode=='unclassified':spec['requirements']=['Opaque unknown runtime requirement']
        elif mode=='source-document':
            p=source/'README.md';p.write_bytes(p.read_bytes()+b'\nBusiness-looking material of unknown runtime role.\n')
        else:config['constraints']={'future_runtime_policy':{'version':'changed'}}
        path=d/'config.json';write_json(path,config);e=env.copy();e['CHEM_PROBE_COUNTER']=str(d/'counter.txt')
        cmd=[sys.executable,'-m','creation_pipeline','build',str(path),'--state-dir',str(d/'state'),'--library-dir',str(d/'library')]
        r=subprocess.run(cmd,cwd=REPO,env=e,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (d/'stdout.json').write_text(redact(r.stdout),encoding='utf-8');(d/'stderr.log').write_text(redact(r.stderr),encoding='utf-8')
        answer=json.loads(r.stdout or r.stderr);marks=(d/'counter.txt').read_text() if (d/'counter.txt').exists() else ''
        record={'mutation':mode,'command':cmd,'exit_code':r.returncode,'response':answer,'models':marks.count('M'),'builds':marks.count('B')}
        write_json(d/'result.json',record);results.append(record)
        assert r.returncode==1 and answer['phase']=='readiness' and answer['model_calls']==0,record
        assert not (d/'state').exists() and not (d/'library').exists() and 'M' not in marks and 'B' not in marks
        assert any(g['code'] in {'tool_request_mismatch','tool_source_mismatch','configuration_invalid'} for g in answer['errors']),answer
    assert manifest(root/'a/library')==before and manifest(root/'shared-tools')==registry
    write_json(directory/'results.json',{'passed':True,'models':0,'builds':0,'old_library_and_registry_bytes_unchanged':True,'operations':results})
    print({'passed':True,'mutations':len(results),'models':0,'builds':0})


if __name__=='__main__':main()
