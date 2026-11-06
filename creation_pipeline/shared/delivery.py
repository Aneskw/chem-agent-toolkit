"""Pure-package delivery; evidence stays in state, never in installed Skill sidecars."""
import json
import shutil
import uuid
from pathlib import Path
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.records import has_link, lease, read_json, safe_relative, write_json
from .environment import fingerprint, runtime


def finalize(package, plan, environment):
    if not environment.get('image') or '@sha256:' not in environment['image']:
        raise ValueError('Delivery requires a published digest-bound image')
    package = Path(package)
    main = package / 'SKILL.md'
    text = main.read_text(encoding='utf-8').replace('{{image}}', environment['image'])
    if environment['image'] not in text or 'runtime.json' not in text:
        raise ValueError('Skill must reference its Docker image and runtime.json')
    main.write_text(text, encoding='utf-8')
    write_json(package / 'runtime.json', runtime(plan, environment['image']))
    if '{{image}}' in text:
        raise ValueError('Unresolved image placeholder')
    return manifest(package)


def adopt(package, result, library):
    if result['status'] not in {'verified', 'pending-validation'}:
        raise ValueError('Only qualified packages may be exported')
    library = Path(library).absolute()
    if has_link(library):
        raise ValueError('Linked Skill library')
    with lease(library, 'shared-catalog'):
        catalog_path = library / 'catalog.json'
        catalog = read_json(catalog_path) if catalog_path.exists() else {'workflow': 'shared-environments', 'skills': []}
        if catalog.get('workflow') != 'shared-environments':
            raise ValueError('Legacy catalog requires explicit migration; cannot overwrite it')
        name = result['name']
        existing = [e for e in catalog['skills'] if e['name'] == name]
        files = manifest(package)
        if existing:
            if existing[0]['files'] == files:
                return existing[0]
            raise ValueError('Skill name conflict: ' + name)
        relative = result['status'] + '/' + name
        destination = safe_relative(library, relative)
        if destination.exists():
            if manifest(destination) != files:
                raise ValueError('Uncommitted delivery path conflict: ' + name)
        else:
            stage = safe_relative(library, '.staging/' + uuid.uuid4().hex)
            stage.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(package, stage)
            if manifest(stage) != files:
                raise ValueError('Package copy verification failed')
            destination.parent.mkdir(parents=True, exist_ok=True)
            stage.rename(destination)
        entry = {'name': name, 'path': relative, 'status': result['status'], 'files': files,
                 'image': result['environment']['image'], 'group': result['group'],
                 'record': result['record'], 'pending': result.get('verification', {}).get('deferred', [])}
        catalog['skills'].append(entry)
        write_json(catalog_path, catalog)
        return entry


def entries(library, include_pending=False):
    library = Path(library)
    with lease(library, 'shared-catalog'):
        catalog = read_json(library / 'catalog.json')
        if catalog.get('workflow') != 'shared-environments':
            raise ValueError('Not a shared-environments catalog')
        result = []
        for entry in catalog['skills']:
            if entry['status'] != 'verified' and not include_pending:
                continue
            if manifest(safe_relative(library, entry['path'])) != entry['files']:
                raise ValueError('Delivered package changed: ' + entry['name'])
            result.append(entry)
        return result


def install(library, name, destination, include_pending=False):
    selected = [e for e in entries(library, include_pending) if e['name'] == name]
    if len(selected) != 1:
        raise ValueError('No eligible Skill; pending packages require explicit selection')
    target = Path(destination).absolute() / name
    if target.exists() or has_link(target):
        raise ValueError('Installation destination exists or is linked')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(safe_relative(Path(library), selected[0]['path']), target)
    if manifest(target) != selected[0]['files']:
        raise ValueError('Installed package verification failed')
    return {'installed': str(target), 'status': selected[0]['status']}


def promote(library, name, report):
    """Explicit human evidence must refer to the exact current package/image and cover all pending items."""
    library = Path(library)
    with lease(library, 'shared-catalog'):
        catalog = read_json(library / 'catalog.json')
        selected = next(e for e in catalog['skills'] if e['name'] == name)
        if selected['status'] == 'verified' and selected.get('manual_verification') == report:
            return selected
        if selected['status'] != 'pending-validation':
            raise ValueError('Skill is not awaiting validation')
        package = safe_relative(library, selected['path'])
        if manifest(package) != selected['files'] or report['package_sha256'] != fingerprint(selected['files']) or report['image'] != selected['image']:
            raise ValueError('Manual verification refers to a different package or image')
        required = {i['item_id'] for i in selected['pending']}
        if {i['item_id'] for i in report['items']} != required or any(i['status'] != 'passed' or not i['evidence'] for i in report['items']):
            raise ValueError('Manual evidence must cover every pending item')
        destination = safe_relative(library, 'verified/' + name)
        if destination.exists() and manifest(destination) != selected['files']:
            raise ValueError('Verified destination already exists with different contents')
        write_json(library / '.promotion.json', {'name': name, 'report': report, 'from': selected['path'], 'to': 'verified/' + name})
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            stage = safe_relative(library, '.staging/' + uuid.uuid4().hex)
            stage.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(package, stage)
            if manifest(stage) != selected['files']:
                raise ValueError('Promotion package copy differs')
            stage.rename(destination)
        selected.update(status='verified', path='verified/' + name, pending=[], manual_verification=report)
        write_json(library / 'catalog.json', catalog)
        # Old pending copy retained until explicit cleanup; catalog is the authoritative commit.
        return selected
