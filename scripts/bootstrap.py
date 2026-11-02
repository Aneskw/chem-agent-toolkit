"""Explicit local venv setup only; never installs models, Codex, Docker or chemistry."""
import argparse
from pathlib import Path
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from creation_pipeline.records import has_link,redact


def bootstrap(destination,*,yaml=False):
    if sys.version_info<(3,11):raise ValueError('Python >=3.11 is required')
    destination=Path(destination).absolute()
    if has_link(destination):raise ValueError('Virtual environment root must not be linked')
    if has_link(destination/'pyvenv.cfg'):raise ValueError('Virtual environment marker must not be linked')
    if destination.exists() and not (destination/'pyvenv.cfg').is_file():
        raise ValueError('Refusing to reuse a non-venv directory: '+str(destination))
    # This mutation is explicitly invoked by the operator, never by readiness/build.
    if not (destination/'pyvenv.cfg').is_file():
        venv.EnvBuilder(with_pip=True,clear=False,system_site_packages=False).create(destination)
    python=destination/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    observed=subprocess.run([str(python),'-c','import sys; print(sys.prefix)'],capture_output=True,
        encoding='utf-8',errors='replace',timeout=30)
    if observed.returncode or Path(observed.stdout.strip()).resolve()!=destination.resolve():
        raise ValueError('Virtual environment prefix mismatch; refusing dependency installation')
    requirements=ROOT/('requirements-yaml.txt' if yaml else 'requirements.txt')
    p=subprocess.run([str(python),'-m','pip','--disable-pip-version-check','install','-r',str(requirements)],
        cwd=ROOT,capture_output=True,encoding='utf-8',errors='replace')
    if p.returncode:raise ValueError('Dependency installation failed: '+redact(p.stdout+p.stderr)[-3000:])
    return {'status':'environment_prepared','python':str(python),'requirements':requirements.name,
            'model_calls':0,'build_calls':0,'next':'Use this Python for: -m creation_pipeline init --model YOUR_MODEL --output .pipeline/config.json'}


def main():
    import json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--venv',default=str(ROOT/'.venv'))
    parser.add_argument('--yaml',action='store_true',help='Also install the optional YAML parser')
    args=parser.parse_args()
    try:answer=bootstrap(args.venv,yaml=args.yaml)
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print(json.dumps({'status':'blocked','reason':redact(str(exc))}));return 1
    print(json.dumps(answer,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
