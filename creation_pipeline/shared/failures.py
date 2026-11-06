"""Host failures have deterministic owners; model diagnosis handles operation results."""


class IntegrityError(ValueError):
    """A source/package identity changed outside the writing stage."""


class InfrastructureError(ValueError):
    """An operation failed before business code could be evaluated."""
    def __init__(self, message, observation=None):
        super().__init__(message)
        self.observation = observation


def route(exc, phase):
    from .verification import TestPlanError, ReviewPlanError
    from .environment import OperationError
    if isinstance(exc, ReviewPlanError):
        return 'review'
    if isinstance(exc, TestPlanError):
        return 'prepare-tests'
    if isinstance(exc, (IntegrityError, InfrastructureError)):
        return 'blocked'
    if isinstance(exc, (OSError, KeyError, TypeError)):
        return 'blocked'
    if isinstance(exc, OperationError):
        # Publishing/connectivity is infrastructure, never a request to edit Skill code.
        return 'blocked' if phase == 'publish' else 'diagnose'
    if phase == 'environment':
        return 'environment'
    if phase in {'prepare-tests', 'audit-tests'}:
        return 'prepare-tests'
    # Generic host validation/persistence errors must not be interpreted as content defects.
    return 'blocked'
