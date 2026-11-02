"""Deep zero-inference startup diagnostics; never invokes exec without --help."""
import re
import shutil
import subprocess
import time

from creation_pipeline.agent.command import codex_command
from creation_pipeline.models import load_config,runtime_spec
from creation_pipeline.readiness import check,configuration_error
from creation_pipeline.records import redact,sanitized


def client_capabilities(*, native=True, runtime=True):
    command=codex_command()
    probes=[];missing=[];outputs={}
    for label,args in [('version',['--version']),('exec',['exec','--help']),('resume',['exec','resume','--help']),('features',['features','list'])]:
        start=time.monotonic()
        try:
            p=subprocess.run(command+args,capture_output=True,encoding='utf-8',errors='replace',timeout=15)
            probes.append({'probe':label,'argv':args,'exit_code':p.returncode,'seconds':time.monotonic()-start})
            outputs[label]=p.stdout
            if p.returncode:missing.append({'field':label,'expected':'successful local capability query','actual':p.returncode,'reason':redact(p.stderr)[:1000]})
        except (OSError,subprocess.TimeoutExpired) as exc:
            probes.append({'probe':label,'argv':args,'exit_code':None,'seconds':time.monotonic()-start})
            outputs[label]=''
            missing.append({'field':label,'expected':'local query completes within 15 seconds','actual':type(exc).__name__,'reason':redact(str(exc))})
    flags=set(re.findall(r'--[a-z][a-z0-9-]*',outputs['exec']))
    required={'--json','--output-schema','--skip-git-repo-check','--sandbox','--enable','--disable','--config','--model'}
    if native:required.add('--ignore-user-config')
    if runtime:required.add('--ephemeral')
    for flag in sorted(required-flags):missing.append({'field':'exec.'+flag,'expected':'supported flag','actual':'not advertised'})
    if native:
        resume=set(re.findall(r'--[a-z][a-z0-9-]*',outputs['resume']))
        for flag in sorted({'--json','--output-schema','--ignore-user-config','--skip-git-repo-check','--enable','--disable','--config','--model'}-resume):
            missing.append({'field':'resume.'+flag,'expected':'supported flag','actual':'not advertised'})
    observed={line.split()[0] for line in outputs['features'].splitlines() if line.split()}
    features={'skip_host_skill_discovery','apps','plugins','multi_agent'}
    if runtime:features|={'hooks','shell_tool'}
    import os
    if runtime and os.name=='nt':features.add('respect_system_proxy')
    for feature in sorted(features-observed):missing.append({'field':'features.'+feature,'expected':'recognized feature','actual':'not listed'})
    # Never save raw help, settings, auth output or feature tables.
    version=redact(outputs['version'].strip().splitlines()[0])[:128] if outputs['version'].strip() else None
    return {'status':'compatible' if not missing else 'incompatible','command':command,'version':version,
            'probes':probes,'missing':missing,'model_calls':0,'authentication':'not_checked','model_entitlement':'not_checked',
            'scope':'advertised CLI flags/features only; no inference or account access proof'}


def from_config(path,offline=False):
    try:config=load_config(path)
    except (ValueError,OSError,KeyError) as exc:return configuration_error(path,'build',exc)
    result=check(config,offline=offline)
    git=shutil.which('git')
    git_check={'object':'host.git','path':'git','expected':'Git executable on PATH','actual':git or 'missing',
               'status':'passed' if git else 'blocked','code':None if git else 'host_git_missing'}
    result.setdefault('checks',[]).append(git_check)
    if not git:result['gaps'].append(git_check)
    native=config['model']['backend']=='codex_cli'
    specs=[runtime_spec(config)]+[runtime_spec(config,n) for n in config['runtime']]
    known=any(s.get('shared_tool') or s.get('plan') for s in specs) or any(
        isinstance(r,dict) and r.get('status')=='required' for r in config.get('runtime_requirements',{}).values())
    runtime=known and not config.get('draft_only') and any(s.get('options',{}).get('backend','codex_cli')=='codex_cli' for s in specs)
    if native or runtime:
        try:
            result['client_compatibility']=client_capabilities(native=native,runtime=runtime)
            if result['client_compatibility']['status']!='compatible':
                result['gaps'].append({'object':'model.client','path':'codex','expected':'all pipeline-required flags/features',
                    'actual':result['client_compatibility']['missing'],'status':'blocked','code':'model_client_incompatible',
                    'reason':'Install a compatible client; isolation/qualification is not weakened as fallback'})
        except (ValueError,OSError) as exc:
            result['gaps'].append({'object':'model.client','path':'codex','expected':'resolvable compatible executable',
                'actual':redact(str(exc)),'status':'blocked','code':'model_client_unavailable'})
    if result['gaps']:result['status']='blocked'
    result['scope']='Zero-inference prerequisites and advertised client capabilities; not authentication, entitlement or acceptance'
    return sanitized(result)
