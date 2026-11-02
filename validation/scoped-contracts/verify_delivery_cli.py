"""Public CLI scoped-envelope recovery and review-bypass refusal; zero models."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from creation_pipeline.records import read_json,write_json,redact
from creation_pipeline.artifacts.package import manifest


def main():
    parent=Path(sys.argv[1]).resolve();root=parent/'delivery-cli';root.mkdir(exist_ok=False)
    out=next((parent/'a/state/outputs').iterdir());name=read_json(out/'summary.json')['entities'][0]['name']
    before=manifest(parent/'a/library');registry=manifest(parent/'shared-tools')
    guard=root/'guard';guard.mkdir()
    c=subprocess.run(['C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe','/nologo','/out:'+str(guard/'docker.exe'),str(REPO/'validation/v3-delivery/CliGuard.cs')],capture_output=True,text=True)
    assert c.returncode==0
    shutil.copyfile(guard/'docker.exe',guard/'codex.exe')
    env=os.environ.copy();env['CHEM_PROBE_REAL_DOCKER']=shutil.which('docker');env['PATH']=str(guard)+os.pathsep+env['PATH'];operations=[]
    def cli(label,args,expected=0):
        d=root/label;d.mkdir();e=env.copy();e['CHEM_PROBE_COUNTER']=str(d/'counter.txt')
        cmd=[sys.executable,'-m','creation_pipeline',*map(str,args)]
        p=subprocess.run(cmd,cwd=REPO,env=e,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (d/'stdout.json').write_text(redact(p.stdout),encoding='utf-8');(d/'stderr.log').write_text(redact(p.stderr),encoding='utf-8')
        response=json.loads(p.stdout or p.stderr);marks=(d/'counter.txt').read_text() if (d/'counter.txt').exists() else ''
        r={'command':cmd,'exit_code':p.returncode,'response':response,'models':marks.count('M'),'builds':marks.count('B')}
        write_json(d/'result.json',r);operations.append(r)
        assert p.returncode==expected and 'M' not in marks and 'B' not in marks,r
        return response
    rejected=root/'rejected-library'
    cli('import-for-refusal',['runtime-import',out,rejected,'--candidate',name],1)
    assert not cli('unqualified',['runtime-inspect',rejected,'--candidate',name])['qualification']['accepted']
    spec=read_json(Path(__file__).with_name('skill-a.json'))['runtime_defaults']
    spec=copy.deepcopy(spec);spec['skill_contract']['requirements'].append('A different business obligation without new authoring and review.')
    spec_path=root/'changed-scope.json';write_json(spec_path,spec)
    failed=cli('reject-business-scope-change',['runtime-prepare',rejected,'--candidate',name,'--spec',spec_path],2)
    assert 'skill_contract_change_requires_review' in failed['error']
    assert not cli('still-unqualified',['runtime-inspect',rejected,'--candidate',name])['qualification']['accepted']
    installed=cli('install',['install',out,'--destination',root/'installed'])
    envelope=Path(installed['installed'])/'runtime'/name;assert envelope.is_dir()
    restored=root/'clean-restored-library'
    cli('import-clean-envelope',['runtime-import',envelope,restored,'--candidate',name],1)
    assert not cli('clean-unqualified',['runtime-inspect',restored,'--candidate',name])['qualification']['accepted']
    result=cli('execute-new-attempt',['runtime-resume',restored,'--candidate',name])
    assert result['accepted'] and result['status']=='execution_passed'
    current=next(i for i in read_json(restored/'catalog.json')['skills'] if i['name']==name)
    report=read_json(restored/current['runtime']['path']/'execution/report.json')
    assert report['acceptance']['complete'] and all(c['status']=='passed' for c in report['cases'])
    frozen=read_json(restored/current['evidence']/'record.json')['delivery']['inputs']
    assert frozen['environment']['payload']['tool_compatibility'] and frozen['acceptance']['payload']['skill_contract']
    assert manifest(parent/'a/library')==before and manifest(parent/'shared-tools')==registry
    write_json(root/'results.json',{'passed':True,'models':0,'actual_builds':0,'cases':len(report['cases']),
        'scope':'same frozen current contract, independent new attempt; no generation or acceptance compilation',
        'old_binding_and_registry_unchanged':True,'operations':operations})
    print({'passed':True,'cases':len(report['cases']),'models':0,'builds':0})


if __name__=='__main__':main()
