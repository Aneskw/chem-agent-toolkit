SOURCE_HASHES = {'retro_star': ('', 'dfe7888706157527071e99bbd9dc101b9bc97517390816fff43f9a90cac8fdf8'), 'mlp_retrosyn': ('retro_star/packages/mlp_retrosyn/mlp_retrosyn/', 'a55bd4fcd017e16883a541b5ac9091fb2cee53dd8518ca40e25f359dd904fa0c'), 'rdchiral': ('retro_star/packages/rdchiral/rdchiral/', '80b729aefbdee1e95496aba92dd0bbe520aefecdf26c2fe1c77ae69321dee97c')}
import hashlib
import json
import pathlib
import subprocess
import sys

name, expected = sys.argv[1:]
sys.argv = [sys.argv[0]]
commit = '60e7a24213810706a7075d113704c9320158d726'
if name in ('retro_star', 'mlp_retrosyn', 'rdchiral'):
    assert pathlib.Path('/opt/retrostar/SOURCE_COMMIT').read_text() == commit
    prefix, digest = SOURCE_HASHES[name]
    source = pathlib.Path('/opt/retrostar/src')
    files = sorted((p for p in source.rglob('*.py') if p.relative_to(source).as_posix().startswith(prefix)), key=lambda p: p.relative_to(source).as_posix())
    observed = hashlib.sha256()
    for path in files:
        observed.update(path.relative_to(source).as_posix().encode() + b'\0' + path.read_bytes())
    assert observed.hexdigest() == digest
    version = commit
    if name == 'retro_star':
        from retro_star.api import RSPlanner
        from retro_star.common import smiles_to_fp
        fingerprint = smiles_to_fp('CCO')
        assert fingerprint.shape == (2048,) and fingerprint.dtype.name == 'bool'
        assert callable(RSPlanner.plan)
    elif name == 'mlp_retrosyn':
        import torch
        from mlp_retrosyn.mlp_inference import MLPModel
        from mlp_retrosyn.mlp_policies import RolloutPolicyNet, preprocess
        assert preprocess('CCO', 2048).shape == (2048,)
        model = RolloutPolicyNet(2).eval()
        with torch.no_grad():
            assert tuple(model(torch.zeros(1, 2048)).shape) == (1, 2)
        assert callable(MLPModel.run)
    else:
        from rdchiral.main import rdchiralRunText
        from rdchiral.initialization import rdchiralReactants
        assert rdchiralReactants('CCO') is not None and callable(rdchiralRunText)
elif name == 'graphviz':
    import graphviz
    version = graphviz.__version__
    graph = graphviz.Digraph(format='pdf')
    graph.edge('a', 'b')
    assert graph.pipe().startswith(b'%PDF-')
elif name == 'Graphviz':
    version = subprocess.check_output(['dpkg-query', '-W', '-f=${Version}', 'graphviz'], universal_newlines=True).strip()
    result = subprocess.run(['dot', '-Tpdf'], input=b'digraph { a -> b }', stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    assert result.stdout.startswith(b'%PDF-')
elif name == 'tqdm':
    import tqdm
    version = tqdm.__version__
    assert list(tqdm.tqdm([1], disable=True)) == [1]
else:
    raise AssertionError(name)
assert version == expected, (version, expected)
print(json.dumps({'version': version}))
