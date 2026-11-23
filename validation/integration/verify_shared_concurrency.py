"""Real shared-stage contention: no models, network downloads or chemistry."""
import concurrent.futures
import json
from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
from creation_pipeline.records import write_json
from creation_pipeline.runtime.local import LocalExecutor,process
from creation_pipeline.runtime.preparation import render
from creation_pipeline.runtime.shared_environment import resolve,inheritance_matches

root=Path(sys.argv[1])
if root.exists():
    raise ValueError('Fresh evidence directory required')
root.mkdir(parents=True)
executor=LocalExecutor()
host=executor.host()
assert host['status']=='available'
pin=executor._local_base_image('python:3.11-slim-bookworm',30)
assert pin
commands=[]
guard=threading.Lock()
building=threading.Event()
release_builder=threading.Event()
contending=threading.Event()
raw_open=Path.open

def observed_open(path,mode='r',*args,**kwargs):
    try:
        return raw_open(path,mode,*args,**kwargs)
    except FileExistsError:
        if mode=='x' and path.parent==root/'registry' and path.suffix=='.lock':
            contending.set()
        raise
def observed(args,timeout):
    if args[:2]==['docker','build'] and '--label' in args:
        building.set()
        assert release_builder.wait(30),'Builder was not released by contention check'
    result=process(args,timeout)
    with guard:
        commands.append({'argv':args,'result':result})
        write_json(root/'commands.json',commands)
    return result

def prepare(name):
    source=root/name/'source'
    (source/'package').mkdir(parents=True)
    (source/'package/main.py').write_text('import pathlib; print('+repr(name)+',pathlib.Path("/opt/shared-concurrency.txt").read_text())\n',encoding='utf-8')
    plan={'source_files':['package/main.py'],'generated_files':[],
          'base_image':'python:3.11-slim-bookworm','platform':'linux/amd64','environment':[],
          'build_layout':{'dependency_files':[],'prefix_steps':1},
          'steps':[{'command':'''python -c "import pathlib; pathlib.Path('/opt/shared-concurrency.txt').write_text('shared-stage-concurrency-v2')"'''}],
          'entrypoint':['python','/opt/skill/package/main.py']}
    materials=root/name/'materials'
    render(source,materials/'context',plan,[],pin)
    attempt=root/name/'attempt'
    attempt.mkdir()
    return materials,attempt

first=prepare('first')
contender=prepare('contender')
def resolve_one(pair):
    return resolve(pair[0],root/'registry',host,observed,time.monotonic()+180,pair[1])

with patch.object(Path,'open',new=observed_open), concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    future=pool.submit(resolve_one,first)
    try:
        assert building.wait(30),'First environment build did not start'
        waiting=pool.submit(resolve_one,contender)
        assert contending.wait(30),'Second request did not encounter the held file lock'
        assert not waiting.done(),'Contender failed or consumed a partial entry'
        assert not list((root/'registry').glob('*.json'))
        assert len(list((root/'registry').glob('*.lock')))==1
    finally:
        release_builder.set()
    context_a,shared_a,_=future.result(timeout=180)
    context_b,shared_b,_=waiting.result(timeout=180)
assert (shared_a['status'],shared_b['status'])==('built','hit')
assert not shared_a['waited_for_builder'] and shared_b['waited_for_builder']
assert shared_a['image_id']==shared_b['image_id']
assert not list((root/'registry').glob('*.lock'))
assert len(list((root/'registry').glob('*.json')))==1
outputs=[]
for pair,context,shared,name in [(first,context_a,shared_a,'first'),(contender,context_b,shared_b,'contender')]:
    iid=pair[1]/'image.id'
    built=observed(['docker','build','--platform','linux/amd64','--iidfile',str(iid),str(context)],180)
    assert built['exit_code']==0
    image=iid.read_text().strip()
    details=observed(['docker','image','inspect',image],30)
    assert details['exit_code']==0 and inheritance_matches(shared,json.loads(details['stdout'])[0])
    result=observed(['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL',
                     '--security-opt','no-new-privileges','--user','10001:10001',image],30)
    assert result['exit_code']==0 and result['stdout'].strip()==name+' shared-stage-concurrency-v2'
    outputs.append({'tool':name,'image_id':image,'stdout':result['stdout']})
builds=sum(c['argv'][:2]==['docker','build'] and '--label' in c['argv'] for c in commands)
assert builds==1
write_json(root/'result.json',{'passed':True,'scope':'real concurrent Docker infrastructure; no model or chemistry execution',
    'environment_builds':builds,'thin_tool_builds':2,'contender':'waited_then_hit_without_resubmission',
    'observations':[shared_a,shared_b],'outputs':outputs})
print(json.dumps({'passed':True,'environment_builds':builds,'thin_tool_builds':2,'evidence':str(root/'result.json')}))
