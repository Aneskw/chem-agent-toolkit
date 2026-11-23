"""Keep the pinned DGL 2.4 nested make jobs consistent with the outer build."""
import hashlib
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
jobs = int(sys.argv[2])
assert jobs > 0
expected = {
    'graphbolt/build.sh': '7d13ac4ca6f179b63c2e53fb562076118d12e1980f7624dbdb2aa475f456f1e0',
    'dgl_sparse/build.sh': 'd7dde19eec9aa19c2be063d576b72808a9ccb32795bf31fdf4f2bca83a87c259',
    'tensoradapter/pytorch/build.sh': '4e001ea2c2850a11aa249c95518bfa428a035c002e5d9a122a89cb15cb9786ac',
}
for relative, digest in expected.items():
    path = root / relative
    original = path.read_bytes()
    assert hashlib.sha256(original).hexdigest() == digest, relative
    updated, count = re.subn(r'(?m)^([ \t]*)make -j[ \t]*$',
                             lambda m: m[1] + 'make -j' + str(jobs), original.decode('utf-8'))
    assert count == 2, (relative, count)
    path.write_text(updated, encoding='utf-8')
    print(relative + ': constrained ' + str(count) + ' nested make calls')
