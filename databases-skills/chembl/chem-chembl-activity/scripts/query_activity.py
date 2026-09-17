#!/usr/bin/env python3
import argparse, json, ssl, urllib.parse, urllib.request
p=argparse.ArgumentParser(); g=p.add_mutually_exclusive_group(required=True); g.add_argument('--molecule-id'); g.add_argument('--target-id'); p.add_argument('--limit',type=int,default=20); a=p.parse_args()
if a.limit<1 or a.limit>1000: print(json.dumps({'ok':False,'error':'limit must be 1..1000'})); raise SystemExit(2)
key='molecule_chembl_id' if a.molecule_id else 'target_chembl_id'; val=a.molecule_id or a.target_id
q=urllib.parse.urlencode({key:val,'limit':a.limit,'format':'json'})
url='https://www.ebi.ac.uk/chembl/api/data/activity.json?'+q
try:
    req=urllib.request.Request(url,headers={'User-Agent':'chem-chembl-activity/0.1'})
    with urllib.request.urlopen(req,timeout=30,context=ssl.create_default_context(cafile='/etc/ssl/cert.pem')) as r: payload=json.load(r)
    acts=payload.get('activities',[])
    print(json.dumps({'ok':True,'query':{key:val,'limit':a.limit},'count':len(acts),'activities':acts,'source_url':url},ensure_ascii=False))
except Exception as e:
    print(json.dumps({'ok':False,'status':'network_or_api_error','error':f'{type(e).__name__}: {e}','source_url':url},ensure_ascii=False)); raise SystemExit(2)
