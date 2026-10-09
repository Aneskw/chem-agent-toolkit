#!/usr/bin/env python3
"""Resolve arbitrary public URLs/local documents into auditable extraction jobs."""
from __future__ import annotations
import argparse
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import ssl
import sqlite3
import sys
import zipfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from core.creation_sources import read_documents

SUPPORTED = {'.pdf','.md','.txt','.html','.htm','.xml','.json','.jsonl','.yaml','.yml',
             '.csv','.tsv','.sql','.sqlite','.sqlite3','.db','.docx','.rst','.ipynb','.py','.sh'}
PRIMARY = {'paper':'paper','database':'database_doc','tool':'tool_doc','model':'model_doc'}

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.pdf=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if tag=='meta' and d.get('name','').lower()=='citation_pdf_url':
            self.pdf.append(d.get('content',''))
        if tag=='a' and ('.pdf' in d.get('href','').lower() or '/download/' in d.get('href','')):
            self.pdf.append(d['href'])


def fetch(url):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Use an HTTP(S) URL without embedded credentials')
    context=ssl.create_default_context()
    if Path('/etc/ssl/cert.pem').exists():context.load_verify_locations('/etc/ssl/cert.pem')
    request=urllib.request.Request(url,headers={'User-Agent':'ChemSkillNet/1.0','Accept-Encoding':'identity'})
    with urllib.request.urlopen(request,context=context,timeout=35) as response:
        data=response.read(50_000_001); final=response.url; mime=response.headers.get_content_type()
    if len(data)>50_000_000:raise ValueError('Remote source exceeds 50 MB')
    if data.startswith(b'\x1f\x8b'):
        import io
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:data=stream.read(50_000_001)
        if len(data)>50_000_000:raise ValueError('Decompressed source exceeds 50 MB')
    return data,final,mime


def download(url, folder, source_type, visited=None):
    visited=set() if visited is None else visited
    if url in visited or len(visited)>=5:raise ValueError('No full text found within link limit')
    visited.add(url)
    data,final,mime=fetch(url)
    if data.startswith(b'%PDF-'):suffix='.pdf'
    elif 'html' in mime or b'<html' in data[:5000].lower() or b'<!doctype html' in data[:5000].lower():
        suffix='.html'
        html=data.decode('utf-8',errors='replace')
        from core.creation_sources import TextHTML
        parser=TextHTML();parser.feed(html);plain=''.join(parser.parts)
        if source_type!='paper' and len(plain.strip())<200:
            # Read literal linked spec URLs, never execute downloaded JS.
            specs=re.findall(r'''(?:spore\.create\(\s*|\burl\s*:\s*)["']([^"']+)["']''',html)
            specs += re.findall(r'''href=["']([^"']+(?:\.json|\.yaml|\.yml))["']''',html,re.I)
            for spec in dict.fromkeys(specs):
                try:return download(urllib.parse.urljoin(final,spec),folder,source_type,visited)
                except (OSError,ValueError):pass
            raise ValueError('JavaScript-only/empty documentation: supply OpenAPI/schema or a text export')
        # For papers follow explicit publisher PDF links before accepting HTML.
        if source_type=='paper':
            links=Links();links.feed(html)
            for href in dict.fromkeys(links.pdf):
                try:return download(urllib.parse.urljoin(final,href),folder,source_type,visited)
                except (OSError,ValueError):pass
            # Full article HTML needs body structure and substantive content;
            # this is a screening heuristic, not a scientific validation.
            if len(plain)<12000 or not re.search(r'(methods|methodology|results|discussion|conclusion)',plain,re.I):
                raise ValueError('Landing/abstract page: supply the full PDF or article body')
        if re.search(r'<title>[^<]*(just a moment|access denied|verify|captcha)',html,re.I):
            raise ValueError('Access challenge page, not source material')
    elif 'json' in mime:suffix='.json'
    elif 'xml' in mime:suffix='.xml'
    else:
        suffix=Path(urllib.parse.urlsplit(final).path).suffix.lower()
        if suffix not in SUPPORTED:
            if mime.startswith('text/'):suffix='.txt'
            else:raise ValueError('Unsupported remote content type: '+mime)
    digest=hashlib.sha256(data).hexdigest()
    path=folder/(digest[:16]+suffix);path.write_bytes(data)
    return path,final,digest


def split_text(text, limit):
    # Never silently discard a long page or a single oversized line.
    chunks=[]; current=''
    for line in text.splitlines(keepends=True):
        while len(line)>limit:
            if current:chunks.append(current);current=''
            chunks.append(line[:limit]);line=line[limit:]
        if len(current)+len(line)>limit:
            chunks.append(current);current=''
        current+=line
    if current:chunks.append(current)
    return chunks


