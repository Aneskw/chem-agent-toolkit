"""Offline source-package checks and mechanism regressions; never calls a model/Docker."""
import argparse
import ast
import contextlib
import hashlib
import importlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
TESTS = ['test_delivery', 'test_runtime_interfaces', 'test_strict_acceptance', 'test_acceptance_v2', 'test_creation_workflow', 'test_runtime_model',
         'test_runtime_cli', 'test_runtime_consistency', 'test_runtime_hardening', 'test_runtime_planning_followup',
         'test_round_two_runtime', 'test_runtime_linux', 'test_creation_contract', 'test_generic_ingestion',
         'test_model_call', 'test_model_network', 'test_decisions', 'test_pair_sources', 'test_table_catalog', 'test_tool_execution']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tests', action='store_true')
    parser.add_argument('--output', type=Path, help='Optional audit JSON outside the sealed source package')
    args=parser.parse_args()
    errors=[]
    manifest=ROOT/'MANIFEST.json'
    checked=0
    if manifest.is_file():
        entries=json.loads(manifest.read_text(encoding='utf-8'))['files']
        actual={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()
                and '__pycache__' not in p.parts and p != manifest}
        if actual != set(entries):errors.append('Manifest file set differs: '+str(sorted(actual.symmetric_difference(entries))))
        for name, expected in entries.items():
            path=ROOT/name
            if not path.resolve().is_relative_to(ROOT) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                errors.append('Manifest mismatch: '+name)
            checked+=1
    for folder in [ROOT/'creation_pipeline', ROOT/'evaluation']:
        for path in folder.rglob('*.py'):
            if any(part in {'runs','results','__pycache__'} for part in path.relative_to(ROOT).parts):continue
            try:ast.parse(path.read_text(encoding='utf-8-sig'))
            except (ValueError,SyntaxError) as exc:errors.append(str(path)+': '+str(exc))
    for module in ['run_pipeline','batch_pipeline','publish_run','inspect_run','strict_acceptance','runtime_model_lifecycle']:
        importlib.import_module(module)
    from core.creation_sources import make_bundle
    from runtime_model import options
    config_path=ROOT/'creation_pipeline/examples/rdkit-source.json'
    config=json.loads(config_path.read_text(encoding='utf-8'))
    bundle=make_bundle(config['jobs'][0],(config_path.parent/config['base']).resolve(),config['max_context_chars'])
    bindings=json.loads((ROOT/'creation_pipeline/examples/rdkit-runtime.json').read_text(encoding='utf-8'))
    options(bindings['planner'])
    if bindings['schema_version']!=3 or not bundle['coverage']['primary_text_supplied']:errors.append('Template invalid')
    for tool in bindings['tools'].values():
        if not (config_path.parent/tool['root']).resolve().is_relative_to(ROOT):errors.append('External template dependency')
        if not (config_path.parent/tool['root']).is_dir():errors.append('Missing tool input')
    for entry in ['run_pipeline.py','batch_pipeline.py','run_public_pipeline.py','publish_run.py','inspect_run.py','prepare_runtime.py','validate_runtime.py','relocate_runtime.py']:
        result=subprocess.run([sys.executable,str(ROOT/'creation_pipeline'/entry),'--help'],capture_output=True,timeout=30)
        if result.returncode:errors.append('CLI import failed: '+entry)
    result={'manifest_files_checked':checked,'errors':errors,'real_model_calls':0,'real_docker_runs':0}
    if args.tests:
        sys.path.insert(0,str(ROOT/'creation_pipeline/tests'))
        # Workspace-local temporary fixtures avoid Windows sandbox temp ACL differences.
        with tempfile.TemporaryDirectory(prefix='.verification-',dir=ROOT) as scratch:
            old=tempfile.tempdir;tempfile.tempdir=scratch
            try:
                suite=unittest.defaultTestLoader.loadTestsFromNames(TESTS)
                tested=unittest.TextTestRunner(verbosity=2).run(suite)
                result.update(tests=tested.testsRun,failures=len(tested.failures),test_errors=len(tested.errors),skipped=len(tested.skipped))
                if not tested.wasSuccessful():errors.append('Regression failure')
            finally:tempfile.tempdir=old
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))
    return 1 if errors else 0


if __name__=='__main__':raise SystemExit(main())
