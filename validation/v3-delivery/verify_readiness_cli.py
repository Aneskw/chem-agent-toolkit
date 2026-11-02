"""Ordinary CLI readiness probes, with an executable boundary blocking inference."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from creation_pipeline.records import read_json,write_json,redact,now


def main():
    root=Path(sys.argv[1]).resolve();root.mkdir(exist_ok=False)
    guard=root/'guard';guard.mkdir()
    compiler='C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    result=subprocess.run([compiler,'/nologo','/out:'+str(guard/'docker.exe'),str(Path(__file__).with_name('CliGuard.cs'))],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    shutil.copyfile(guard/'docker.exe',guard/'codex.exe')
    env=os.environ.copy();env['CHEM_PROBE_REAL_DOCKER']=shutil.which('docker');env['PATH']=str(guard)+os.pathsep+env['PATH']
    config=read_json(REPO/'validation/codex-planner/skill-a.json');records=[]
    def run(label,argv,expected,config_override=None,missing_daemon=False):
        directory=root/label;directory.mkdir()
        cfg=directory/'config.json';write_json(cfg,config if config_override is None else config_override)
        argv=[str(cfg) if x=='CONFIG' else x for x in argv]
        e=env.copy();e['CHEM_PROBE_COUNTER']=str(directory/'counter.txt')
        if missing_daemon:
            e.pop('DOCKER_CONTEXT',None);e['DOCKER_HOST']='npipe:////./pipe/chem-readiness-isolated-absent'
        cmd=[sys.executable,'-m','creation_pipeline',*argv]
        started=time.monotonic();r=subprocess.run(cmd,cwd=REPO,env=e,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (directory/'stdout.json').write_text(redact(r.stdout),encoding='utf-8');(directory/'stderr.log').write_text(redact(r.stderr),encoding='utf-8')
        response=json.loads(r.stdout or r.stderr);marks=(directory/'counter.txt').read_text() if (directory/'counter.txt').exists() else ''
        rec={'label':label,'command':cmd,'exit_code':r.returncode,'response':response,'seconds':time.monotonic()-started,
             'models':marks.count('M'),'builds':marks.count('B'),'docker_commands':marks.count('D')}
        write_json(directory/'result.json',rec);records.append(rec)
        assert r.returncode==expected and rec['models']==rec['builds']==0,rec
        return response,rec
    good,_=run('ready',['readiness','CONFIG'],0);assert good['status']=='ready'
    offline,rec=run('offline',['readiness','CONFIG','--offline'],0,missing_daemon=True)
    assert offline['status']=='deferred' and rec['docker_commands']==0
    draft,_=run('draft-offline',['readiness','CONFIG','--mode','draft'],0,missing_daemon=True)
    assert draft['status']=='deferred' and not draft['gaps']
    absent=copy.deepcopy(config);absent['sources'][0]['path']=str(root/'absent-source')
    state=str(root/'forbidden-state')
    bad,_=run('missing-source',['build','CONFIG','--state-dir',state],1,absent)
    assert bad['phase']=='readiness' and not Path(state).exists()
    run('configuration-only',['build','CONFIG','--preflight'],0,absent)
    run('missing-daemon',['build','CONFIG','--state-dir',state],1,missing_daemon=True)
    wrong=copy.deepcopy(config);wrong['runtime_defaults']['shared_tool']['bundled_data'][0]['sha256']='0'*64
    bad,_=run('data-drift',['build','CONFIG','--state-dir',state],1,wrong)
    assert 'expected sha256=' in str(bad['errors'])
    selected=copy.deepcopy(config);selected['runtime_defaults']['tool_artifact']={'request_key':'0'*64,'artifact_id':'1'*64}
    run('selected-version-missing',['build','CONFIG','--state-dir',state],1,selected)
    local=root/'unknown-source';shutil.copytree(config['sources'][0]['path'],local)
    entry=local/'scripts/triage.py';entry.write_bytes(entry.read_bytes()+b'\nimport subprocess\n')
    unsupported=copy.deepcopy(config);unsupported['sources'][0]['path']=str(local)
    bad,_=run('known-unsupported',['build','CONFIG','--state-dir',state],1,unsupported)
    assert 'external process invocation' in str(bad['errors'])
    write_json(root/'results.json',{'at':now(),'passed':True,'models':0,'builds':0,'qualification':'not_granted',
        'fault':'DOCKER_HOST override applies only to child processes; daemon/images/cache unchanged','operations':records})
    print(json.dumps({'passed':True,'operations':len(records),'models':0,'builds':0,'root':str(root)}))


if __name__=='__main__':main()
