"""Versioned, opt-in, local closed-bundle tool images. Never stores acceptance.

The caller explicitly declares the implementation closure. All package support
and source files are included; only the non-executable SKILL.md is excluded.
Dynamic loaders and Markdown entrypoints are unsupported by this first ABI.
"""
import ast
import copy
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import uuid
from contextlib import contextmanager

from creation_pipeline.artifacts.package import manifest
from creation_pipeline.contracts import fingerprint
from creation_pipeline.records import has_link, read_json, safe_relative, write_json, sanitized
from . import external_tool, bundled_data

ABI = 'shared_tool_image_v1'
POLICY = 'closed-python-bundle-v1'
ACCEPTANCE = {'tests', 'acceptance_json', 'output_contract', 'unverified_behavior'}
INTEGRITY_COMMAND = 'test -z "$(find package sources -type l -print)" && find package sources -type f -exec sha256sum -- {} +'


def registry_root():
    from creation_pipeline.paths import ROOT
    root = Path(os.environ.get('CHEM_AGENT_SHARED_TOOLS') or ROOT / '.pipeline/shared-tools')
    if not root.is_absolute() or has_link(root):
        raise ValueError('shared_tool.registry: expected absolute unlinked local directory')
    return root


def validate_declaration(declaration):
    """Validate caller-known support boundaries before any paid generation."""
    expected = {'closure', 'requirements', 'interface', 'platform', 'policy'}
    if isinstance(declaration, dict) and declaration.get('policy') == bundled_data.POLICY:
        expected.add('bundled_data')
        bundled_data.declaration(declaration.get('bundled_data'))
    if not isinstance(declaration, dict) or set(declaration) != expected:
        raise ValueError('shared_tool.declaration: require closure, requirements, interface, platform, policy')
    if declaration['closure'] != 'all-package-and-sources-except-skill-document':
        raise ValueError('shared_tool.closure: explicit complete bundle declaration missing')
    if declaration['policy'] not in {POLICY, external_tool.POLICY, bundled_data.POLICY} or declaration['platform'] != 'linux/amd64':
        raise ValueError('shared_tool.policy/platform: unsupported ' + repr(declaration))
    interface = declaration['interface']
    if (not isinstance(interface, dict) or set(interface) != {'entrypoint', 'workdir', 'resources', 'runtime_network'}
            or interface['workdir'] != '/opt/skill' or interface['resources'] != []
            or interface['runtime_network'] is not False):
        raise ValueError('shared_tool.interface: require /opt/skill, no external resources, no runtime network')
    if not isinstance(declaration['requirements'], dict):
        raise ValueError('shared_tool.requirements: explicit dependency/executable requirements object required')
    requirements_spec = declaration['requirements']
    if (set(requirements_spec) != {'imports', 'executables'} or not isinstance(requirements_spec['imports'], dict)
            or not isinstance(requirements_spec['executables'], list)
            or any(not isinstance(v, str) or not v for v in requirements_spec['imports'].values())):
        raise ValueError('shared_tool.requirements: require explicit imports/version requirements and executables')
    if declaration['policy'] == external_tool.POLICY:
        external_tool.validate_requirements(requirements_spec['executables'])
    elif requirements_spec['executables']:
        raise ValueError('shared_tool.requirements.executables: external executables unsupported in v1; actual='
                         + repr(requirements_spec['executables'])
                         + '; use self-contained mode without shared_tool or a supported Python-only tool')
    for name, version in requirements_spec['imports'].items():
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name) or (version != 'unpinned' and not re.fullmatch(r'[0-9][A-Za-z0-9.+_-]*', version)):
            raise ValueError('shared_tool.requirements.imports.' + str(name) + ': require exact version or explicit unpinned')


