import contextlib
import importlib
import importlib.metadata as md
import io
import json
import platform
import sys

name, expected = sys.argv[1:]
with contextlib.redirect_stdout(io.StringIO()):
    if name == 'Python':
        observed = platform.python_version()
        assert sys.version_info[:2] == (3, 11)
    else:
        observed = md.version(name)
        aliases = {'faiss-cpu': 'faiss', 'syntheseus-local-retro': 'local_retro', 'scikit-learn': 'sklearn', 'PyYAML': 'yaml', 'pyyaml': 'yaml', 'Pillow': 'PIL', 'pillow': 'PIL', 'python-dateutil': 'dateutil', 'typing-extensions': 'typing_extensions', 'more-itertools': 'more_itertools', 'markupsafe': 'markupsafe', 'pydantic-core': 'pydantic_core', 'typing-inspection': 'typing_inspection', 'charset-normalizer': 'charset_normalizer', 'threadpoolctl': 'threadpoolctl', 'annotated-types': 'annotated_types'}
        module = importlib.import_module(aliases.get(name, name.replace('-', '_')))
        if name == 'torch':
            import numpy as np
            assert module.version.cuda is None
            assert module.from_numpy(np.array([2.0], dtype=np.float32)).sum().item() == 2.0
        elif name == 'dgl':
            import torch
            import dgl.function as fn
            graph = module.graph(([0], [1]), num_nodes=2)
            graph.ndata['h'] = torch.tensor([[2.0], [0.0]])
            graph.update_all(fn.copy_u('h', 'm'), fn.sum('m', 'out'))
            assert graph.ndata['out'][1].item() == 2.0
        elif name == 'dgllife':
            from dgllife.utils import smiles_to_bigraph, WeaveAtomFeaturizer, CanonicalBondFeaturizer
            graph = smiles_to_bigraph('CC', node_featurizer=WeaveAtomFeaturizer(), edge_featurizer=CanonicalBondFeaturizer(self_loop=True), add_self_loop=True, canonical_atom_order=False)
            assert graph.num_nodes() == 2 and graph.ndata['h'].shape[0] == 2
        elif name == 'syntheseus':
            from syntheseus.interface.molecule import Molecule
            from syntheseus.reaction_prediction.inference.retro_knn import RetroKNNModel
            assert Molecule(smiles='CC').smiles == 'CC' and callable(RetroKNNModel)
        elif name == 'syntheseus-local-retro':
            from local_retro.scripts.utils import init_featurizer, load_model
            from local_retro.Retrosynthesis import load_templates
            assert init_featurizer({})['node_featurizer'].feat_size() > 0
            assert callable(load_model) and callable(load_templates)
        elif name == 'faiss-cpu':
            import tempfile
            import pathlib
            import torch
            import faiss.contrib.torch_utils
            assert module.__version__ == expected
            index = module.IndexFlatL2(2)
            vectors = torch.tensor([[0., 0.], [1., 0.]], dtype=torch.float32)
            index.add(vectors)
            with tempfile.TemporaryDirectory() as directory:
                path = pathlib.Path(directory) / 'index.faiss'
                module.write_index(index, str(path))
                index = module.read_index(str(path), module.IO_FLAG_ONDISK_SAME_DIR)
                distances, indices = index.search(vectors, 1)
                assert isinstance(distances, torch.Tensor)
                assert indices[:, 0].tolist() == [0, 1]
                assert distances.sum().item() == 0
        elif name == 'torch-scatter':
            import torch
            assert module.__version__ == expected
            source = torch.tensor([1., 2.])
            groups = torch.tensor([0, 0])
            assert module.scatter(source, groups).tolist() == [3.]
            assert module.scatter_max(source, groups)[0].tolist() == [2.]
        elif name == 'rdkit':
            from rdkit import Chem
            assert Chem.MolFromSmiles('CC').GetNumAtoms() == 2
        elif name == 'numpy':
            assert module.array([1, 2]).sum() == 3
            assert module.allclose(module.linalg.solve([[2.0]], [4.0]), [2.0])
        elif name == 'pandas':
            assert module.DataFrame({'a': [1]}).iloc[0, 0] == 1
        elif name == 'scipy':
            from scipy.linalg import solve
            assert solve([[2.0]], [4.0])[0] == 2.0
assert observed == expected, (name, observed, expected)
print(json.dumps({'version': observed}))
