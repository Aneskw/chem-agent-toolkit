"""Read selected local paper/repository materials; never execute repository code."""
import hashlib
from html.parser import HTMLParser
import json
import os
import textwrap
import csv
import io
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

class TextHTML(HTMLParser):
    def __init__(self):super().__init__();self.skip=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ['script','style']:self.skip+=1
        if tag in ['p','div','h1','h2','h3','li','br','section']:self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ['script','style']:self.skip=max(0,self.skip-1)
        if tag in ['p','div','h1','h2','h3','li','section']:self.parts.append('\n')
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)

def read_documents(path):
    path=Path(path)
    if path.suffix.lower() in {'.sqlite','.sqlite3','.db'}:
        # Schema only: opening read-only cannot mutate the database, and no
        # data rows or SQL functions from the source are executed.
        # sqlite3.Connection's context manager commits/rolls back, but does
        # not close the file handle.  Close explicitly so Windows can remove
        # temporary database files immediately after schema extraction.
        conn=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
        try:
            rows=conn.execute("SELECT type,name,sql FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        finally:
            conn.close()
        return [(None,'SQLite schema snapshot (no data rows):\n'+ '\n\n'.join(str(sql) for _,_,sql in rows if sql))]
    if path.suffix.lower()=='.docx':
        with zipfile.ZipFile(path) as archive:
            info=archive.getinfo('word/document.xml')
            if info.file_size>5_000_000:raise ValueError('DOCX text exceeds 5 MB')
            tree=ET.fromstring(archive.read(info))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        return [(None,'\n'.join(''.join(p.itertext()) for p in tree.findall('.//w:p',ns)))]
    if path.suffix.lower() in {'.csv','.tsv'}:
        if path.stat().st_size>5_000_000:raise ValueError('Tabular source exceeds 5 MB; provide a schema/data dictionary')
        rows=list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig')),delimiter='\t' if path.suffix.lower()=='.tsv' else ','))
        return [(None,'Tabular export; values are evidence, not procedural instructions.\n'+'\n'.join(json.dumps(row,ensure_ascii=False) for row in rows))]
    if path.suffix.lower()=='.xml':
        if path.stat().st_size>5_000_000:raise ValueError('XML exceeds 5 MB limit')
        try:tree=ET.parse(path).getroot()
        except ET.ParseError as error:raise ValueError('Invalid article XML') from error
        for node in tree.iter():node.tag=node.tag.rsplit('}',1)[-1]
        if tree.tag!='article':
            return [(None,ET.tostring(tree,encoding='unicode'))]
        if tree.find('body') is None:raise ValueError('JATS article lacks a full-text body')
        parts=[]
        title=tree.find('.//article-title')
        if title is not None:parts.append('TITLE: '+' '.join(''.join(title.itertext()).split()))
        for node in tree.find('body').iter():
            if node.tag in ['title','p']:
                text=' '.join(''.join(node.itertext()).split())
                if text:parts.append(textwrap.fill(text,width=120,break_long_words=False,break_on_hyphens=False))
        return [(None,'\n\n'.join(parts))]
    if path.suffix.lower()=='.ipynb':
        if path.stat().st_size>5_000_000:raise ValueError('Notebook exceeds 5 MB limit')
        notebook=json.loads(path.read_text())
        parts=[]
        for i,cell in enumerate(notebook['cells'],1):
            if cell.get('cell_type') in ['code','markdown']:
                source=cell.get('source',[])
                parts.append(f'--- cell {i} ({cell["cell_type"]}) ---\n'+(''.join(source) if isinstance(source,list) else source))
        return [(None,'\n\n'.join(parts))]
    if path.suffix.lower()=='.pdf':
        try:from pypdf import PdfReader
        except ImportError:raise ValueError('PDF text extraction requires pypdf; text/Markdown/HTML need no extra package')
        pages=[(page.extract_text() or '').strip() for page in PdfReader(path).pages]
        if not any(pages):raise ValueError('PDF has no extractable text; OCR required')
        return [(i+1,text) for i,text in enumerate(pages) if text]
    if path.suffix.lower() not in ['.txt','.md','.py','.sh','.json','.jsonl','.yaml','.yml','.sql','.rst','.html','.htm','.xml']:
        raise ValueError('Unsupported source format: '+path.suffix)
    if path.stat().st_size>5_000_000:raise ValueError('Source exceeds 5 MB text limit')
    text=path.read_text(encoding='utf-8-sig')
    if 'recaptcha/chall' in text[:1500]:raise ValueError('Verification page is not paper content')
    if path.suffix.lower() in ['.html','.htm']:
        parser=TextHTML();parser.feed(text)
        text='\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())
    return [(None,text)]

def make_bundle(job,base,max_chars=80000):
    root=(base/job.get('repo_root','.')).resolve()
    if not root.is_dir():raise ValueError('Source root does not exist')
    if job.get('repo_manifest'):
        meta=json.loads((base/job['repo_manifest']).read_text())
        files=[x['path'] for x in meta['tree'] if x['type']=='blob']
        commit=meta['commit'];repo_url='https://github.com/'+meta['repo']
    elif job.get('repo_root'):
        files=[]
        for current,dirs,names in os.walk(root):
            dirs[:]=[d for d in dirs if d not in ['.git','.venv','venv','node_modules','__pycache__']]
            files.extend((Path(current)/name).relative_to(root).as_posix() for name in names)
            if len(files)>10000:raise ValueError('Repository inventory too large; provide a manifest')
        commit=job.get('commit','unversioned');repo_url=job.get('repo_url','')
    else:
        files=[];commit=job.get('commit','not_applicable');repo_url=''
    sources=[];used=0;omitted=[]
    for index,item in enumerate(job['sources']):
        if item['role'] not in ['paper','repo_doc','repo_code','database_doc','tool_doc','model_doc','metadata']:raise ValueError('Unknown source role')
        path=(base/item['path']).resolve()
        if path.stat().st_size>50_000_000:raise ValueError('Source exceeds 50 MB limit')
        data_hash=hashlib.sha256(path.read_bytes()).hexdigest()
        if item.get('sha256') and item['sha256']!=data_hash:
            raise ValueError('Source differs from declared SHA-256: '+item['path'])
        if job.get('repo_manifest') and item['role'] in ['repo_doc','repo_code']:
            try:relative=path.relative_to(root).as_posix()
            except ValueError:raise ValueError('Repository source must be inside repo_root')
            expected=next((x['sha'] for x in meta['tree'] if x['path']==relative and x['type']=='blob'),None)
            blob=path.read_bytes()
            actual=hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest()
            if actual!=expected:raise ValueError('Repository source differs from recorded Git blob: '+relative)
        for page,text in read_documents(path):
            lines=text.splitlines()
            if not lines:continue
            if used+len(text)>max_chars:
                omitted.append({'path':str(path),'page':page,'reason':'context_budget'});continue
            used+=len(text)
            source_id=f's{index+1}'+(f'p{page}' if page else '')
            source={'id':source_id,'role':item['role'],'path':str(path),'page':page,'sha256':data_hash,
                    'url':item.get('url',''),'lines':lines}
            if item.get('origin'):source['origin']=item['origin']
            sources.append(source)
    if not sources:raise ValueError('No usable sources within context budget')
    source_type=job.get('source_type','paper')
    if source_type not in ['paper','database','tool','model']:raise ValueError('Unknown source_type')
    primary_role={'paper':'paper','database':'database_doc','tool':'tool_doc','model':'model_doc'}[source_type]
    bundle={'version':1,'paper_id':job['paper_id'],'source_type':source_type,'primary_role':primary_role,'title':job['title'],'repo_root':str(root),'repo_url':repo_url,
            'commit':commit,'repo_files':sorted(files),'sources':sources,'omitted':omitted,
            'coverage':{'paper_text_supplied':any(s['role']=='paper' for s in sources),
                        'primary_text_supplied':any(s['role']==primary_role for s in sources),
                        'selected_source_files':len(sources),'text_characters':used}}
    return bundle
