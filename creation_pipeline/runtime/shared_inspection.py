"""Read-only observations of dependency environments, never skill qualification."""
import json
from pathlib import Path
import re

from creation_pipeline.contracts import fingerprint
from creation_pipeline.records import has_link, read_json, sanitized


def inspect_registry(root, *, offline=False, executor=None, probe=None):
    root=Path(root)
    if has_link(root):
        raise ValueError('Linked shared registry root')
    entries=[]
    if not root.exists():
        return {'status':'inspected','registry':str(root),'entries':entries,'counts':{},
                'qualification':'not_evaluated','mode':'offline' if offline else 'current'}
    from .local import LocalExecutor, process
    probe=probe or process
    host=None if offline else (executor or LocalExecutor()).host()
    names={p.stem for suffix in ('*.json','*.lock') for p in root.glob(suffix)
           if re.fullmatch(r'[a-f0-9]{64}',p.stem)}
    for key in sorted(names):
        row={'recipe_key':key,'locked':(root/(key+'.lock')).exists()}
        path=root/(key+'.json')
        if not path.exists():
            row['status']='pending_or_interrupted'
        else:
            try:
                if has_link(path):
                    raise ValueError('Linked entry')
                entry=read_json(path)
                recipe=entry['recipe']; image=entry['image_id']
                if (fingerprint(recipe)!=key or not isinstance(image,str)
                        or not re.fullmatch(r'sha256:[a-f0-9]{64}',image)):
                    raise ValueError('Invalid identity')
                row.update(image_id=image,platform=recipe['platform'],base=recipe['base'],
                           complete_rebuild_lock=entry.get('complete_rebuild_lock') is True)
                if offline:
                    row['status']='historical_unverified'
                elif host.get('status')!='available':
                    row['status']='host_unavailable'
                elif entry.get('daemon_id')!=host.get('engine_id'):
                    row['status']='different_daemon'
                else:
                    observation=probe(['docker','image','inspect',image],30)
                    details=json.loads(observation['stdout'])[0] if observation['exit_code']==0 else {}
                    row['status']=('available' if details.get('Id')==image
                        and details.get('Config',{}).get('Labels',{}).get('chem.shared.recipe')==key
                        and details.get('Os','')+'/'+details.get('Architecture','')==recipe['platform']
                        else 'image_unavailable_or_changed')
            except (OSError,ValueError,KeyError,IndexError,TypeError):
                row['status']='invalid_record'
        entries.append(row)
    counts={status:sum(e['status']==status for e in entries) for status in sorted({e['status'] for e in entries})}
    return sanitized({'status':'inspected','registry':str(root),'entries':entries,'counts':counts,
            'qualification':'not_evaluated','mode':'offline' if offline else 'current'})
