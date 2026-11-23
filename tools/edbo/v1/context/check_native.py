import json
import pathlib
import subprocess
import sys
import sysconfig

root = pathlib.Path(sysconfig.get_paths()['purelib']) / 'rdkit'
files = list(root.rglob('*.so')) + list((pathlib.Path(sys.prefix) / 'lib').glob('libRDKit*.so*'))
files = sorted({p.resolve() for p in files if p.is_file()})
assert files, 'No RDKit shared libraries found'
missing = {}
errors = {}
for path in files:
    result = subprocess.run(['/usr/bin/ldd', str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    text = result.stdout + result.stderr
    unresolved = sorted({line.strip().split('=>')[0].strip() for line in text.splitlines() if '=> not found' in line})
    if unresolved:
        missing[str(path)] = unresolved
    if result.returncode != 0:
        errors[str(path)] = text.strip()
print(json.dumps({'checked_libraries': len(files), 'missing': missing, 'errors': errors}, sort_keys=True))
assert not missing and not errors, 'RDKit native dependencies are unresolved; see audit output'
