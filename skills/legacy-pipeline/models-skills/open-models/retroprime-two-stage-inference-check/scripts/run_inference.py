#!/usr/bin/env python3
"""Launch the pinned RetroPrime stages using explicit checkpoint paths."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

TRANSFORMER='retroprime/transformer_model'
SCRIPTS=[TRANSFORMER+'/script/smi_tokenizer.py', TRANSFORMER+'/translate.py',
         TRANSFORMER+'/script/evaluate.py', TRANSFORMER+'/script/mix_c2c_top3_after_rerank.py']

def run(source_root,input_file,p2s,s2r,output_dir,target_python,beam=10,cores=8,gpu=0):
    source_root,input_file,p2s,s2r,output_dir=map(lambda p:Path(p).expanduser().resolve(),
        (source_root,input_file,p2s,s2r,output_dir))
    report={'status':'running','output_dir':str(output_dir),'completed_stages':[]}
    if beam<1 or cores<1 or gpu < -1:raise ValueError('beam/cores must be positive; gpu is -1 or nonnegative')
    if not source_root.is_dir():raise ValueError('Source root missing')
    for relative in SCRIPTS:
        if not (source_root/relative).is_file():raise ValueError('Missing full-checkout source: '+relative)
    for file in (input_file,p2s,s2r):
        if not file.is_file() or not file.stat().st_size:raise ValueError('Missing or empty input/checkpoint: '+str(file))
    lines=input_file.read_text(encoding='utf-8').splitlines()
    if not lines or any(not line.strip() for line in lines):raise ValueError('Input needs one nonempty product SMILES per line')
    if output_dir.exists() or not output_dir.parent.is_dir():raise ValueError('Use a new output directory with an existing parent')
    output_dir.mkdir()
    cache=output_dir/'cache';cache.mkdir()
    tokenized=output_dir/'canonical_token_for_input.txt'
    synthons=output_dir/'synthon_predicted.txt'
    stage2=output_dir/'to_synthon_tokenlized.txt'
    reactants=output_dir/'reactants_predicted.txt'
    mixed=output_dir/'reactants_predicted_mix.txt'
    def program(index,*args):return [str(target_python),str(source_root/SCRIPTS[index]),*map(str,args)]
    stages=[
      ('tokenize',program(0,'-input',input_file,'-output',tokenized),tokenized),
      ('p2s',program(1,'-gpu',gpu,'-model',p2s,'-src',tokenized,'-output',synthons,
         '-batch_size',64,'-replace_unk','-max_length',200,'-beam_size',beam,'-n_best',beam),synthons),
      ('prepare_s2r',program(2,'-beam_size',beam,'-src_file',tokenized,'-pre_file',synthons,
         '-save_rank_results_file',cache/'pre_synthons_rank.csv','-save_top',cache/'pre_synthons_top_results.csv',
         '-write_to_step2','-core',cores,'-step2_save_file',stage2),stage2),
      ('s2r',program(1,'-gpu',gpu,'-model',s2r,'-src',stage2,'-output',reactants,
         '-batch_size',64,'-replace_unk','-max_length',200,'-beam_size',beam,'-n_best',beam),reactants),
      ('rerank',program(3,'-pre_file',reactants,'-mix_save_file',mixed,'-beam_size',beam,'-core',cores),mixed),
    ]
    def digest(file):
        h=hashlib.sha256()
        with file.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        return h.hexdigest()
    report.update(input=str(input_file),input_rows=len(lines),input_sha256=digest(input_file),
                  checkpoints={'p2s':{'path':str(p2s),'sha256':digest(p2s)},'s2r':{'path':str(s2r),'sha256':digest(s2r)}},
                  beam=beam,cores=cores,gpu=gpu,source_root=str(source_root))
    environment=os.environ.copy()
    # Match upstream use of the selected visible GPU; -1 requests the translator's CPU mode.
    if gpu>=0:environment['CUDA_VISIBLE_DEVICES']=str(gpu)
    # With one visible GPU its process-local index is 0, irrespective of the physical selection.
    if gpu>0:
        for _,command,_ in stages:
            if '-gpu' in command:command[command.index('-gpu')+1]='0'
    try:
        for name,command,expected in stages:
            report['stage']=name
            log=output_dir/(name+'.log')
            with log.open('wb') as stream:
                result=subprocess.run(command,cwd=source_root,env=environment,stdout=stream,stderr=subprocess.STDOUT)
            if result.returncode:raise RuntimeError(f'{name} exited {result.returncode}; inspect {log}')
            if not expected.is_file():raise RuntimeError(f'{name} did not create {expected}')
            report['completed_stages'].append(name)
        report.update(status='completed',prediction_file=str(mixed),output_nonempty=bool(mixed.stat().st_size),
                      scope='Stage completion and file provenance, not prediction correctness')
    except (OSError,RuntimeError) as error:
        report.update(status='failed',error=str(error))
    (output_dir/'run.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('source-root','input','p2s','s2r','output-dir','python'):p.add_argument('--'+flag,required=True)
    p.add_argument('--beam',type=int,default=10);p.add_argument('--cores',type=int,default=8)
    p.add_argument('--gpu',type=int,default=0)
    a=p.parse_args()
    try:r=run(a.source_root,a.input,a.p2s,a.s2r,a.output_dir,a.python,a.beam,a.cores,a.gpu)
    except (OSError,ValueError) as error:r={'status':'failed','error':str(error)}
    print(json.dumps(r,ensure_ascii=False));return 0 if r['status']=='completed' else 2

if __name__=='__main__':raise SystemExit(main())
