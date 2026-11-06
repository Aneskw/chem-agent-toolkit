"""Explicit cleanup of archived verified runs; shared resources are never deleted here."""
import time
from pathlib import Path
from creation_pipeline.records import has_link, lease, read_json, write_json, safe_relative, clean_run
from creation_pipeline.artifacts.package import manifest


def pin(state, build_id, value):
    state = Path(state).absolute()
    with lease(state, build_id):
        run = safe_relative(state, 'runs/' + build_id)
        if read_json(run / 'checkpoint.json').get('workflow') != 'shared-environments':
            raise ValueError('Not a grouped creation run')
        write_json(run / 'retention.json', {'pinned': bool(value)})
        return {'build_id': build_id, 'pinned': bool(value)}


def eligible(state, build_id):
    state = Path(state).absolute()
    run = safe_relative(state, 'runs/' + build_id)
    if has_link(run):
        raise ValueError('Linked run cannot be cleaned')
    saved = read_json(run / 'checkpoint.json')
    if saved.get('workflow') != 'shared-environments':
        raise ValueError('Historical run is not managed by grouped cleanup')
    marker = run / 'retention.json'
    if marker.exists() and read_json(marker).get('pinned'):
        raise ValueError('Pinned workspace')
    candidates = [e for g in saved['groups'].values() for e in g['entities'].values()]
    if saved.get('status') != 'ready' or any(e['status'] != 'verified' for e in candidates):
        raise ValueError('Retain incomplete or pending workspace for recovery')
    for entry in candidates:
        record_path = Path(entry['record']).absolute()
        if not record_path.is_relative_to((state / 'records').resolve()) or has_link(record_path):
            raise ValueError('Durable archive outside managed records')
        record = read_json(record_path)
        if record['final_files'] != manifest(record_path.parent / 'package'):
            raise ValueError('Durable archived package differs; cleanup refused')
    return run


def clean(state, build_id, dry_run=False):
    with lease(state, build_id):
        eligible(state, build_id)
        return clean_run(state, build_id, dry_run)


def sweep(state, days=7, dry_run=True):
    if type(days) is not int or days < 0:
        raise ValueError('Retention days must be a nonnegative integer')
    state = Path(state).absolute()
    removed, retained = [], []
    for path in (state / 'runs').glob('*'):
        if not path.is_dir():
            continue
        try:
            if time.time() - (path / 'checkpoint.json').stat().st_mtime < days * 86400:
                continue
            result = clean(state, path.name, dry_run)
            removed += result['removed']
        except (ValueError, OSError, KeyError) as exc:
            retained.append({'build_id': path.name, 'reason': str(exc)})
    return {'removed': removed, 'retained': retained, 'dry_run': dry_run,
            'shared_cache_and_environment_materials': 'preserved'}
