"""Consumer facts are separate from investigation and build instructions."""
import re


CONTRACT_VERSION = 2  # Internal checkpoint format, never a Skill runtime field.


def tool_name(value):
    return re.sub(r'[-_.]+', '-', value).casefold()


def tool_version(value):
    return tuple(int(p) for p in value.split('.')) if re.fullmatch(r'[0-9]+(?:\.[0-9]+)*', value) else value


def requirements(plan):
    if plan.get('contract_version') != CONTRACT_VERSION:
        raise ValueError('Historical environment contract needs explicit reinvestigation in a new batch')
    return {k: plan[k] for k in ('platform', 'conditions')}


def validate(plan):
    requirements(plan)
    if not re.fullmatch(r'linux/(amd64|arm64)', plan['platform']):
        raise ValueError('Unsupported platform')
    conditions = plan['conditions']
    if set(conditions) != {'accelerator', 'minimum_memory_gib', 'network_required'}:
        raise ValueError('Invalid typed runtime conditions')
    if conditions['accelerator'] not in {'none', 'nvidia', 'amd'} or type(conditions['network_required']) is not bool:
        raise ValueError('Invalid accelerator/network requirement')
    memory = conditions['minimum_memory_gib']
    if memory is not None and (type(memory) not in (int, float) or memory <= 0):
        raise ValueError('Minimum memory must be positive or null when not established')
    seen = set()
    for tool in plan['tools']:
        key = (tool['kind'], tool_name(tool['name']))
        if key in seen or not tool['version'].strip() or re.search(r'[<>=*\s]', tool['version']) or not tool['probe']:
            raise ValueError('Tool contracts need unique identities, exact versions and concrete probes')
        seen.add(key)
    if not seen or not plan['evidence'] or plan['unresolved']:
        raise ValueError('Ready environment requires source-backed tools and no unresolved installation gaps')


def runtime(plan, image='{{image}}'):
    """Whitelist projection: no probes, files, evidence, rationale or investigation notes."""
    validate(plan)
    return {'image': image, 'platform': plan['platform'],
            'environment': {'tools': [{k: t[k] for k in ('name', 'version', 'kind')} for t in plan['tools']],
                            'conditions': dict(plan['conditions'])},
            'resources': [{k: r[k] for k in ('name', 'url', 'version', 'included_in_image', 'usage')}
                          for r in plan['resources']],
            'usage_notes': list(plan['usage_notes'])}


def handoff(plan):
    """The author/reviewer needs use requirements, not the entire build context."""
    return {'runtime': runtime(plan), 'evidence': plan['evidence']}