def validate_python(tree, module, declaration, local_modules, entry):
    """Same finite implementation checks for delivered and declared source modules."""
    path = 'package/' + module
    data_profile = declaration['policy'] == bundled_data.POLICY
    external = declaration['policy'] == external_tool.POLICY
    requirements_spec = declaration['requirements']
    allowed_file_nodes = bundled_data.reads(tree, module, declaration['bundled_data']) if data_profile else set()
    if external:
        external_tool.validate_wrapper(tree, path, entry)
    for node in ast.walk(tree):
        # No declaration can hide a runtime dependency on excluded prose
        # or a dynamically loaded, unenumerated implementation.
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and 'SKILL.md' in node.value:
            raise ValueError('shared_tool.closure: excluded document referenced at ' + path)
        if (isinstance(node, ast.Name) and node.id in {'eval', 'exec', '__import__', '__file__'}
                and id(node) not in allowed_file_nodes):
            raise ValueError('shared_tool.closure: dynamic implementation dependency at ' + path + ':' + str(node.lineno))
        if isinstance(node, ast.Attribute) and node.attr in {'system', 'popen', 'execv', 'execve', 'spawnv', 'spawnve'}:
            raise ValueError('shared_tool.closure: external executable dependency at ' + path)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or '']
            if any(m.split('.')[0] in {'importlib', 'runpy', 'ctypes'} for m in modules):
                raise ValueError('shared_tool.closure: unsupported dynamic loader in ' + path)
            for module in modules:
                name = module.split('.')[0]
                if name and name not in sys.stdlib_module_names and name not in local_modules and name not in requirements_spec['imports']:
                    raise ValueError('shared_tool.requirements.imports.' + name + ': missing explicit dependency requirement; ' + path)
            if not external and any(m.split('.')[0] in {'subprocess'} for m in modules):
                raise ValueError('shared_tool.closure: external process invocation unsupported in v1; ' + path)


def describe(source, binding, declaration, requirements=(), constraints=(), runtime_limits=None):
    """Request identity uses only pre-planning inputs, including explicit requirements."""
    validate_declaration(declaration)
    interface = declaration['interface']
    requirements_spec = declaration['requirements']
    external = declaration['policy'] == external_tool.POLICY
    if binding.get('kind') == 'markdown_python' or binding.get('association') != 'identical':
        raise ValueError('shared_tool.binding: only byte-identical source-backed Python scripts supported')
    if not binding['entry'].endswith('.py'):
        raise ValueError('shared_tool.entry: Python script required')
    from .preparation import validate_bound_entrypoint
    validate_bound_entrypoint({'script': 'package/' + binding['entry'], 'entrypoint': interface['entrypoint']}, binding)
    files = []
    data_profile = declaration['policy'] == bundled_data.POLICY
    if data_profile:
        bundled_data.verify(Path(source) / 'package', declaration['bundled_data'])
    local_modules = {p.stem for p in (Path(source) / 'package').rglob('*.py')}
    local_modules |= {p.parent.name for p in (Path(source) / 'package').rglob('__init__.py')}
    for directory in ('package', 'sources'):
        for item in manifest(Path(source) / directory):
            if directory == 'package' and item['path'] == 'SKILL.md':
                continue
            path = directory + '/' + item['path']
            real = safe_relative(source, path)
            files.append(dict(item, path=path, mode=real.stat().st_mode & 0o777))
            if directory == 'package' and path.endswith('.py'):
                tree = ast.parse(real.read_text(encoding='utf-8-sig'), filename=path)
                validate_python(tree, item['path'], declaration, local_modules, binding['entry'])
    from .planner import DEFAULTS
    limits = runtime_limits if runtime_limits is not None else DEFAULTS
    return {'abi': external_tool.ABI if external else bundled_data.ABI if data_profile else ABI, 'declaration': copy.deepcopy(declaration), 'files': sorted(files, key=lambda f: f['path']),
            'entry': binding['entry'], 'entry_sha256': binding['entry_sha256'],
            'requirements': list(requirements), 'constraints': list(constraints),
            'runtime_limits': {k: limits[k] for k in ('memory', 'cpus', 'pids')}}


