import hashlib
import importlib.metadata
from pathlib import Path

root = importlib.metadata.distribution('auto-qchem')
path = Path(root.locate_file('autoqchem/rdkit_utils.py'))
raw = path.read_bytes()
assert hashlib.sha256(raw).hexdigest() == '769cc0f715c7d307ef3937e8f9ea0c34424e3e5d587482cdb646b78ac92f34a0', 'Unexpected upstream source'
text = raw.decode('utf-8')
statement = 'from autoqchem.gaussian_log_extractor import gaussian_log_extractor\n'
assert text.count(statement) == 1
text = text.replace(statement, '')
needle = '            le = gaussian_log_extractor('
assert text.count(needle) == 2
text = text.replace(needle, '            ' + statement + needle)
path.write_text(text, encoding='utf-8')
for name, expected in {
    'gaussian_log_extractor.py': '61126640feddb1524f24b0fbda1a3a7a6674d048ea3e6335a0703cb148fba667',
    'descriptor_functions.py': 'fb66c1550bda4e10e391035d50e90679633b89da2e8ac414e929f1b97cb1bd5d',
}.items():
    p = Path(root.locate_file('autoqchem/' + name))
    assert hashlib.sha256(p.read_bytes()).hexdigest() == expected
