#!/usr/bin/env python3
import argparse, json
p=argparse.ArgumentParser(); p.add_argument('--platform', default='CPU'); a=p.parse_args()
try:
    import openmm
    from openmm import Platform
except Exception as e:
    print(json.dumps({'ok':False,'status':'blocked_resources','error':str(e)})); raise SystemExit(2)
platforms=[]
for i in range(Platform.getNumPlatforms()): platforms.append(Platform.getPlatform(i).getName())
if a.platform not in platforms:
    print(json.dumps({'ok':False,'status':'unsupported_platform','requested_platform':a.platform,'available_platforms':platforms})); raise SystemExit(2)
print(json.dumps({'ok':True,'openmm_version':openmm.__version__,'platform':a.platform,'available_platforms':platforms}))
