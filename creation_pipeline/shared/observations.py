"""Keep large diagnostics accessible once instead of copying them into every record."""
from pathlib import Path
from creation_pipeline.records import digest, file_digest, long_path, now, redact


def compact(value, work):
    if isinstance(value, dict):
        return {key: compact(item, work) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [compact(item, work) for item in value]
    if isinstance(value, str) and len(value) > 8192:
        text = redact(value)
        sha = digest(text.encode('utf-8'))
        path = long_path(Path(work) / 'diagnostics' / (sha[:16] + '.txt'))
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(text, encoding='utf-8', newline='\n')
        elif file_digest(path) != sha:
            raise ValueError('Diagnostic artifact identity conflict')
        return {'artifact': str(path), 'sha256': sha, 'excerpt': text[:2048] + '\n…\n' + text[-4096:]}
    return value


def event(work, **fields):
    import json
    path = long_path(Path(work) / 'operations.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'at': now(), **fields}, ensure_ascii=False) + '\n')
