#!/usr/bin/env python3
"""Retrieve one explicitly bounded page of ChEMBL activity annotations."""
import argparse
from datetime import datetime, timezone
import json
import ssl
import urllib.parse
import urllib.request

def query_activity(molecule_id=None,target_id=None,limit=20,offset=0):
    if bool(molecule_id)==bool(target_id):raise ValueError('Provide exactly one molecule or target ID')
    if not 1<=limit<=1000 or offset<0:raise ValueError('limit must be 1..1000; offset must be nonnegative')
    key='molecule_chembl_id' if molecule_id else 'target_chembl_id'
    query={key:molecule_id or target_id,'limit':limit,'offset':offset,'format':'json'}
    url='https://www.ebi.ac.uk/chembl/api/data/activity.json?'+urllib.parse.urlencode(query)
    request=urllib.request.Request(url,headers={'User-Agent':'chem-chembl-activity/0.2'})
    with urllib.request.urlopen(request,timeout=30,context=ssl.create_default_context()) as response:
        payload=json.load(response)
    if not isinstance(payload.get('activities'),list) or not isinstance(payload.get('page_meta'),dict):
        raise ValueError('Unexpected ChEMBL response schema')
    return {'ok':True,'query':query,'count':len(payload['activities']),'activities':payload['activities'],
            'page_meta':payload['page_meta'],'source_url':url,
            'retrieved_at':datetime.now(timezone.utc).isoformat()}

def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--molecule-id');g.add_argument('--target-id')
    p.add_argument('--limit',type=int,default=20);p.add_argument('--offset',type=int,default=0)
    a=p.parse_args()
    try: result=query_activity(a.molecule_id,a.target_id,a.limit,a.offset)
    except Exception as e:result={'ok':False,'error':f'{type(e).__name__}: {e}'}
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result['ok'] else 2

if __name__=='__main__':raise SystemExit(main())
