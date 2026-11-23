import hashlib
import io
import pathlib
import tarfile
import urllib.request

COMMIT = '60e7a24213810706a7075d113704c9320158d726'
URL = 'https://api.github.com/repos/binghong-ml/retro_star/tarball/' + COMMIT
EXPECTED = 'cb21f6cd3ad785b99aa458a0489386f5cf9bb2902db7aaaffe87853bbf818c8f'
request = urllib.request.Request(URL, headers={'User-Agent': 'retrostar-environment'})
last_error = None
for attempt in range(3):
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            content = response.read()
        assert hashlib.sha256(content).hexdigest() == EXPECTED, 'source hash mismatch'
        break
    except Exception as error:
        last_error = error
else:
    raise last_error
parent = pathlib.Path('/opt/retrostar/unpack')
parent.mkdir(parents=True, exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(content), mode='r:gz') as archive:
    members = archive.getmembers()
    roots = {member.name.split('/')[0] for member in members}
    assert len(roots) == 1
    for member in members:
        path = pathlib.PurePosixPath(member.name)
        assert not path.is_absolute() and '..' not in path.parts
        assert member.isdir() or member.isfile(), 'unsupported archive member'
    archive.extractall(str(parent))
source = parent / roots.pop()
source.rename('/opt/retrostar/src')
pathlib.Path('/opt/retrostar/SOURCE_COMMIT').write_text(COMMIT, encoding='ascii')
