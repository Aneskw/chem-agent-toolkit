#!/usr/bin/env python3
import argparse, json, shutil
p=argparse.ArgumentParser(); p.add_argument('--config',required=True); a=p.parse_args()
if not shutil.which('reinvent'):
    print(json.dumps({'ok':False,'status':'blocked_resources','error':'reinvent executable not found','config':a.config})); raise SystemExit(2)
print(json.dumps({'ok':True,'status':'preflight_only','config':a.config,'executable':shutil.which('reinvent')}))
