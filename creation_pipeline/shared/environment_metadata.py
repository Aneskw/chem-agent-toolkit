"""Portable environment descriptions and content-bound private observations."""
import json
from collections import Counter

from creation_pipeline.records import digest, read_json, safe_relative
from .contracts import CONTRACT_VERSION


PRIVATE_FIELDS = ('contract_version', 'fingerprint', 'tag', 'content_id', 'checks', 'anonymous_access', 'checked_at')
DEFAULT_CONDITIONS = {'accelerator': 'none', 'minimum_memory_gib': None, 'network_required': False}


def identity(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def describe(record):
    """Keep facts needed to locate, reproduce and check this environment."""
    if record.get('contract_version', CONTRACT_VERSION) != CONTRACT_VERSION:
        raise ValueError('Historical environment contract requires reinvestigation')
    value = {k: record[k] for k in ('id', 'version', 'platform', 'base_image', 'files')}
    for key in ('image', 'digest'):
        if record.get(key):
            value[key] = record[key]
    prefixes = Counter(tuple(t['probe'][:-2]) for t in record['tools']
        if len(t['probe']) > 2 and t['probe'][-2:] == [t['name'], t['version']])
    shared = list(prefixes.most_common(1)[0][0]) if prefixes and prefixes.most_common(1)[0][1] > 1 else None
    if shared:
        value['probe'] = shared
    value['tools'] = []
    for tool in record['tools']:
        item = {k: tool[k] for k in ('name', 'version', 'kind')}
        if shared is None or tool['probe'] != shared + [tool['name'], tool['version']]:
            item['probe'] = tool['probe']
        value['tools'].append(item)
    if record.get('resources'):
        value['resources'] = [{k: resource[k] for k in ('name', 'url', 'version', 'included_in_image', 'usage')}
                              for resource in record['resources']]
    conditions = {k: record['conditions'][k] for k in DEFAULT_CONDITIONS
                  if record.get('conditions', {}).get(k) not in (None, False, 'none')}
    if conditions:
        value['conditions'] = conditions
    return value


def index_entry(record):
    return {k: record[k] for k in ('id', 'version', 'path')}


def state_path(private, record):
    return safe_relative(private, 'records/' + record['id'] + '/' + record['version'] + '.json')


def observation(record, metadata):
    return {'metadata_sha256': identity(metadata),
            **{k: record[k] for k in PRIVATE_FIELDS if k in record}}


def restore(root, private, entry):
    # Read existing full catalogs until they are explicitly compacted or updated.
    if 'files' in entry:
        if entry.get('contract_version') == 3:
            return {**entry, 'contract_version': CONTRACT_VERSION, 'checks': 'unverified',
                    'anonymous_access': {'status': 'unverified'}}
        return entry
    if set(entry) != {'id', 'version', 'path'}:
        raise ValueError('Invalid environment index entry')
    directory = safe_relative(root, entry['path'])
    metadata = read_json(directory / 'environment.json')
    if any(metadata.get(k) != entry[k] for k in ('id', 'version')):
        raise ValueError('Environment metadata differs from its index')
    tools = []
    for tool in metadata['tools']:
        probe = tool.get('probe')
        if probe is None:
            if not metadata.get('probe'):
                raise ValueError('Environment tool has no check command')
            probe = metadata['probe'] + [tool['name'], tool['version']]
        tools.append({**tool, 'probe': probe})
    record = {**{k: metadata[k] for k in ('platform', 'base_image', 'files')}, **entry,
              'tools': tools, 'contract_version': CONTRACT_VERSION,
              'resources': metadata.get('resources', []),
              'conditions': {**DEFAULT_CONDITIONS, **metadata.get('conditions', {})},
              'image': metadata.get('image'), 'digest': metadata.get('digest'),
              'checks': 'unverified', 'anonymous_access': {'status': 'unverified'}}
    saved = state_path(private, entry)
    if saved.exists():
        facts = read_json(saved)
        if facts.get('metadata_sha256') == identity(metadata) and facts.get('contract_version') == CONTRACT_VERSION:
            record.update({k: facts[k] for k in PRIVATE_FIELDS if k in facts})
    if record.get('image') and record.get('digest'):
        record['state'] = 'published'
        record.setdefault('tag', record['image'].split(':', 1)[0] + '@' + record['digest'])
    else:
        record['state'] = 'built'
        record.setdefault('tag', 'chem-env:' + identity(metadata))
    return record
