"""One explicitly authorized ordinary-CLI generation, no replay or injected plans."""
import os
from pathlib import Path
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from creation_pipeline.models import load_config
from creation_pipeline.records import write_json,read_json,redact,file_digest,now
from creation_pipeline.artifacts.package import manifest


def main():
    root=Path(sys.argv[1]).resolve();root.mkdir(exist_ok=False)
    config_path=Path(sys.argv[2]).resolve();config=load_config(config_path)
    assert config['limits']['max_candidates']==config['limits']['max_builds']==1
    sources={s['path']:manifest(s['path']) for s in config['sources']}
    config_sha=file_digest(config_path)
    write_json(root/'inputs-before.json',{'config':{'path':str(config_path),'sha256':config_sha},'sources':sources,
        'implementation':{p.as_posix():file_digest(p) for p in sorted((REPO/'creation_pipeline').rglob('*.py'))}})
    write_json(root/'envelope.json',{'model':config['model'],'limits':config['limits'],
        'runtime_options':config['runtime_defaults']['options'],'qualification_inherited':False})
    env=os.environ.copy()
    env['CHEM_AGENT_SHARED_TOOLS']=str(root/'shared-tools')
    env['CHEM_AGENT_SHARED_ENVIRONMENTS']=str(root/'shared-environments')
    operations=[]
    def call(label,argv):
        dest=root/'operations'/label;dest.mkdir(parents=True)
        command=[sys.executable,'-m','creation_pipeline',*map(str,argv)]
        write_json(dest/'command.json',{'command':command,'cwd':str(REPO),'started_at':now()})
        start=time.monotonic();p=subprocess.run(command,cwd=REPO,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (dest/'stdout.json').write_text(redact(p.stdout),encoding='utf-8');(dest/'stderr.log').write_text(redact(p.stderr),encoding='utf-8')
        answer=read_json(dest/'stdout.json') if p.stdout.strip() else None
        result={'label':label,'command':command,'seconds':time.monotonic()-start,'exit_code':p.returncode,'response':answer}
        write_json(dest/'result.json',result);operations.append(result)
        print(label,p.returncode,(answer or {}).get('status'),flush=True)
        if p.returncode:raise ValueError('Public CLI failed: '+label+'; evidence='+str(dest))
        return answer
    try:
        call('configuration',['build',config_path,'--preflight'])
        readiness=call('readiness',['readiness',config_path])
        assert readiness['status']=='ready' and readiness['model_calls']==readiness['build_calls']==0
        built=call('build',['build',config_path,'--state-dir',root/'state','--library-dir',root/'library','--keep-debug'])
        assert built['status']=='ready' and len(built['entities'])==1
        output=Path(built['output']);summary=read_json(output/'summary.json');name=built['entities'][0]['name']
        entity=read_json(output/'records'/(name+'.json'))
        assert summary['model_calls']==read_json(root/'state/runs'/built['build_id']/'agent-state.json')['receipts']
        assert len(summary['model_calls'])<=config['limits']['model_calls']
        call('layout-check',['check',output,'--config',config_path])
        qualified=call('qualification',['library',root/'library','--name',name])
        assert qualified['current_qualification']['accepted']
        receipt=read_json(output/entity['runtime']['path']/'receipt.json');report=read_json(output/entity['runtime']['path']/'execution/report.json')
        assert report['acceptance']['complete'] and all(c['status']=='passed' for c in report['cases'])
        assert file_digest(config_path)==config_sha and all(manifest(path)==files for path,files in sources.items())
        write_json(root/'results.json',{'at':now(),'passed':True,'new_generation_batches':1,'new_skills':1,'build_id':built['build_id'],
            'name':name,'model_admissions':len(summary['model_calls']),'model_phases':[c.get('phase') for c in summary['model_calls']],
            'cases':len(report['cases']),'build_calls':receipt.get('build_calls'),'accepted':True,'source_and_config_unchanged':True,
            'cache_scope':'fresh shared registries; existing daemon images and BuildKit cache retained, not a cold-cache measurement',
            'operations':operations})
    except BaseException as exc:
        write_json(root/'results.json',{'at':now(),'passed':False,'reason':redact(str(exc)),
            'operations':operations,'resume_or_restart':False,'source_and_config_unchanged':file_digest(config_path)==config_sha and all(manifest(path)==files for path,files in sources.items())})
        raise


if __name__=='__main__':main()
