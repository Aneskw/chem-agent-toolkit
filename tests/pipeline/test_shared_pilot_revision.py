"""Regressions from the five-group pilot; no Docker or model service required."""
import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.records import read_json, write_json, file_digest
from creation_pipeline.models import load_config
from creation_pipeline.shared.contracts import runtime
from creation_pipeline.shared.environment import compatible
from creation_pipeline.shared.assets import resolve_inputs
from creation_pipeline.shared.observations import compact
from creation_pipeline.shared.library import reindex, locations
from creation_pipeline.shared.delivery import entries, promote
from creation_pipeline.shared.verification import bind_items, execute, execution_key, TestPlanError
from tests.pipeline.test_shared_creation import env_plan


class PilotRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for module in ('environment_state', 'library'):
            state = patch('creation_pipeline.shared.' + module + '.STATE_ROOT', self.root / ('private-' + module))
            state.start()
            self.addCleanup(state.stop)

    def resource(self, name, included=False):
        return {'name': name, 'version': '1', 'url': 'https://example.org/' + name,
                'included_in_image': included, 'usage': 'Input for prediction'}

    def test_external_weights_do_not_distinguish_installed_images(self):
        installed, request = env_plan(), env_plan()
        installed['resources'] = [self.resource('retroknn-weights')]
        request['resources'] = [self.resource('localretro-weights')]
        request['skill_resources'] = ['localretro-weights']
        self.assertTrue(compatible(installed, request))
        self.assertEqual([r['name'] for r in runtime(request)['resources']], ['localretro-weights'])
        request['resources'][0]['included_in_image'] = True
        self.assertFalse(compatible(installed, request))
        request['resources'] = []
        request['tools'][0]['version'] = '3.12'
        self.assertFalse(compatible(installed, request))

    def test_training_requirements_do_not_copy_inherited_resources_or_tools(self):
        p = env_plan()
        p['tools'].append({'name': 'unused', 'kind': 'python', 'version': '1', 'probe': ['unused']})
        p['resources'] = [self.resource('unrelated-pretrained-weights')]
        self.assertNotIn('resources', runtime(p))
        self.assertEqual([t['name'] for t in runtime(p)['environment']['tools']], ['python'])
        p['skill_tools'] = ['imagined']
        with self.assertRaisesRegex(ValueError, 'unknown'):
            runtime(p)

    def test_different_external_weights_reuse_one_build_and_stay_out_of_image_metadata(self):
        from tests.pipeline.test_shared_next import SharedNextTests
        client, remote, calls = SharedNextTests.environment_library(self)
        p = env_plan()
        p['resources'] = [self.resource('retroknn-weights')]
        p['skill_resources'] = ['retroknn-weights']
        first = client.ensure(p, self.root / 'first')
        p['resources'] = [self.resource('localretro-weights')]
        p['skill_resources'] = ['localretro-weights']
        second = client.ensure(p, self.root / 'second')
        self.assertEqual(first['fingerprint'], second['fingerprint'])
        self.assertTrue(second['reuse'])
        self.assertEqual(second['resources'], [])
        self.assertEqual(sum(c[:2] == ['docker', 'build'] for c in calls), 1)

    def sources(self, file):
        from creation_pipeline.resources.intake import Sources
        from creation_pipeline.resources.workspace import prepare
        config_path = self.root / 'input.json'
        write_json(config_path, {'sources': [{'id': 'weights', 'path': str(file)}]})
        sources = Sources(load_config(config_path), self.root / 'cache')
        prepare(sources, self.root / 'group')
        return sources

    def test_real_binary_archive_input_is_readonly_and_hash_bound(self):
        archive = self.root / 'weights.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('model/checkpoint.bin', b'\x00\xff\x01\x80')
        sources = self.sources(archive)
        package = self.root / 'package'
        package.mkdir()
        (package / 'script.py').write_text("from pathlib import Path\nprint(len(Path('weights.bin').read_bytes()))\n")
        items = bind_items(package, [{'id': 'predict', 'file': 'script.py', 'start_line': 1, 'end_line': 2,
            'necessary': True, 'reason': 'Binary input', 'expected_check': 'Read four binary bytes'}])
        case = {'item_id': 'predict', 'files': [], 'inputs': [{'source': 'weights', 'path': 'weights.zip',
            'member': 'model/checkpoint.bin', 'target': 'weights.bin'}], 'command': ['python', '/code/predict.py'],
            'expected_exit': 0, 'stdout_contains': ['4'], 'output_files': [], 'check_command': [], 'basis': 'Real binary input'}
        resolve_inputs(sources, [case])
        source = Path(case['_inputs'][0]['host_path'])
        self.assertEqual(source.read_bytes(), b'\x00\xff\x01\x80')
        before = file_digest(archive)
        commands = []
        def docker(argv, timeout):
            commands.append(argv)
            return {'exit_code': 0, 'stdout': '4', 'stderr': ''}
        plan = {'cases': [case], 'deferred': [], 'audit_risks': []}
        key = execution_key(package, {'digest': 'sha256:a', 'platform': 'linux/amd64'}, items[0], case)
        result = execute(package, 'image', 'linux/amd64', items, plan, self.root / 'execution', 10, docker)
        self.assertEqual(result['status'], 'verified')
        self.assertTrue(any('target=/work/weights.bin,readonly' in arg for arg in commands[0]))
        self.assertEqual(file_digest(archive), before)
        source.write_bytes(b'changed')
        with self.assertRaisesRegex(TestPlanError, 'changed'):
            execute(package, 'image', 'linux/amd64', items, plan, self.root / 'again', 10, docker)
        resolve_inputs(sources, [case])
        self.assertEqual(source.read_bytes(), b'\x00\xff\x01\x80')
        case['_inputs'][0]['sha256'] = 'other'
        self.assertNotEqual(key, execution_key(package, {'digest': 'sha256:a', 'platform': 'linux/amd64'}, items[0], case))

    def test_archive_traversal_and_overlapping_inputs_are_rejected(self):
        archive = self.root / 'input.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('../escape', b'bad')
        sources = self.sources(archive)
        with self.assertRaises(ValueError):
            resolve_inputs(sources, [{'inputs': [{'source': 'weights', 'path': 'input.zip', 'member': '../escape', 'target': 'data'}]}])
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            resolve_inputs(sources, [{'inputs': [
                {'source': 'weights', 'path': 'input.zip', 'member': '', 'target': 'data'},
                {'source': 'weights', 'path': 'input.zip', 'member': '', 'target': 'data/inside'}]}])

    def test_asset_acquisition_uses_registered_snapshots_without_group_binary_copy(self):
        from types import SimpleNamespace
        from creation_pipeline.shared.assets import acquire_requests
        from creation_pipeline.shared.resources import archive_sources
        original = self.root / 'source.txt'
        original.write_text('Official model instructions')
        sources = self.sources(original)
        binary = self.root / 'checkpoint.bin'
        binary.write_bytes(b'\x00\xffcheckpoint')
        session = SimpleNamespace(sources=sources, work=self.root / 'group')
        with patch('creation_pipeline.resources.acquisition.Acquisition.download', return_value=(binary, {})) as download:
            results = acquire_requests(session, [{'url': 'https://example.org/checkpoint.bin',
                'reason': 'Validate inference with official weights', 'related_to': ['weights']}])
        self.assertEqual(download.call_count, 1)
        source = session.sources.entries[results[0]['source']]
        self.assertTrue(source['test_asset'])
        self.assertEqual(Path(source['path']).read_bytes(), binary.read_bytes())
        retained = archive_sources(session.work, self.root / 'archive')
        self.assertEqual(next(r for r in retained if r.get('test_asset'))['path'], source['path'])
        self.assertFalse((self.root / 'archive/sources').exists())

    def test_common_probe_is_mounted_and_rechecked_without_building(self):
        from tests.pipeline.test_shared_next import SharedNextTests
        client, remote, calls = SharedNextTests.environment_library(self)
        p = env_plan()
        p['tools'][0]['probe'] = ['@python-version']
        client.probe('existing-image', p, self.root)
        client.probe('existing-image', p, self.root)
        runs = [c for c in calls if c[:3] == ['docker', 'run', '--rm']]
        self.assertEqual(len(runs), 2)
        self.assertTrue(all(any('target=/pipeline-check.py,readonly' in a for a in c) for c in runs))
        self.assertFalse(any(c[:2] in (['docker', 'build'], ['docker', 'push']) for c in calls))
        self.assertTrue(read_json(self.root / 'environment-check.json')['definition'])

    def test_large_log_stored_once_and_agent_receives_readable_artifact(self):
        log = 'compile log\n' * 110000
        first = compact({'stderr': log}, self.root)
        second = compact([first, {'stderr': log}], self.root)
        self.assertLess(len(json.dumps(second)), 16000)
        self.assertEqual(Path(first['stderr']['artifact']).read_text(encoding='utf-8'), log)
        self.assertEqual(len(list((self.root / 'diagnostics').iterdir())), 1)

    def test_archived_diagnostic_references_survive_workspace_cleanup(self):
        from creation_pipeline.shared.pipeline import archive_candidate
        source = self.root / 'candidate'
        source.mkdir()
        log = 'long failure log\n' * 1000
        result = {'name': 'skill', 'group': 'group', 'status': 'blocked',
                  'history': [compact({'stderr': log}, source)]}
        archived = archive_candidate(self.root / 'state', 'batch', 'group', 'skill', source, result)
        reference = archived['history'][0]['stderr']['artifact']
        self.assertFalse(Path(reference).is_absolute())
        self.assertEqual((Path(archived['record']).parent / reference).read_text(encoding='utf-8'), log)
        again = archive_candidate(self.root / 'state', 'batch', 'group', 'skill', source, archived)
        self.assertEqual(again['record'], archived['record'])

    def test_reindex_recovers_locations_without_recreating_approval(self):
        library = self.root / 'skills'
        package = library / 'group/verified/real-skill'
        package.mkdir(parents=True)
        (package / 'SKILL.md').write_text('---\nname: real-skill\ndescription: A real capability\n---\nUse it.\n')
        write_json(package / 'runtime.json', {'image': 'ghcr.io/example/tools:python-v1'})
        before = (package / 'SKILL.md').read_bytes()
        with patch('creation_pipeline.shared.library.STATE_ROOT', self.root / 'private'):
            self.assertEqual(reindex(library)['recovered'], 1)
            self.assertEqual(entries(library), [])
            self.assertEqual(entries(library, True)[0]['status'], 'recovered')
            with self.assertRaisesRegex(ValueError, 'not awaiting'):
                promote(library, 'real-skill', {})
            with self.assertRaisesRegex(ValueError, 'already exists'):
                reindex(library)
        self.assertEqual((package / 'SKILL.md').read_bytes(), before)
        self.assertEqual({p.name for p in package.iterdir()}, {'SKILL.md', 'runtime.json'})

    def test_factual_finding_requires_record_repair_and_content_revision(self):
        from creation_pipeline.generation.content_author import review
        package = self.root / 'package'
        package.mkdir()
        (package / 'SKILL.md').write_text('Identifiers are retained.')
        finding = {'location': 'SKILL.md', 'problem': 'Identifiers discarded by loader',
            'evidence': 'Molecule(smiles) does not pass identifiers', 'impact': 'Wrong interpretation',
            'action': 'Correct or remove', 'category': 'factual', 'owner': 'content', 'blocking': False}
        first = {'status': 'pass', 'resolution': 'none', 'findings': [finding], 'execution_items': [], 'code_decisions': []}
        second = copy.deepcopy(first)
        second.update(status='fail', resolution='revise_files')
        second['findings'][0]['blocking'] = True
        class Session:
            contexts = []
            def stage(self, instructions, context, schema=None):
                self.contexts.append(context)
                return first if len(self.contexts) == 1 else second
        session = Session()
        with patch('creation_pipeline.generation.content_author.candidate_context', return_value={}):
            result = review(session, {}, {'package': str(package)}, [], {})
        self.assertEqual(result['status'], 'fail')
        self.assertIn('record_format_error', session.contexts[1])

    def test_successful_shared_turn_drops_transcripts_but_preserves_recovery(self):
        from creation_pipeline.agent.backend import NativeSession
        session = NativeSession.__new__(NativeSession)
        session.config, session.keep_debug = {'workflow': 'shared-environments'}, False
        for name in ('prompt.txt', 'schema.json', 'events.jsonl', 'stderr.log', 'result.json', 'command.json'):
            (self.root / name).write_text('retained data')
        session.discard_success_debug(self.root)
        self.assertEqual({p.name for p in self.root.iterdir()}, {'result.json', 'command.json'})

    def test_environment_reference_repair_is_local_and_preserves_requirements(self):
        from tests.pipeline.test_shared_creation import Session, Library
        from creation_pipeline.shared.pipeline import build
        class RepairSession(Session):
            phases = []
            def stage(self, instructions, context, schema=None):
                phase = context['_phase']
                self.phases.append(phase)
                if phase == 'environment':
                    p = env_plan()
                    p['evidence'] = ['unregistered-id']
                    return p
                if phase == 'environment-record':
                    return env_plan()
                return super().stage(instructions, context, schema)
        original = self.root / 'source.txt'
        original.write_text('Documented print(2)')
        config = self.root / 'input.json'
        write_json(config, {'sources': [{'id': 'code', 'path': str(original)}]})
        with patch('creation_pipeline.shared.pipeline.EnvironmentLibrary', Library), \
             patch('creation_pipeline.shared.environment_state.STATE_ROOT', self.root / 'tool-state'), \
             patch('creation_pipeline.shared.library.STATE_ROOT', self.root / 'library-state'), \
             patch.object(Session, 'mode', 'exempt'):
            result = build(config, self.root / 'state', library_root=self.root / 'skills', _session_factory=RepairSession)
        self.assertEqual(result['counts'], {'verified': 1}, result)
        self.assertEqual(RepairSession.phases.count('environment'), 1)
        self.assertEqual(RepairSession.phases.count('environment-record'), 1)


if __name__ == '__main__':
    unittest.main()