def prepare(items, base, out, max_chars=80000):
    if max_chars<2000:raise ValueError('max_context_chars must be at least 2000')
    out.mkdir(parents=True,exist_ok=False)
    downloads=out/'downloads';downloads.mkdir()
    normalized=out/'normalized';normalized.mkdir()
    jobs=[];report=[]; ids=set()
    for index,item in enumerate(items,1):
        kind=item.get('source_type','paper')
        record={'id':item.get('id',item.get('paper_id',f'source-{index:03d}')),'status':'pending','sources':[]}
        try:
            ident=str(record['id'])
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,55}',ident) or ident in ids:
                raise ValueError('IDs must be unique, safe, and at most 55 characters')
            ids.add(ident)
            if kind not in PRIMARY:raise ValueError('source_type must be paper/database/tool/model')
            inputs=item.get('sources') or [{k:item[k] for k in ('path','url','role') if k in item}]
            parts=[];character_count=0
            for number,src in enumerate(inputs,1):
                if 'path' in src:
                    path=(base/src['path']).resolve();url=src.get('url','')
                    if path.stat().st_size>50_000_000:raise ValueError('Source exceeds 50 MB')
                    digest=hashlib.sha256(path.read_bytes()).hexdigest()
                else:path,url,digest=download(src['url'],downloads,kind)
                docs=read_documents(path)
                if path.suffix.lower() in {'.html','.htm'} and sum(len(t) for _,t in docs)<200:
                    raise ValueError('HTML documentation lacks substantive text; provide API/schema export')
                if kind=='paper' and path.suffix.lower() in {'.html','.htm'}:
                    plain='\n'.join(t for _,t in docs)
                    if len(plain)<12000 or not re.search(r'(methods|methodology|results|discussion|conclusion)',plain,re.I):
                        raise ValueError('Local HTML is a landing/abstract page; supply full article text')
                role=src.get('role',PRIMARY[kind])
                # Raw table rows alone cannot establish a documented procedure.
                if path.suffix.lower() in {'.csv','.tsv'} and 'role' not in src:role='metadata'
                source_info={'path':str(path),'url':url,'sha256':digest,'role':role,'pages':len(docs),'segments':[]}
                for page,text in docs:
                    character_count+=len(text)
                    for n,chunk in enumerate(split_text(text,max_chars-200),1):
                        name=f'{ident}-s{number}-p{page or 0}-c{n}.txt'
                        dest=normalized/name;dest.write_text(chunk,encoding='utf-8')
                        source_info['segments'].append({'path':str(dest.resolve()),'page':page,'part':n,'characters':len(chunk)})
                        parts.append({'path':str(dest.resolve()),'role':role,'url':url,
                                      'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'size':len(chunk),
                                      'origin':{'path':str(path),'sha256':digest,'page':page,'part':n}})
                record['sources'].append(source_info)
            if not parts:raise ValueError('No extractable source text; scanned PDFs require OCR')
            if not any(p['role']==PRIMARY[kind] for p in parts):
                raise ValueError('Primary documentation missing; add documentation alongside raw data')
            # Cover every section with separate jobs instead of dropping text at
            # a context limit. Cross-segment reasoning is not claimed here.
            groups=[];group=[];size=0
            for part in parts:
                if group and size+part['size']>max_chars:
                    groups.append(group);group=[];size=0
                size+=part['size'];group.append(part)
            if group:groups.append(group)
            queued=0
            for n,group in enumerate(groups,1):
                # metadata-only segments are retained in the provenance report;
                # they are not turned into primary evidence by role relabelling.
                if not any(p['role']==PRIMARY[kind] for p in group):continue
                job={'paper_id':f'{ident}-part{n:03d}','title':item.get('title',ident),
                     'source_type':kind,'sources':[{k:v for k,v in p.items() if k!='size'} for p in group]}
                jobs.append(job)
                queued+=1
            record.update(status='prepared',text_characters=character_count,segments=len(parts),jobs=queued,
                          metadata_only_groups_not_queued=len(groups)-queued)
        except (OSError,ValueError,KeyError,sqlite3.DatabaseError,zipfile.BadZipFile) as error:
            record.update(status='source_error',error=str(error))
        report.append(record)
    manifest={'max_context_chars':max_chars,'jobs':jobs}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (out/'ingestion_report.json').write_text(json.dumps({'created_at':datetime.now(timezone.utc).isoformat(),
        'items':report,'prepared_jobs':len(jobs),'scope':'Source ingestion only; no utility claims'},ensure_ascii=False,indent=2)+'\n')
    return manifest,report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',action='append',help='Local document, directory, or public URL; repeatable')
    p.add_argument('--catalog',type=Path,help='JSON with items[] or jobs[] including sources')
    p.add_argument('--source-type',choices=list(PRIMARY),default='paper')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--max-context-chars',type=int,default=80000)
    a=p.parse_args()
    if bool(a.input)==bool(a.catalog):p.error('Use --input or --catalog')
    if a.catalog:
        data=json.loads(a.catalog.read_text());items=data.get('items',data.get('jobs',[]))
        base=a.catalog.resolve().parent
    else:
        items=[];base=Path.cwd()
        for value in a.input:
            if value.startswith(('https://','http://')):
                items.append({'url':value,'source_type':a.source_type})
            else:
                path=Path(value).resolve()
                paths=sorted(p for p in path.rglob('*') if p.suffix.lower() in SUPPORTED and p.is_file()) if path.is_dir() else [path]
                items.extend({'path':str(p),'title':p.stem,'source_type':a.source_type} for p in paths)
    if not items:p.error('No sources found')
    manifest,report=prepare(items,base,a.out.resolve(),a.max_context_chars)
    print(json.dumps({'manifest':str(a.out.resolve()/'manifest.json'),'jobs':len(manifest['jobs']),
                      'failed_sources':sum(r['status']=='source_error' for r in report)}))
    return 0 if manifest['jobs'] else 1


if __name__=='__main__':
    raise SystemExit(main())