def environment_plan(plan):
    return {k: copy.deepcopy(v) for k, v in plan.items() if k not in ACCEPTANCE}


def check_plan(request, plan):
    interface = request['declaration']['interface']
    for key in ('entrypoint', 'resources', 'runtime_network'):
        if plan.get(key) != interface[key]:
            raise ValueError('shared_tool.interface.' + key + ': expected ' + repr(interface[key]) + ', actual ' + repr(plan.get(key)))
    if plan['platform'] != request['declaration']['platform']:
        raise ValueError('shared_tool.platform: plan differs from request')
    # Builds must not alter code or depend on the excluded document.
    if plan['steps'][plan['build_layout']['prefix_steps']:] or plan['generated_files']:
        raise ValueError('shared_tool.recipe: code-dependent steps/generated files unsupported')
    allowed = {f['path'] for f in request['files']}
    provenance = {'package/SKILL.md', 'source-identities.json'}
    if set(plan['source_files']) - allowed - provenance:
        raise ValueError('shared_tool.source_files: outside closure ' + repr(sorted(set(plan['source_files']) - allowed - provenance)))
    if any(n not in allowed for n in plan['build_layout']['dependency_files']):
        raise ValueError('shared_tool.dependencies: dependency file not in implementation closure')
    assessment = plan.get('resource_assessment') or {}
    if assessment.get('status') == 'complete' and assessment.get('source_path') not in allowed:
        raise ValueError('shared_tool.resource_assessment.source_path: expected a stable file in the '
                         'implementation closure; actual=' + repr(assessment.get('source_path'))
                         + '; allowed=' + repr(sorted(allowed))
                         + '. The excluded Skill document changes across callers and cannot ground '
                           'a reusable environment requirement. Read the original source or unchanged '
                           'delivered entry and cite its exact passage; do not rewrite code or waive resources.')
    dependencies = {d['name'].lower(): d['version'] for d in plan['dependencies']}
    for name, version in request['declaration']['requirements']['imports'].items():
        if dependencies.get(name.lower()) != version:
            raise ValueError('shared_tool.dependencies.' + name + ': expected ' + version + ', actual ' + str(dependencies.get(name.lower())))
    if request['abi'] == external_tool.ABI:
        if 'tests' in plan:
            external_tool.validate_plan(plan, request['declaration']['requirements']['executables'][0]['version'])
        for variable in plan['environment']:
            if variable['name'].startswith(('BABEL_', 'LD_')):
                raise ValueError('shared_tool.external_loader_override: ' + variable['name'])


def read_record(path, request=None):
    if has_link(path):
        raise ValueError('shared_tool.record: linked path')
    return validate_record(read_json(path), request)


def validate_reference(reference):
    if (not isinstance(reference, dict) or set(reference) != {'request_key', 'artifact_id'}
            or any(not isinstance(v, str) or not re.fullmatch(r'[0-9a-f]{64}', v) for v in reference.values())):
        raise ValueError('shared_tool.reference: require lowercase SHA256 request_key and artifact_id; paths/tags are unsupported')
    return reference


