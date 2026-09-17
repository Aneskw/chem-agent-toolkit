#!/usr/bin/env python3
import argparse, json, os
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--receptor',required=True); p.add_argument('--ligand',required=True); p.add_argument('--endpoint',default=os.getenv('DIFFDOCK_ENDPOINT','')); a=p.parse_args()
missing=[]
if not Path(a.receptor).is_file(): missing.append('receptor')
if not Path(a.ligand).is_file(): missing.append('ligand')
if not a.endpoint: missing.append('endpoint')
if missing:
    print(json.dumps({'ok':False,'status':'blocked_resources','missing':missing})); raise SystemExit(2)
print(json.dumps({'ok':True,'status':'preflight_only','receptor':a.receptor,'ligand':a.ligand,'endpoint':a.endpoint}))
