"""One execution-policy gate; counts and stored booleans never replace evidence."""
from pathlib import Path
import json
from runtime_docker import evidence

ROOT = Path(__file__).resolve().parent.parent


def reports_pass(reports, expected):
    return (type(expected) is int and expected > 0 and len(reports) == expected and
            all(r.get('status') == 'execution_passed' and r.get('acceptance_version') == 2
                and r.get('current_acceptance_validated') is True for r in reports.values()))


def evaluate(paths, expected):
    paths = [Path(p) if Path(p).is_absolute() else ROOT / p for p in paths]
    unique = len({p.resolve() for p in paths}) == len(paths)
    reports = {}
    for path in paths:
        try:
            report = evidence(path)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            report = {'status': 'needs_review', 'error': str(exc)}
        reports[str(path.resolve())] = report
    return {'current_acceptance_validated': unique and reports_pass(reports, expected),
            'candidate_paths': [str(p.resolve()) for p in paths],
            'current_acceptance_checks': {p: {'status': r.get('status'),
                'acceptance_version': r.get('acceptance_version'),
                'current_acceptance_validated': r.get('current_acceptance_validated', False),
                'error': r.get('error')} for p, r in reports.items()}}


def record_passes(record):
    """Revalidate at the final exit boundary, including no-publish and batch paths."""
    expected = record.get('candidate_count')
    statuses = record.get('execution_checks', record.get('runtime_checks', {}))
    if (record.get('current_acceptance_validated') is not True or type(expected) is not int or expected < 1
            or len(statuses) != expected or any(s != 'execution_passed' for s in statuses.values())
            or len(record.get('candidate_paths', [])) != expected):
        return False
    return evaluate(record['candidate_paths'], expected)['current_acceptance_validated']


def candidates(directory):
    return sorted(p for p in Path(directory).glob('*') if (p / 'SKILL.md').is_file())


def publication_completed(stdout):
    for line in (stdout or '').splitlines():
        try:
            if json.loads(line).get('status') == 'published_locally':
                return True
        except (ValueError, AttributeError):
            pass
    return False
