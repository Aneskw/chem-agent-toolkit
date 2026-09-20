#!/usr/bin/env python3
"""Convert an unfamiliar paper/resource table into the generic catalog format."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import urllib.parse

ALIASES = {
    'id': {'id','paper_id','paperid','record_id','key','uid'},
    'title': {'title','paper','paper_title','article','article_title','name','publication'},
    'doi': {'doi','digital_object_identifier'},
    'url': {'url','link','web','landing_page','paper_url','article_url','pdf','pdf_url','source'},
    'repo': {'repo','repository','repository_url','github','github_url','code','code_url'},
    'type': {'type','source_type','category','class','kind','target'},
}


def normalize(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', value.strip().lower()).strip('_')


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if path.suffix.lower() in {'.xlsx', '.xlsm'}:
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise ValueError('XLSX support requires openpyxl in the active Python environment') from exc
        sheet = load_workbook(path, read_only=True, data_only=True).active
        values=list(sheet.values)
        if not values: return [], []
        headers=[str(x or '').strip() for x in values[0]]
        return headers,[{headers[i]: '' if i>=len(row) or row[i] is None else str(row[i]).strip()
                         for i in range(len(headers))} for row in values[1:]]
    with path.open(newline='', encoding='utf-8-sig') as handle:
        reader=csv.DictReader(handle)
        return reader.fieldnames or [], [dict(row) for row in reader]


def choose_columns(headers: list[str]) -> tuple[dict[str, str], dict[str, list[str]]]:
    normalized={normalize(h):h for h in headers}
    selected={}; ambiguous={}
    for role,aliases in ALIASES.items():
        hits=[normalized[a] for a in aliases if a in normalized]
        if len(hits)==1:selected[role]=hits[0]
        elif len(hits)>1:
            # Prefer the exact conventional name, otherwise retain all choices
            # in the report and choose the first deterministic column.
            exact=next((h for h in hits if normalize(h)==role),None)
            selected[role]=exact or hits[0]; ambiguous[role]=hits
    if 'title' not in selected and 'doi' not in selected and 'url' not in selected:
        raise ValueError('Could not identify a title, DOI, or URL column')
    return selected,ambiguous


def as_url(value: str, role: str) -> str:
    value=value.strip()
    if role=='doi' and value and not value.startswith(('http://','https://')):
        return 'https://doi.org/'+value.removeprefix('doi:').strip()
    return value


def infer_type(row: dict[str,str], columns: dict[str,str], default: str) -> str:
    raw=row.get(columns.get('type',''),'').lower()
    text=' '.join(row.get(columns.get(role,''),'') for role in ('type','repo')).lower()
    if raw in {'journalarticle','journal article','preprint','conferencepaper','conference paper','article','report'}:
        return 'paper'
    if any(x in raw+' '+text for x in ('database','pubchem','chembl','uspto','dataset')):return 'database'
    if any(x in raw+' '+text for x in ('tool','rdkit','openbabel','openmm','pyscf')):return 'tool'
    if any(x in raw+' '+text for x in ('model','network','transformer','gnn','prediction')):return 'model'
    return default


def convert(path: Path, output: Path, default_type: str = 'paper') -> dict:
    headers,rows=read_rows(path)
    columns,ambiguous=choose_columns(headers)
    items=[];issues=[]
    for number,row in enumerate(rows,1):
        title=row.get(columns.get('title',''),'').strip() or row.get(columns.get('doi',''),'').strip() or f'row-{number}'
        raw_id=row.get(columns.get('id',''),'').strip() if columns.get('id') else ''
        ident=re.sub(r'[^A-Za-z0-9_-]+','-',raw_id or title.lower()).strip('-')[:55] or f'row-{number:04d}'
        sources=[]
        seen_urls=set()
        for role in ('url','doi','repo'):
            column=columns.get(role);value=as_url(row.get(column,'') if column else '',role)
            if value and value not in seen_urls:
                seen_urls.add(value)
                if role=='repo' or 'github' in value.lower():source_role='repo_doc'
                else:source_role='paper' if infer_type(row,columns,default_type)=='paper' else 'metadata'
                sources.append({'url':value,'role':source_role})
        if not sources:
            issues.append({'row':number,'issue':'no URL, DOI, or repository found'})
            continue
        item={'id':ident,'title':title,'source_type':infer_type(row,columns,default_type),'sources':sources}
        items.append(item)
    result={'items':items,'table':str(path.resolve()),'headers':headers,'column_mapping':columns,
            'ambiguous_columns':ambiguous,'issues':issues,
            'note':'Column mapping is heuristic; inspect the report before model extraction.'}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    output.with_name(output.stem+'.report.json').write_text(json.dumps({k:result[k] for k in ('table','headers','column_mapping','ambiguous_columns','issues','note')},ensure_ascii=False,indent=2)+'\n')
    return result


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--default-type',choices=['paper','database','tool','model'],default='paper')
    args=parser.parse_args()
    result=convert(args.input.resolve(),args.output.resolve(),args.default_type)
    print(json.dumps({'items':len(result['items']),'issues':len(result['issues']),'mapping':result['column_mapping']}))
    return 0 if result['items'] else 1


if __name__=='__main__':raise SystemExit(main())
