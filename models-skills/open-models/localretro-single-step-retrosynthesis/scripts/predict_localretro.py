"""CPU LocalRetro inference using pinned source, templates and weights."""
import argparse
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

def predict(product, top_k, source_root, manifest):
    from rdkit import Chem
    if not 1 <= top_k <= 100:
        raise ValueError('top_k must be between 1 and 100')
    mol=Chem.MolFromSmiles(product) if product.strip() else None
    if mol is None: raise ValueError('Invalid product SMILES')
    if len(Chem.GetMolFrags(mol))!=1 or mol.GetNumBonds()==0:
        raise ValueError('This wrapper requires one connected product containing at least one bond')
    for atom in mol.GetAtoms(): atom.SetAtomMapNum(0)
    canonical=Chem.MolToSmiles(mol)
    for relative,digest in manifest['files'].items():
        file=(source_root/relative).resolve()
        if not file.is_relative_to(source_root) or not file.is_file():
            raise ValueError('Missing pinned resource: '+relative)
        if hashlib.sha256(file.read_bytes()).hexdigest()!=digest:
            raise ValueError('Resource hash mismatch: '+relative)
    os.environ['DGLBACKEND']='pytorch'
    sys.path[:0]=[str(source_root),str(source_root/'scripts')]
    import torch
    import Retrosynthesis as upstream
    from scripts.utils import get_configure
    from models import LocalRetro_model

    # Equivalent model construction to scripts/utils.py, with tensor-only loading.
    def load_model(args):
        cfg=get_configure(args)
        model=LocalRetro_model(node_in_feats=cfg['in_node_feats'],edge_in_feats=cfg['in_edge_feats'],
            node_out_feats=cfg['node_out_feats'],edge_hidden_feats=cfg['edge_hidden_feats'],
            num_step_message_passing=cfg['num_step_message_passing'],attention_heads=cfg['attention_heads'],
            attention_layers=cfg['attention_layers'],AtomTemplate_n=cfg['AtomTemplate_n'],
            BondTemplate_n=cfg['BondTemplate_n'],activation=cfg.get('activation','relu'))
        checkpoint=torch.load(args['model_path'],map_location='cpu',weights_only=True)
        model.load_state_dict(checkpoint['model_state_dict'],strict=True)
        return model.to('cpu')

    upstream.load_model=load_model
    torch.set_num_threads(2)
    args={'data_dir':str(source_root/'data/USPTO_50K'),
          'model_path':str(source_root/'models/LocalRetro_USPTO_50K.pth'),
          'config_path':str(source_root/'data/configs/default_config.json'),
          'device':torch.device('cpu')}
    model=upstream.LocalRetro(args)
    table=model.retrosnythesis(canonical,top_k=top_k)
    candidates=[]
    seen={canonical}
    for _,row in table.iloc[1:].iterrows():
        candidate=Chem.MolFromSmiles(row['SMILES'])
        if candidate is None: continue
        normalized=Chem.MolToSmiles(candidate)
        if normalized in seen: continue
        score=float(row['Score'])
        if not math.isfinite(score): continue
        seen.add(normalized)
        candidates.append({'rank':len(candidates)+1,'reactants_smiles':normalized,
                           'model_score':score,'local_template':row['Local reaction template']})
    if not candidates: raise ValueError('Model produced no valid non-placeholder candidates')
    return {'ok':True,'product_smiles':canonical,'requested_edit_candidates':top_k,
            'candidate_count':len(candidates),'candidates':candidates,'device':'cpu',
            'commit':manifest['commit'],'model_sha256':manifest['files']['models/LocalRetro_USPTO_50K.pth'],
            'note':'Scores are model scores, not experimental success probabilities. Candidate count may be below top_k.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--product',required=True)
    parser.add_argument('--top-k',type=int,default=10)
    parser.add_argument('--source-root',type=Path,required=True)
    args=parser.parse_args()
    start=time.monotonic()
    try:
        manifest=json.loads(Path(__file__).with_name('inference_manifest.json').read_text())
        with contextlib.redirect_stdout(sys.stderr):
            result=predict(args.product,args.top_k,args.source_root.resolve(),manifest)
        result['elapsed_seconds']=round(time.monotonic()-start,3)
        print(json.dumps(result,ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'ok':False,'error':str(error),'error_type':type(error).__name__},ensure_ascii=False))
        raise SystemExit(2)
