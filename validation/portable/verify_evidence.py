"""Read-only verification of published evidence bytes, not current qualification."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from creation_pipeline.records import read_json,file_digest,safe_relative


def main():
    index=read_json(ROOT/'validation/portable/results-20261102.json')
    for item in index['evidence_files']:
        path=safe_relative(ROOT,item['path'])
        if not path.is_file() or path.stat().st_size!=item['bytes'] or file_digest(path)!=item['sha256']:
            raise ValueError('Evidence byte mismatch: '+item['path']+'; expected sha256='+item['sha256'])
    print({'status':'evidence_bytes_verified','files':len(index['evidence_files']),
           'scope':'published historical evidence only; no current availability or qualification'})
    return 0


if __name__=='__main__':raise SystemExit(main())
