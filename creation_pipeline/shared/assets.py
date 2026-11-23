"""Resolve registered binary test inputs; reuse the existing acquisition path."""
import shutil
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from creation_pipeline.records import file_digest, safe_relative, lease, has_link


def resolve_inputs(sources, cases):
    sources.verify()
    for case in cases:
        resolved = []
        targets = []
        for item in case.get('inputs', []):
            entry = sources.entries.get(item['source'])
            if entry is None:
                fact = next((e for e in sources.evidence if e['id'] == item['source']), None)
                entry = sources.entries.get(fact['source']) if fact else None
            if entry is None:
                raise ValueError('Unknown registered test source: ' + item['source'])
            root = Path(entry['path'])
            facts = [f for f in entry['inventory'] if f['path'] == item['path']]
            if len(facts) != 1:
                raise ValueError('Select a registered input inventory path: ' + item['path'])
            source = root if root.is_file() else safe_relative(root, item['path'])
            if has_link(source) or file_digest(source) != facts[0]['sha256']:
                raise ValueError('Registered test input changed')
            if item.get('member'):
                try:
                    source = extract_member(sources.cache, source, facts[0]['sha256'], item['member'])
                except (tarfile.TarError, zipfile.BadZipFile, KeyError) as exc:
                    raise ValueError('Invalid declared archive input: ' + str(exc)) from exc
            target = item['target']
            if target.startswith('/work/'):
                target = target[6:]
            path = PurePosixPath(target)
            if not target or path.is_absolute() or '..' in path.parts or '\\' in target or ':' in target:
                raise ValueError('Input target must be a relative path beneath /work')
            if any(path == other or path in other.parents or other in path.parents for other in targets):
                raise ValueError('Overlapping test input targets')
            targets.append(path)
            resolved.append({**item, 'target': path.as_posix(), 'host_path': str(source.resolve()),
                             'sha256': file_digest(source)})
        if resolved:
            case['_inputs'] = resolved


def extract_member(cache, archive, sha256, member):
    """Extract only the requested regular file; retain its registered archive provenance."""
    target = safe_relative(Path(cache) / 'test-inputs' / sha256, member)
    with lease(Path(cache), 'test-input-' + sha256):
        # Always read the immutable archive: a mutable cache cannot grant input integrity.
        if zipfile.is_zipfile(archive):
            container = zipfile.ZipFile(archive)
            matches = [i for i in container.infolist() if i.filename == member]
            if len(matches) != 1 or matches[0].is_dir() or (matches[0].external_attr >> 16) & 0o170000 == 0o120000:
                container.close()
                raise ValueError('Select one regular archive member')
            stream = container.open(matches[0])
        else:
            container = tarfile.open(archive)
            matches = [i for i in container.getmembers() if i.name == member]
            if len(matches) != 1 or not matches[0].isfile():
                container.close()
                raise ValueError('Select one regular archive member')
            stream = container.extractfile(matches[0])
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.writing')
        try:
            with container, stream, temporary.open('wb') as output:
                shutil.copyfileobj(stream, output)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return target


def acquire_requests(session, requests):
    from creation_pipeline.resources.supplements import supplement
    from creation_pipeline.resources.workspace import sync_sources, prepare
    results = []
    for request in requests:
        result = supplement(session.work, {'url': request['url']}, request['reason'],
                            related_to=request['related_to'])
        results.append({'url': request['url'], **result})
    sync_sources(session.sources, session.work)
    for result in results:
        entry = session.sources.entries.get(result.get('source'))
        if entry is not None:
            entry['test_asset'] = True
    session.workspace = prepare(session.sources, session.work)
    return results
