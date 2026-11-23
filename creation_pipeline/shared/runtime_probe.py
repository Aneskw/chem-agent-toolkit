"""Read-only container check, compatible with Python 3.7+; no extra installation."""
import importlib
import json
import platform
import sys


def check(name, module):
    if not module:
        return {'version': platform.python_version()}
    loaded = importlib.import_module(module)
    try:
        from importlib.metadata import version
    except ImportError:
        from pkg_resources import get_distribution
        version = lambda package: get_distribution(package).version
    observed = version(name)
    if module == 'numpy':
        assert loaded.dot([1, 2], [3, 4]) == 11
    elif module == 'torch':
        assert loaded.tensor([1, 2]).sum().item() == 3
    elif module in ('rdkit', 'rdkit.Chem'):
        from rdkit import Chem
        assert Chem.MolFromSmiles('CCO').GetNumAtoms() == 3
    return {'version': observed}


if __name__ == '__main__':
    print(json.dumps(check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '')))
