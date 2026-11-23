"""Two real Python/Docker processes in different checkouts, one host registry."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

parser=argparse.ArgumentParser()
parser.add_argument('evidence',type=Path)
mode=parser.add_mutually_exclusive_group(required=True)
mode.add_argument('--checkouts',nargs=2,type=Path)
mode.add_argument('--worker',type=Path,help=argparse.SUPPRESS)
parser.add_argument('--role',choices=('one','two'))
parser.add_argument('--concurrent',action='store_true',help='Force a real same-key lock collision between workers')
args=parser.parse_args()
if args.worker and args.role is None:
    parser.error('Internal worker mode requires --role')
root=args.evidence.resolve()
checkout=args.worker.resolve() if args.worker else args.checkouts[0].resolve()
sys.path.insert(0,str(checkout))
from creation_pipeline.records import write_json,read_json

def wait_for(path,timeout=30):
    deadline=time.monotonic()+timeout
    while not path.is_file():
        if time.monotonic()>=deadline:
            raise TimeoutError('Test coordination deadline: '+str(path))
        time.sleep(.05)

if args.worker:
    from creation_pipeline.paths import ROOT
    from creation_pipeline.runtime import local
    from creation_pipeline.runtime.preparation import render
    from creation_pipeline.runtime.shared_environment import resolve,registry_root,inheritance_matches,CACHE_ROOT_ENV
    assert ROOT.resolve()==checkout
    common=root/'registry'
    assert registry_root()==common
    role=args.role
    source=root/role/'source'
    if source.exists():
        raise ValueError('Worker evidence is not fresh')
    (source/'package').mkdir(parents=True)
    (source/'package/main.py').write_text('import json,pathlib; print(json.dumps({"tool":'+repr(role)+',"shared":pathlib.Path("/opt/cross-checkout-registry.txt").read_text()}))\n',encoding='utf-8')
    calls=[]
    raw_process=local.process
    raw_open=Path.open
    def observed_open(path,mode='r',*positional,**kwargs):
        try:
            return raw_open(path,mode,*positional,**kwargs)
        except FileExistsError:
            if args.concurrent and role=='two' and mode=='x' and path.parent==common and path.suffix=='.lock':
                write_json(root/'contending.json',{'pid':os.getpid()})
            raise
    def observed(command,timeout):
        if args.concurrent and role=='one' and command[:2]==['docker','build'] and '--label' in command:
            write_json(root/'building.json',{'pid':os.getpid()})
            wait_for(root/'release-builder.json')
        result=raw_process(command,timeout)
        calls.append({'command':command,'result':result})
        write_json(root/role/'commands.json',calls)
        return result
    with patch('creation_pipeline.runtime.model_call.call',side_effect=AssertionError('No models')), \
         patch('creation_pipeline.agent.backend.NativeSession.stage',side_effect=AssertionError('No native model stages')), \
         patch.object(Path,'open',new=observed_open), \
         patch.object(local,'process',side_effect=observed):
        executor=local.LocalExecutor()
        host=executor.host(); assert host['status']=='available'
        pin=executor._local_base_image('python:3.11-slim-bookworm',30); assert pin
        plan={'source_files':['package/main.py'],'generated_files':[],
              'base_image':'python:3.11-slim-bookworm','platform':'linux/amd64','environment':[],
              'build_layout':{'dependency_files':[],'prefix_steps':1},
              'steps':[{'command':'''python -c "from pathlib import Path; Path('/opt/cross-checkout-registry.txt').write_text('same-env-v1')"'''}],
              'entrypoint':['python','/opt/skill/package/main.py']}
        materials=root/role/'materials'
        render(source,materials/'context',plan,[],pin)
        assert str(common) not in (materials/'shared-environment.json').read_text(encoding='utf-8')
        attempt=root/role/'attempt'; attempt.mkdir()
        context,shared,_=resolve(materials,None,host,observed,time.monotonic()+180,attempt)
        assert Path(shared['registry'])==common
        iid=attempt/'image.id'
        built=observed(['docker','build','--platform','linux/amd64','--iidfile',str(iid),str(context)],180)
        assert built['exit_code']==0
        image=iid.read_text().strip()
        detail=observed(['docker','image','inspect',image],30)
        assert detail['exit_code']==0 and inheritance_matches(shared,json.loads(detail['stdout'])[0])
        result=observed(['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL',
                         '--security-opt','no-new-privileges','--user','10001:10001',image],30)
        assert result['exit_code']==0 and json.loads(result['stdout'])=={'tool':role,'shared':'same-env-v1'}
        record={'checkout':str(checkout),'cwd':str(Path.cwd()),'pid':os.getpid(),'shared':shared,
                'tool_image':image,'output':json.loads(result['stdout']),
                'environment_build_invocations':sum(c['command'][:2]==['docker','build']
                    and any('chem.shared.recipe=' in item for item in c['command']) for c in calls)}
        write_json(root/role/'result.json',record)
        print(json.dumps(record))
    sys.exit(0)

if not args.checkouts or len({p.resolve() for p in args.checkouts})!=2:
    raise ValueError('Provide two distinct pipeline checkouts')
if root.exists():
    raise ValueError('Fresh evidence root required')
root.mkdir(parents=True)
allowed={'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','TMPDIR','HOME','USERPROFILE','APPDATA','LOCALAPPDATA',
         'PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432','COMSPEC','LANG','LC_ALL',
         'DOCKER_HOST','DOCKER_CONTEXT','DOCKER_CONFIG','DOCKER_CERT_PATH','DOCKER_TLS_VERIFY'}
environment={k:v for k,v in os.environ.items() if k.upper() in allowed}
environment.update(CHEM_AGENT_SHARED_ENVIRONMENTS=str(root/'registry'),PYTHONIOENCODING='utf-8',
                   PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
workers=[]
captured={}
try:
    records=[]
    for role,location in zip(('one','two'),args.checkouts):
        command=[sys.executable,'-u',str(Path(__file__).resolve()),str(root),'--worker',str(location.resolve()),'--role',role]
        if args.concurrent:
            command.append('--concurrent')
        worker=subprocess.Popen(command,cwd=location,env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                text=True,encoding='utf-8')
        workers.append((role,command,worker))
        if args.concurrent:
            if role=='one':
                wait_for(root/'building.json')
                continue
            wait_for(root/'contending.json')
            assert not list((root/'registry').glob('*.json'))
            assert len(list((root/'registry').glob('*.lock')))==1
            assert all(w.poll() is None for _,_,w in workers)
            write_json(root/'release-builder.json',{'contender_observed':True})
        else:
            captured[role]=worker.communicate(timeout=900)
    for role,command,worker in workers:
        stdout,stderr=captured[role] if role in captured else worker.communicate(timeout=900)
        write_json(root/(role+'-process.json'),{'command':command,'exit_code':worker.returncode,
                                               'stdout':stdout,'stderr':stderr})
        if worker.returncode:
            raise ValueError('Worker failed: '+role+'; see its retained process record')
        records.append(read_json(root/role/'result.json'))
    assert [r['shared']['status'] for r in records]==['built','hit']
    assert records[0]['shared']['image_id']==records[1]['shared']['image_id']
    assert records[0]['shared']['recipe_key']==records[1]['shared']['recipe_key']
    assert records[0]['tool_image']!=records[1]['tool_image']
    assert records[0]['pid']!=records[1]['pid'] and records[0]['cwd']!=records[1]['cwd']
    assert sum(r['environment_build_invocations'] for r in records)==1
    if args.concurrent:
        assert not records[0]['shared']['waited_for_builder'] and records[1]['shared']['waited_for_builder']
    assert len(list((root/'registry').glob('*.json')))==1 and not list((root/'registry').glob('*.lock'))
    result={'passed':True,'scope':'two-checkout, two-process Docker infrastructure; no chemistry or model calls',
            'environment_build_invocations':1,'thin_tool_build_invocations':2,
            'different_checkouts':True,'different_processes':True,'concurrent_wait_and_reuse':args.concurrent,
            'model_calls':0,'records':records}
    write_json(root/'result.json',result)
    print({k:v for k,v in result.items() if k!='records'})
except BaseException as exc:
    write_json(root/'failure.json',{'type':type(exc).__name__,'error':str(exc),'scope':'failed fresh trial; no restart'})
    raise
finally:
    for role,command,worker in workers:
        if not (root/(role+'-process.json')).exists():
            if worker.poll() is None:
                worker.kill()
            stdout,stderr=worker.communicate(timeout=30)
            write_json(root/(role+'-aborted-process.json'),{'command':command,'exit_code':worker.returncode,
                                                         'stdout':stdout,'stderr':stderr})
