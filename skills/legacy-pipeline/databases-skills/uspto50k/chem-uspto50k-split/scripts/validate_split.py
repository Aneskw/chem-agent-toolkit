#!/usr/bin/env python3
"""Validate reaction_smiles columns and exact-text cross-split overlap."""
import argparse
import csv
import json
from pathlib import Path

def validate(root):
    root=Path(root); result={'ok':True,'root':str(root),'splits':{},'errors':[],
        'comparison':'exact stripped reaction_smiles text; no chemical canonicalization'}
    seen={}
    for split in ('train','valid','test'):
        file=root/(split+'.csv')
        if not file.is_file():
            result['errors'].append(f'{split}: missing split file');continue
        with file.open(newline='',encoding='utf-8-sig') as h:
            reader=csv.DictReader(h)
            if 'reaction_smiles' not in (reader.fieldnames or []):
                result['errors'].append(f'{split}: missing reaction_smiles column');continue
            values=[(r.get('reaction_smiles') or '').strip() for r in reader]
        empty=sum(not v for v in values)
        seen[split]={v for v in values if v}
        result['splits'][split]={'file':str(file),'rows':len(values),'empty_reactions':empty,
            'within_split_duplicates':len(values)-empty-len(seen[split])}
        if not values:result['errors'].append(f'{split}: no reaction rows')
        if empty:result['errors'].append(f'{split}: {empty} empty reaction values')
    overlap={}
    for left,right in (('train','valid'),('train','test'),('valid','test')):
        if left in seen and right in seen:overlap[left+'_'+right]=len(seen[left]&seen[right])
    result['overlap_rows']=overlap
    if any(overlap.values()):result['errors'].append('cross-split exact-text overlap')
    result['ok']=not result['errors']
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);a=p.parse_args()
    try:r=validate(a.root)
    except (OSError,UnicodeError,csv.Error) as e:r={'ok':False,'error':f'{type(e).__name__}: {e}'}
    print(json.dumps(r,ensure_ascii=False));return 0 if r['ok'] else 2

if __name__=='__main__':raise SystemExit(main())
