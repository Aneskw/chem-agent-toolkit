"""Map native check declarations into auditable container cases, never host argv."""
import re
from pathlib import PurePosixPath
from creation_pipeline.validation.runtime import validate_test


def mapped_checks(definitions, plan, source_ids):
    definitions = definitions or {}
    if 'author_tests' in definitions:
        definitions = definitions['author_tests']
    macros = {'{package}': '/opt/skill/package', '{run}': '/output'}
    macros.update({'{source:' + sid + '}': '/sources/' + sid for sid in source_ids})
    interpreter = plan['entrypoint'][0]
    if 'python' in plan['language'].lower():
        macros['{python}'] = interpreter
    def translate(value):
        for token, target in macros.items():
            value = value.replace(token, target)
        if re.search(r'\{(?:package|source:|python|run|bundle|tool:)', value) or re.search(r'[A-Za-z]:[\\/]', value):
            raise ValueError('Unmapped host/macro path in container check')
        return value
    cases = []
    for origin in ('configured', 'generated', 'reviewed'):
        for test in definitions.get(origin, []):
            validate_test(test)
            argv = [translate(a) for a in test['argv']]
            for arg in argv:
                if arg.startswith('/') and not arg.startswith(('/opt/skill/', '/sources/', '/output', '/input', '/usr/bin/', '/bin/')):
                    raise ValueError('Check references an undeclared host file: ' + arg)
            cwd = translate(test.get('cwd', '{run}') or '{run}')
            if not cwd.startswith(('/opt/skill/package', '/sources/', '/output')) or '..' in PurePosixPath(cwd).parts:
                raise ValueError('Check cwd is outside mapped container locations')
            for path in test.get('artifacts', []):
                if PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts or '\\' in path:
                    raise ValueError('Check artifact must be relative to /output')
            cases.append({'name': 'check-' + origin + '-' + test['name'], 'origin': 'authored_check',
                'basis': test.get('purpose', 'Explicit configured check'), 'layer': 'interface',
                'kind': 'reference', 'oracle_status': 'supported', 'tolerance': 0,
                'source_paths': [], 'limitations': [], 'entrypoint': argv[0], 'args': argv[1:],
                'expected_exit': test.get('expected_exit', 0), 'stdout_contains': test.get('stdout_contains', []),
                'json_equals': test.get('json_equals', {}), 'artifacts': test.get('artifacts', []),
                'mapped_check': True, 'workdir': cwd})
    return cases
