#!/usr/bin/env python3
import argparse, csv, json
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--root',required=True); a=p.parse_args(); root=Path(a.root)
summary={'ok':True,'root':str(root),'splits':{}}
seen={}; missing=[]
for split in ('train','valid','test'):
    f=root/(split+'.csv')
    if not f.is_file(): missing.append(str(f)); continue
    with f.open(newline='',encoding='utf-8') as h:
        rows=list(csv.DictReader(h))
    if 'reaction_smiles' not in (rows[0].keys() if rows else []):
        print(json.dumps({'ok':False,'status':'missing_required_column','file':str(f),'required':'reaction_smiles'})); raise SystemExit(2)
    vals=[r.get('reaction_smiles','') for r in rows]; seen[split]=set(vals)
    summary['splits'][split]={'file':str(f),'rows':len(rows),'empty_reactions':sum(not v for v in vals)}
if missing:
    print(json.dumps({'ok':False,'status':'missing_split_files','missing':missing,'partial':summary})); raise SystemExit(2)
overlap={}
for x,y in (('train','valid'),('train','test'),('valid','test')): overlap[f'{x}_{y}']=len(seen[x]&seen[y])
summary['overlap_rows']=overlap; summary['ok']=all(v==0 for v in overlap.values())
if not summary['ok']: summary['status']='split_overlap'
print(json.dumps(summary,ensure_ascii=False)); raise SystemExit(0 if summary['ok'] else 2)
