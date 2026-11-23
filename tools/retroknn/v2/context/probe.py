import contextlib, hashlib, importlib, io, json, os, pathlib, sys
root=pathlib.Path('/opt/localretro/src')
version=pathlib.Path('/opt/localretro/VERSION').read_text().strip()
assert version==sys.argv[1]
manifest=json.loads(pathlib.Path('/opt/localretro/installed-manifest.json').read_text())
assert manifest
for name,expected in manifest.items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected,name
config=json.loads((root/'data/configs/default_config.json').read_text())
assert config['activation']=='gelu' and config['attention_heads']==8
sys.argv=sys.argv[:1]
sys.path[:0]=[str(root/'scripts'),str(root/'preprocessing'),str(root)]
os.chdir(root/'scripts')
with contextlib.redirect_stdout(io.StringIO()):
    for name in ['Train','Test','Decode_predictions','Extract_from_train_data','Run_preprocessing']:
        importlib.import_module(name)
    from utils import init_featurizer
    from dgllife.utils import smiles_to_bigraph
    from models import LocalRetro_model
    import torch
    args=init_featurizer({})
    g=smiles_to_bigraph('CCO',add_self_loop=True,canonical_atom_order=False,node_featurizer=args['node_featurizer'],edge_featurizer=args['edge_featurizer'])
    model=LocalRetro_model(args['node_featurizer'].feat_size(),args['edge_featurizer'].feat_size(),16,8,1,2,1,2,2,activation='gelu').eval()
    with torch.no_grad():
        atoms,bonds,attention=model(g,g.ndata['h'],g.edata['e'])
    assert atoms.shape==(3,3) and bonds.shape==(4,3)
    assert torch.isfinite(atoms).all() and torch.isfinite(bonds).all()
print(json.dumps({'version':version,'resources':{'localretro-default-config':True}}))
