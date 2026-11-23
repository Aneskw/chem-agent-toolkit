"""Pure-package delivery; evidence stays in state, never in installed Skill sidecars."""
import shutil
import uuid
from pathlib import Path
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.artifacts.content_delivery import validate_package
from creation_pipeline.records import has_link, long_path, safe_relative, write_json
from .environment import fingerprint, runtime
from .registry import split_image
from .failures import IntegrityError
from .library import locked


def qualify(environment):
    split_image(environment.get('image', ''))
    if '@' in environment['image']:
        raise ValueError('Consumer delivery requires a version tag, not a digest reference')
    proof = environment.get('anonymous_access', {})
    if proof.get('status') != 'verified' or proof.get('digest') != environment.get('digest') or proof.get('image') != environment['image']:
        raise ValueError('Delivery requires current anonymous access evidence for the exact tag and digest')


def finalize(package, plan, environment):
    qualify(environment)
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
    qualify(result['environment'])
    files = validate_package(package)
    if files != result['final_files']:
        raise IntegrityError('Package differs from final approved files; export refused')
    with locked(library) as (library, state, catalog):
        catalog_path = state / 'catalog.json'
        name = result['name']
        existing = [e for e in catalog['skills'] if e['name'] == name]
        if manifest(package) != files:
            raise IntegrityError('Package changed during export')
        if existing:
            if existing[0]['files'] == files and existing[0]['status'] != 'recovered':
                return existing[0]
            if existing[0]['files'] != files:
                raise ValueError('Skill name conflict: ' + name)
            # A new qualified run may supply missing evidence, never the folder name.
            catalog['skills'].remove(existing[0])
        relative = result['status'] + '/' + name
        destination = safe_relative(library, relative)
        if existing and existing[0]['status'] == 'recovered' and existing[0]['path'] != relative:
            previous = safe_relative(library, existing[0]['path'])
            if destination.exists() or manifest(previous) != files:
                raise IntegrityError('Recovered package move conflicts with existing files')
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Both resolved paths are checked beneath this explicitly selected library.
            long_path(previous).rename(long_path(destination))
        if destination.exists():
            if manifest(destination) != files:
                raise ValueError('Uncommitted delivery path conflict: ' + name)
        else:
            stage = safe_relative(state, 'staging/' + uuid.uuid4().hex)
            stage.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(long_path(package), long_path(stage))
            if manifest(stage) != files:
                raise ValueError('Package copy verification failed')
            destination.parent.mkdir(parents=True, exist_ok=True)
            long_path(stage).rename(long_path(destination))
        entry = {'name': name, 'path': relative, 'status': result['status'], 'files': files,
                 'image': result['environment']['image'], 'group': result['group'],
                 'record': result['record'], 'pending': result.get('verification', {}).get('deferred', [])}
        catalog['skills'].append(entry)
        write_json(catalog_path, catalog)
        return entry


def entries(library, include_pending=False):
    with locked(library, required=True) as (library, state, catalog):
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
    with locked(library, required=True) as (library, state, catalog):
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
        write_json(state / 'promotion.json', {'name': name, 'report': report, 'from': selected['path'], 'to': 'verified/' + name})
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            stage = safe_relative(state, 'staging/' + uuid.uuid4().hex)
            stage.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(long_path(package), long_path(stage))
            if manifest(stage) != selected['files']:
                raise ValueError('Promotion package copy differs')
            long_path(stage).rename(long_path(destination))
        selected.update(status='verified', path='verified/' + name, pending=[], manual_verification=report)
        write_json(state / 'catalog.json', catalog)
        # Old pending copy retained until explicit cleanup; catalog is the authoritative commit.
        return selected
