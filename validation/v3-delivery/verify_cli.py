"""Fresh-directory v3 delivery/recovery experiments through public CLI subprocesses.

Read-only manifests/catalogs audit results. No internal adoption, seal, prepared
plan or qualification injection; drift and image-absence observations are explicit.
"""
import argparse
from pathlib import Path
import os
import shutil
import subprocess
import sys
import time
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
from creation_pipeline.records import read_json,write_json,sanitized,redact,now
from creation_pipeline.artifacts.package import manifest


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--sources',type=Path,required=True)
    a=p.parse_args();root=a.root.resolve();root.mkdir(exist_ok=False)
    guard=root/'guard';guard.mkdir()
    real=shutil.which('docker');assert real
    compiler=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
    compiled=subprocess.run([str(compiler),'/nologo','/out:'+str(guard/'docker.exe'),str(Path(__file__).with_name('CliGuard.cs'))],capture_output=True,text=True)
    write_json(root/'guard-build.json',sanitized({'exit_code':compiled.returncode,'stdout':compiled.stdout,'stderr':compiled.stderr,'real_docker':real}))
    assert compiled.returncode==0
    shutil.copyfile(guard/'docker.exe',guard/'codex.exe')
    env=os.environ.copy();env['PATH']=str(guard)+os.pathsep+env['PATH'];env['CHEM_PROBE_REAL_DOCKER']=real
    env['CHEM_AGENT_SHARED_TOOLS']=str(root/'absent-registry');env['CHEM_AGENT_SHARED_ENVIRONMENTS']=str(root/'absent-environments')
    observations=[];executions=[]
    def cli(label,args,expected=(0,),missing=None):
        d=root/'operations'/label;d.mkdir(parents=True,exist_ok=False)
        e=env.copy();e['CHEM_PROBE_COUNTER']=str(d/'counter.txt')
        if missing:e['CHEM_PROBE_MISSING_IMAGE']=missing
        command=[sys.executable,'-m','creation_pipeline',*map(str,args)]
        start=time.monotonic();r=subprocess.run(command,cwd=REPO,env=e,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (d/'stdout.json').write_text(redact(r.stdout),encoding='utf-8');(d/'stderr.log').write_text(redact(r.stderr),encoding='utf-8')
        try:answer=__import__('json').loads(r.stdout or r.stderr)
        except ValueError:answer=None
        marks=(d/'counter.txt').read_text() if (d/'counter.txt').exists() else ''
        result={'at':now(),'command':command,'exit_code':r.returncode,'seconds':time.monotonic()-start,'response':answer,
                'actual_docker_commands':marks.count('D')+marks.count('B'),'actual_build_commands':marks.count('B'),
                'blocked_model_commands':marks.count('M'),'injected_image_observations':marks.count('F')}
        write_json(d/'result.json',sanitized(result));observations.append(result)
        assert r.returncode in expected,(label,result)
        assert result['actual_build_commands']==result['blocked_model_commands']==0,(label,result)
        return answer
    def entry(lib,name):return next(e for e in read_json(lib/'catalog.json')['skills'] if e['name']==name)
    def unqualified(label,lib,name):
        info=cli(label,['runtime-inspect',lib,'--candidate',name]);assert not info['qualification']['accepted'],info
    def run(label,lib,name,operation,original):
        before=entry(lib,name);old_path=before.get('runtime',{}).get('path')
        response=cli(label,[operation,lib,'--candidate',name])
        assert response['status']=='execution_passed' and response.get('accepted') is True and response.get('business_acceptance')=='passed',response
        after=entry(lib,name);assert after['runtime']['path']!=old_path
        assert after['delivery']['revision_id']==original['delivery']['revision_id']
        report=read_json(lib/after['runtime']['path']/'execution/report.json')
        assert report['status']=='execution_passed' and all(c['status']=='passed' for c in report['cases'])
        assert report['acceptance']['complete'] and report['validation']['behavior']=='passed'
        info=cli(label+'-qualification',['runtime-inspect',lib,'--candidate',name]);assert info['qualification']['accepted']
        executions.append({'label':label,'attempt':str(lib/after['runtime']['path']),'cases':len(report['cases']),
                           'revision_id':after['delivery']['revision_id'],'qualification':info['qualification']})
    originals=[]
    for label in ('a','b'):
        src=a.sources.resolve()/label;originals.append({'path':str(src),'files':manifest(src)})
        write_json(root/'source-before.json',sanitized(originals))
        output=next((src/'state/outputs').iterdir());summary=read_json(output/'summary.json');name=summary['entities'][0]['name']
        record=read_json(output/'records'/(name+'.json'));receipt=read_json(output/record['runtime']['path']/'receipt.json')
        assert receipt['tool_artifact']['abi']=='shared_tool_image_v3'
        current=cli(label+'-original',['runtime-inspect',src/'library','--candidate',name]);assert current['qualification']['accepted']
        installed=cli(label+'-install',['install',output,'--destination',root/label/'installed'])
        envelope=Path(installed['installed'])/'runtime'/name
        lib=root/label/'envelope-library'
        cli(label+'-import-envelope',['runtime-import',envelope,lib,'--candidate',name],(1,))
        unqualified(label+'-import-unqualified',lib,name)
        cli(label+'-install-before-execution',['install',lib,'--name',name,'--destination',root/label/'forbidden-install'],(2,))
        run(label+'-envelope-resume',lib,name,'runtime-resume',record)
        cli(label+'-qualified-install',['install',lib,'--name',name,'--destination',root/label/'qualified-install'])
        moved=root/label/'migrated-library';shutil.copytree(lib,moved)
        cli(label+'-relocate',['runtime-relocate',moved,'--candidate',name],(1,))
        unqualified(label+'-migrated-unqualified',moved,name)
        run(label+'-migrated-resume',moved,name,'runtime-resume',record)
        native=root/label/'native-library'
        cli(label+'-import-native',['runtime-import',output,native,'--candidate',name],(1,))
        unqualified(label+'-native-unqualified',native,name)
        run(label+'-native-validate',native,name,'runtime-validate',record)
        run(label+'-explicit-build',native,name,'runtime-build',record)
        run(label+'-ready-resume',lib,name,'runtime-resume',record)
        for mode in ('data','binding'):
            bad=root/label/('bad-'+mode);shutil.copytree(envelope,bad)
            file=bad/'frozen/package/scripts/data/rules.json' if mode=='data' else bad/'frozen/record.json'
            if mode=='data':file.write_bytes(file.read_bytes()+b'\n ')
            else:
                obj=read_json(file);obj['delivery']['inputs']['bindings']['payload']['entry']='scripts/other.py';write_json(file,obj)
            target=root/label/(mode+'-rejected-library')
            failure=cli(label+'-reject-'+mode,['runtime-import',bad,target,'--candidate',name],(2,))
            assert not target.exists() and 'changed' in failure['error'].lower()
        fault=root/label/'missing-image-library'
        cli(label+'-missing-import',['runtime-import',envelope,fault,'--candidate',name],(1,))
        failed=cli(label+'-missing-resume',['runtime-resume',fault,'--candidate',name],(1,),receipt['image_id'])
        assert failed['status']!='ready'
        unqualified(label+'-missing-unqualified',fault,name)
        restored=root/label/'restored-library'
        cli(label+'-restored-import',['runtime-import',envelope,restored,'--candidate',name],(1,))
        run(label+'-restored-resume',restored,name,'runtime-resume',record)
        for mode,source in [('bare',envelope/'frozen/package'),('archive',root/label/'image.tar')]:
            if mode=='archive':source.write_bytes(b'unsupported archive format probe')
            target=root/label/(mode+'-unsupported-library')
            cli(label+'-unsupported-'+mode,['runtime-import',source,target,'--candidate',name],(2,));assert not target.exists()
        assert manifest(src)==originals[-1]['files']
        info=cli(label+'-original-after',['runtime-inspect',src/'library','--candidate',name]);assert info['qualification']['accepted']
    assert len({e['attempt'] for e in executions})==len(executions)
    write_json(root/'source-before.json',sanitized(originals))
    write_json(root/'results.json',sanitized({'passed':True,'scope':'public CLI; current locked contracts re-executed, no new acceptance model',
        'executions':executions,'cases':sum(e['cases'] for e in executions),'commands':observations,
        'actual_build_commands':0,'actual_model_processes':0,'image_missing_scope':'OS command-boundary injection only; no real image deleted',
        'originals_preserved':True,'unsupported':['bare Skill import','archive/OCI import','cross-host distribution']}))
    print({'passed':True,'cases':sum(e['cases'] for e in executions),'independent_attempts':len(executions)})


if __name__=='__main__':main()
