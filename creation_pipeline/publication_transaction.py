"""Stage local publications and roll back directory replacements on failure."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile

from runtime_common import files, write


def move(source, target):
    Path(source).rename(target)


class PublicationTransaction:
    def __init__(self, root, run_id, targets, replace=False):
        self.root = Path(root).resolve()
        self.run_id, self.replace = run_id, replace
        self.targets = [Path(p).absolute() for p in targets]
        self.created_parents, self.entries = [], []
        self.folder = None
        self.lock = self.root / '.publication-transactions/lock'
        self.owns_lock = False
        self.committed = False
        self.preserve = False
        self.preflight()

    def checked(self, path):
        path = Path(os.path.abspath(path))
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError('Publication path escapes repository: ' + str(path))
        for node in (path, *path.parents):
            if node == self.root: break
            if node.is_symlink() or (hasattr(node, 'is_junction') and node.is_junction()):
                raise ValueError('Publication path contains a link: ' + str(node))
            if node.exists() and not node.is_dir():
                raise ValueError('Publication path is not a directory: ' + str(node))
        return path

    def preflight(self):
        unique = set()
        conflicts = []
        for target in self.targets:
            self.checked(target)
            key = os.path.normcase(str(target))
            if key in unique: raise ValueError('Duplicate publication target: ' + str(target))
            unique.add(key)
            if target.exists() and not self.replace: conflicts.append(str(target))
        if any(a != b and a.is_relative_to(b) for a in self.targets for b in self.targets):
            raise ValueError('Overlapping publication targets')
        if conflicts:
            raise ValueError('Publication target conflict: ' + '; '.join(conflicts) + '. Use --replace-existing only for an intentional replacement.')

    def snapshot(self, target):
        if not target.exists(): return None
        for child in target.rglob('*'):
            if child.is_symlink() or (hasattr(child, 'is_junction') and child.is_junction()):
                raise ValueError('Existing publication contains a link: ' + str(child))
        return files(target)

    def __enter__(self):
        self.checked(self.lock.parent)
        self.lock.parent.mkdir(exist_ok=True)
        try:
            with self.lock.open('x', encoding='utf-8') as stream:
                self.owns_lock = True
                json.dump({'pid': os.getpid(), 'run_id': self.run_id}, stream)
            for journal in self.lock.parent.glob('txn-*/transaction.json'):
                try:
                    state = json.loads(journal.read_text(encoding='utf-8'))['state']
                except (OSError, ValueError, KeyError) as exc:
                    raise RuntimeError('Publication journal needs inspection before retry: ' + str(journal)) from exc
                if state not in {'committed', 'rolled_back'}:
                    raise RuntimeError('Publication recovery required before retry: ' + str(journal))
            self.preflight()
            self.folder = Path(tempfile.mkdtemp(prefix='txn-', dir=self.lock.parent))
            for n, target in enumerate(self.targets):
                self.entries.append({'target': str(target), 'stage': str(self.folder / f'stage-{n}'),
                                     'backup': str(self.folder / f'backup-{n}'), 'before': self.snapshot(target),
                                     'backed_up': False, 'installed': False})
            self.journal('staging')
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def journal(self, state, errors=None):
        write(self.folder / 'transaction.json', {'run_id': self.run_id, 'state': state,
                                                'entries': self.entries, 'errors': errors or []})

    def stage(self, target):
        return Path(next(e['stage'] for e in self.entries if Path(e['target']) == Path(target).absolute()))

    def make_parents(self, target):
        missing = []
        node = target.parent
        while not node.exists():
            missing.append(node); node = node.parent
        for directory in reversed(missing):
            directory.mkdir()
            self.created_parents.append(directory)

    def commit(self):
        self.preflight()
        for entry in self.entries:
            if self.snapshot(Path(entry['target'])) != entry['before']:
                raise ValueError('Publication target changed while staging: ' + entry['target'])
            if not Path(entry['stage']).is_dir(): raise ValueError('Missing staged publication')
        self.journal('committing')
        try:
            for entry in self.entries:
                target, backup = Path(entry['target']), Path(entry['backup'])
                self.make_parents(target)
                if target.exists():
                    move(target, backup)
                    entry['backed_up'] = True
                    self.journal('committing')
                move(entry['stage'], target)
                entry['installed'] = True
                self.journal('committing')
            self.journal('committed')
            self.committed = True
        except BaseException:
            self.rollback()
            raise

    def rollback(self):
        # An interrupted recovery must never trigger deletion of its backups.
        self.preserve = True
        errors = []
        for entry in reversed(self.entries):
            try:
                target, backup = self.checked(entry['target']), Path(entry['backup'])
                # Infer completed renames as well as recorded flags, covering an
                # interruption after the rename but before the journal update.
                installed = entry['installed'] or not Path(entry['stage']).exists()
                if installed and target.exists():
                    shutil.rmtree(target)
                    entry['installed'] = False
                if backup.exists():
                    move(backup, target)
                    entry['backed_up'] = False
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
        for parent in reversed(self.created_parents):
            try: parent.rmdir()
            except OSError: pass
        self.preserve = bool(errors)
        self.journal('recovery_required' if errors else 'rolled_back', errors)
        if errors:
            raise RuntimeError('Publication rollback needs recovery; backups and journal preserved at ' + str(self.folder))

    def __exit__(self, *exc):
        try:
            if self.folder and not self.preserve:
                # Only the private transaction folder, after commit or rollback.
                try: shutil.rmtree(self.checked(self.folder))
                except OSError:
                    if not self.committed: raise
        finally:
            if self.owns_lock:
                self.lock.unlink()
                self.owns_lock = False
