"""Run one upstream stage in the isolated compatibility copy."""
import collections
import collections.abc
from pathlib import Path
import runpy
import sys

runtime=Path(sys.argv.pop(1)).resolve()
stage=sys.argv.pop(1)
sys.path[:0]=[str(runtime),str(runtime/'retroprime/transformer_model')]
for name in ['Mapping','MutableMapping','Sequence','Iterable']:
    if not hasattr(collections,name): setattr(collections,name,getattr(collections.abc,name))
if stage=='translate':
    import torch
    torch.set_num_threads(2)
    path=runtime/'retroprime/transformer_model/translate.py'
elif stage in ['evaluate','mix_c2c_top3_after_rerank','smi_tokenizer']:
    path=runtime/'retroprime/transformer_model/script'/f'{stage}.py'
else:
    raise ValueError('Unknown stage')
runpy.run_path(str(path),run_name='__main__')
