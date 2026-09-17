#!/usr/bin/env python3
import argparse, json, shutil, subprocess, sys
p=argparse.ArgumentParser()
p.add_argument('--input', required=True); p.add_argument('--input-format', required=True)
p.add_argument('--output-format', required=True); p.add_argument('--output', required=True)
a=p.parse_args()
if shutil.which('obabel') is None:
    print(json.dumps({'ok':False,'error':'obabel executable not found','status':'blocked_resources'})); raise SystemExit(2)
cmd=['obabel','-i',a.input_format,a.input,'-o',a.output_format,'-O',a.output]
r=subprocess.run(cmd,capture_output=True,text=True)
if r.returncode:
    print(json.dumps({'ok':False,'error':r.stderr.strip() or 'Open Babel conversion failed','exit_code':r.returncode})); raise SystemExit(2)
print(json.dumps({'ok':True,'input':a.input,'output':a.output,'input_format':a.input_format,'output_format':a.output_format,'stderr':r.stderr.strip()}))
