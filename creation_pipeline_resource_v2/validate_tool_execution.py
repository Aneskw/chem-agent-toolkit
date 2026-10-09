#!/usr/bin/env python3
"""Run declared local script fixtures in an isolated temporary working copy."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def contained(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ValueError('Fixture script must be a relative path')
    path=(root/relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Fixture script is absent or escapes skill directory')
    if path.suffix!='.py' or not path.is_relative_to((root/'scripts').resolve()):
        raise ValueError('Only packaged Python scripts under scripts/ can run')
    return path


def subset(expected, actual) -> bool:
    if isinstance(expected,dict):
        return isinstance(actual,dict) and all(k in actual and subset(v,actual[k]) for k,v in expected.items())
    if isinstance(expected,list):
        return isinstance(actual,list) and len(expected)==len(actual) and all(subset(a,b) for a,b in zip(expected,actual))
    return type(expected)==type(actual) and expected==actual


def validate(skill: Path, python: str = sys.executable) -> dict:
    skill=skill.resolve()
    scripts=list((skill/'scripts').rglob('*.py')) if (skill/'scripts').is_dir() else []
    if not scripts:
        return {'skill':skill.name,'status':'not_applicable','cases':[],
                'scope':'No packaged Python script; evaluate agent usefulness separately.'}
    fixture=skill/'execution'/'fixtures.json'
    if not fixture.is_file():
        return {'skill':skill.name,'status':'untested_no_fixture','cases':[],
                'scope':'Packaged scripts exist, but no declared execution fixtures were supplied.'}
    try:
        cases=json.loads(fixture.read_text(encoding='utf-8'))['cases']
        if not isinstance(cases,list) or not cases:raise ValueError('cases[] must be nonempty')
    except (OSError,ValueError,KeyError,TypeError) as exc:
        return {'skill':skill.name,'status':'failed','cases':[], 'error':f'Invalid fixture: {exc}'}
    observations=[]
    with tempfile.TemporaryDirectory(prefix='chem-skill-exec-') as tmp:
        root=Path(tmp)/'skill'
        shutil.copytree(skill,root,symlinks=False)
        for case in cases:
            name=str(case.get('name','unnamed'))
            try:
                script=contained(root,str(case['script']))
                args=case.get('args',[])
                if not isinstance(args,list) or any(not isinstance(arg,str) for arg in args):
                    raise ValueError('args must be a string array')
                timeout=int(case.get('timeout_seconds',30))
                if not 1<=timeout<=60:raise ValueError('timeout_seconds must be 1..60')
                env={k:v for k,v in os.environ.items() if k in {'PATH','LANG','LC_ALL','DYLD_LIBRARY_PATH'}}
                env.update({'HOME':str(Path(tmp)),'PYTHONDONTWRITEBYTECODE':'1'})
                proc=subprocess.run([python,str(script),*args],cwd=root,env=env,
                                    capture_output=True,text=True,timeout=timeout)
                expected_exit=case.get('expected_exit',0)
                passed=proc.returncode==expected_exit
                error=None if passed else f'exit {proc.returncode}; expected {expected_exit}'
                if 'expected_json_lines' in case:
                    try:
                        actual=[json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
                        if not subset(case['expected_json_lines'],actual):
                            passed=False;error='stdout JSON did not match expected values'
                    except json.JSONDecodeError:
                        passed=False;error='stdout was not JSON lines'
                observations.append({'name':name,'status':'passed' if passed else 'failed',
                                     'exit_code':proc.returncode,'error':error,
                                     'stderr_tail':proc.stderr[-500:] if not passed else ''})
            except (OSError,ValueError,KeyError,subprocess.TimeoutExpired) as exc:
                observations.append({'name':name,'status':'failed','error':type(exc).__name__+': '+str(exc)[:300]})
    return {'skill':skill.name,'status':'passed' if all(c['status']=='passed' for c in observations) else 'failed',
            'cases':observations,
            'scope':'Declared local script cases only; does not establish scientific correctness or agent utility.'}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('skill',type=Path)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    report=validate(args.skill)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['status'] in {'passed','not_applicable','untested_no_fixture'} else 2


if __name__=='__main__':raise SystemExit(main())
