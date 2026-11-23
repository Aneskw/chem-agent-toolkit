"""Real, network-free infrastructure test; no model or chemistry execution."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from creation_pipeline.records import write_json
from creation_pipeline.runtime.local import LocalExecutor, process
from creation_pipeline.runtime.preparation import render
from creation_pipeline.runtime.shared_environment import resolve, inheritance_matches


def main(root):
    if root.exists():
        raise ValueError('Use a fresh infrastructure evidence directory')
    root.mkdir(parents=True)
    executor=LocalExecutor()
    host=executor.host()
    if host['status'] != 'available':
        raise ValueError('Docker unavailable')
    pin=executor._local_base_image('python:3.11-slim-bookworm',30)
    if not pin:
        raise ValueError('Pinned cached base unavailable')
    commands=[]
    def observed(args,timeout):
        result=process(args,timeout)
        commands.append({'argv':args,'result':result})
        write_json(root/'commands.json',commands)
        return result
    observations=[]
    for name in ('one','two'):
        source=root/name/'source'
        (source/'package').mkdir(parents=True)
        (source/'package/main.py').write_text('import json,pathlib; print(json.dumps({"tool":'+repr(name)+',"environment":pathlib.Path("/opt/environment-version.txt").read_text().strip()}))\n',encoding='utf-8')
        plan={'source_files':['package/main.py'],'generated_files':[], 'base_image':'python:3.11-slim-bookworm',
              'platform':'linux/amd64','environment':[], 'build_layout':{'dependency_files':[],'prefix_steps':1},
              'steps':[{'command':'python -m pip --version > /opt/environment-version.txt'}],
              'entrypoint':['python','/opt/skill/package/main.py']}
        materials=root/name/'materials'
        render(source,materials/'context',plan,[],pin)
        attempt=root/name/'attempt'; attempt.mkdir()
        context,shared,logs=resolve(materials,root/'registry',host,observed,time.monotonic()+180,attempt)
        iid=attempt/'image.id'
        built=observed(['docker','build','--platform','linux/amd64','--iidfile',str(iid),str(context)],180)
        if built['exit_code'] != 0:
            raise ValueError('Thin tool build failed')
        image=iid.read_text().strip()
        inspection=observed(['docker','image','inspect',image],30)
        assert inspection['exit_code']==0 and inheritance_matches(shared,json.loads(inspection['stdout'])[0])
        result=observed(['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL',
                         '--security-opt','no-new-privileges','--user','10001:10001',image],30)
        output=json.loads(result['stdout'])
        assert result['exit_code']==0 and output['tool']==name and output['environment'].startswith('pip ')
        observations.append({'tool':name,'shared':shared,'tool_image':image,'output':output})
    assert [o['shared']['status'] for o in observations]==['built','hit']
    assert observations[0]['shared']['image_id']==observations[1]['shared']['image_id']
    assert observations[0]['tool_image']!=observations[1]['tool_image']
    environment_builds=sum(c['argv'][:2]==['docker','build'] and '--label' in c['argv'] for c in commands)
    assert environment_builds==1
    write_json(root/'result.json',{'passed':True,'scope':'infrastructure only; no model/chemistry calls',
        'environment_builds':environment_builds,'thin_tool_builds':2,'observations':observations,'commands':commands})
    print(json.dumps({'passed':True,'environment_builds':1,'thin_tool_builds':2,'evidence':str(root/'result.json')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('evidence',type=Path)
    main(p.parse_args().evidence)