def select(request, reference, host, process, root=None):
    """Resolve only the explicitly selected version, without searching or fallback."""
    validate_reference(reference)
    root = Path(root) if root is not None else registry_root()
    observation = {'status': 'miss', 'selection': 'explicit', 'reference': copy.deepcopy(reference),
                   'request_key': fingerprint(request)}
    if has_link(root):
        return None, dict(observation, reason='linked_registry')
    path = root / (reference['request_key'] + '-' + reference['artifact_id'] + '.json')
    try:
        record = read_record(path)
        if any(record[k] != reference[k] for k in reference):
            raise ValueError('shared_tool.reference: stored version differs from selected filename identity')
    except FileNotFoundError:
        return None, dict(observation, reason='selected_artifact_not_found', path=str(path))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, dict(observation, reason='invalid_selected_record', path=str(path), detail=str(exc))
    if record['request'] != request:
        expected = record['request']
        mismatches = []
        for key in sorted(set(expected) | set(request)):
            if expected.get(key) != request.get(key):
                if key == 'files':
                    old = {f['path']: f for f in expected[key]}
                    new = {f['path']: f for f in request[key]}
                    mismatches += [{'field': 'files.' + p, 'expected': old.get(p), 'actual': new.get(p)}
                                   for p in sorted(set(old) | set(new)) if old.get(p) != new.get(p)]
                else:
                    mismatches.append({'field': key, 'expected': expected.get(key), 'actual': request.get(key)})
        return None, dict(observation, reason='selected_request_mismatch', mismatches=mismatches)
    reason = available(record, host, process)
    if reason != 'available':
        return None, dict(observation, reason=reason, artifact_id=record['artifact_id'])
    return record, dict(observation, status='hit', reason='selected_exact_version_and_current_image',
                        artifact_id=record['artifact_id'])


def validate_record(record, request=None):
    expected = {'abi', 'request', 'request_key', 'recipe_key', 'plan', 'base_image', 'environment',
                'image_id', 'daemon_id', 'artifact_id'}
    if isinstance(record, dict) and record.get('abi') == external_tool.ABI:
        expected.add('external_identity')
    if not isinstance(record, dict) or set(record) != expected or record['abi'] not in {ABI, external_tool.ABI, bundled_data.ABI}:
        raise ValueError('shared_tool.record: unsupported schema')
    req = record['request']
    if (not isinstance(req, dict) or not isinstance(req.get('declaration'), dict)
            or not isinstance(req.get('files'), list) or not req['files']
            or not isinstance(record['plan'], dict) or not isinstance(record['environment'], dict)):
        raise ValueError('shared_tool.record: malformed request/plan/environment')
    paths = []
    for item in req['files']:
        if (not isinstance(item, dict) or set(item) != {'path', 'sha256', 'bytes', 'mode'}
                or not isinstance(item['path'], str) or not re.fullmatch(r'[0-9a-f]{64}', str(item['sha256']))
                or type(item['mode']) is not int or type(item['bytes']) is not int):
            raise ValueError('shared_tool.files: malformed manifest entry')
        safe_relative(Path(__file__).parent / '__schema_only__', item['path'])
        paths.append(item['path'])
    if paths != sorted(set(paths)):
        raise ValueError('shared_tool.files: duplicate/unsorted implementation paths')
    policy = external_tool.POLICY if record['abi'] == external_tool.ABI else bundled_data.POLICY if record['abi'] == bundled_data.ABI else POLICY
    if record['request'].get('abi') != record['abi'] or record['request']['declaration']['policy'] != policy:
        raise ValueError('shared_tool.policy: version no longer supported')
    validate_declaration(req['declaration'])
    if record['abi'] == external_tool.ABI:
        external_tool.validate_identity(record['external_identity'])
    if record['request_key'] != fingerprint(record['request']):
        raise ValueError('shared_tool.request_key: corrupt request')
    if record['recipe_key'] != fingerprint({'plan': record['plan'], 'base_image': record['base_image']}):
        raise ValueError('shared_tool.recipe_key: corrupt recipe')
    if record['artifact_id'] != fingerprint({k: v for k, v in record.items() if k != 'artifact_id'}):
        raise ValueError('shared_tool.artifact_id: corrupt version')
    if request is not None and record['request'] != request:
        raise ValueError('shared_tool.request: implementation/interface/requirements/platform/policy mismatch')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', record['image_id']) or not record['daemon_id']:
        raise ValueError('shared_tool.identity: missing local image/daemon identity')
    if set(record['plan']) & ACCEPTANCE:
        raise ValueError('shared_tool.record: acceptance must never be published')
    check_plan(record['request'], record['plan'])
    return record


