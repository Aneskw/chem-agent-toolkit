"""Run the unchanged offline suite under an owned process session, with diagnostics."""
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from creation_pipeline.runtime.runner import process
from creation_pipeline.records import redact,sanitized,write_json

CHILD='''import faulthandler,runpy,sys
selection=sys.argv[1:]
faulthandler.dump_traceback_later(30 if selection else 120,repeat=True)
sys.argv=['unittest',*selection] if selection else ['unittest','discover','-s','tests','-v']
try:
    runpy.run_module('unittest',run_name='__main__',alter_sys=True)
finally:
    faulthandler.cancel_dump_traceback_later()
'''


def run(command,timeout=18*60):
    if os.environ.get('SKILLNET_EXECUTION_SCOPE'):
        raise ValueError('Offline suite must run outside a business execution scope')
    try:
        result=process(command,timeout,cwd=ROOT,supervise=False)
    except subprocess.TimeoutExpired as exc:
        def text(value):return value.decode('utf-8','replace') if isinstance(value,bytes) else value or ''
        result={'exit_code':124,'stdout':text(exc.output),'stderr':text(exc.stderr),
                'error':'offline_suite_timeout','cleanup':getattr(exc,'cleanup',[])}
    sys.stdout.write(redact(result['stdout']));sys.stdout.flush()
    sys.stderr.write(redact(result['stderr']));sys.stderr.flush()
    write_json(ROOT/'.pipeline/offline-suite-result.json',sanitized({
        k:v for k,v in result.items() if k not in {'stdout','stderr'}}))
    code=result['exit_code']
    return code if isinstance(code,int) and 0<=code<=255 else 1


def self_check():
    checks=[('success','print("offline supervisor success")',5,0),
            ('failure','raise SystemExit(7)',5,7),
            ('timeout','import time;time.sleep(30)',1,124)]
    if os.name=='posix':
        checks.append(('owned_group','import os,signal;os.killpg(os.getpgrp(),signal.SIGKILL)',5,1))
    for name,code,timeout,expected in checks:
        actual=run([sys.executable,'-c',code],timeout)
        if actual!=expected:raise ValueError(f'Offline supervisor {name}: expected={expected}; actual={actual}')
        print(f'offline supervisor {name}: passed',flush=True)
    return 0


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check',action='store_true')
    parser.add_argument('--module',choices=['tests.pipeline.'+p.stem for p in sorted((ROOT/'tests/pipeline').glob('test_*.py'))])
    args=parser.parse_args()
    command=[sys.executable,'-u','-c',CHILD]+([args.module,'-v'] if args.module else [])
    raise SystemExit(self_check() if args.self_check else run(command,120 if args.module else 18*60))
