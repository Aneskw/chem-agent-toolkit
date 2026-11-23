import contextlib
import importlib
import io
import json
import platform
import sys
import pkg_resources

name, expected = sys.argv[1:3]
modules = {'edbo':'edbo.bro', 'scikit-learn':'sklearn', 'pyro-ppl':'pyro', 'pyclustering':'pyclustering.cluster.kmedoids', 'ipython':'IPython', 'Pillow':'PIL', 'python-dateutil':'dateutil', 'opt-einsum':'opt_einsum', 'pyro-api':'pyroapi', 'prompt-toolkit':'prompt_toolkit', 'Pygments':'pygments', 'ipython-genutils':'ipython_genutils'}
with contextlib.redirect_stdout(io.StringIO()):
    if name == 'Python':
        version = platform.python_version()
        assert sys.version_info[:3] == (3, 7, 5)
    elif name in ('libxrender1', 'libxext6'):
        import ctypes
        import subprocess
        version = subprocess.check_output(['dpkg-query', '-W', '-f=${Version}', name], universal_newlines=True).strip()
        ctypes.CDLL({'libxrender1': 'libXrender.so.1', 'libxext6': 'libXext.so.6'}[name])
    elif name == 'rdkit':
        import rdkit
        from rdkit import Chem
        version = rdkit.__version__
        assert Chem.MolFromSmiles('CCO').GetNumAtoms() == 3
    else:
        mod = importlib.import_module(modules.get(name, name.replace('-', '_')))
        version = pkg_resources.get_distribution(name).version
        if name == 'edbo':
            assert all(callable(getattr(mod.BO_express, key)) for key in ['init_sample', 'add_results', 'run', 'get_experiments', 'export_proposed'])
        elif name == 'torch':
            assert mod.tensor([1., 2.]).sum().item() == 3.
            assert mod.version.cuda is None
        elif name == 'gpytorch':
            import torch
            assert mod.kernels.MaternKernel()(torch.zeros(2, 1)).evaluate().shape == (2, 2)
        elif name == 'pandas':
            assert mod.DataFrame({'x':[1]}).iloc[0, 0] == 1
        elif name == 'numpy':
            assert mod.array([1, 2]).sum() == 3
        elif name == 'mordred':
            from mordred import Calculator, descriptors
            assert len(Calculator(descriptors, ignore_3D=True).descriptors) > 0
    assert version == expected, (name, version, expected)
print(json.dumps({'version': version}))
