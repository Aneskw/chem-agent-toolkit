"""Normalize resource groups while preserving the legacy configuration contract explicitly."""
import copy
import json
import re
from pathlib import Path


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', value):
        raise ValueError('IDs must be simple nonempty identifiers')
    return value


def load(path, legacy):
    path = Path(path).resolve()
    raw = path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() == '.json':
        data = json.loads(raw)
    else:
        import yaml
        data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError('Configuration must be an object')
    workflow = data.get('workflow', 'shared-environments')
    if workflow not in {'shared-environments', 'legacy-script-images'}:
        raise ValueError('Unknown workflow')
    extras = {'workflow', 'resource_groups', 'research_access', 'environments'}
    base = {k: v for k, v in data.items() if k not in extras}
    if workflow == 'legacy-script-images':
        if 'resource_groups' in data:
            raise ValueError('Resource groups require shared-environments workflow')
        result = legacy(path, base)
        result['workflow'] = workflow
        return result
    if 'resource_groups' in data and 'sources' in data:
        raise ValueError('Use either sources or resource_groups, not both')
    groups = data.get('resource_groups', [{'id': 'default', 'sources': data.get('sources')}])
    if not isinstance(groups, list) or not groups:
        raise ValueError('resource_groups must be a nonempty array')
    normalized, seen = [], set()
    for group in groups:
        if not isinstance(group, dict) or set(group) != {'id', 'sources'}:
            raise ValueError('Each resource group needs id and sources')
        gid = identifier(group['id'])
        if gid in seen:
            raise ValueError('Duplicate resource group ID')
        seen.add(gid)
        items = copy.deepcopy(group['sources'])
        if not isinstance(items, list) or not items:
            raise ValueError('Each group needs sources')
        links = {}
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError('Each source must be an object')
            sid = item.setdefault('id', f'source{i+1}')
            links[sid] = item.pop('related_to', [])
        if any(not isinstance(v, list) or any(s not in links for s in v) for v in links.values()):
            raise ValueError('related_to must reference sources in the same group')
        part = legacy(path, {**base, 'sources': items})
        normalized.append({'id': gid, 'sources': part['sources'], 'relationships': links})
    result = part
    result.update(workflow=workflow, resource_groups=normalized,
                  research_access=data.get('research_access', 'supplement'))
    if result['research_access'] not in {'supplement', 'known_only'}:
        raise ValueError('research_access must be supplement or known_only')
    env = data.get('environments', {})
    if not isinstance(env, dict) or set(env) - {'root', 'image_prefix', 'source_url', 'operation_timeout', 'publish'}:
        raise ValueError('Unknown environments settings')
    env = dict(env)
    env['root'] = str((path.parent / env.get('root', 'tools/environments')).resolve())
    env.setdefault('image_prefix', '')
    env.setdefault('source_url', '')
    env.setdefault('operation_timeout', 600)
    env.setdefault('publish', True)
    if type(env['publish']) is not bool:
        raise ValueError('environments.publish must be boolean')
    if type(env['operation_timeout']) is not int or env['operation_timeout'] <= 0:
        raise ValueError('operation_timeout must be a positive integer')
    if env['image_prefix'] and not re.fullmatch(r'[a-z0-9][a-z0-9./_-]+', env['image_prefix']):
        raise ValueError('image_prefix must be a registry/repository path without tag')
    result['environments'] = env
    if result['model']['backend'] != 'codex_cli':
        raise ValueError('Shared environment Agents require native tool access via codex_cli; deepseek_api remains available with workflow=legacy-script-images')
    result['execution']['progress_watch'] = data.get('execution', {}).get('progress_watch', 'observe')
    for field in ('runtime', 'runtime_defaults', 'runtime_requirements', 'checks'):
        if data.get(field):
            raise ValueError(field + ' uses the legacy script-image protocol; select workflow=legacy-script-images explicitly')
    return result
