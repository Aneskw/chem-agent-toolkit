"""Local multi-file replacement with explicit Windows-compatible rollback."""
import os
from pathlib import Path
import shutil
import tempfile
import functools
import uuid
from runtime_common import read, write


def preserve_runtime_on_failure(function):
    """Preparation already archives the old runtime; restore it on failed regeneration.

    Keep the failed new runtime as a separate report, never overwrite old history.
    """
    @functools.wraps(function)
    def wrapped(candidate, *args, **kwargs):
        root = Path(candidate).resolve()
        runtime = root / 'runtime'
        if not runtime.exists():
            return function(candidate, *args, **kwargs)
        previous_archives = set((root / 'reports').glob('runtime-archive-*'))
        documents = {name: (root / name).read_bytes() if (root / name).exists() else None
                     for name in ('SKILL.md', 'DOCKER.md')}
        def restore():
            archives = set((root / 'reports').glob('runtime-archive-*')) - previous_archives
            if len(archives) != 1:
                return None  # Failure before the existing code moved the old runtime.
            saved = archives.pop()
            if saved.is_symlink() or saved.resolve().parent != (root / 'reports').resolve():
                raise ValueError('Unsafe recovery archive')
            failed = root / 'reports' / ('failed-generation-' + uuid.uuid4().hex)
            if runtime.exists():
                os.replace(runtime, failed)
            os.replace(saved, runtime)
            for name, content in documents.items():
                target = root / name
                if content is None:
                    target.unlink(missing_ok=True)
                else:
                    target.write_bytes(content)
            write(root / 'reports' / (failed.name + '.recovery.json'),
                  {'restored_runtime': str(runtime), 'previous_archive': str(saved), 'failed_generation': str(failed)})
            return str(failed)
        try:
            result = function(candidate, *args, **kwargs)
        except BaseException:
            restore()
            raise
        if result['status'] not in {'prepared', 'not_required'}:
            failure = restore()
            if failure:
                result = dict(result, restored_previous_runtime=True, failed_generation=failure)
        return result
    return wrapped


def commit_generated(destination, plan, tool_id, render, before_commit=None):
    parent = destination.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink() or destination.resolve().parent != parent:
        raise ValueError('Invalid context destination')
    temporary = Path(tempfile.mkdtemp(prefix='.generation-', dir=parent))
    installed, backups = [], []
    preserve = False
    try:
        tool, proof = render(temporary / 'context')
        if tool is None:
            return tool, proof
        write(temporary / 'environment_plan.json', plan)
        write(temporary / 'provenance.json', proof)
        write(temporary / 'tool.json', tool)
        entries = [(temporary / name, parent / name) for name in
                   ('context', 'environment_plan.json', 'provenance.json', 'tool.json')]
        package_path = parent.parent.parent / 'package.json'
        if package_path.is_file():
            package = read(package_path)
            if tool_id in package['tools']:
                package['tools'][tool_id] = tool
                write(temporary / 'package.json', package)
                entries.append((temporary / 'package.json', package_path))
        if before_commit is not None:
            before_commit(temporary / 'context', tool, proof)
        # Move nonempty directories out first; os.replace cannot replace them on Windows.
        write(temporary / 'recovery.json', {'entries': [
            {'target': str(target), 'backup': str(temporary / ('backup-' + str(i)))}
            for i, (_, target) in enumerate(entries)]})
        try:
            for number, (staged, target) in enumerate(entries):
                if target.is_symlink():
                    raise ValueError('Refusing symlink transaction target')
                backup = temporary / ('backup-' + str(number))
                if target.exists():
                    backups.append((backup, target))
                    os.replace(target, backup)
                installed.append(target)
                os.replace(staged, target)
        except BaseException:
            try:
                for number, target in enumerate(reversed(installed)):
                    if target.exists():
                        os.replace(target, temporary / ('discard-' + str(number)))
                for backup, target in reversed(backups):
                    if backup.exists():
                        os.replace(backup, target)
            except BaseException as recovery:
                preserve = True
                raise OSError('Rollback could not finish; retained recovery files at ' + str(temporary)) from recovery
            raise
        return tool, proof
    finally:
        # Only this invocation's directory; never follow an externally substituted link.
        if not preserve and temporary.exists():
            if temporary.is_symlink() or temporary.resolve().parent != parent:
                raise ValueError('Unsafe transaction cleanup path')
            shutil.rmtree(temporary)
