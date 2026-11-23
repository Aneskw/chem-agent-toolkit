"""Audit ELF dependencies with bundled providers, then test normal Python loading."""
import importlib.metadata as md
import json
import os
import pathlib
import subprocess
import sys
import sysconfig

root = pathlib.Path(sysconfig.get_paths()['purelib'])
providers = [root / 'torch' / 'lib', root / 'dgl']
providers += sorted(root.glob('*.libs'))
for directory in providers:
    assert directory.is_dir(), str(directory)
assert (root / 'dgl' / 'libdgl.so').is_file()
assert (root / 'torch' / 'lib' / 'libc10.so').is_file()
assert (root / 'torch' / 'lib' / 'libtorch_cpu.so').is_file()
failures = []
count = 0
for path in sorted(root.rglob('*.so*')):
    if not path.is_file():
        continue
    with path.open('rb') as stream:
        if stream.read(4) != b'\x7fELF':
            continue
    # ldd starts a fresh loader; it does not inherit libraries preloaded by Python.
    # Include the audited file's own directory and the installed bundled providers.
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = os.pathsep.join(dict.fromkeys(
        [str(path.parent)] + [str(p) for p in providers]))
    result = subprocess.run(['ldd', str(path)], env=env, text=True, capture_output=True)
    output = result.stdout + result.stderr
    if 'not found' in output or (result.returncode and 'statically linked' not in output):
        failures.append(str(path) + '\n' + output)
    count += 1
assert count > 0
if failures:
    raise RuntimeError('\n'.join(failures))
# These fresh processes use the image's ordinary environment, without audit paths.
for name in ['torch', 'dgl', 'dgllife', 'torch-scatter', 'rdkit', 'faiss-cpu', 'numpy', 'scipy']:
    result = subprocess.run([sys.executable, '/opt/retroknn/probe.py', name, md.version(name)],
                            text=True, capture_output=True, check=True)
    observed = json.loads(result.stdout)
    assert observed['version'] == md.version(name)
