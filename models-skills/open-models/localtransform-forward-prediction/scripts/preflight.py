"""Inspect a local checkout without importing its code or loading model weights."""
import argparse
import json
import subprocess
from pathlib import Path

def check(root, requirements):
    root = Path(root).resolve()
    missing=[]
    empty=[]
    for name in requirements['files']:
        p=(root/name).resolve()
        if not p.is_relative_to(root): raise ValueError('Path escapes checkout')
        if not p.is_file(): missing.append(name)
        elif p.stat().st_size == 0: empty.append(name)
    try:
        revision=subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
    except (OSError,subprocess.CalledProcessError): revision=None
    return {'missing_files':missing,'empty_files':empty,'observed_commit':revision,
            'expected_commit':requirements['commit'],
            'passed':not missing and not empty and revision==requirements['commit'],
            'scope':'File presence and commit only; no dependency compatibility, weight integrity or inference test.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repo_root',type=Path)
    args=parser.parse_args()
    req=json.loads((Path(__file__).with_name('requirements.json')).read_text())
    result=check(args.repo_root,req)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['passed'] else 2)
