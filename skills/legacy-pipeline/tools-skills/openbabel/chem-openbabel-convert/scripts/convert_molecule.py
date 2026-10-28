#!/usr/bin/env python3
"""Convert one file through obabel, preserving diagnostics and the input."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

def convert(source,source_format,target_format,destination):
    source,destination=Path(source),Path(destination)
    if not source.is_file():raise ValueError('Input file does not exist')
    if source.resolve()==destination.resolve():raise ValueError('Output must differ from input')
    if destination.exists():raise ValueError('Output file already exists; choose a new path')
    executable=shutil.which('obabel')
    if not executable:raise ValueError('obabel executable not found on PATH')
    command=[executable,'-i',source_format,str(source),'-o',target_format,'-O',str(destination)]
    result=subprocess.run(command,capture_output=True,text=True)
    if result.returncode or not destination.is_file() or destination.stat().st_size==0:
        return {'ok':False,'error':result.stderr.strip() or 'No nonempty output file produced',
                'exit_code':result.returncode,'stdout':result.stdout,'output':str(destination)}
    return {'ok':True,'input':str(source),'output':str(destination),
            'input_format':source_format,'output_format':target_format,'stderr':result.stderr.strip()}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('input','input-format','output-format','output'):p.add_argument('--'+flag,required=True)
    a=p.parse_args()
    try:r=convert(a.input,a.input_format,a.output_format,a.output)
    except (OSError,ValueError) as e:r={'ok':False,'error':str(e)}
    print(json.dumps(r,ensure_ascii=False));return 0 if r['ok'] else 2

if __name__=='__main__':raise SystemExit(main())
