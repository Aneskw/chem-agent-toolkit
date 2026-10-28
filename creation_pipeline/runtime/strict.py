"""Migrated strict_acceptance gate. Evidence must be recomputed at each boundary."""
def reports_pass(reports, expected):
    return (type(expected) is int and expected > 0 and len(reports) == expected and
            all(r.get('status') == 'execution_passed' and r.get('acceptance_version') == 2
                and r.get('current_acceptance_validated') is True for r in reports.values()))
