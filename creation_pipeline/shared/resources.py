"""Cross-group lookup adopts immutable snapshots with group-local evidence IDs."""
import copy
import shutil
from pathlib import Path
from creation_pipeline.records import lease, read_json, write_json, digest, file_digest, safe_relative, has_link, long_path
from creation_pipeline.resources.supplements import restore, anchors_for
from creation_pipeline.resources.workspace import prepare


def index(sources):
    cache = Path(sources.cache)
    with lease(cache, 'resource-index'):
        path = cache / 'resource-index.json'
        values = read_json(path) if path.exists() else []
        keyed = {(v['snapshot_id'], v.get('url'), v.get('repo'), v.get('ref')): v for v in values}
        for value in sources.manifest():
            # Do not offer references into mutable user files as shared immutable snapshots.
            if not Path(value['path']).resolve().is_relative_to((cache / 'snapshots').resolve()):
                continue
            keyed[(value['snapshot_id'], value.get('url'), value.get('repo'), value.get('ref'))] = value
        write_json(path, list(keyed.values()))


def lookup(run, query):
    sources = restore(run)
    index(sources)
    values = read_json(Path(sources.cache) / 'resource-index.json')
    return [{k: v for k, v in value.items() if k not in {'inventory', 'path', 'original_path', 'files'}}
            for value in values if query.lower() in str({k: value.get(k) for k in ('url', 'repo', 'ref', 'version', 'snapshot_id')}).lower()]


def adopt(run, snapshot_id, reason, related_to):
    if not reason.strip():
        raise ValueError('Adoption requires a group-local purpose')
    run = Path(run)
    with lease(run, 'resources'):
        sources = restore(run)
        anchors = anchors_for(sources, related_to)
        with lease(sources.cache, 'resource-index'):
            matches = [v for v in read_json(Path(sources.cache) / 'resource-index.json') if v['snapshot_id'] == snapshot_id]
        if not matches:
            raise ValueError('Shared snapshot not found')
        entry = copy.deepcopy(matches[0])
        if not Path(entry['path']).resolve().is_relative_to((Path(sources.cache) / 'snapshots').resolve()):
            raise ValueError('Snapshot outside shared cache')
        entry.update(id='adopted-' + digest((snapshot_id + reason).encode())[:16],
                     supplemental=True, related_to=anchors, acquisition_reason=reason)
        sources.entries[entry['id']] = entry
        sources.verify()
        prepare(sources, run)
        return {'status': 'adopted', 'source': entry['id']}


def archive_sources(run, destination):
    """Retain registered supplemental evidence independently of mutable workspaces."""
    sources = restore(run)
    sources.verify()
    destination = Path(destination)
    retained = copy.deepcopy(sources.manifest())
    for entry in retained:
        if not entry.get('supplemental'):
            continue
        if entry.get('test_asset'):
            # Binary validation assets already have immutable shared snapshots and hashes.
            # Do not duplicate full checkpoints/archives into every group's evidence tree.
            continue
        root = Path(entry['path'])
        target = safe_relative(destination, 'sources/' + entry['snapshot_id'][:16])
        for item in entry['inventory']:
            original = root if root.is_file() else safe_relative(root, item['path'])
            saved = safe_relative(target, item['path'])
            long_path(saved.parent).mkdir(parents=True, exist_ok=True)
            if not long_path(saved).exists():
                shutil.copyfile(long_path(original), long_path(saved))
            if has_link(saved) or file_digest(saved) != item['sha256']:
                raise ValueError('Supplement archive differs: ' + entry['id'])
        entry['path'] = str(target / root.name if root.is_file() else target)
    write_json(destination / 'sources.json', retained)
    write_json(destination / 'source-evidence.json', sources.evidence)
    return retained
