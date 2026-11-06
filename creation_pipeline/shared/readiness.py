"""Observe all resource groups without inference or building images."""
import copy


def check(config, mode='build', offline=False):
    from creation_pipeline.readiness import check as legacy_check
    checks = []
    for group in config['resource_groups']:
        part = copy.deepcopy(config)
        part.update(workflow='legacy-script-images', sources=group['sources'])
        result = legacy_check(part, 'discover', offline=True)
        checks += [{**c, 'group': group['id']} for c in result['checks']]
    if offline:
        checks.append({'object': 'cli', 'status': 'deferred', 'code': 'startup_not_observed'})
        if mode == 'build':
            checks.append({'object': 'docker', 'status': 'deferred', 'code': 'docker_not_observed'})
    else:
        from .preflight import observe
        checks.extend(observe(config, mode))
    blocked = [c for c in checks if c['status'] == 'blocked']
    return {'workflow': 'shared-environments', 'status': 'blocked' if blocked else 'deferred' if any(c['status'] == 'deferred' for c in checks) else 'ready',
            'checks': checks, 'gaps': blocked, 'mode': mode, 'model_calls': 0, 'build_calls': 0,
            'qualification': 'not_granted', 'runtime_required': mode == 'build'}
