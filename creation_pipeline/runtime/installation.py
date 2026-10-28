"""Install frozen runtime materials/evidence beside, not inside, authored files."""
import shutil
from pathlib import Path
from creation_pipeline.records import safe_relative, has_link
from creation_pipeline.artifacts.package import manifest


def install_envelope(root, frozen, attempt, destination):
    destination = Path(destination)
    if destination.exists() or has_link(destination):
        raise ValueError('Runtime installation destination exists or is linked')
    try:
        for relative, name in ((frozen, 'frozen'), (attempt, 'attempt')):
            source = safe_relative(Path(root), relative)
            expected = manifest(source)
            shutil.copytree(source, destination / name)
            if manifest(destination / name) != expected:
                raise ValueError('Installed runtime evidence changed')
    except BaseException:
        if destination.exists():
            from creation_pipeline.artifacts.store import remove
            remove(destination.parent, destination)
        raise
