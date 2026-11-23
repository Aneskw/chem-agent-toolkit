"""Private counters, preparation caches and locks for a tool environment library."""
import os
import shutil
import uuid
from contextlib import contextmanager, ExitStack
from pathlib import Path

from creation_pipeline.paths import ROOT
from creation_pipeline.records import digest, file_digest, has_link, lease, now, read_json, safe_relative, write_json


STATE_ROOT = ROOT / '.pipeline' / 'tool-libraries'
CONTROL_FILES = ('versions.json', 'prepared-plans.json')
LOCK_NAMES = ('catalog', 'versions', 'prepared-plans')


def locations(library):
    library = Path(library).absolute()
    if has_link(library):
        raise ValueError('Linked environment library')
    library = library.resolve()
    key = digest(os.path.normcase(str(library)).encode('utf-8'))[:24]
    state = safe_relative(STATE_ROOT, key)
    if state.resolve().is_relative_to(library):
        raise ValueError('Environment library state must be outside build materials')
    return library, state


def migrate(library):
    """Move legacy control files without changing build contexts or image bindings."""
    library, state = locations(library)
    with lease(state, 'migration'):
        legacy = {name: safe_relative(library, name) for name in CONTROL_FILES}
        leases = safe_relative(library, 'leases')
        if not any(p.exists() for p in legacy.values()) and not leases.exists():
            return state
        allowed = {name + '.lock' for name in LOCK_NAMES}
        if any(p.exists() and not p.is_file() for p in legacy.values()):
            raise ValueError('Environment control paths must be files')
        if leases.exists() and any(p.name not in allowed or has_link(p) or not p.is_file() for p in leases.iterdir()):
            raise ValueError('Unexpected environment lock files; migration refused')
        with ExitStack() as stack:
            for name in LOCK_NAMES:
                stack.enter_context(lease(state, name))
            for name in LOCK_NAMES:
                stack.enter_context(lease(library, name))
            values = {name: read_json(path) for name, path in legacy.items() if path.is_file()}
            for name, value in values.items():
                valid = isinstance(value, dict) if name == 'versions.json' else isinstance(value, list)
                if not valid:
                    raise ValueError('Invalid environment control file: ' + name)
                private = state / name
                if private.exists() and read_json(private) != value:
                    raise ValueError('Conflicting private and legacy environment control files: ' + name)
            journal = state / 'migration.json'
            if not journal.exists():
                write_json(journal, {'at': now(), 'library_root': str(library),
                    'files': {name: file_digest(legacy[name]) for name in values}})
            for name in values:
                source, destination = legacy[name], state / name
                if not destination.exists():
                    temporary = destination.with_name(name + '.' + uuid.uuid4().hex + '.tmp')
                    try:
                        shutil.copy2(source, temporary)
                        temporary.replace(destination)
                    finally:
                        temporary.unlink(missing_ok=True)
                if read_json(destination) != values[name]:
                    raise ValueError('Environment control copy changed: ' + name)
                source.unlink()
        for name in allowed:
            (leases / name).unlink(missing_ok=True)
        leases.rmdir()
    return state


@contextmanager
def locked(library, name):
    state = migrate(library)
    with lease(state, name):
        yield state
