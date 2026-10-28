#!/usr/bin/env python3
"""Query one PubChem compound, with explicit namespaces and JSON errors."""
import argparse
from datetime import datetime, timezone
import json
import ssl
import sys
import urllib.parse
import urllib.request

BASE='https://pubchem.ncbi.nlm.nih.gov/rest/pug'
PROPERTIES='ConnectivitySMILES,SMILES,MolecularFormula,MolecularWeight'

def query_pubchem(value, namespace='name'):
    value=str(value).strip()
    if namespace not in ('name','cid','inchikey','smiles') or not value:
        raise ValueError('Provide a nonempty query and supported namespace')
    if namespace=='cid' and (not value.isdigit() or int(value)<1):
        raise ValueError('cid requires one positive integer')
    if namespace=='smiles':
        url=f'{BASE}/compound/smiles/property/{PROPERTIES}/JSON'
        data=urllib.parse.urlencode({'smiles':value}).encode('utf-8')
    else:
        url=f'{BASE}/compound/{namespace}/{urllib.parse.quote(value,safe="")}/property/{PROPERTIES}/JSON'
        data=None
    request=urllib.request.Request(url,data=data,headers={'User-Agent':'chem-pubchem-query/0.2'})
    with urllib.request.urlopen(request,timeout=30,context=ssl.create_default_context()) as response:
        payload=json.load(response)
    rows=payload.get('PropertyTable',{}).get('Properties',[])
    common={'input':value,'namespace':namespace,'source_url':url,
            'retrieved_at':datetime.now(timezone.utc).isoformat()}
    if not rows or any('CID' not in row for row in rows):
        return {**common,'ok':False,'error':'No usable compound record returned'}
    if len(rows)!=1:
        return {**common,'ok':False,'error':'Ambiguous input; select a CID and query again',
                'matched_cids':[row['CID'] for row in rows]}
    row=rows[0]
    connectivity=row.get('ConnectivitySMILES') or row.get('CanonicalSMILES')
    return {**common,'ok':True,'cid':row['CID'],'properties':{
        'canonical_smiles':connectivity, 'connectivity_smiles':connectivity,
        'isomeric_smiles':row.get('SMILES') or row.get('IsomericSMILES'),
        'molecular_formula':row.get('MolecularFormula'),'molecular_weight':row.get('MolecularWeight')}}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--query',required=True)
    p.add_argument('--namespace',choices=['name','cid','inchikey','smiles'],default='name')
    p.add_argument('--output')
    args=p.parse_args()
    try: result=query_pubchem(args.query,args.namespace)
    except Exception as exc:
        result={'ok':False,'input':args.query,'namespace':args.namespace,'error':f'{type(exc).__name__}: {exc}'}
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        with open(args.output,'w',encoding='utf-8') as f:f.write(text)
    else:sys.stdout.write(text)
    return 0 if result['ok'] else 2

if __name__=='__main__':raise SystemExit(main())
