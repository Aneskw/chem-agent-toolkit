#!/usr/bin/env python3
import argparse, json
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--repo',required=True); p.add_argument('--checkpoint',required=True); a=p.parse_args()
repo=Path(a.repo); ckpt=Path(a.checkpoint)
missing=[]
if not repo.is_dir(): missing.append('repo')
if not ckpt.is_file(): missing.append('checkpoint')
if missing:
    print(json.dumps({'ok':False,'status':'blocked_resources','missing':missing,'repo':str(repo),'checkpoint':str(ckpt)})); raise SystemExit(2)
print(json.dumps({'ok':True,'status':'preflight_only','repo':str(repo),'checkpoint':str(ckpt)}))
