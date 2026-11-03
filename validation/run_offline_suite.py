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
faulthandler.dump_traceback_later(120,repeat=True)
sys.argv=['unittest','discover','-s','tests','-v']
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


if __name__=='__main__':raise SystemExit(run([sys.executable,'-u','-c',CHILD]))