def available(record, host, process, timeout=30, *, verify_external=True):
    if host.get('engine_id') != record['daemon_id']:
        return 'different_daemon'
    result = process(['docker', 'image', 'inspect', record['image_id']], timeout)
    try:
        image = json.loads(result['stdout'])[0]
        config = image['Config']
        if (result['exit_code'] != 0 or image['Id'] != record['image_id']
                or image['Os'] + '/' + image['Architecture'] != record['request']['declaration']['platform']
                or config['Labels'].get('chem.tool.request') != record['request_key']
                or config['Labels'].get('chem.tool.recipe') != record['recipe_key']
                or config['Entrypoint'] != record['plan']['entrypoint']
                or config['WorkingDir'] != '/opt/skill' or config['User'] != '10001:10001'):
            return 'image_unavailable_or_changed'
        from .shared_environment import inheritance_matches
        if not inheritance_matches(record['environment'], image):
            return 'environment_inheritance_changed'
    except (ValueError, KeyError, TypeError, IndexError):
        return 'image_unavailable_or_changed'
    if record['abi'] == external_tool.ABI:
        if config.get('Volumes'):
            return 'external_identity_unsupported_image_volumes'
        if not verify_external:
            return 'external_identity_not_observed'
        try:
            observed = external_tool.observe(record['image_id'], record['request']['declaration']['requirements']['executables'],
                                             process, timeout)
            external_tool.verify(record['external_identity'], observed)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return 'external_identity_unavailable_or_changed: ' + str(exc)
    return 'available'


def resolve(request, host, process, root=None):
    """Read-only lookup; no mkdir, lock, build, business execution or qualification."""
    root = Path(root) if root is not None else registry_root()
    if has_link(root):
        return None, {'status': 'miss', 'reason': 'linked_registry'}
    key = fingerprint(request)
    reasons = []
    for path in sorted(root.glob(key + '-*.json')):
        try:
            record = read_record(path, request)
            reason = available(record, host, process)
            if reason == 'available':
                return record, {'status': 'hit', 'reason': 'exact_request_and_current_image', 'request_key': key,
                                'artifact_id': record['artifact_id']}
            reasons.append({'artifact': path.name, 'reason': reason})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            reasons.append({'artifact': path.name, 'reason': 'invalid_record', 'detail': str(exc)})
    mismatches = []
    if not reasons:
        for path in sorted(root.glob('*.json'))[:32]:
            try:
                other = read_record(path)
                differences = []
                for field in ('abi', 'entry', 'entry_sha256', 'requirements', 'constraints', 'runtime_limits'):
                    if other['request'].get(field) != request.get(field):
                        differences.append(field)
                for field in ('platform', 'policy', 'requirements', 'interface', 'closure'):
                    if other['request']['declaration'].get(field) != request.get('declaration', {}).get(field):
                        differences.append('declaration.' + field)
                if isinstance(request.get('files'), list):
                    old = {f['path']: f for f in other['request']['files']}
                    new = {f['path']: f for f in request['files']}
                    differences += ['files.' + p for p in sorted(set(old) | set(new)) if old.get(p) != new.get(p)]
                elif other['request']['files'] != request.get('files'):
                    differences.append('files')
                mismatches.append({'artifact_id': other['artifact_id'], 'mismatched_objects': differences})
            except (OSError, ValueError, KeyError, TypeError):
                continue
    return None, {'status': 'miss', 'reason': 'no_available_exact_request', 'request_key': key,
                  'candidates': reasons, 'other_versions': mismatches}


@contextmanager
def locked(root, key, deadline):
    root = Path(root)
    if has_link(root):
        raise ValueError('shared_tool.registry: linked root')
    root.mkdir(parents=True, exist_ok=True)
    path = root / (key + '.lock')
    owner = str(os.getpid()) + ':' + uuid.uuid4().hex
    while True:
        if time.monotonic() >= deadline:
            raise ValueError('shared_tool.lock: deadline reached for ' + key)
        try:
            handle = path.open('x', encoding='utf-8')
            break
        except FileExistsError:
            time.sleep(min(.1, max(0, deadline - time.monotonic())))
    try:
        with handle:
            handle.write(owner)
        yield
    finally:
        # Cancellation/timeout must never release a replacement owner's lock.
        if not has_link(path):
            try:
                if path.read_text(encoding='utf-8') == owner:
                    path.unlink()
            except FileNotFoundError:
                pass


