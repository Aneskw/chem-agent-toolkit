import contextlib
import importlib
import importlib.metadata
import io
import json
import platform
import subprocess
import sys

name, expected = sys.argv[1:]
with contextlib.redirect_stdout(io.StringIO()):
    if name == 'Python':
        observed = platform.python_version()
        assert sys.version_info[:2] == (3, 12)
        import ssl
        assert ssl.OPENSSL_VERSION
    elif name == 'openbabel':
        from openbabel import pybel
        observed = pybel.ob.OBReleaseVersion()
        assert pybel.ob.GetSymbol(6) == 'C'
        assert pybel.ob.GetVdwRad(6) > 0
        assert pybel.readstring('smi', 'C').OBMol.NumAtoms() == 1
    elif name == 'micromamba':
        observed = subprocess.check_output(['micromamba', '--version'], text=True).strip()
    else:
        observed = importlib.metadata.version(name)
        modules = {'auto-qchem': 'autoqchem.gaussian_log_extractor', 'PyYAML': 'yaml', 'py3Dmol': 'py3Dmol'}
        module = importlib.import_module(modules.get(name, name))
        if name == 'auto-qchem':
            cls = module.gaussian_log_extractor
            assert callable(cls.check_for_exceptions) and callable(cls.get_descriptors)
            from autoqchem.molecule import GetVdwRad
            assert GetVdwRad(6) > 0
        elif name == 'numpy':
            assert module.array([1, 2]).sum() == 3
        elif name == 'pandas':
            frame = module.DataFrame({'x': [1.0, 2.0]})
            assert frame.to_dict(orient='list') == {'x': [1.0, 2.0]}
            assert len(frame.unstack()) == 2
        elif name == 'scipy':
            from scipy.spatial.distance import cdist
            assert cdist([[0., 0., 0.]], [[1., 0., 0.]])[0, 0] == 1.
        elif name == 'rdkit':
            from rdkit import Chem
            assert Chem.MolFromSmiles('C').GetNumAtoms() == 1
        elif name == 'PyYAML':
            assert module.safe_load('x: 1')['x'] == 1
assert observed == expected, (name, observed, expected)
print(json.dumps({'version': observed}))
