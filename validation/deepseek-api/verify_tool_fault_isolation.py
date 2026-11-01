"""Real Docker fault trials on uniquely owned stdlib ToolArtifacts; zero models.

Fault injection is explicit: paused atomic rename, Python KeyboardInterrupt at
an active command, and deliberately failing/sleeping build steps. Never edits a
frozen contract, waives qualification, or removes pre-existing images/caches.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from creation_pipeline.artifacts.evidence import seal
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.contracts import finalize, qualify
from creation_pipeline.records import read_json, write_json, sanitized, redact
from creation_pipeline.runtime import local, shared_tool as st
from creation_pipeline.runtime.preparation import prepare
from creation_pipeline.runtime.service import execute_prepared, resume_build
from creation_pipeline.runtime.installation import install_envelope
from creation_pipeline.runtime.recovery import import_candidate, inspect_candidate
from creation_pipeline.artifacts import store
from tests.pipeline.test_runtime_build import TEXT, QUOTE, plan
from tests.pipeline.test_shared_tool import declaration


def save(path, value):
    write_json(path, sanitized(value))


def wait_for(predicate, seconds=90):
    end = time.monotonic()+seconds
    while not predicate():
        if time.monotonic() >= end:
            raise ValueError('Experiment synchronization deadline exceeded')
        time.sleep(.1)


def no_models():
    from contextlib import ExitStack
    stack = ExitStack()
    for target in ('creation_pipeline.runtime.model_call.call', 'creation_pipeline.agent.backend.NativeSession.stage'):
        stack.enter_context(patch(target, side_effect=AssertionError('No model calls allowed')))
    return stack


def execution_command(command, image):
    # The current LocalExecutor invokes Docker directly, not an outer runner.py.
    return command[:2]==['docker','run'] and image in command and '--entrypoint' not in command


def worker(root, directory, mode):
    from contextlib import ExitStack
    from creation_pipeline.runtime import runner
    record = read_json(directory/'record.json') if mode!='interrupt-execution' else None
    executor = local.LocalExecutor(deadline=time.monotonic()+4 if mode=='wait-timeout' else None)
    original_replace = Path.replace
    original_communicate = subprocess.Popen.communicate
    original_process = local.process
    injected = False
    def fault_process(command, timeout):
        if mode in {'build-failure','build-timeout','cancel-build'} and command[:2]==['docker','build']:
            dockerfile=Path(command[-1])/'Dockerfile'
            step=('python -c "raise SystemExit(17)"' if mode=='build-failure' else
                  'python -c "import time; print(\'P1_BUILD_RUNNING\',flush=True); time.sleep(20)"')
            dockerfile.write_text(dockerfile.read_text(encoding='utf-8')+'\nRUN '+step+'\n',encoding='utf-8')
            save(directory/'build-fault-injection.json',{'scope':'attempt-local generated Dockerfile only; frozen inputs unchanged',
                'dockerfile':str(dockerfile),'step':step})
        return original_process(command,timeout)
    def replace(path, target):
        if mode=='publisher' and Path(target).parent == root/'tools':
            save(root/'publication-paused.json', {'temp':str(path),'target':str(target)})
            wait_for(lambda: (root/'release-publication').exists())
        return original_replace(path, target)
    def communicate(proc, *args, **kwargs):
        nonlocal injected
        command = proc.args
        wanted = (mode=='cancel-build' and command[:2]==['docker','build'])
        wanted |= mode=='interrupt-execution' and execution_command(command, read_json(directory/'image.json')['id'])
        if wanted and not injected:
            injected = True
            if mode=='interrupt-execution':
                image = read_json(directory/'image.json')['id']
                observed = []
                def running():
                    p = local.process(['docker','ps','--no-trunc','--filter','ancestor='+image,'--format','{{json .}}'], 10)
                    observed[:] = [json.loads(s) for s in p['stdout'].splitlines() if s]
                    return any('main.py' in c.get('Command','') for c in observed)
                wait_for(running)
                save(directory/'business-running-at-interrupt.json', observed)
            else:
                time.sleep(3)
            raise KeyboardInterrupt('Explicit P1 active-command cancellation')
        return original_communicate(proc, *args, **kwargs)
    try:
        with no_models(), ExitStack() as stack:
            stack.enter_context(patch.object(Path, 'replace', replace))
            stack.enter_context(patch.object(subprocess.Popen, 'communicate', communicate))
            stack.enter_context(patch.object(local,'process',fault_process))
            if mode=='cancel-waiter':
                stack.enter_context(patch.object(st.time, 'sleep', side_effect=KeyboardInterrupt('cancel waiting caller')))
            if mode=='interrupt-execution':
                result = resume_build(directory/'library', 'slow', reuse_image=True)
                raise AssertionError('Expected active execution interruption: '+str(result))
            receipt = execute_prepared(directory, record, executor, persist_record=True)
            accepted, reason = qualify(record['delivery'],runtime_root=directory,runtime_ref=record['runtime'],
                frozen_directory=directory/'frozen',freeze_sha256=record['durable_evidence']['freeze_sha256'])
            save(directory/'result.json',{'accepted':accepted,'reason':reason,'receipt':receipt})
            save(directory/'record.json',record)
    except KeyboardInterrupt as exc:
        save(directory/'interruption.json',{'type':'KeyboardInterrupt','mode':mode,
            'output':getattr(exc,'output',''),'stderr':getattr(exc,'stderr',''),
            'cleanup':getattr(exc,'cleanup',[]),'scope':getattr(exc,'scope',None)})


def main(root):
    root.mkdir(parents=True,exist_ok=False)
    (root/'experiment-source.py').write_text(redact(Path(__file__).read_text(encoding='utf-8')),encoding='utf-8')
    from creation_pipeline.records import file_digest
    save(root/'pipeline-code.json',[{'path':str(p.relative_to(REPO)),'sha256':file_digest(p)}
         for p in sorted((REPO/'creation_pipeline').rglob('*.py'))])
    os.environ['CHEM_AGENT_SHARED_TOOLS']=str(root/'tools')
    os.environ['CHEM_AGENT_SHARED_ENVIRONMENTS']=str(root/'environments')
    executor=local.LocalExecutor(); host=executor.host(); save(root/'host.json',host)
    assert host['status']=='available',host
    pin=executor._local_base_image('python:3.11-slim-bookworm',30); assert pin
    save(root/'base.json',pin)
    before_ids=set(local.process(['docker','image','ls','--no-trunc','--quiet'],30)['stdout'].splitlines())
    save(root/'preexisting-image-ids.json',sorted(before_ids))
    protected=[]
    for label in ('a','b'):
        base=root.parent/'descriptor-layout-cli-20261101-05'/label
        protected.append({'path':str(base),'files':manifest(base)})
        assert inspect_candidate(base/'library','chem-rdkit-descriptors')['qualification']['accepted']
    save(root/'protected-before.json',protected)
    nonce=uuid.uuid4().hex
    def prepared(name, family, step=None, slow=False, seconds=180):
        directory=root/name; package=directory/'package'; source=directory/'source'
        package.mkdir(parents=True); source.mkdir()
        text=TEXT+'\n# Dedicated P1 artifact '+nonce+' '+family+'\n'
        if slow: text=text.replace('print("ok")','import time\ntime.sleep(15)\nprint("ok")')
        for p in (package/'main.py',source/'main.py'): p.write_text(text,encoding='utf-8')
        (package/'SKILL.md').write_text('# '+name+'\nInfrastructure fixture, not native review.\n')
        sources=[{'id':'tool','path':str(source),'inventory':manifest(source),'resolved_ref':'P1-infrastructure-fixture'}]
        record={'name':name,'kind':'skill','status':'ready','files':manifest(package),'plan':{'name':name},
            'checks':[{'name':'content_review','status':'pass','requirement_assessment':'confirmed',
                       'scope':'Deterministic fixture only; no claim of new native Agent review'}]}
        finalize(record,sources,{'status':'required','reason':'Execute actual fixture',
            'citations':[{'source_id':'tool','path':'main.py','quote':QUOTE}]})
        p=plan();p['base_image']=pin['reference']
        if step:p['steps']=[{'command':step,'purpose':'P1 fault injection','evidence':'Explicit isolated experiment step'}]
        with patch.object(executor,'resolve_base_image',return_value=pin):
            materials=prepare(record,package,sources,directory/'work',{'plan':p,'shared_tool':declaration(p),
                'options':{'pin_base_image':True,'build_seconds':seconds}},executor)
        assert record['runtime_preparation']['status']=='prepared',record['runtime_preparation']
        freeze=seal(directory/'frozen',package,record,sources,materials)
        record['durable_evidence']={'path':'frozen','freeze_sha256':freeze}
        save(directory/'record.json',record)
        return directory
    def launch(directory,mode):
        proc=subprocess.Popen([sys.executable,__file__,str(root),'--worker',str(directory),'--mode',mode],
            cwd=REPO,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
        save(directory/('command-'+mode+'.json'),{'pid':proc.pid,'command':proc.args})
        return proc,directory/('worker-'+mode+'.log')
    def finish(child):
        proc,log=child
        output,_=proc.communicate(timeout=180)
        log.write_text(redact(output),encoding='utf-8')
        assert proc.returncode==0,('worker failed',proc.args,proc.returncode)
    def execute(directory):
        finish(launch(directory,'normal'))
        return read_json(directory/'result.json')
    results={}
    with no_models():
        # Both processes freeze a miss before either publisher starts.
        a=prepared('publisher-a','concurrent');b=prepared('publisher-b','concurrent')
        waiter=prepared('wait-timeout','concurrent');cancel=prepared('cancel-waiter','concurrent')
        pa=launch(a,'publisher');wait_for(lambda:(root/'publication-paused.json').exists())
        target=read_json(root/'publication-paused.json');lock=next((root/'tools').glob('*.lock'))
        owner=lock.read_text();request=read_json(a/'record.json')['delivery']['inputs']['environment']['payload']['shared_tool']['request']
        found,obs=st.resolve(request,host,local.process,root/'tools');assert found is None
        assert not list((root/'tools').glob('*.json')) and Path(target['temp']).is_file()
        pb=launch(b,'normal')
        finish(launch(waiter,'wait-timeout'));assert not read_json(waiter/'result.json')['accepted']
        finish(launch(cancel,'cancel-waiter'));assert (cancel/'interruption.json').is_file()
        assert lock.read_text()==owner
        save(root/'partial-publication-observation.json',{'observation':obs,'temp':target,'foreign_lock_unchanged':True})
        (root/'release-publication').write_text('release')
        finish(pa);finish(pb)
        ra,rb=read_json(a/'result.json'),read_json(b/'result.json')
        assert ra['accepted'] and rb['accepted']
        assert sum(r['receipt']['build_calls']['tool'] for r in (ra,rb))==1
        assert ra['receipt']['shared_tool']['artifact_id']==rb['receipt']['shared_tool']['artifact_id']
        assert len(list((root/'tools').glob('*.json')))==1
        results['concurrent']={'a':ra,'b':rb,'partial_record_not_read':True,'foreign_lock_preserved':True}
        old_registry=manifest(root/'tools');old_a=manifest(a)
        for name,mode,seconds in (('build-failure','build-failure',180),
            ('build-timeout','build-timeout',8),('build-cancel','cancel-build',180)):
            directory=prepared(name,name,seconds=seconds);finish(launch(directory,mode))
            if mode!='cancel-build':
                result=read_json(directory/'result.json');assert not result['accepted']
                assert result['receipt']['build_calls']=={'environment':0,'tool':1}
                assert result['receipt']['status']=='build_failed'
            else:
                interruption=read_json(directory/'interruption.json')
                assert 'P1_BUILD_RUNNING' in interruption['output']+interruption['stderr']
            assert manifest(root/'tools')==old_registry
            assert not list((root/'tools').glob('*.lock'))
            results[name]={'published':False,'accepted':False,'directory':str(directory)}
        # Actual image loss: only a newly created, nonce-specific image, archived first.
        image=ra['receipt']['image_id'];assert image not in before_ids
        archive=root/'owned-image.tar'
        assert local.process(['docker','image','save','--output',str(archive),image],90)['exit_code']==0
        envelope=root/'envelope';record=read_json(a/'record.json')
        install_envelope(a,'frozen',record['runtime']['path'],envelope)
        missing=root/'missing-library';import_candidate(envelope,missing,'publisher-a')
        assert not inspect_candidate(missing,'publisher-a')['qualification']['accepted']
        removed=local.process(['docker','image','rm',image],30);save(root/'image-removal.json',removed);assert removed['exit_code']==0
        assert st.resolve(request,host,local.process,root/'tools')[0] is None
        with patch.object(local.LocalExecutor,'build',side_effect=AssertionError('Pinned recovery must not build')):
            failed=resume_build(missing,'publisher-a',reuse_image=True)
        assert not failed['accepted'];save(root/'missing-image-result.json',failed)
        frozen_failure=manifest(missing)
        restored=local.process(['docker','image','load','--input',str(archive)],90);save(root/'image-restoration.json',restored)
        assert restored['exit_code']==0 and st.resolve(request,host,local.process,root/'tools')[0]['image_id']==image
        recovery=root/'image-recovery-library';import_candidate(envelope,recovery,'publisher-a')
        with patch.object(local.LocalExecutor,'build',side_effect=AssertionError('No rebuild')):
            recovered=resume_build(recovery,'publisher-a',reuse_image=True)
        assert recovered['accepted'] and manifest(missing)==frozen_failure
        save(root/'image-recovery-result.json',recovered)
        # Real active business container interrupted; recover in a new copied library.
        slow=prepared('slow','slow',slow=True);rs=execute(slow);assert rs['accepted']
        sr=read_json(slow/'record.json');slow_image=rs['receipt']['image_id']
        se=root/'slow-envelope';install_envelope(slow,'frozen',sr['runtime']['path'],se)
        interruption=root/'execution-interrupt';interruption.mkdir();save(interruption/'image.json',{'id':slow_image})
        import_candidate(se,interruption/'library','slow')
        finish(launch(interruption,'interrupt-execution'))
        assert (interruption/'business-running-at-interrupt.json').exists()
        pending=store.get(interruption/'library','slow',include_candidates=True)
        assert pending['pending_runtime'] and not pending['current_qualification']['accepted']
        cleanup=read_json(interruption/'interruption.json');assert cleanup['scope']
        left=local.process(['docker','ps','-aq','--filter','label=skillnet.scope='+cleanup['scope']],30)
        assert left['exit_code']==0 and not left['stdout'].strip()
        save(root/'interrupted-container-cleanup.json',{'scope':cleanup['scope'],'remaining':left,'cleanup':cleanup['cleanup']})
        frozen_interrupt=manifest(interruption)
        copylib=root/'execution-recovery-library';shutil.copytree(interruption/'library',copylib)
        with patch.object(local.LocalExecutor,'build',side_effect=AssertionError('No rebuild')):
            recovered=resume_build(copylib,'slow',reuse_image=True)
        assert recovered['accepted'] and manifest(interruption)==frozen_interrupt
        save(root/'execution-recovery-result.json',recovered)
        assert manifest(a)==old_a
        for item in old_registry:
            assert file_digest(root/'tools'/item['path'])==item['sha256']
        for item in protected:
            assert manifest(Path(item['path']))==item['files']
            assert inspect_candidate(Path(item['path'])/'library','chem-rdkit-descriptors')['qualification']['accepted']
        results.update({'image_loss_and_exact_restore':True,'active_execution_interrupt_and_new_recovery':True,
                        'protected_P0_bindings_unchanged_and_qualified':True})
        save(root/'result.json',{'passed':True,'scope':'Real Docker infrastructure fixtures, not new generated or reviewed Skills',
            'models':0,'results':results,'no_cache_cleanup':True,'failure_directories_not_reused':True})
        print({'passed':True,'root':str(root)},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path)
    parser.add_argument('--worker',type=Path);parser.add_argument('--mode',default='normal');args=parser.parse_args()
    try:
        if args.worker:worker(args.root.resolve(),args.worker.resolve(),args.mode)
        else:main(args.root.resolve())
    except BaseException as exc:
        if args.root.is_dir():save(args.root/('failure-'+(args.worker.name if args.worker else 'main')+'.json'),
            {'type':type(exc).__name__,'error':str(exc)})
        raise
