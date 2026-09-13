"""Run pinned RetroPrime P2S and S2R models on CPU; emit one JSON result."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

def prepare_runtime(source, runtime, manifest):
    for name,digest in manifest['files'].items():
        file=(source/name).resolve()
        if not file.is_relative_to(source) or not file.is_file(): raise ValueError('Missing resource: '+name)
        if hashlib.sha256(file.read_bytes()).hexdigest()!=digest: raise ValueError('Resource hash mismatch: '+name)
        if name.endswith('.py'):
            target=runtime/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
    edits=[('retroprime/transformer_model/onmt/translate/beam.py','prev_k = best_scores_id / num_words',
            "prev_k = torch.div(best_scores_id, num_words, rounding_mode='floor')")]
    for file in ['evaluate.py','mix_c2c_top3_after_rerank.py']:
        edits.append(('retroprime/transformer_model/script/'+file,'from multiprocessing import Pool','from retroprime_serial import Pool'))
    for name,before,after in edits:
        p=runtime/name;content=p.read_text()
        if content.count(before)!=1: raise ValueError('Compatibility patch context differs: '+name)
        p.write_text(content.replace(before,after))
    (runtime/'retroprime_serial.py').write_text('class Pool:\n    def __init__(self, *args, **kwargs): pass\n    def imap_unordered(self, fn, tasks): return map(fn, tasks)\n')

def predict(product, top_k, source, workspace, manifest):
    from rdkit import Chem
    if not 1<=top_k<=10: raise ValueError('top_k must be between 1 and 10; beam size is fixed at 10')
    mol=Chem.MolFromSmiles(product) if product.strip() else None
    if mol is None: raise ValueError('Invalid product SMILES')
    if len(Chem.GetMolFrags(mol))!=1 or mol.GetNumBonds()==0:
        raise ValueError('This wrapper requires one connected product containing at least one bond')
    for atom in mol.GetAtoms(): atom.SetAtomMapNum(0)
    canonical=Chem.MolToSmiles(mol)
    runtime=workspace/'runtime';runtime.mkdir()
    prepare_runtime(source,runtime,manifest)
    (workspace/'input.txt').write_text(canonical+'\n')
    stage_runner=Path(__file__).with_name('retroprime_stage.py')
    completed=[]
    def stage(name,arguments):
        started=time.monotonic()
        process=subprocess.run([sys.executable,str(stage_runner),str(runtime),name,*map(str,arguments)],
                               capture_output=True,text=True,timeout=180)
        (workspace/(f'{len(completed)+1:02d}-'+name+'.log')).write_text(process.stdout+'\n'+process.stderr)
        if process.returncode!=0: raise RuntimeError(name+' failed: '+(process.stderr or process.stdout)[-1500:])
        completed.append({'stage':name,'seconds':round(time.monotonic()-started,3)})
    tokens=workspace/'tokens.txt';p2s=workspace/'p2s.txt';bridge=workspace/'s2r_input.txt';s2r=workspace/'s2r.txt';final=workspace/'final.txt'
    stage('smi_tokenizer',['-input',workspace/'input.txt','-output',tokens])
    def translate(model,input_file,output_file):
        stage('translate',['-gpu','-1','-model',source/model,'-src',input_file,'-output',output_file,
                           '-batch_size','1','-replace_unk','-max_length','200','-beam_size','10','-n_best','10'])
    translate(manifest['p2s_model'],tokens,p2s)
    stage('evaluate',['-beam_size','10','-src_file',tokens,'-pre_file',p2s,'-save_rank_results_file',workspace/'marked.csv',
                      '-save_top',workspace/'marked_top.csv','-write_to_step2','-core','1','-step2_save_file',bridge])
    bridge_lines=bridge.read_text().splitlines()
    if len(bridge_lines)!=3 or not any(line.strip() and line.strip()!='.' for line in bridge_lines):
        raise RuntimeError('P2S produced no usable intermediate representations')
    translate(manifest['s2r_model'],bridge,s2r)
    stage('mix_c2c_top3_after_rerank',['-pre_file',s2r,'-mix_save_file',final,'-beam_size','10','-core','1'])
    seen={canonical};candidates=[]
    for raw_rank,line in enumerate(final.read_text().splitlines(),1):
        candidate=Chem.MolFromSmiles(line) if line.strip() else None
        if candidate is None: continue
        text=Chem.MolToSmiles(candidate)
        if text in seen: continue
        seen.add(text)
        candidates.append({'rank':len(candidates)+1,'reactants_smiles':text,'upstream_mixed_position':raw_rank})
        if len(candidates)>=top_k:break
    if not candidates: raise RuntimeError('No valid non-placeholder candidates')
    return {'ok':True,'product_smiles':canonical,'candidate_count':len(candidates),'candidates':candidates,
            'requested_top_k':top_k,'beam_size':10,'device':'cpu','commit':manifest['commit'],
            'weight_sha256':{k:manifest['files'][manifest[k]] for k in ['p2s_model','s2r_model']},
            'stages':completed,'note':'Upstream mixed ordering with empty/invalid/duplicate outputs removed; no calibrated probability is supplied.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--product',required=True)
    parser.add_argument('--top-k',type=int,default=10)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args();start=time.monotonic()
    try:
        manifest=json.loads(Path(__file__).with_name('inference_manifest.json').read_text())
        if args.output_dir:
            args.output_dir.mkdir(parents=True,exist_ok=False)
            result=predict(args.product,args.top_k,args.source_root.resolve(),args.output_dir.resolve(),manifest)
            result['output_dir']=str(args.output_dir.resolve())
        else:
            with tempfile.TemporaryDirectory(prefix='chemskillnet-retroprime-') as folder:
                result=predict(args.product,args.top_k,args.source_root.resolve(),Path(folder),manifest)
        result['elapsed_seconds']=round(time.monotonic()-start,3)
        print(json.dumps(result,ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'ok':False,'error':str(error),'error_type':type(error).__name__},ensure_ascii=False))
        raise SystemExit(2)
