import importlib.metadata as md
from pathlib import Path
import subprocess

count = 0
for distribution in ('rdkit', 'torch'):
    dist = md.distribution(distribution)
    for relative in dist.files or []:
        path = Path(dist.locate_file(relative))
        if '.so' not in path.name or not path.is_file():
            continue
        result = subprocess.run(['ldd', str(path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        assert result.returncode == 0 and 'not found' not in result.stdout, (str(path), result.stdout)
        count += 1
assert count > 0
print('Native dependency audit passed for', count, 'shared objects')
