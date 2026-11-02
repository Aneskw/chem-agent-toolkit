"""Export candidate source into a credential-free Windows operational workspace.

No model calls, model probes, images or library imports. Explicit bootstrap installs
only host validators into the isolated checkout's venv. Failed rounds are retained.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO))
from creation_pipeline.records import read_json,write_json,file_digest,redact,now,has_link,safe_relative


def main():
    root=Path(sys.argv[1]).resolve();root.mkdir(exist_ok=False)
    files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=REPO).decode().split('\0')
    source=root/'source';source.mkdir();inputs={}
    for name in sorted(set(files)-{''}):
        original=safe_relative(REPO,name)
        if not original.is_file():continue
        assert not has_link(original) and name!='.env' and '.pipeline' not in Path(name).parts
        target=safe_relative(source,name);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
        inputs[name]=file_digest(original)
    write_json(root/'source-inputs.json',inputs)
    assert not (source/'.env').exists() and not (source/'.pipeline').exists() and not (source/'.venv').exists()
    checkout=root/'Windows user checkout with spaces';shutil.copytree(source,checkout)
    env=os.environ.copy()
    for key in list(env):
        if key.startswith(('DEEPSEEK_','OPENAI_','CHEM_AGENT_SHARED_')) or key in {'CODEX_ACCESS_TOKEN','CODEX_API_KEY','PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'}:env.pop(key,None)
    env.update(CODEX_HOME=str(root/'empty owner home'),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1')
    Path(env['CODEX_HOME']).mkdir()
    # Remove installed client directories during engineering tests; no auth/client is required.
    entries=[]
    for entry in env.get('PATH','').split(os.pathsep):
        path=Path(entry)
        if any((path/('codex'+suffix)).is_file() for suffix in ('','.exe','.EXE','.cmd','.CMD','.bat')):continue
        entries.append(entry)
    env['PATH']=os.pathsep.join(entries)
    operations=[]
    def call(label,args,expected=0,settings=None):
        dest=root/'operations'/label;dest.mkdir(parents=True)
        start=time.monotonic();p=subprocess.run(list(map(str,args)),cwd=checkout,env=settings or env,
            capture_output=True,encoding='utf-8',errors='replace')
        (dest/'stdout.log').write_text(redact(p.stdout),encoding='utf-8');(dest/'stderr.log').write_text(redact(p.stderr),encoding='utf-8')
        record={'label':label,'command':list(map(str,args)),'exit_code':p.returncode,'seconds':time.monotonic()-start}
        write_json(dest/'result.json',record);operations.append(record);print(label,p.returncode,flush=True)
        assert p.returncode==expected,label
        return p.stdout
    call('bootstrap',[sys.executable,'scripts/bootstrap.py','--yaml'])
    python=checkout/'.venv/Scripts/python.exe'
    call('bootstrap-reuse',[python,'scripts/bootstrap.py','--yaml'])
    facts=call('isolation',[python,'-c','import sys,json,shutil,importlib.metadata,creation_pipeline; print(json.dumps({"prefix":sys.prefix,"base_prefix":sys.base_prefix,"module":creation_pipeline.__file__,"codex":shutil.which("codex"),"jsonschema":importlib.metadata.version("jsonschema")}))'])
    facts=__import__('json').loads(facts);assert Path(facts['prefix'])==checkout/'.venv' and facts['codex'] is None and Path(facts['module']).is_relative_to(checkout)
    write_json(root/'isolation.json',facts)
    call('initialize',[python,'-m','creation_pipeline','init','--model','account-model-placeholder','--output','.pipeline/configs/descriptor.json'])
    config=read_json(checkout/'.pipeline/configs/descriptor.json')
    assert not Path(config['sources'][0]['path']).is_absolute()
    assert (checkout/'.pipeline/configs'/config['sources'][0]['path']).resolve().is_relative_to(checkout)
    call('preflight',[python,'-m','creation_pipeline','build','.pipeline/configs/descriptor.json','--preflight'])
    negative=call('missing-client',[python,'-m','creation_pipeline','doctor','.pipeline/configs/descriptor.json','--offline'],1)
    assert 'model_client_unavailable' in negative
    call('unittest',[python,'-m','unittest','discover','-s','tests','-q'])
    for label,argv in [('prompt-contract',['validation/deepseek-api/verify_prompt_contract.py']),
                       ('acceptance-prompt',['validation/deepseek-api/verify_acceptance_prompt.py','check']),
                       ('planner',['validation/deepseek-api/verify_planner.py','check']),
                       ('platform-contract',['validation/deepseek-api/verify_skillnet_contract.py'])]:call(label,[python,*argv])
    # Separately observe official npm client capabilities with an empty CODEX_HOME.
    client=Path(sys.argv[2]).resolve();client_env=dict(env,PATH=str(client)+os.pathsep+env['PATH'])
    positive=call('stable-client-doctor',[python,'-m','creation_pipeline','doctor','.pipeline/configs/descriptor.json'],settings=client_env)
    answer=__import__('json').loads(positive);assert answer['status']=='ready' and answer['client_compatibility']['status']=='compatible'
    assert answer['client_compatibility']['authentication']=='not_checked'
    assert not (checkout/'.env').exists() and not (checkout/'.pipeline/shared-tools').exists() and not (checkout/'.pipeline/library').exists()
    assert all(file_digest(REPO/name)==sha for name,sha in inputs.items())
    write_json(root/'results.json',{'at':now(),'passed':True,'models':0,'builds':0,'new_business_executions':0,
        'source_export':'candidate tracked and untracked nonignored source; no operational data or credentials',
        'isolation':facts,'stable_client_version':answer['client_compatibility']['version'],'operations':operations})
    print({'passed':True,'models':0,'builds':0})


if __name__=='__main__':main()
