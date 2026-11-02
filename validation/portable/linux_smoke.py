"""Run in an ephemeral Linux container without Docker socket or model credentials."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

work=Path('/workspace');shutil.copytree('/input',work,dirs_exist_ok=True)
sys.path.insert(0,str(work))
from creation_pipeline.records import write_json,redact,now

root=Path('/evidence');operations=[]
env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',CODEX_HOME='/empty-owner-home')
Path(env['CODEX_HOME']).mkdir()


def call(label,args,expected=0):
    start=time.monotonic();p=subprocess.run(list(map(str,args)),cwd=work,env=env,capture_output=True,encoding='utf-8',errors='replace')
    (root/(label+'.log')).write_text(redact(p.stdout+p.stderr),encoding='utf-8')
    operations.append({'label':label,'command':list(map(str,args)),'exit_code':p.returncode,'seconds':time.monotonic()-start})
    write_json(root/'progress.json',{'operations':operations});print(label,p.returncode,flush=True)
    if p.returncode!=expected:raise ValueError('Linux check failed: '+label)
    return p.stdout


# The slim base intentionally lacks Git; install it only in this disposable
# container, never on the host or through pipeline readiness.
call('system-package-index',['apt-get','update'])
call('system-git',['apt-get','install','-y','--no-install-recommends','git'])
call('git-version',['git','--version'])
call('bootstrap',[sys.executable,'scripts/bootstrap.py','--yaml'])
python=work/'.venv/bin/python'
call('bootstrap-reuse',[python,'scripts/bootstrap.py','--yaml'])
facts=json.loads(call('isolation',[python,'-c','import sys,shutil,json,creation_pipeline; print(json.dumps({"prefix":sys.prefix,"base_prefix":sys.base_prefix,"codex":shutil.which("codex"),"module":creation_pipeline.__file__}))']))
assert facts['prefix']!=facts['base_prefix'] and facts['codex'] is None and facts['module'].startswith('/workspace/')
call('initialize',[python,'-m','creation_pipeline','init','--model','account-model-placeholder','--output','.pipeline/configs/descriptor.json'])
call('preflight',[python,'-m','creation_pipeline','build','.pipeline/configs/descriptor.json','--preflight'])
negative=call('missing-client',[python,'-m','creation_pipeline','doctor','.pipeline/configs/descriptor.json','--offline'],1)
assert 'model_client_unavailable' in negative
call('unittest',[python,'-m','unittest','discover','-s','tests','-q'])
for label,argv in [('prompt-contract',['validation/deepseek-api/verify_prompt_contract.py']),
                   ('acceptance-prompt',['validation/deepseek-api/verify_acceptance_prompt.py','check']),
                   ('planner',['validation/deepseek-api/verify_planner.py','check']),
                   ('platform-contract',['validation/deepseek-api/verify_skillnet_contract.py'])]:call(label,[python,*argv])
# Infrastructure workload only: fresh container dependencies, not a Skill qualification.
call('chemistry-dependencies',[python,'-m','pip','install','--no-cache-dir','-r','validation/sibling-json/source/requirements.txt'])
script='validation/sibling-json/source/scripts/screen.py'
for label,smiles,weight,selected in [('ethanol','CCO',46.069,True),('phenol','c1ccccc1O',94.113,False)]:
    value=json.loads(call(label,[python,script,'--smiles',smiles]));assert value['descriptors']['molecular_weight']==weight and value['selected'] is selected
for label,smiles in [('invalid','not-a-smiles'),('empty',''),('whitespace','   ')]:
    value=json.loads(call(label,[python,script,'--smiles',smiles],2));assert value['ok'] is False
write_json(root/'results.json',{'at':now(),'passed':True,'models':0,'pipeline_generation_batches':0,'qualification':'not_granted',
    'scope':'Linux clean Python venv/bootstrap, offline suite and source workload infrastructure; no Docker socket or existing tool images/registries',
    'isolation':facts,'workload_cases':5,'operations':operations})
