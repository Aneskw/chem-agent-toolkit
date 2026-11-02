"""Explicit caller scopes, never an NLP classifier or a source-file exclusion."""
import copy
import json
import re

from creation_pipeline.contracts import fingerprint, versioned
from creation_pipeline.records import safe_relative

ABI = 'shared_tool_image_v5'
REQUEST_PROTOCOL = 2
VERSION = 1
SOURCE_POLICY = 'complete-snapshots-v1'


def strings(value, field):
    if not isinstance(value, list) or any(not isinstance(s, str) or not s.strip() for s in value):
        raise ValueError(field + ': expected list of nonempty strings; actual=' + repr(value))
    return value


def compatibility(value, *, frozen=False):
    expected = {'version', 'requirements', 'constraints', 'source_policy'} | ({'unclassified'} if frozen else set())
    if not isinstance(value, dict) or set(value) != expected or type(value.get('version')) is not int or value['version'] != VERSION:
        raise ValueError('tool_compatibility: expected version=1 and fields=' + repr(sorted(expected)) + '; actual=' + repr(value))
    if value['source_policy'] != SOURCE_POLICY:
        raise ValueError('tool_compatibility.source_policy: expected ' + SOURCE_POLICY + '; actual=' + repr(value['source_policy']))
    req = value['requirements']; constraints = value['constraints']
    if (not isinstance(req, dict) or set(req) != {'base_image', 'language', 'language_version'}
            or req['language'] != 'python' or not isinstance(req['base_image'], str) or not req['base_image'].strip()
            or not isinstance(req['language_version'], str) or not re.fullmatch(r'[0-9]+\.[0-9]+(?:\.[0-9]+)?', req['language_version'])):
        raise ValueError('tool_compatibility.requirements: expected explicit base_image, language=python, language_version; actual=' + repr(req))
    if not isinstance(constraints, dict) or set(constraints) != {'dependency_files', 'install_commands', 'environment'}:
        raise ValueError('tool_compatibility.constraints: expected dependency_files/install_commands/environment; actual=' + repr(constraints))
    for path in strings(constraints['dependency_files'], 'tool_compatibility.constraints.dependency_files'):
        safe_relative('/schema-only', path)
        if not path.startswith(('package/', 'sources/')):
            raise ValueError('tool_compatibility.constraints.dependency_files: outside implementation closure: ' + path)
    strings(constraints['install_commands'], 'tool_compatibility.constraints.install_commands')
    env = constraints['environment']
    if (not isinstance(env, list) or any(not isinstance(e, dict) or set(e) != {'name', 'value'}
            or not isinstance(e['name'], str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', e['name'])
            or not isinstance(e['value'], str) for e in env) or len({e['name'] for e in env}) != len(env)):
        raise ValueError('tool_compatibility.constraints.environment: expected unique name/value strings; actual=' + repr(env))
    if frozen:
        opaque = value['unclassified']
        if not isinstance(opaque, dict) or set(opaque) != {'requirements', 'constraints', 'caller_constraints'}:
            raise ValueError('tool_compatibility.unclassified: expected legacy requirements/constraints and complete caller_constraints')
        for field in ('requirements', 'constraints'): strings(opaque[field], 'tool_compatibility.unclassified.' + field)
        if not isinstance(opaque['caller_constraints'], dict):
            raise ValueError('tool_compatibility.unclassified.caller_constraints: expected complete caller object')
    return value


def skill(value, *, frozen=False):
    expected = {'version', 'requirements', 'constraints'} | ({'caller_context'} if frozen else set())
    if not isinstance(value, dict) or set(value) != expected or type(value.get('version')) is not int or value['version'] != VERSION:
        raise ValueError('skill_contract: expected version=1 and fields=' + repr(sorted(expected)) + '; actual=' + repr(value))
    for field in ('requirements', 'constraints'): strings(value[field], 'skill_contract.' + field)
    if frozen:
        context = value['caller_context']
        if (not isinstance(context, dict) or set(context) != {'prompt', 'notes', 'constraints', 'checks'}
                or not isinstance(context['prompt'], str) or not isinstance(context['notes'], str)
                or not isinstance(context['constraints'], dict) or not isinstance(context['checks'], list)):
            raise ValueError('skill_contract.caller_context: invalid original caller snapshot')
    return value


def validate_spec(spec):
    if not {'tool_compatibility', 'skill_contract'} & set(spec): return
    if not all(k in spec for k in ('tool_compatibility', 'skill_contract', 'shared_tool')):
        raise ValueError('scoped_contracts_required: tool_compatibility, skill_contract and shared_tool must be explicit together')
    compatibility(spec['tool_compatibility']); skill(spec['skill_contract'])
    # External executable identity remains exclusively under its existing v2 ABI.
    if spec['shared_tool']['requirements']['executables']:
        raise ValueError('scoped_tool_profile_unsupported: external executable identity requires legacy request protocol')


def tool_payload(spec, context=None):
    value = copy.deepcopy(spec['tool_compatibility'])
    value['unclassified'] = {k: copy.deepcopy(spec.get(k, [])) for k in ('requirements', 'constraints')}
    value['unclassified']['caller_constraints'] = copy.deepcopy((context or {}).get('constraints', {}))
    return compatibility(value, frozen=True)


def caller_context(config):
    return copy.deepcopy({k: config.get(k, default) for k, default in
                          (('prompt', ''), ('notes', ''), ('constraints', {}), ('checks', []))})


def skill_payload(spec, context=None):
    value = copy.deepcopy(spec['skill_contract'])
    value['caller_context'] = copy.deepcopy(context if context is not None else caller_context({}))
    return skill(value, frozen=True)


def business_texts(payload):
    skill(payload, frozen=True)
    context = payload['caller_context']
    return [*payload['requirements'], *payload['constraints'], context['prompt'], context['notes'],
            'Current Skill caller constraints: ' + json.dumps(context['constraints'], ensure_ascii=False)]


def check_plan(request, plan):
    value = compatibility(request['tool_compatibility'], frozen=True)
    expected = {**value['requirements'], 'environment': value['constraints']['environment']}
    actual = {key: plan.get(key) for key in expected}
    expected['dependency_files'] = value['constraints']['dependency_files']
    actual['dependency_files'] = plan['build_layout']['dependency_files']
    expected['install_commands'] = value['constraints']['install_commands']
    actual['install_commands'] = [s['command'] for s in plan['steps']]
    for key in expected:
        if expected[key] != actual[key]:
            raise ValueError('tool_compatibility.' + key + ': expected=' + repr(expected[key]) + '; actual=' + repr(actual[key]))


def envelope(value, field):
    if (not isinstance(value, dict) or set(value) != {'version', 'payload', 'sha256'}
            or value['version'] != 1 or type(value['version']) is not int
            or value['sha256'] != fingerprint(value['payload'])):
        raise ValueError(field + ': versioned scope envelope changed or unsupported')
    return value['payload']


def verify_inputs(inputs):
    """Called by qualification, frozen verification and execution inputs."""
    env = inputs['environment']['payload'] or {}
    acceptance = inputs['acceptance']['payload'] or {}
    request = (env.get('shared_tool') or {}).get('request') or {}
    scoped = request.get('request_protocol') == REQUEST_PROTOCOL
    if not scoped and not env.get('tool_compatibility') and not acceptance.get('skill_contract'): return
    tool = compatibility(envelope(env.get('tool_compatibility'), 'tool_compatibility'), frozen=True)
    current = skill(envelope(acceptance.get('skill_contract'), 'skill_contract'), frozen=True)
    from creation_pipeline.artifacts.layout import extract, require
    context = current['caller_context']
    require(inputs['files'], extract({**context, 'runtime_defaults': {'skill_contract': {
        k: v for k, v in current.items() if k != 'caller_context'}}}))
    if env.get('incomplete') and not request:
        return  # Preserved rejected preparation, never executable/qualified.
    if not scoped or request.get('abi') != ABI:
        raise ValueError('scoped_contracts_binding: scoped fields require a v5 request protocol 2 binding')
    if tool != request.get('tool_compatibility'):
        raise ValueError('scoped_contracts_binding: frozen compatibility differs from ToolArtifact request')


def inherit(spec, inputs):
    """Runtime-only repair preserves caller scopes, never silently becomes legacy."""
    env = inputs['environment']['payload'] or {}; acceptance = inputs['acceptance']['payload'] or {}
    if not env.get('tool_compatibility'):
        if 'tool_compatibility' in spec or 'skill_contract' in spec:
            raise ValueError('scope_migration_requires_new_skill: legacy frozen revision needs fresh authoring/review to opt into scoped contracts')
        return None
    verify_inputs(inputs)
    old = envelope(env['tool_compatibility'], 'tool_compatibility')
    current = envelope(acceptance['skill_contract'], 'skill_contract')
    old_skill = {k: copy.deepcopy(v) for k,v in current.items() if k != 'caller_context'}
    if 'skill_contract' in spec and spec['skill_contract'] != old_skill:
        raise ValueError('skill_contract_change_requires_review: runtime-only repair cannot replace the frozen caller business scope; create a new authored/reviewed Skill')
    if 'tool_compatibility' not in spec:
        spec['tool_compatibility'] = {k: copy.deepcopy(v) for k, v in old.items() if k != 'unclassified'}
    for field in ('requirements', 'constraints'): spec.setdefault(field, copy.deepcopy(old['unclassified'][field]))
    declaration = (env.get('shared_tool') or {}).get('request', {}).get('declaration') or env.get('shared_tool_declaration')
    if not declaration: raise ValueError('scoped_contracts_binding: missing implementation declaration for recovery')
    spec.setdefault('shared_tool', copy.deepcopy(declaration))
    spec.setdefault('skill_contract', old_skill)
    return copy.deepcopy(current['caller_context'])
