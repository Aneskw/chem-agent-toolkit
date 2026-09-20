#!/usr/bin/env python3
"""Pair any real PDF with a pinned Git snapshot; no catalog-specific adapters."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from ingest_sources import download
from core.creation_sources import read_documents


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], timeout=300)


def priority(path):
    low=path.lower()
    return (sum(word in low for word in ('predict','search','eval','test','template','preprocess','data','train')),
            low.endswith('.py'))


def pair(pdf, repo, out, ref='HEAD', files=None, max_files=16, paper_id='paper',
         title=None, clone_timeout=900):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,55}',paper_id):raise ValueError('Unsafe paper ID')
    if not 1<=max_files<=100:raise ValueError('max_files must be between 1 and 100')
    if clone_timeout<30:raise ValueError('clone_timeout must be at least 30 seconds')
    out=Path(out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    pdf_url=pdf if str(pdf).startswith(('https://','http://')) else ''
    if pdf_url:
        path,pdf_url,_=download(pdf_url,out,'paper')
    else:path=Path(pdf).resolve()
    if path.suffix.lower()!='.pdf' or not path.read_bytes().startswith(b'%PDF-'):
        raise ValueError('Supply/download an actual full-text PDF; renaming an abstract/HTML file is not conversion')
    pages=read_documents(path)
    pdf_dest=out/'paper.pdf'
    pdf_dest.write_bytes(path.read_bytes())
    source_repo=Path(repo).expanduser()
    if not source_repo.is_dir():
        if not (str(repo).startswith('https://') or str(repo).startswith('git@')):
            raise ValueError('Repository must be a local Git checkout or HTTPS/SSH Git URL')
        source_repo=out/'checkout'
        clone_command=['git','clone','--no-checkout','--filter=blob:none','--no-tags',
                       '--',str(repo),str(source_repo)]
        try:
            subprocess.run(clone_command,check=True,timeout=clone_timeout)
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired,OSError) as error:
            # The output directory was created by this invocation, so its
            # partial checkout is disposable and must not poison a retry.
            shutil.rmtree(source_repo,ignore_errors=True)
            raise RuntimeError(
                f'Git clone failed or timed out after {clone_timeout}s for {repo}; '
                'retry with --clone-timeout or provide a local checkout') from error
    # Read the chosen Git objects, never mutable working-tree bytes or scripts.
    commit=git(source_repo,'rev-parse','--verify',ref+'^{commit}').decode().strip()
    entries=[]
    for row in git(source_repo,'ls-tree','-r','-z',commit).split(b'\0'):
        if not row:continue
        info,name=row.split(b'\t',1);mode,kind,sha=info.decode().split()
        if kind=='blob' and mode!='120000':
            entries.append({'path':name.decode(),'type':'blob','sha':sha})
    inventory={entry['path']:entry for entry in entries}
    if files:
        selected=list(dict.fromkeys(files))
        if any(f not in inventory for f in selected):raise ValueError('Selected file absent at pinned commit')
    else:
        allowed=[p for p in inventory if Path(p).suffix.lower() in {'.py','.md','.sh','.rst','.txt'}
                 and not any(part in {'vendor','third_party','node_modules'} for part in Path(p).parts)]
        docs=[p for p in allowed if Path(p).name.lower().startswith(('readme','license'))][:2]
        selected=(docs+[p for p in sorted(allowed,key=lambda p:(-priority(p)[0],-priority(p)[1],p)) if p not in docs])[:max_files]
    source_root=out/'repo';source_root.mkdir()
    sources=[{'path':'paper.pdf','role':'paper','url':pdf_url,
              'sha256':hashlib.sha256(pdf_dest.read_bytes()).hexdigest()}]
    skipped=[]
    for relative in selected:
        p=Path(relative)
        if p.is_absolute() or '..' in p.parts:raise ValueError('Unsafe Git path')
        size=int(git(source_repo,'cat-file','-s',inventory[relative]['sha']))
        if size>1_000_000:
            skipped.append({'path':relative,'reason':'file exceeds 1 MB'});continue
        content=git(source_repo,'cat-file','blob',inventory[relative]['sha'])
        target=source_root/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
        sources.append({'path':'repo/'+relative,'role':'repo_code' if p.suffix in {'.py','.sh'} else 'repo_doc',
                        'url':'','sha256':hashlib.sha256(content).hexdigest()})
    try:
        origin=subprocess.check_output(
            ['git','-C',str(source_repo),'remote','get-url','origin'],
            timeout=120,stderr=subprocess.DEVNULL).decode().strip()
    except subprocess.CalledProcessError:origin=str(source_repo.resolve())
    slug=re.sub(r'^(?:https://github.com/|git@github.com:)','',origin).removesuffix('.git')
    manifest={'repo':slug,'commit':commit,'tree':entries}
    (out/'repo.json').write_text(json.dumps(manifest,indent=2)+'\n')
    job={'paper_id':paper_id,'title':title or Path(pdf).stem,'repo_root':'repo',
         'repo_manifest':'repo.json','sources':sources}
    config={'base':'.','schema_version':2,'max_context_chars':240000,'jobs':[job]}
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    report={'paper_id':paper_id,'pdf_sha256':sources[0]['sha256'],'pdf_pages':len(pages),
            'repository':origin,'commit':commit,'selection':'explicit' if files else 'filename_heuristic',
            'selected_files':[s['path'] for s in sources[1:]],'skipped':skipped,
            'unselected_files':[p for p in inventory if 'repo/'+p not in {s['path'] for s in sources[1:]}],
            'note':'Selection coverage is recorded; unselected code and PDF graphics are not reviewed.'}
    (out/'source_pair.json').write_text(json.dumps(report,indent=2)+'\n')
    return out/'config.json'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pdf',required=True);p.add_argument('--repo',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--ref',default='HEAD')
    p.add_argument('--file',action='append');p.add_argument('--max-files',type=int,default=16)
    p.add_argument('--paper-id',default='paper');p.add_argument('--title')
    p.add_argument('--clone-timeout',type=int,default=900,
                   help='Seconds allowed for a remote Git clone (default: 900)')
    a=p.parse_args()
    print(pair(a.pdf,a.repo,a.out,a.ref,a.file,a.max_files,a.paper_id,a.title,a.clone_timeout))

if __name__=='__main__':main()