def combine(record, acceptance):
    if not isinstance(acceptance, dict) or set(acceptance) != ACCEPTANCE:
        raise ValueError('shared_tool.current_acceptance_required: supply exactly ' + ', '.join(sorted(ACCEPTANCE)))
    return dict(copy.deepcopy(record['plan']), **copy.deepcopy(acceptance))


def verify_binding(env, materials):
    binding = env['shared_tool']
    if binding.get('abi') not in {ABI, external_tool.ABI, bundled_data.ABI}:
        raise ValueError('shared_tool.binding: unsupported ABI')
    request = binding['request']
    if binding['abi'] != request['abi']:
        raise ValueError('shared_tool.binding: ABI differs from request')
    if binding['request_key'] != fingerprint(request):
        raise ValueError('shared_tool.binding: request key mismatch')
    actual = describe(Path(materials) / 'context',
                      {'entry': request['entry'], 'entry_sha256': request['entry_sha256'], 'association': 'identical'},
                      request['declaration'], request['requirements'], request['constraints'], env['limits'])
    if actual != request:
        raise ValueError('shared_tool.binding: complete current closure/runtime requirements differ from request')
    check_plan(request, env['plan'])
    for item in request['files']:
        path = safe_relative(Path(materials) / 'context', item['path'])
        from creation_pipeline.records import file_digest
        if file_digest(path) != item['sha256'] or path.stat().st_mode & 0o777 != item['mode']:
            raise ValueError('shared_tool.closure: frozen content/mode changed at ' + item['path'])
    concrete = binding.get('artifact')
    if 'selection' in binding:
        reference = validate_reference(binding['selection'])
        if not concrete or any(concrete.get(k) != reference[k] for k in reference):
            raise ValueError('shared_tool.selection: frozen artifact differs from explicitly selected version')
    if concrete:
        validate_record(concrete, request)
        # Validate the embedded record without trusting a mutable registry pointer.
        if (concrete['request'] != request or concrete['plan'] != environment_plan(env['plan'])
                or concrete['base_image'] != env.get('base_image')):
            raise ValueError('shared_tool.binding: concrete recipe differs from frozen inputs')
    return binding


def build_process(args, timeout, deadline, process, logs, build_calls):
    """Keep owned probe cleanup possible even after the build deadline expires."""
    cleanup = (len(args) == 4 and args[:3] == ['docker', 'rm', '--force']
               and re.fullmatch(r'chem-external-identity-[0-9a-f]{32}', args[3]))
    remaining = deadline - time.monotonic()
    if remaining <= 0 and not cleanup:
        raise ValueError('shared_tool.build: original deadline exhausted')
    if args[:2] == ['docker', 'build']:
        build_calls['environment' if 'chem.shared.recipe=' in ' '.join(args) else 'tool'] += 1
    result = process(args, min(10, timeout or 10) if cleanup else min(remaining, timeout or remaining))
    logs.append(result)
    return result


