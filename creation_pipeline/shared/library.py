"""Private library indexes, locks and export workspaces outside delivery packages."""
import os
from contextlib import contextmanager
from pathlib import Path

from creation_pipeline.artifacts.package import manifest
from creation_pipeline.paths import ROOT
from creation_pipeline.records import digest, has_link, lease, long_path, now, read_json, safe_relative, write_json


STATE_ROOT = ROOT / '.pipeline' / 'skill-libraries'


def locations(library):
    library = Path(library).absolute()
    if has_link(library):
        raise ValueError('Linked Skill library')
    library = library.resolve()
    key = digest(os.path.normcase(str(library)).encode('utf-8'))[:24]
    state = safe_relative(STATE_ROOT, key)
    if state.resolve().is_relative_to(library):
        raise ValueError('Library state must be outside the delivery directory')
    return library, state


def catalog_path(library):
    library, state = locations(library)
    private = state / 'catalog.json'
    return private if private.is_file() else library / 'catalog.json'


def is_library(library):
    path = catalog_path(library)
    return path.is_file() and read_json(path).get('workflow') == 'shared-environments'


def validate_catalog(catalog, library):
    if catalog.get('workflow') != 'shared-environments':
        raise ValueError('Legacy catalog requires explicit migration; cannot overwrite it')
    owner = catalog.get('library_root')
    if owner is not None and os.path.normcase(str(Path(owner).resolve())) != os.path.normcase(str(library)):
        raise ValueError('Catalog belongs to a different delivery directory')
    return {**catalog, 'library_root': str(library)}


def migrate_legacy(library, state):
    """Preserve package bytes and interrupted staging while relocating an old catalog."""
    source = safe_relative(library, 'catalog.json')
    if not source.is_file():
        return
    # Validate before creating an old-format lock in a non-shared library.
    validate_catalog(read_json(source), library)
    legacy_leases = safe_relative(library, 'leases')
    if legacy_leases.exists() and any(p.name != 'shared-catalog.lock' for p in legacy_leases.iterdir()):
        raise ValueError('Unexpected legacy lock files; retain them for inspection')
    with lease(library, 'shared-catalog'):
        original = read_json(source)
        catalog = validate_catalog(original, library)
        private = state / 'catalog.json'
        if private.exists() and validate_catalog(read_json(private), library) != catalog:
            raise ValueError('Conflicting internal and delivery-directory catalogs')
        for entry in catalog['skills']:
            package = safe_relative(library, entry['path'])
            if manifest(package) != entry['files']:
                raise ValueError('Delivered package changed; catalog migration refused: ' + entry['name'])
        backup = state / 'migration.json'
        if not backup.exists():
            write_json(backup, {'at': now(), 'source_catalog': str(source), 'catalog': original})
        staging = safe_relative(library, '.staging')
        if staging.exists():
            if any(has_link(p) for p in staging.rglob('*')):
                raise ValueError('Linked legacy staging contents; migration refused')
            if any(staging.iterdir()):
                target = safe_relative(state, 'staging/recovered')
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    raise ValueError('Recovered staging already exists; retain both copies for inspection')
                # Both resolved move endpoints stay inside their explicitly managed roots.
                if not staging.resolve().is_relative_to(library) or not target.resolve().is_relative_to(state.resolve()):
                    raise ValueError('Staging migration escapes its managed directories')
                long_path(staging).rename(long_path(target))
            else:
                staging.rmdir()
        promotion = safe_relative(library, '.promotion.json')
        if promotion.exists():
            destination = state / 'promotion.json'
            value = read_json(promotion)
            if destination.exists() and read_json(destination) != value:
                raise ValueError('Conflicting promotion records')
            write_json(destination, value)
            promotion.unlink()
        write_json(private, catalog)
    # Keep the source catalog until all old work files have been handled, so an
    # interrupted migration can retry without guessing whether cleanup completed.
    (legacy_leases / 'shared-catalog.lock').unlink(missing_ok=True)
    legacy_leases.rmdir()
    source.unlink()


@contextmanager
def locked(library, *, required=False):
    library, state = locations(library)
    with lease(state, 'shared-catalog'):
        migrate_legacy(library, state)
        path = state / 'catalog.json'
        if path.exists():
            catalog = validate_catalog(read_json(path), library)
        elif required:
            raise FileNotFoundError('No shared Skill library catalog: ' + str(library))
        else:
            catalog = {'workflow': 'shared-environments', 'library_root': str(library), 'skills': []}
        yield library, state, catalog


def migrate(library):
    """Explicit offline migration; no Agent, Docker or image publication calls."""
    with locked(library, required=True) as (library, state, catalog):
        return {'library': str(library), 'catalog': str(state / 'catalog.json'), 'skills': len(catalog['skills'])}


def reindex(library):
    """Recover locations and hashes after state loss, never historical approval."""
    from creation_pipeline.artifacts.content_delivery import validate_package
    import re
    with locked(library) as (library, state, catalog):
        destination = state / 'catalog.json'
        if destination.exists():
            raise ValueError('A library catalog already exists; preserve its evidence')
        names = set()
        for main in sorted(library.rglob('SKILL.md')):
            package = main.parent
            parts = package.relative_to(library).parts
            if not any(p in {'verified', 'pending-validation'} for p in parts):
                continue
            if has_link(package):
                raise ValueError('Linked recovered package')
            files = validate_package(package)
            match = re.search(r'^name:\s*[\"\']?([a-z0-9]+(?:-[a-z0-9]+)*)[\"\']?\s*$', main.read_text(encoding='utf-8'), re.M)
            if not match or match[1] in names:
                raise ValueError('Recovered packages need unique valid names')
            names.add(match[1])
            runtime = read_json(package / 'runtime.json')
            catalog['skills'].append({'name': match[1], 'path': package.relative_to(library).as_posix(),
                'status': 'recovered', 'evidence': 'unavailable', 'files': files, 'image': runtime['image']})
        write_json(destination, catalog)
        return {'recovered': len(catalog['skills']), 'qualification': 'unavailable; review/revalidation required'}
