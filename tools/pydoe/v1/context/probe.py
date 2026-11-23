import importlib.metadata as m
import json, platform, sys
name, expected = sys.argv[1:]
observed = platform.python_version() if name == 'Python' else m.version(name)
assert observed == expected, (name, observed, expected)
if name == 'numpy':
    import numpy as np
    assert np.arange(3).sum() == 3
elif name == 'scipy':
    from scipy.special import binom
    assert binom(4, 2) == 6
elif name == 'pyDOE2':
    import numpy as np
    from pyDOE2 import gsd
    expected_design = [[0,0,0],[0,0,4],[0,1,1],[0,1,5],[0,2,2],[0,3,3],[1,0,1],[1,0,5],[1,1,2],[1,2,3],[1,3,0],[1,3,4],[2,0,2],[2,1,3],[2,2,0],[2,2,4],[2,3,1],[2,3,5]]
    assert np.array_equal(gsd([3,4,6], 4, n=1), expected_design)
    try:
        gsd([2,3], 5)
    except ValueError:
        pass
    else:
        raise AssertionError('Expected ValueError')
print(json.dumps({'version': observed}))
