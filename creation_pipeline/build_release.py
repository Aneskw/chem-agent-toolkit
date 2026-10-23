"""Create a new immutable source ZIP and sample ZIP; never overwrite releases."""
import argparse
import json
import re
from pathlib import Path
import shutil
import zipfile

from runtime_common import read, write, sha, files
import delivery

ROOT=Path(__file__).resolve().parent.parent


def copy_file(source,destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,destination)


def copy_tree(source,destination):
    shutil.copytree(source,destination,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git','.venv','node_modules'))


def zip_tree(source,target):
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(source.rglob('*')):
            if path.is_file():archive.write(path,Path(source.name)/path.relative_to(source))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version',required=True)
    p.add_argument('--run-id',required=True)
    p.add_argument('--regression',type=Path,required=True)
    args=p.parse_args()
    if any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._' for c in args.version):p.error('Unsafe version')
    name='chem-agent-toolkit-'+args.version
    output=ROOT/'deliverables'/name;archive=output.with_suffix('.zip') if '.' not in name else output.parent/(name+'.zip')
    sample_zip=output.parent/(name+'-example-skill.zip')
    if any(x.exists() for x in [output,archive,sample_zip]):p.error('Release already exists; use a new version')
    regression=read(args.regression)
    if regression.get('errors') or regression.get('failures') or regression.get('test_errors') or not regression.get('tests'):
        p.error('Passing mechanism regression report required')
    run=ROOT/'creation_pipeline/runs'/args.run_id
    candidates=sorted(x for x in (run/'drafts-v03').iterdir() if (x/'SKILL.md').exists())
    assessment=delivery.evaluate(candidates,len(candidates))
    if not assessment['delivery_accepted']:p.error('Current sample evidence is not accepted')
    output.mkdir(parents=True)
    # Explicit source/fixture selection; never copy the workspace wholesale.
    for path in (ROOT/'creation_pipeline').iterdir():
        if path.is_file() and (path.suffix in {'.py','.md'} or path.name=='requirements-runtime-model.txt'):
            copy_file(path,output/path.relative_to(ROOT))
    for folder in ['creation_pipeline/core','creation_pipeline/tests','creation_pipeline/examples']:
        copy_tree(ROOT/folder,output/folder)
    for path in (ROOT/'evaluation').rglob('*'):
        if path.is_file() and path.suffix in {'.py','.md'} and not any(part in {'runs','results','__pycache__'} for part in path.parts):
            copy_file(path,output/path.relative_to(ROOT))
    for name_ in ['papers.jsonl','repo_map.json']:
        path=ROOT/'creation_pipeline'/name_
        if path.exists():copy_file(path,output/'creation_pipeline'/name_)
    copy_tree(ROOT/'tools-skills/rdkit/chem-rdkit-descriptors',output/'tools-skills/rdkit/chem-rdkit-descriptors')
    copy_file(ROOT/'LICENSE',output/'LICENSE')
    sample=output/'examples/accepted-skill'
    sample.mkdir(parents=True)
    for candidate in candidates:copy_tree(candidate,sample/candidate.name)
    copy_tree(run,output/'evidence/runs'/args.run_id)
    copy_file(args.regression,output/'evidence/current-regression.json')
    regression_log=args.regression.with_suffix('.log')
    if regression_log.exists():copy_file(regression_log,output/'evidence/current-regression.log')
    origin=ROOT/'creation_pipeline/runs/delivery-r2-rdkit-live-01'
    if origin.exists():copy_tree(origin,output/'evidence/runs'/origin.name)
    for name_ in ['delivery-r2-text-live-01.json',args.run_id+'.json']:
        path=ROOT/'creation_pipeline/results'/name_
        if path.exists():copy_file(path,output/'evidence'/name_)
    for name_ in ['delivery-r2-regression.log','delivery-r2-final-targeted.log','delivery-r2-host-dependencies.txt',
                  'delivery-r2-portable-preflight.log','delivery-r2-rdkit-live-01.log','delivery-r2-rdkit-live-02.log','delivery-r2-publish-recovery.log']:
        path=ROOT/'reports'/name_
        if path.exists():copy_file(path,output/'evidence'/name_)
    published=ROOT/'skills/generated'/args.run_id/'PUBLISHING.json'
    if published.exists():copy_file(published,output/'evidence/PUBLISHING.json')
    execution=read(candidates[0]/'runtime/execution.json')
    summary={'release':args.version,'scope':'Requirement-aware engineering delivery; not scientific or agent-effect validation',
             'mechanism_regression':regression,'real_run_id':args.run_id,'delivery':assessment,
             'real_tool_tests':[{ 'tool_id':t['tool_id'],'image_id':t['image_id'],'cases':[
                 {'name':c['name'],'status':c['status'],'layer':c.get('layer')} for c in t['cases']]} for t in execution['tools']],
             'images_embedded':False,'final_zip_acceptance':'See sibling FINAL-ACCEPTANCE.json bound to final ZIP SHA-256',
             'publication_recovery':'Existing category target was backed up under validation/r2-prepublish-backup before explicit replacement; no extraction or rebuild during retry-publish.'}
    targeted=ROOT/'reports/delivery-r2-final-targeted.log'
    if targeted.exists():
        log=targeted.read_text(encoding='utf-8')
        match=re.search(r'Ran (\d+) tests',log)
        summary['additional_targeted_regression']={'tests':int(match[1]) if match else None,
            'passed':bool(re.search(r'^OK\s*$',log,re.M)), 'scope':'Final delivery and ZIP metadata migration changes; mocked model/engine'}
    write(output/'evidence/ACCEPTANCE.json',summary)
    write(output/'RELEASE.json',{'version':args.version,'delivery_version':delivery.VERSION,'runtime_acceptance_version':2,
          'images_embedded':False,'network_required_for_first_build':True,'entrypoint':'creation_pipeline/run_pipeline.py',
          'example':'examples/accepted-skill/'+candidates[0].name,
          'excludes':['credentials','virtual environments','unrelated caches','model weights','Docker image archives']})
    (output/'README.md').write_text('# Skill delivery '+args.version+'\n\n'
        'Start with [creation and delivery guide](creation_pipeline/DELIVERY.md). Default creation accepts each candidate according to its sourced tool requirement.\n\n'
        'The tested sample is in [examples/accepted-skill](examples/accepted-skill/README.md). '
        'This is a buildable runtime source package, NOT an exported Docker image. First build needs network.\n\n'
        'Run `python creation_pipeline/verify_release.py --tests` before modifying the package. '
        'For new host paths use the documented relocate_runtime.py command on a working copy. '
        'Historical evidence retains original absolute audit paths; relocation verifies bundled equivalent sources and creates fresh acceptance without those old paths.\n\n'
        'Optional literature collection needs its own documents and PDF/Git tools; independent resource-v2 research is outside this delivery. '
        'No credentials or machine-specific Python environment are bundled.\n',encoding='utf-8')
    image=execution['tools'][0]['image_id']
    (sample/'README.md').write_text('# Accepted RDKit example\n\n'
        f'Skill directory: `{candidates[0].name}`. See its SKILL.md, DOCKER.md and runtime/delivery.json.\n\n'
        'The sibling main source ZIP contains the full validator and byte-identical original tool sources/bindings. '
        'Use its relocate_runtime.py on a copy of this Skill to rebuild and rerun every locked test on a new host. '
        'Do not edit historical fingerprints or treat old absolute audit paths as current acceptance.\n\n'
        'No image tar is included. Image export/import (requires Docker and the image on the export host):\n\n'
        f'```sh\ndocker image save -o rdkit-image.tar {image}\ndocker image load -i rdkit-image.tar\n```\n\n'
        'A load alone is not fresh acceptance. Network is normally needed for a rebuild.\n',encoding='utf-8')
    write(output/'MANIFEST.json',{'algorithm':'sha256','files':files(output)})
    zip_tree(output,archive)
    zip_tree(sample,sample_zip)
    for path in [archive,sample_zip]:path.with_name(path.name+'.sha256').write_text(sha(path)+'  '+path.name+'\n',encoding='utf-8')
    print(json.dumps({'directory':str(output),'zip':str(archive),'sha256':sha(archive),
                      'example_zip':str(sample_zip),'example_sha256':sha(sample_zip)},indent=2))


if __name__=='__main__':main()