def build(executor, request, record, env, materials):
    """Bind a checked concrete image, or publish a fully checked new version."""
    from .local import process, binding_identity, gap
    from .shared_environment import resolve as resolve_environment
    from .execution import image_files_match
    from . import runner
    from creation_pipeline.records import file_digest, now
    binding = verify_binding(env, materials)
    attempt = Path(request.attempt_directory)
    attempt.mkdir(parents=True, exist_ok=False)
    preflight = executor.preflight(request)
    receipt = dict(preflight, version=2, backend='local-docker', request=binding_identity(request),
                   started_at=now(), status='runtime_blocked', execution_status='runtime_blocked',
                   business_acceptance='not_run', image_id=None, shared_tool={'status': 'miss'},
                   build_calls={'environment': 0, 'tool': 0})
    write_json(attempt / 'attempt-start.json', sanitized(receipt))
    logs = []
    deadline = min(time.monotonic() + env['limits']['build_seconds'], executor.deadline or float('inf'))
    def run(args, timeout=None):
        return build_process(args, timeout, deadline, process, logs, receipt['build_calls'])
    def check_bytes(artifact):
        expected = {f['path']: f['sha256'] for f in binding['request']['files']}
        tool = {'limits': env['limits'], 'runtime_network': False, 'execution_scope': attempt.name}
        # Both the canonical tool tree and the compatibility execution layout
        # must contain exactly the frozen implementation bytes.
        for directory in ('/opt/skill', '/opt/tools/' + binding['request_key']):
            observation = runner.run(tool, artifact['image_id'],
                ['-c', 'cd ' + directory + ' && ' + INTEGRITY_COMMAND],
                entrypoint='/bin/sh', timeout=min(executor.probe_timeout, max(.1, deadline-time.monotonic())))
            logs.append(observation)
            if not image_files_match(observation, expected):
                raise ValueError('shared_tool.image_files: implementation differs at ' + directory)
        required = binding['request']['declaration']['requirements']['imports']
        if required:
            code = 'import importlib.metadata,json; print(json.dumps({n:importlib.metadata.version(n) for n in ' + repr(list(required)) + '}))'
            observed = runner.run(tool, artifact['image_id'], ['-c', code], entrypoint='python',
                                  timeout=min(executor.probe_timeout, max(.1, deadline-time.monotonic())))
            logs.append(observed)
            versions = json.loads(observed['stdout']) if observed['exit_code'] == 0 else {}
            for name, version in required.items():
                if name not in versions or (version != 'unpinned' and versions[name] != version):
                    raise ValueError('shared_tool.installed_dependency.' + name + ': expected ' + version + ', actual ' + str(versions.get(name)))
    try:
        if preflight['gaps']:
            return receipt
        concrete = binding.get('artifact')
        if concrete:
            reason = available(concrete, preflight['host'], run)
            if reason != 'available':
                raise ValueError('shared_tool.bound_artifact ' + concrete['artifact_id'] + ': ' + reason + '; explicit prepare required')
            check_bytes(concrete)
            status = 'hit'
        else:
            root = registry_root()
            with locked(root, binding['request_key'], deadline):
                concrete, observation = resolve(binding['request'], preflight['host'], run, root)
                # A racing publisher may only supply the exact frozen recipe.
                if concrete and (concrete['plan'] != environment_plan(env['plan']) or concrete['base_image'] != env['base_image']):
                    concrete = None
                status = 'hit' if concrete else 'built'
                if not concrete:
                    context, shared, _ = resolve_environment(materials, None, preflight['host'], run, deadline, attempt)
                    target = attempt / 'shared-tool-context'
                    target.mkdir()
                    for item in binding['request']['files']:
                        dest = safe_relative(target, item['path'])
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(safe_relative(context, item['path']), dest)
                    original = (context / 'Dockerfile').read_text(encoding='utf-8')
                    # Retain prefix and non-root/entrypoint semantics; no prose or
                    # acceptance fixtures enter this tool-only image.
                    text = original.replace('COPY . ./', 'COPY . /opt/tools/' + binding['request_key'] + '/\nCOPY . ./')
                    (target / 'Dockerfile').write_text(text, encoding='utf-8')
                    recipe = fingerprint({'plan': environment_plan(env['plan']), 'base_image': env['base_image']})
                    result = run(['docker', 'build', '--platform', env['plan']['platform'], '--iidfile', str(attempt / 'image.id'),
                                  '--label', 'chem.tool.request=' + binding['request_key'],
                                  '--label', 'chem.tool.recipe=' + recipe, str(target)])
                    if result['exit_code'] != 0:
                        receipt['status'] = receipt['execution_status'] = 'build_failed'
                        raise ValueError('shared_tool.build: Docker tool build failed; see build-log.json')
                    concrete = {'abi': binding['request']['abi'], 'request': binding['request'], 'request_key': binding['request_key'],
                                'recipe_key': recipe, 'plan': environment_plan(env['plan']), 'base_image': env['base_image'],
                                'environment': {k: v for k, v in shared.items() if k != 'registry'},
                                'image_id': (attempt / 'image.id').read_text().strip(), 'daemon_id': preflight['host']['engine_id']}
                    if concrete['abi'] == external_tool.ABI:
                        concrete['external_identity'] = external_tool.observe(concrete['image_id'],
                            binding['request']['declaration']['requirements']['executables'], run,
                            min(executor.probe_timeout, max(.1, deadline-time.monotonic())))
                    concrete['artifact_id'] = fingerprint(concrete)
                    validate_record(concrete, binding['request'])
                    reason = available(concrete, preflight['host'], run)
                    if reason != 'available':
                        raise ValueError('shared_tool.publish: ' + reason)
                    check_bytes(concrete)
                    executor.inputs(request)
                    path = root / (binding['request_key'] + '-' + concrete['artifact_id'] + '.json')
                    if has_link(path) or has_link(path.with_suffix('.json.tmp')):
                        raise ValueError('shared_tool.publish: linked record')
                    if not path.exists():
                        write_json(path, sanitized(concrete))
                else:
                    check_bytes(concrete)
        receipt.update(status='built', execution_status='not_run', image_id=concrete['image_id'], tag=concrete['image_id'],
                       tool_artifact=concrete, shared_tool={'status': status, 'artifact_id': concrete['artifact_id'],
                                                        'request_key': binding['request_key']},
                       shared_environment=(concrete['environment'] if status == 'built' else
                                           {'status': 'not_requested_tool_hit', 'artifact_environment': concrete['environment']}))
    except KeyboardInterrupt:
        receipt['gaps'] = [gap('caller_cancelled', 'ToolArtifact build/bind interrupted before completion: '
                               + binding['request_key'])]
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        if getattr(exc, 'status', None) == 'build_failed':
            receipt['status'] = receipt['execution_status'] = 'build_failed'
        receipt['gaps'] = [gap('shared_tool_unavailable', str(exc))]
    finally:
        executor.inputs(request)
        write_json(attempt / 'build-log.json', sanitized(logs))
        receipt.update(finished_at=now(), log_sha256=file_digest(attempt / 'build-log.json'))
        write_json(attempt / 'receipt.json', sanitized(receipt))
    return receipt


def inspect(root=None, host=None, process=None):
    root = Path(root) if root is not None else registry_root()
    result = []
    if has_link(root):
        raise ValueError('shared_tool.registry: linked root')
    for path in sorted(root.glob('*.json')):
        try:
            record = read_record(path)
            status = available(record, host, process) if process else 'historical_unverified'
            result.append({'path': str(path), 'artifact_id': record['artifact_id'], 'status': status,
                           'abi': record['abi'],
                           'reference': {k: record[k] for k in ('request_key', 'artifact_id')},
                           'recipe_key': record['recipe_key'], 'image_id': record['image_id'],
                           'daemon_id': record['daemon_id'], 'platform': record['request']['declaration']['platform']})
            if record['abi'] == external_tool.ABI:
                identity = record['external_identity']
                result[-1]['external_identity'] = {k: identity[k] for k in ('executable', 'rootfs', 'plugins', 'data')}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result.append({'path': str(path), 'status': 'invalid_record', 'detail': str(exc)})
    return sanitized({'abi': ABI, 'supported_abis': [ABI, external_tool.ABI, bundled_data.ABI], 'registry': str(root), 'artifacts': result,
                      'pending': [p.name for p in root.glob('*.lock')], 'business_acceptance': 'not_run'})
