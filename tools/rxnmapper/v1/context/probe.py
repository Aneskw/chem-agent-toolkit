import ctypes
import importlib
import importlib.metadata as md
import inspect
import json
from pathlib import Path
import platform
import subprocess
import sys

name, expected = sys.argv[1:]
resources = {}
system = {
    'libx11-6': 'libX11.so.6', 'libxext6': 'libXext.so.6',
    'libxrender1': 'libXrender.so.1', 'libexpat1': 'libexpat.so.1',
    'libstdc++6': 'libstdc++.so.6', 'libgcc-s1': 'libgcc_s.so.1',
    'zlib1g': 'libz.so.1',
    'libquadmath0': 'libquadmath.so.0',
}
modules = {
    'rxn-chem-utils': 'rxn.chemutils.reaction_smiles',
    'rxn-utils': 'rxn.utilities.containers', 'rdkit': 'rdkit.Chem',
    'huggingface-hub': 'huggingface_hub', 'pyyaml': 'yaml',
    'typing-extensions': 'typing_extensions', 'python-dateutil': 'dateutil',
    'pillow': 'PIL.Image', 'hf-xet': 'hf_xet',
    'charset-normalizer': 'charset_normalizer', 'markupsafe': 'markupsafe',
    'pydantic-settings': 'pydantic_settings', 'pydantic-core': 'pydantic_core',
    'annotated-types': 'annotated_types', 'typing-inspection': 'typing_inspection',
    'python-dotenv': 'dotenv', 'dnspython': 'dns.resolver',
}
if name == 'Python':
    observed = platform.python_version()
    assert json.loads(json.dumps([1])) == [1]
elif name in system or name == 'gcc-14-base':
    observed = subprocess.check_output(['dpkg-query', '-W', '-f=${Version}', name], text=True)
    if name in system:
        ctypes.CDLL(system[name])
    else:
        assert Path('/usr/share/doc/gcc-14-base/copyright').read_bytes()
else:
    observed = md.version(name)
    if name == 'setuptools':
        import pkg_resources
        assert callable(pkg_resources.resource_filename)
    else:
        importlib.import_module(modules.get(name, name.replace('-', '_')))
    if name == 'numpy':
        import numpy as np
        assert np.dot([1, 2], [3, 4]) == 11
    elif name == 'scipy':
        from scipy.linalg import det
        assert abs(det([[2., 0.], [0., 3.]]) - 6) < 1e-10
    elif name == 'torch':
        import numpy as np
        import torch
        assert not torch.cuda.is_available()
        assert torch.from_numpy(np.ones(2)).sum().item() == 2
    elif name == 'rdkit':
        from rdkit import Chem
        assert Chem.MolFromSmiles('CCO').GetNumAtoms() == 3
    elif name == 'transformers':
        from transformers import AlbertModel, BertModel, RobertaModel, BertTokenizer
        assert all(callable(x) for x in (AlbertModel, BertModel, RobertaModel, BertTokenizer))
    elif name == 'rxn-chem-utils':
        from rxn.chemutils.reaction_smiles import parse_any_reaction_smiles, to_reaction_smiles, determine_format
        assert to_reaction_smiles(parse_any_reaction_smiles('CCO>>CCO'), determine_format('CCO>>CCO')) == 'CCO>>CCO'
    elif name == 'rxn-utils':
        from rxn.utilities.containers import chunker
        from rxn.utilities.types import RxnEnum
        from rxn.utilities.files import PathLike
        assert list(chunker(range(3), 2)) == [[0, 1], [2]]
    elif name == 'rxnmapper':
        import rxnmapper
        from rxnmapper import RXNMapper, BatchedMapper
        model_dir = Path(rxnmapper.__file__).parent / 'models/transformers/albert_heads_8_uspto_all_1310k'
        for filename in ('config.json', 'pytorch_model.bin', 'vocab.txt', 'special_tokens_map.json', 'tokenizer_config.json'):
            with (model_dir / filename).open('rb') as stream:
                assert stream.read(1), filename
        model = RXNMapper()
        assert model.device.type == 'cpu' and not model.model.training
        assert model.head == 5 and model.layers == [10] and model.attention_multiplier == 90.0
        assert model.model.config.max_position_embeddings == 512
        attention = model.convert_batch_to_attns(['CCO>>CCO'])
        assert len(attention) == 1 and attention[0].ndim == 2
        assert attention[0].shape[0] == attention[0].shape[1] > 1
        assert inspect.signature(BatchedMapper).parameters['canonicalize'].default is False
        assert callable(BatchedMapper.map_reactions_with_info)
        resources['rxnmapper-albert'] = True
assert observed == expected, (name, observed, expected)
result = {'version': observed}
if resources:
    result['resources'] = resources
print(json.dumps(result))
