"""New workflow integration and invariants; Docker calls are simulated explicitly."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.models import load_config
from creation_pipeline.records import read_json, write_json, lease
from creation_pipeline.resources.workspace import prepare
from creation_pipeline.shared.environment import compatible, fingerprint, EnvironmentLibrary, OperationError
from creation_pipeline.shared.delivery import entries, install, promote
from creation_pipeline.shared.pipeline import build
from creation_pipeline.shared.verification import bind_items, validate_plan, execute
from creation_pipeline.shared.resources import index, lookup, adopt
from creation_pipeline.shared.retention import pin, clean
from creation_pipeline.resources.intake import Sources


IMAGE = 'ghcr.io/example/project/env@sha256:' + 'a' * 64


def env_plan():
    return {'status': 'ready', 'reason': '', 'resume_when': '', 'selection': 'new',
        'environment_id': 'env-python', 'platform': 'linux/amd64', 'base_image': 'python:3.11',
        'tools': [{'name': 'python', 'version': '3.11', 'kind': 'runtime', 'probe': ['python', '-V']}],
        'contract_version': 2, 'conditions': {'accelerator': 'none', 'minimum_memory_gib': None, 'network_required': False},
        'resources': [], 'usage_notes': [], 'investigation_notes': [], 'unresolved': [], 'evidence': ['e1'],
        'files': [{'path': 'Dockerfile', 'content': 'FROM python:3.11\n'}], 'rationale': 'Documented runtime'}


class Session:
    calls = []
    mode = 'exempt'
    def __init__(self, config, sources, limits, work):
        self.config, self.sources, self.limits, self.work = config, sources, limits, Path(work)
        self.workspace = prepare(sources, work)
        self.receipts, self.state = [], {'completed': {}}
        self.model_name = 'simulated'

    def stage(self, instructions, context, schema=None):
        phase = context['_phase']
        self.calls.append((self.config['_group_id'], phase))
        self.receipts.append({'phase': phase})
        if phase == 'discovery':
            return {'outcome': 'candidates', 'summary': 'A grounded callable', 'saved_candidates': [],
                    'candidates': [{'name': 'skill-' + self.config['_group_id'], 'capability': 'Print result',
                        'boundary': 'No input', 'value': 'Concrete workflow', 'usage_path': 'python print',
                        'construction': 'Existing documented API', 'evidence': [{'id': 'e1', 'claim': 'Print result'}],
                        'gaps': [], 'blocked': False, 'tools': ['python'], 'resources': [],
                        'tool_requirements': [], 'environment_gaps': []}], 'omitted': [], 'limitations': []}
        if phase == 'environment':
            return env_plan()
        if phase == 'author':
            target = Path(context['output_directory'])
            name = context['plan']['name']
            (target / 'SKILL.md').write_text('---\nname: ' + name + '\ndescription: Print the result\n---\n# Print\n'
                'Use {{image}}; see [runtime.json](runtime.json).\n```python\nprint(2)\n```\n'
                '```bash\ndocker pull {{image}}\ndocker run --rm {{image}} python code.py\n```\n', encoding='utf-8')
            write_json(context['metadata_path'], {'basis': [{'location': 'SKILL.md', 'claim': 'Print result',
                'source': 'e1', 'locator': 'Original example', 'origin': 'upstream'}]})
            return {'completed': True, 'summary': 'Written'}
        if phase == 'review':
            if self.mode == 'mutating-review':
                package = next((self.work / 'candidates').glob('*/package/SKILL.md'))
                package.write_text(package.read_text(encoding='utf-8') + '\nUnreviewed replacement\n', encoding='utf-8')
            return {'status': 'pass', 'resolution': 'none', 'findings': [], 'execution_items': [{
                'id': 'sample', 'file': 'SKILL.md', 'start_line': 8, 'end_line': 8,
                'necessary': self.mode != 'exempt', 'reason': 'Documented call' if self.mode == 'exempt' else 'Custom result',
                'expected_check': 'Print 2'}]}
        if phase == 'execution':
            return {'status': 'ready', 'reason': '', 'resume_when': '', 'blocked_owner': 'none', 'audit_risks': [], 'cases': [], 'deferred': [
                {'item_id': 'sample', 'reason': 'Unavailable licensed input', 'resume_when': 'Supply input'}], 'context_notes': []}
        if phase == 'execution-audit':
            return {'status': 'pass', 'reason': 'A genuine resource limitation'}
        if phase.startswith('repair-'):
            return {'action': 'blocked', 'reason': 'External environment unavailable',
                    'new_evidence_or_change': '', 'resume_when': 'Start Docker'}
        raise AssertionError(phase)


class Library:
    fail = False
    def __init__(self, config, state):
        self.root = Path(config['environments']['root'])
        self.timeout, self.run = 30, lambda *args: {'exit_code': 0, 'stdout': '', 'stderr': ''}
    def records(self):
        return []
    def ensure(self, plan, directory):
        if self.fail:
            raise ValueError('Docker unavailable')
        return {**plan, 'id': 'env-python', 'version': '1', 'checks': 'passed', 'tag': 'local:1', 'image': None}
    def probe(self, *args):
        pass
    def publish(self, env):
        return {**env, 'image': IMAGE}


class SharedCreationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'source.txt').write_text('Documented print(2)', encoding='utf-8')
        self.config_path = self.root / 'input.json'
        self.config = {'resource_groups': [{'id': g, 'sources': [{'id': 'code', 'path': 'source.txt'}]} for g in ('a', 'b')]}
        write_json(self.config_path, self.config)
        Session.calls, Session.mode, Library.fail = [], 'exempt', False

    def run_build(self, **kwargs):
        with patch('creation_pipeline.shared.pipeline.EnvironmentLibrary', Library):
            return build(self.config_path, self.root / 'state', library_root=self.root / 'skills', _session_factory=Session, **kwargs)

    def test_groups_serial_exempt_is_verified_and_install_pure(self):
        result = self.run_build()
        self.assertEqual(result['status'], 'ready', result)
        self.assertEqual(result['counts'], {'verified': 2})
        phases = [g for g, p in Session.calls]
        self.assertEqual(phases, sorted(phases))
        self.assertEqual(sum(p == 'discovery' for _, p in Session.calls), 2)
        package = self.root / 'skills/verified/skill-a'
        self.assertEqual(read_json(package / 'runtime.json')['image'], IMAGE)
        self.assertNotIn('{{image}}', (package / 'SKILL.md').read_text())
        self.assertEqual(set(p.name for p in package.iterdir()), {'SKILL.md', 'runtime.json'})
        installed = install(self.root / 'skills', 'skill-a', self.root / 'installed')
        self.assertTrue(Path(installed['installed']).is_dir())

    def test_necessary_external_gap_is_pending_and_manual_evidence_bound(self):
        Session.mode = 'necessary'
        result = self.run_build()
        self.assertEqual(result['counts'], {'pending-validation': 2}, result)
        self.assertEqual(entries(self.root / 'skills'), [])
        entry = entries(self.root / 'skills', True)[0]
        report = {'image': IMAGE, 'package_sha256': fingerprint(entry['files']),
                  'items': [{'item_id': 'sample', 'status': 'passed', 'evidence': 'human run receipt'}]}
        self.assertEqual(promote(self.root / 'skills', entry['name'], report)['status'], 'verified')

    def test_environment_failure_blocks_candidates_but_next_group_runs(self):
        Library.fail = True
        result = self.run_build()
        self.assertEqual(result['counts'], {'blocked': 2}, result)
        self.assertEqual(sum(p == 'discovery' for _, p in Session.calls), 2)
        self.assertFalse((self.root / 'skills').exists())
        Library.fail = False
        with patch('creation_pipeline.shared.pipeline.EnvironmentLibrary', Library):
            resumed = build(state_root=self.root / 'state', resume_id=result['build_id'],
                            library_root=self.root / 'skills', _session_factory=Session)
        self.assertEqual(resumed['counts'], {'verified': 2}, resumed)
        self.assertEqual(sum(p == 'discovery' for _, p in Session.calls), 2)

    def test_input_ambiguity_and_old_single_group(self):
        write_json(self.config_path, {'sources': [{'path': 'source.txt'}]})
        self.assertEqual(load_config(self.config_path)['resource_groups'][0]['id'], 'default')
        write_json(self.config_path, {**self.config, 'sources': [{'path': 'source.txt'}]})
        with self.assertRaises(ValueError):
            load_config(self.config_path)

    def test_local_validation_never_publishes_or_exports(self):
        self.config['environments'] = {'publish': False}
        write_json(self.config_path, self.config)
        with patch.object(Library, 'publish', side_effect=AssertionError('No registry publication')):
            result = self.run_build()
        self.assertEqual(result['counts'], {'local-verified': 2}, result)
        self.assertFalse((self.root / 'skills').exists())

    def test_real_preflight_initializes_an_empty_source_registry(self):
        class PreflightSession(Session):
            def stage(self, instructions, context, schema=None):
                if context['_phase'] == 'preflight':
                    self.assert_empty = not self.sources.entries
                    if not self.assert_empty:
                        raise AssertionError('Preflight acquired research sources')
                    for key in ('local_probe', 'cache_probe', 'resume_probe'):
                        Path(context[key]).write_text(context['token'], encoding='utf-8')
                    return {'ready': True}
                return super().stage(instructions, context, schema)
        with patch('creation_pipeline.shared.pipeline.NativeSession', PreflightSession), \
             patch('creation_pipeline.agent.backend.NativeSession', PreflightSession), \
             patch('creation_pipeline.shared.preflight.observe', return_value=[]), \
             patch('creation_pipeline.shared.pipeline.EnvironmentLibrary', Library):
            result = build(self.config_path, self.root / 'state', library_root=self.root / 'skills')
        self.assertEqual(result['counts'], {'verified': 2}, result)

    def test_reviewer_cannot_change_delivered_content(self):
        Session.mode = 'mutating-review'
        result = self.run_build()
        self.assertEqual(result['counts'], {'blocked': 2}, result)
        self.assertFalse((self.root / 'skills').exists())

    def test_cleanup_requires_archive_and_preserves_pinned_and_pending(self):
        result = self.run_build()
        pin(self.root / 'state', result['build_id'], True)
        with self.assertRaises(ValueError):
            clean(self.root / 'state', result['build_id'])
        pin(self.root / 'state', result['build_id'], False)
        removed = clean(self.root / 'state', result['build_id'])
        self.assertEqual(len(removed['removed']), 1)
        self.assertEqual(len(entries(self.root / 'skills')), 2)
        self.assertTrue((self.root / 'state/cache/snapshots').exists())
        Session.mode = 'necessary'
        pending = self.run_build()
        with self.assertRaises(ValueError):
            clean(self.root / 'state', pending['build_id'])

    def test_cross_group_adoption_preserves_snapshot_and_local_evidence(self):
        config = load_config(self.config_path)
        sources = Sources(config, self.root / 'cache')
        a, b = self.root / 'group-a', self.root / 'group-b'
        a.mkdir(); b.mkdir()
        prepare(sources, a); prepare(sources, b)
        index(sources)
        values = lookup(a, '')
        adopted = adopt(b, values[0]['snapshot_id'], 'Confirm documented call', ['code'])
        self.assertEqual(adopted['status'], 'adopted')
        self.assertEqual(read_json(b / 'source-evidence.json')[0]['id'], 'e1')

    def test_necessary_coverage_cannot_be_silently_omitted(self):
        with self.assertRaises(ValueError):
            validate_plan([{'id': 'x', 'necessary': True}], {'cases': [], 'deferred': []})

    def test_version_and_platform_mismatch_never_hit(self):
        plan = env_plan()
        self.assertTrue(compatible(plan, plan))
        changed = copy.deepcopy(plan)
        changed['tools'][0]['version'] = '3.12'
        self.assertFalse(compatible(plan, changed))

        changed = {**plan, 'platform': 'linux/arm64'}
        self.assertFalse(compatible(plan, changed))

    def test_rdkit_zero_padding_does_not_prevent_equivalent_version_match(self):
        original = env_plan()
        original['tools'][0]['version'] = '2024.09.6'
        requested = copy.deepcopy(original)
        requested['tools'][0]['version'] = '2024.9.6'
        self.assertTrue(compatible(original, requested))
        requested['tools'][0]['version'] = '2024.9.7'
        self.assertFalse(compatible(original, requested))

    def test_container_work_paths_are_normalized_but_other_absolute_paths_rejected(self):
        case = {'item_id': 'x', 'files': [{'path': '/work/input.csv', 'content': 'x'}],
                'command': ['python', '/code/x.py'], 'basis': 'Source',
                'stdout_contains': [], 'output_files': ['/work/output.csv'], 'check_command': []}
        plan = {'cases': [case], 'deferred': []}
        validate_plan([{'id': 'x', 'necessary': True}], plan)
        self.assertEqual(case['files'][0]['path'], 'input.csv')
        self.assertEqual(case['output_files'], ['output.csv'])
        case['files'][0]['path'] = '/outside/input.csv'
        with self.assertRaises(ValueError):
            validate_plan([{'id': 'x', 'necessary': True}], plan)

    def test_atomic_record_write_retries_transient_windows_sharing_failure(self):
        original_replace = Path.replace
        calls = []
        def replace(path, destination):
            calls.append(path)
            if len(calls) == 1:
                raise PermissionError('Transient file sharing violation')
            return original_replace(path, destination)
        with patch.object(Path, 'replace', replace):
            write_json(self.root / 'receipt.json', {'status': 'saved'})
        self.assertEqual(read_json(self.root / 'receipt.json'), {'status': 'saved'})
        self.assertEqual(len(calls), 2)

    def test_os_lock_can_be_reacquired_without_removing_marker(self):
        with lease(self.root, 'x'):
            with self.assertRaises(OSError):
                with lease(self.root, 'x'):
                    pass
        with lease(self.root, 'x'):
            pass

    def test_build_publish_reuse_and_version_expansion_preserve_old_materials(self):
        config = load_config(self.config_path)
        config['environments'].update(root=str(self.root / 'environments'),
            image_prefix='ghcr.io/example/project', source_url='https://github.com/example/project')
        calls = []
        current = env_plan()
        repository = 'ghcr.io/example/project/env-python'
        def docker(command, timeout):
            calls.append(command)
            stdout = ''
            if command[:3] == ['docker', 'image', 'inspect']:
                stdout = json.dumps([{'Os': 'linux', 'Architecture': 'amd64',
                    'RepoDigests': [repository + '@sha256:' + 'a'*64] if command[-1].startswith(repository)
                                   else ['python@sha256:' + 'b'*64]}])
            if command[:3] == ['docker', 'run', '--rm']:
                stdout = json.dumps({'version': next(t['version'] for t in current['tools'] if t['probe'][0] == command[-1])})
            return {'exit_code': 0, 'stdout': stdout, 'stderr': ''}
        current['tools'][0]['probe'] = ['probe-python']
        work = self.root / 'attempt'; work.mkdir()
        library = EnvironmentLibrary(config, self.root / 'state', docker)
        first = library.ensure(current, work)
        first = library.publish(first)
        self.assertEqual(first['image'], IMAGE.replace('/env@', '/env-python@'))
        original_files = copy.deepcopy(first['files'])
        reused = library.ensure(current, work)
        self.assertTrue(reused['reuse'])
        self.assertEqual(sum(c[:2] == ['docker', 'build'] for c in calls), 1)
        current = copy.deepcopy(current)
        current.update(selection='extend', environment_id='env-python')
        current['tools'].append({'name': 'other', 'version': '1', 'kind': 'python', 'probe': ['probe-other']})
        current['files'][0]['content'] += 'RUN echo installing-other\n'
        expanded = library.ensure(current, work)
        self.assertNotEqual(expanded['version'], first['version'])
        self.assertEqual(library.records()[0]['files'], original_files)
        self.assertTrue(any(c[:3] == ['docker', '--config', c[2]] and 'manifest' in c for c in calls if len(c)>2))

    def test_probe_wrong_version_cannot_qualify_environment(self):
        config = load_config(self.config_path)
        library = EnvironmentLibrary(config, self.root / 'state', lambda *args: {
            'exit_code': 0, 'stdout': '{"version":"wrong"}', 'stderr': ''})
        with self.assertRaises(OperationError):
            library.probe('image', env_plan(), self.root)

    def test_execution_runs_original_checks_result_and_rejects_replacement(self):
        package = self.root / 'package'; package.mkdir()
        (package / 'task.py').write_text('print(2)\n', encoding='utf-8')
        item = {'id': 'sample', 'file': 'task.py', 'start_line': 1, 'end_line': 1,
                'necessary': True, 'reason': 'Custom logic', 'expected_check': 'Print 2'}
        items = bind_items(package, [item])
        case = {'item_id': 'sample', 'files': [], 'command': ['python', '/code/sample.py'],
                'expected_exit': 0, 'stdout_contains': ['2'], 'output_files': [], 'check_command': [], 'basis': 'Exact arithmetic'}
        plan = {'cases': [case], 'deferred': []}
        def runner(command, timeout):
            return {'exit_code': 0, 'stdout': '2\n', 'stderr': ''}
        result = execute(package, IMAGE, 'linux/amd64', items, plan, self.root / 'attempt', 30, runner)
        self.assertEqual(result['status'], 'verified')
        case['command'] = ['python', '-c', 'print(2)']
        with self.assertRaises(ValueError):
            execute(package, IMAGE, 'linux/amd64', items, plan, self.root / 'attempt', 30, runner)


if __name__ == '__main__':
    unittest.main()
