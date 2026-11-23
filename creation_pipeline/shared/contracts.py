"""Consumer facts are separate from investigation and build instructions."""
import re


CONTRACT_VERSION = 4  # Internal checkpoint format, never a Skill runtime field.


def tool_name(value):
    return re.sub(r'[-_.]+', '-', value).casefold()


def tool_version(value):
    return tuple(int(p) for p in value.split('.')) if re.fullmatch(r'[0-9]+(?:\.[0-9]+)*', value) else value


def bundled(plan):
    return [r for r in plan['resources'] if r['included_in_image']]


def skill_requirements(plan):
    """Resolve selections without duplicating the installed inventory in Agent records."""
    tools, resources = [], []
    for field, entries, target in (('skill_tools', plan['tools'], tools),
                                    ('skill_resources', plan['resources'], resources)):
        selected = plan.get(field)
        if not isinstance(selected, list) or any(not isinstance(n, str) for n in selected) or len(selected) != len(set(selected)):
            raise ValueError(field + ' must select unique names from the environment contract')
        for name in selected:
            matches = [entry for entry in entries if
                       (tool_name(entry['name']) == tool_name(name) if field == 'skill_tools' else entry['name'] == name)]
            if len(matches) != 1:
                raise ValueError(field + ' contains an unknown or ambiguous name: ' + str(name))
            target.append(matches[0])
    if not tools:
        raise ValueError('Select the tools needed by this Skill')
    return tools, resources


def requirements(plan):
    if plan.get('contract_version') != CONTRACT_VERSION:
        raise ValueError('Historical environment contract needs explicit reinvestigation in a new batch')
    return {k: plan[k] for k in ('platform', 'conditions')}


def validate(plan):
    requirements(plan)
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', plan['environment_id']):
        raise ValueError('Choose a short, stable environment_id; it must not be empty')
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
    skill_requirements(plan)


def runtime(plan, image='{{image}}'):
    """Whitelist projection: no probes, files, evidence, rationale or investigation notes."""
    validate(plan)
    tools, resources = skill_requirements(plan)
    environment = {'tools': [{k: t[k] for k in ('name', 'version', 'kind')} for t in tools]}
    conditions = {k: v for k, v in plan['conditions'].items() if v is not None and v is not False and v != 'none'}
    if conditions:
        environment['conditions'] = conditions
    result = {'image': image, 'platform': plan['platform'], 'environment': environment}
    if resources:
        result['resources'] = [{k: r[k] for k in ('name', 'url', 'version', 'included_in_image', 'usage')} for r in resources]
    if plan['usage_notes']:
        result['usage_notes'] = list(plan['usage_notes'])
    return result



def handoff(plan):
    """The author/reviewer needs use requirements, not the entire build context."""
    return {'runtime': runtime(plan), 'evidence': plan['evidence']}
