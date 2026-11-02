"""Public CLI regression of the retained self-contained Open Babel delivery."""
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
    root=Path(sys.argv[1]).resolve();root.mkdir(exist_ok=False)
    source=REPO.parent/'acceptance-openbabel-run74-20261029/library';name='chem-openbabel-convert'
    before=manifest(source);guard=root/'guard';guard.mkdir()
    result=subprocess.run(['C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe','/nologo','/out:'+str(guard/'docker.exe'),str(Path(__file__).with_name('CliGuard.cs'))],capture_output=True,text=True)
    assert result.returncode==0
    shutil.copyfile(guard/'docker.exe',guard/'codex.exe')
    env=os.environ.copy();env['CHEM_PROBE_REAL_DOCKER']=shutil.which('docker');env['PATH']=str(guard)+os.pathsep+env['PATH'];operations=[]
    def cli(label,argv,expected=0):
        d=root/label;d.mkdir();e=env.copy();e['CHEM_PROBE_COUNTER']=str(d/'counter.txt')
        command=[sys.executable,'-m','creation_pipeline',*map(str,argv)]
        r=subprocess.run(command,cwd=REPO,env=e,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (d/'stdout.json').write_text(redact(r.stdout),encoding='utf-8');(d/'stderr.log').write_text(redact(r.stderr),encoding='utf-8')
        reply=json.loads(r.stdout or r.stderr);marks=(d/'counter.txt').read_text() if (d/'counter.txt').exists() else ''
        record={'command':command,'exit_code':r.returncode,'response':reply,'models':marks.count('M'),'builds':marks.count('B')}
        write_json(d/'result.json',record);operations.append(record)
        assert r.returncode==expected and 'M' not in marks and 'B' not in marks,record
        return reply
    original=cli('original',['runtime-inspect',source,'--candidate',name]);assert original['qualification']['accepted']
    cli('install',['install',source,'--name',name,'--destination',root/'installed'])
    envelope=root/'installed/.runtime'/name;assert envelope.is_dir()
    lib=root/'imported-library'
    cli('import',['runtime-import',envelope,lib,'--candidate',name],1)
    info=cli('unqualified',['runtime-inspect',lib,'--candidate',name]);assert not info['qualification']['accepted']
    response=cli('execute',['runtime-validate',lib,'--candidate',name]);assert response['accepted']
    def report(library):
        entry=next(e for e in read_json(library/'catalog.json')['skills'] if e['name']==name)
        assert not entry['delivery']['inputs']['environment']['payload'].get('shared_tool')
        report=read_json(library/entry['runtime']['path']/'execution/report.json')
        assert all(c['status']=='passed' for c in report['cases']) and report['acceptance']['complete']
        return len(report['cases'])
    count=report(lib);moved=root/'moved-library';shutil.copytree(lib,moved)
    cli('relocate',['runtime-relocate',moved,'--candidate',name],1)
    info=cli('moved-unqualified',['runtime-inspect',moved,'--candidate',name]);assert not info['qualification']['accepted']
    response=cli('moved-execute',['runtime-validate',moved,'--candidate',name]);assert response['accepted']
    count+=report(moved)
    assert manifest(source)==before
    write_json(root/'results.json',{'passed':True,'cases':count,'models':0,'builds':0,'mode':'self_contained','original_library_unchanged':True,'operations':operations})
    print({'passed':True,'cases':count,'models':0,'builds':0})


if __name__=='__main__':main()
