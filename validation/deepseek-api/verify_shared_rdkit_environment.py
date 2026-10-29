"""Real shared-environment compatibility trial, not a new model acceptance batch."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
from creation_pipeline.records import file_digest, write_json
from creation_pipeline.runtime.local import LocalExecutor, process
from creation_pipeline.runtime.preparation import render
from creation_pipeline.runtime.shared_environment import resolve


def main(root):
    if root.exists():
        raise ValueError('Fresh evidence directory required')
    root.mkdir(parents=True)
    sources=REPO.parent/'chem-agent-toolkit_newpipeline/tools-skills/rdkit'
    host=LocalExecutor().host()
    assert host['status']=='available'
    pin=LocalExecutor()._local_base_image('python:3.11-slim-bookworm',30)
    assert pin
    commands=[]; observations=[]
    def run(args,timeout):
        out=process(args,timeout); commands.append({'argv':args,'result':out})
        write_json(root/'commands.json',commands)
        return out
    for skill,script in [('chem-rdkit-descriptors','calc_descriptors.py'),
                        ('chem-reaction-atommap-audit','audit_atom_maps.py')]:
        source=root/skill/'source'; (source/'package/scripts').mkdir(parents=True)
        original=sources/skill/'scripts'/script
        delivered=source/'package/scripts'/script
        shutil.copy2(original,delivered)
        (source/'package/resources').mkdir()
        shutil.copy2(sources/'chem-rdkit-descriptors/requirements.txt',source/'package/resources/requirements.txt')
        plan={'source_files':['package/scripts/'+script,'package/resources/requirements.txt'],
              'generated_files':[],'platform':'linux/amd64','base_image':'python:3.11-slim-bookworm',
              'environment':[], 'build_layout':{'dependency_files':['package/resources/requirements.txt'],'prefix_steps':1},
              'steps':[{'command':'python -m pip install --no-cache-dir --only-binary=:all: -r /opt/skill/package/resources/requirements.txt && python -m pip check'}],
              'entrypoint':['python','/opt/skill/package/scripts/'+script]}
        materials=root/skill/'materials'; render(source,materials/'context',plan,[],pin)
        attempt=root/skill/'attempt'; attempt.mkdir()
        context,shared,_=resolve(materials,root/'registry',host,run,time.monotonic()+600,attempt)
        iid=attempt/'image.id'
        built=run(['docker','build','--platform','linux/amd64','--iidfile',str(iid),str(context)],300)
        assert built['exit_code']==0, built['stderr'][-500:]
        image=iid.read_text().strip()
        calls=([(['--smiles','CCO'],0),(['--smiles','not-a-smiles'],2)] if script=='calc_descriptors.py' else
               [(['--reaction','[CH3:1][CH2:2][Br:3]>>[CH3:1][CH2:2]'],0),
                (['--reaction','[CH3:1][CH2:1]>>[CH3:1]'],2)])
        cases=[]
        for args,expected in calls:
            result=run(['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL',
                        '--security-opt','no-new-privileges','--user','10001:10001',image]+args,30)
            value=json.loads(result['stdout'])
            assert result['exit_code']==expected
            if expected==2:
                assert value['ok'] is False
            elif script=='calc_descriptors.py':
                assert value['ok'] and value['descriptors']['molecular_weight']==46.069
                assert value['descriptors']['h_bond_donors']==value['descriptors']['h_bond_acceptors']==1
            else:
                assert value['ok'] and value['reactant_only_maps']==[3]
            cases.append({'args':args,'exit_code':result['exit_code'],'value':value,'passed':True})
        observations.append({'skill':skill,'original_sha256':file_digest(original),'delivered_sha256':file_digest(delivered),
                             'shared':shared,'tool_image':image,'cases':cases})
    assert [o['shared']['status'] for o in observations]==['built','hit']
    assert len({o['shared']['image_id'] for o in observations})==1
    count=sum(c['argv'][:2]==['docker','build'] and '--label' in c['argv'] for c in commands)
    assert count==1
    result={'passed':True,'model_calls':0,'scope':'Original-tool compatibility on a shared pinned RDKit environment; not full skill-generation acceptance',
            'environment_builds':count,'thin_tool_builds':2,'passed_business_cases':4,'observations':observations}
    write_json(root/'result.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='observations'}))


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('evidence',type=Path); main(p.parse_args().evidence)
