"""Linux-native process/Docker probes; positive start observations precede timeouts."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import time
import uuid
from unittest.mock import patch


def stamp(): return {'utc':datetime.now(timezone.utc).isoformat(),'monotonic':time.monotonic()}


def backend_started(log, nonce):
    # A Dockerfile command echo containing START is not an executed RUN.
    return bool(re.search(r'^#\d+ [\d.]+ START_'+re.escape(nonce)+r'\s*$', log, re.M))


def state(pid):
    try:
        raw=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        return {'pid':pid,'state':raw[0],'ppid':int(raw[1]),'pgid':int(raw[2]),'alive':raw[0] not in {'Z','X'}}
    except FileNotFoundError: return {'pid':pid,'alive':False,'state':'absent'}


def rows(path):
    if not path.exists(): return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def wait_for(predicate,seconds=8):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        value=predicate()
        if value: return value
        time.sleep(.05)
    raise TimeoutError('Probe startup was not positively observed')


def worker(args,runner):
    if args.worker=='tree':
        entry=dict(stamp(),pid=os.getpid(),ppid=os.getppid(),pgid=os.getpgid(0),sid=os.getsid(0),level=args.level)
        fd=os.open(args.ready,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        os.write(fd,(json.dumps(entry)+'\n').encode());os.close(fd)
        if args.level:
            argv=[sys.executable,__file__,'--worker','tree','--level',str(args.level-1),'--ready',str(args.ready)]
            if args.normal: argv+=['--normal']
            subprocess.Popen(argv,stdout=subprocess.DEVNULL if args.normal else None,stderr=subprocess.DEVNULL if args.normal else None)
        if args.normal and args.level==3:
            wait_for(lambda:len(rows(args.ready))==4)
            print('parent-completed');return
        time.sleep(120)
    elif args.worker=='docker':
        runner.run({'behavior':{'file_io':False}},args.image,['-c','import time; time.sleep(120)'],entrypoint='python',timeout=130)
    elif args.worker=='build':
        # Stream instrumentation preserves the actual client's log even when its
        # outer supervisor kills this worker. No command/result is simulated.
        log=args.context.parent/'native-build.log'
        def streamed(argv,timeout=60,cwd=None,**kwargs):
            with log.open('w') as stream:
                process=subprocess.Popen(argv,cwd=cwd,stdout=stream,stderr=subprocess.STDOUT)
                (args.context.parent/'native-build-client.json').write_text(json.dumps({'pid':process.pid,'pgid':os.getpgid(process.pid),'command':argv,**stamp()}))
                code=process.wait(timeout=timeout)
            return {'command':argv,'exit_code':code,'stdout':log.read_text(),'stderr':''}
        runner.process=streamed
        result=runner.build(args.context.parent,{'context':args.context.name,'platform':'linux/amd64','local_tag':args.tag,'limits':{'build_seconds':120}})
        print(json.dumps(result),flush=True)
        raise SystemExit(result['exit_code'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--implementation',type=Path,default=Path(__file__).resolve().parents[1]/'runtime_package.py')
    p.add_argument('--workdir',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--docker',action='store_true')
    p.add_argument('--build',action='store_true')
    p.add_argument('--skip-processes',action='store_true')
    p.add_argument('--image',default='skillnet-model:bf44e690a2a48efd021aae78')
    p.add_argument('--worker',choices=['tree','docker','build'])
    p.add_argument('--ready',type=Path)
    p.add_argument('--level',type=int,default=3)
    p.add_argument('--normal',action='store_true')
    p.add_argument('--context',type=Path)
    p.add_argument('--tag')
    args=p.parse_args()
    spec=importlib.util.spec_from_file_location('probe_runner',args.implementation);runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    if args.worker: return worker(args,runner)
    if os.name!='posix' or platform.system()!='Linux': p.error('Run with native Linux Python')
    root=args.workdir.resolve();root.mkdir(mode=0o700,parents=True,exist_ok=False)
    report={'environment':{'platform':platform.platform(),'python':sys.version,'executable':sys.executable,'uid':os.getuid(),'gid':os.getgid(),
                          'workdir':str(root),'workdir_mode':oct(root.stat().st_mode&0o777),'implementation':str(args.implementation)},'started':stamp(),'processes':[]}
    script=str(Path(__file__).resolve())
    def save(): args.output.write_text(json.dumps(report,indent=2)+'\n')
    control=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            for normal in (() if args.skip_processes else (False,True)):
                ready=root/('normal.jsonl' if normal else 'timeout.jsonl')
                argv=[sys.executable,script,'--implementation',str(args.implementation),'--worker','tree','--ready',str(ready)]
                if normal: argv+=['--normal']
                future=executor.submit(runner.process,argv,4,None,supervise=True)
                observed=wait_for(lambda:rows(ready) if len(rows(ready))==4 else None,seconds=3)
                item={'mode':'normal' if normal else 'timeout','started_observation':stamp(),'ready':observed}
                try: item['result']=future.result()
                except subprocess.TimeoutExpired as exc:
                    item.update(timed_out=True,timeout_observation=stamp(),cleanup=getattr(exc,'cleanup',[]),scope=getattr(exc,'scope',None))
                wait_for(lambda:all(not state(row['pid'])['alive'] for row in observed))
                item['after']=[state(row['pid']) for row in observed];item['unrelated_control']=state(control.pid)
                assert item['unrelated_control']['alive']
                report['processes'].append(item);save()
            if args.docker:
                executable=__import__('shutil').which('docker')
                report['environment']['docker_executable']=executable
                assert Path(executable).read_bytes()[:4]==b'\x7fELF','A Windows docker.exe bridge is not native Linux evidence'
                info=runner.process(['docker','info','--format','{{json .}}'],30)
                server=json.loads(info['stdout']);report['environment']['engine']={k:server.get(k) for k in ['ID','ServerVersion','OperatingSystem','OSType','Architecture']}
                assert server['OperatingSystem']=='Docker Desktop','Do not use a second daemon for this probe'
                control_name='skillnet-linux-control-'+uuid.uuid4().hex
                started=runner.process(['docker','run','-d','--name',control_name,'--entrypoint','python',args.image,'-c','import time; time.sleep(120)'],30)
                assert started['exit_code']==0,started
                report['unrelated_container']={'name':control_name,'id':started['stdout'].strip()}
                try:
                    for fail_cleanup in (False,True):
                        scope=uuid.uuid4().hex
                        actual_cleanup=runner.cleanup_scope
                        def failing_cleanup(value):
                            with patch.dict(os.environ,{'DOCKER_HOST':'unix://'+str(root/'deliberately-unavailable.sock')}):
                                return actual_cleanup(value)
                        with patch.object(runner.uuid,'uuid4',return_value=type('Token',(),{'hex':scope})()), \
                             patch.object(runner,'cleanup_scope',side_effect=failing_cleanup if fail_cleanup else actual_cleanup):
                            argv=[sys.executable,script,'--implementation',str(args.implementation),'--worker','docker','--image',args.image]
                            future=executor.submit(runner.process,argv,7,None,supervise=True)
                            def running():
                                result=runner.process(['docker','ps','-q','--filter','label=skillnet.scope='+scope],10)
                                return result['stdout'].strip()
                            container_id=wait_for(running,5)
                            item={'scope':scope,'id':container_id,'start_confirmed':stamp(),'cleanup_fault_injected':fail_cleanup}
                            try: future.result();raise AssertionError('Expected outer timeout')
                            except subprocess.TimeoutExpired as exc: item.update(timeout_observation=stamp(),cleanup=getattr(exc,'cleanup',[]),exception_scope=getattr(exc,'scope',None))
                        item['after']=runner.process(['docker','ps','-q','--filter','id='+container_id],10)
                        if fail_cleanup:
                            assert item['after']['stdout'].strip(),'Injected cleanup failure should leave an inspectable owned container'
                            item['recovery']=actual_cleanup(scope)
                            assert not running()
                        else: assert not item['after']['stdout'].strip()
                        item['unrelated_container_running']=runner.process(['docker','inspect',control_name,'--format','{{.State.Running}}'],10)['stdout'].strip()=='true'
                        assert item['unrelated_container_running']
                        report.setdefault('containers',[]).append(item);save()
                finally: report['control_container_cleanup']=runner.process(['docker','rm','--force',control_name],15)
            if args.build:
                nonce=uuid.uuid4().hex
                context=root/('build-'+nonce);context.mkdir()
                code="import os,time,json;print('START_"+nonce+"',flush=True);[(print('HEARTBEAT:'+json.dumps({'token':'"+nonce+"','pid':os.getpid(),'time':time.time(),'tick':i}),flush=True),time.sleep(.5)) for i in range(90)]"
                (context/'Dockerfile').write_text('FROM '+args.image+'\nUSER 0:0\nRUN python -c '+json.dumps(code)+'\n')
                tag='skillnet-linux-build:'+nonce
                future=executor.submit(runner.process,[sys.executable,script,'--implementation',str(args.implementation),'--worker','build','--context',str(context),'--tag',tag],18,None,supervise=True)
                try:
                    log=context.parent/'native-build.log'
                    before=wait_for(lambda:{'observed':stamp(),'native_log':log.read_text()} if log.exists() and backend_started(log.read_text(),nonce) else None,12)
                except TimeoutError:
                    try: client=future.result()
                    except subprocess.TimeoutExpired as exc: client={'timeout':str(exc),'stdout':exc.output,'stderr':exc.stderr}
                    report['build_startup_error']={'client':client}
                    raise
                item={'nonce':nonce,'tag':tag,'started_backend':before,
                      'client':json.loads((root/'native-build-client.json').read_text()),'started_client_processes':runner.process(['ps','-eo','pid,ppid,pgid,args'],10)['stdout']}
                try: future.result();raise AssertionError('Expected uncached build timeout')
                except subprocess.TimeoutExpired as exc: item.update(timeout_observation=stamp(),cleanup=getattr(exc,'cleanup',[]),scope=getattr(exc,'scope',None))
                time.sleep(2)
                item['backend_history']=runner.process(['docker','buildx','history','ls','--format','json'],20)
                entries=[json.loads(line) for line in item['backend_history']['stdout'].splitlines() if line.startswith('{')]
                item['matching_backend_records']=[entry for entry in entries if nonce in entry.get('name','')]
                for entry in item['matching_backend_records']:
                    history_id=entry['ref'].rsplit('/',1)[-1]
                    entry['inspect']=runner.process(['docker','buildx','history','inspect',history_id,'--format','json'],20)
                    entry['logs']=runner.process(['docker','buildx','history','logs',history_id],20)
                item['client_after']=state(item['client']['pid'])
                item['image_inspect']=runner.process(['docker','image','inspect',tag],10)
                item['remaining_client_processes']=runner.process(['ps','-eo','pid,ppid,pgid,args'],10)['stdout']
                item['unrelated_control_alive']=state(control.pid)['alive']
                item['limitation']='Use exact build history/error and recorded RUN heartbeat; no image is not proof of backend cleanup. No claim about all daemon resources.'
                report['build']=item;save()
    finally:
        if control.poll() is None: os.killpg(control.pid,signal.SIGKILL)
        control.wait();report['finished']=stamp();save()
    print(json.dumps({'output':str(args.output),'process_modes':len(report['processes']),'containers':len(report.get('containers',[]))}))


if __name__=='__main__': main()
