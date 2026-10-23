"""Rebind an unchanged portable package to equivalent local inputs, then revalidate.

Never retain acceptance when changing host paths. No model calls, no changed test
oracles, no tool-source edits. An unavailable or changed source fails before mutation.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import uuid

from runtime_common import read, write, sha, digest, artifacts
from candidate_identity import resolve
import runtime_model as planner
import runtime_docker
import delivery


def relocate(candidate, bindings):
    root=Path(candidate).resolve();bindings=Path(bindings).resolve()
    prepared=read(root/'runtime/prepared.json')
    execution_path=root/'runtime/execution.json'
    prior=read(execution_path) if execution_path.exists() else prepared
    if artifacts(root) != prior['artifacts']:
        raise ValueError('Package artifacts changed; relocation cannot bless drift')
    if execution_path.exists() and prior.get('prepared_sha256') != digest(prepared):
        raise ValueError('Preparation evidence changed')
    if sha(bindings) != prepared['bindings_sha256']:
        raise ValueError('Relocation requires byte-identical bindings; use explicit fresh preparation for changed inputs')
    settings=read(bindings)
    rule,association=resolve(settings,root,prepared['job_id'])
    if set(rule['tools']) != {t['tool_id'] for t in prepared['tools']}:
        raise ValueError('Binding selects different tools')
    updated=copy.deepcopy(prepared)
    from runtime_model_lifecycle import reset_observations, refresh_docs
    if execution_path.exists():
        updated['tools']=copy.deepcopy(prior['tools'])
    for tool in updated['tools']:
        source=(bindings.parent/settings['tools'][tool['tool_id']]['root']).resolve()
        inventory=planner.inventory(source,prepared['options'])
        if any(inventory[k] != tool['source_inventory'][k] for k in ('files','excluded')):
            raise ValueError('Relocated source inventory differs from locked source')
        tool['source_root']=str(source)
        tool.pop('pending_attempt',None)
        reset_observations(tool)
        tool['status']='prepared'
    requirement=delivery.determine(root,prepared['job_id'],bindings)
    if requirement.get('blocker'):raise ValueError(requirement['blocker'])
    metadata_entries=[]
    for metadata in root.glob('runtime/tools/*/context/.skillnet/source-metadata.json'):
        context=metadata.parent.parent.resolve()
        for name, expected in read(metadata).items():
            path=(context/name).resolve()
            if not path.is_relative_to(context) or path.is_symlink() or not path.is_file():
                raise ValueError('Unsafe/missing packaged source metadata path')
            metadata_entries.append((path,expected))
    # All external inputs have now been checked. Preserve the full old proof before
    # invalidating acceptance and changing path metadata; tests/contexts stay intact.
    archive=root/'reports/relocation'/uuid.uuid4().hex
    archive.mkdir(parents=True)
    for path in [root/'runtime/prepared.json',execution_path,root/'runtime/images.json',root/'delivery/requirement.json']:
        if path.exists():shutil.copyfile(path,archive/path.name)
    if execution_path.exists():execution_path.unlink()
    write(root/'runtime/images.json',{'schema_version':3,'tools':{}})
    # ZIP timestamps have lower precision than the existing runtime guard. All
    # content hashes and source inventories were checked above; restore recorded
    # metadata rather than relaxing that guard or rewriting its expected values.
    for path,expected in metadata_entries:
        path.chmod(expected['mode'])
        os.utime(path,ns=(path.stat().st_atime_ns,expected['mtime_ns']))
    updated.update(bindings_path=str(bindings),association=association,preparation_seconds=0,status='prepared')
    write(root/'delivery/requirement.json',requirement)
    refresh_docs(root,'prepared')
    if (root/'runtime/delivery.json').exists():
        metadata=read(root/'runtime/delivery.json');metadata['validation_status']='prepared'
        for tool in metadata.get('tools',{}).values():
            tool.update(accepted=False,image_id=None,save_argv=None,inspect_argv=None)
        write(root/'runtime/delivery.json',metadata)
    write(archive/'relocation.json',{'previous_bindings':prepared['bindings_path'],'new_bindings':str(bindings),
          'old_prepared_sha256':digest(prepared),'new_source_roots':[t['source_root'] for t in updated['tools']],
          'acceptance_retained':False,'locked_tests_unchanged':True,
          'restored_source_metadata_files':len(metadata_entries)})
    updated['artifacts']=artifacts(root)
    write(root/'runtime/prepared.json',updated)
    return updated


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate',type=Path);p.add_argument('--tool-bindings',type=Path,required=True)
    p.add_argument('--total-seconds',type=int,default=900)
    args=p.parse_args()
    if args.total_seconds<1:p.error('Budget must be positive')
    try:
        relocate(args.candidate,args.tool_bindings)
        # Portable revalidation never invokes the planner. Fail with the original
        # evidence if the fixed environment/tests cannot run on the new host.
        runtime_docker.validate(args.candidate,budget={'total_seconds':args.total_seconds,'max_attempts':1})
        report=delivery.evaluate([args.candidate],1)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        report={'delivery_accepted':False,'delivery_status':'blocked','error':str(exc)}
    print(json.dumps(report,ensure_ascii=True))
    return 0 if report['delivery_accepted'] else 2


if __name__=='__main__':raise SystemExit(main())
