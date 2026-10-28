"""Program checks and explicit model/Docker doubles, not live acceptance."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.runtime.entry import markdown_entry, materialize, verify_material, associate, EntryError
from creation_pipeline.runtime.preparation import prepare
from creation_pipeline.runtime.local import LocalExecutor
from creation_pipeline.runtime import planner
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.artifacts.evidence import seal, verify
from creation_pipeline.contracts import finalize, runtime_request, fingerprint
from creation_pipeline.runtime.execution import locked_inputs
from tests.pipeline.test_runtime_build import plan, TEXT, QUOTE, HOST


class MarkdownEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.package = self.root / 'package'; self.package.mkdir()
        self.source = self.root / 'source'; self.source.mkdir()
        (self.source / 'main.py').write_text(TEXT, encoding='utf-8')
        self.code = b'print("ok")\r\n'
        (self.package / 'SKILL.md').write_bytes(b'# Example\r\n```python\r\n' + self.code + b'```\r\n')
        self.sources = [{'id': 'tool', 'path': str(self.source), 'inventory': manifest(self.source)}]
        self.record = {'name': 'example', 'status': 'ready', 'files': manifest(self.package), 'plan': {'name': 'example'},
            'checks': [{'name': 'content_review', 'status': 'pass', 'requirement_assessment': 'confirmed'}]}
        finalize(self.record, self.sources, {'status': 'required', 'reason': 'Execute example',
            'citations': [{'source_id': 'tool', 'path': 'main.py', 'quote': QUOTE}]})
        self.proposal = {'source_id': 'tool', 'source_path': 'main.py', 'quote': QUOTE, 'reason': 'same printing capability',
            'invocation': 'python entry/skill.py; no arguments; stdout ok', 'supported': True}
        self.review = {'review': {'status': 'pass', 'binding_verified': True, 'requirement_assessment': 'confirmed'}}

    def tearDown(self):
        self.temp.cleanup()

    def associated(self):
        with patch('creation_pipeline.runtime.model_call.call', return_value=(self.proposal, {})), \
             patch('creation_pipeline.runtime.review.review_snapshot', return_value=self.review):
            return associate(self.record, self.package, self.sources, self.root / 'audit', planner.options({}))

    def test_exact_crlf_bytes_locator_and_material_drift(self):
        binding = self.associated()
        self.assertEqual(markdown_entry(self.package)[1], self.code)
        materialize(self.package, binding, self.root / 'materials')
        self.assertEqual((self.root / 'materials/entry/skill.py').read_bytes(), self.code)
        verify_material(self.package, binding, self.root / 'materials')
        (self.root / 'materials/entry/skill.py').write_bytes(b'print("wrong")\n')
        with self.assertRaisesRegex(ValueError, 'exact delivered'):
            verify_material(self.package, binding, self.root / 'materials')
        changed = copy.deepcopy(binding); changed['extraction']['start_byte'] += 1
        with self.assertRaises(ValueError):
            materialize(self.package, changed, self.root / 'changed')

    def test_multiple_interactive_incomplete_and_missing_context(self):
        examples = [('```python\nprint(1)\n```\n```python\nprint(2)\n```\n', 'binding'),
            ('```python\ninput()\n```\n', 'binding'), ('```python\nprint(\n```\n', 'content'),
            ('```python\nprint(previous_result)\n```\n', 'content'), ('```py\ndef f():\n return missing\n```\n', 'content')]
        for text, lane in examples:
            (self.package / 'SKILL.md').write_text(text, encoding='utf-8')
            with self.assertRaises(EntryError) as caught:
                markdown_entry(self.package)
            self.assertEqual(caught.exception.lane, lane)

    def test_function_with_declared_context_is_supported(self):
        (self.package / 'SKILL.md').write_text('```python\nimport math\ndef f(x):\n return math.sqrt(x)\n```\n', encoding='utf-8')
        self.assertEqual(markdown_entry(self.package)[0]['kind'], 'markdown_python')

    def test_a_one_based_index_over_a_single_block_is_normalised_visibly(self):
        # Run 18: the author declared block_index 1 for a SKILL.md that has exactly one
        # block. One candidate means no interpretation is guessed, so it is accepted
        # and the normalisation is recorded rather than hidden.
        (self.package / 'SKILL.md').write_text('```python\nprint(1)\n```\n', encoding='utf-8')
        binding, _ = markdown_entry(self.package, 1)
        self.assertEqual(binding['extraction']['block_index'], 0)
        self.assertEqual(binding['extraction']['declared_block_index'], 1)
        self.assertIn('one-based', binding['extraction']['block_index_basis'])
        plain, _ = markdown_entry(self.package, 0)
        self.assertNotIn('declared_block_index', plain['extraction'])

    def test_an_out_of_range_index_still_fails_and_says_zero_based(self):
        (self.package / 'SKILL.md').write_text('```python\nprint(1)\n```\n', encoding='utf-8')
        with self.assertRaises(EntryError) as caught:
            markdown_entry(self.package, 2)
        self.assertEqual(caught.exception.code, 'entry_declaration_missing')
        self.assertIn('0-based', str(caught.exception))

    def test_a_one_based_index_over_multiple_blocks_is_still_refused(self):
        # With more than one block, one-based and zero-based differ: refuse instead of
        # guessing which block the author meant.
        (self.package / 'SKILL.md').write_text('```python\nprint(1)\n```\n```python\nprint(2)\n```\n',
                                               encoding='utf-8')
        binding, _ = markdown_entry(self.package, 1)
        self.assertEqual(binding['extraction']['block_index'], 1)
        with self.assertRaises(EntryError):
            markdown_entry(self.package, 2)

    def test_python_fence_inside_literal_markdown_is_not_an_entry(self):
        for outer in ('````markdown', '~~~markdown'):
            closing = '````' if outer.startswith('`') else '~~~'
            (self.package / 'SKILL.md').write_text(
                outer + '\n```python\nprint(1)\n```\n' + closing + '\n', encoding='utf-8')
            with self.assertRaises(EntryError):
                markdown_entry(self.package)

    def test_missing_context_revokes_content_without_planning(self):
        (self.package / 'SKILL.md').write_text('```python\nprint(undeclared)\n```\n', encoding='utf-8')
        with patch.object(planner, 'plan', side_effect=AssertionError('planner called')):
            prepare(self.record, self.package, self.sources, self.root / 'missing', {}, LocalExecutor())
        self.assertEqual(self.record['delivery']['content']['status'], 'failed')
        self.assertEqual(self.record['runtime_preparation']['gaps'][0]['repair_lane'], 'content')

    def test_probe_diagnostic_identifies_case_without_rewriting_code(self):
        from creation_pipeline.runtime.preparation import handoff
        handoff(self.package, self.sources, self.root / 'handoff')
        p = plan(); p['source_files'] = ['package/SKILL.md', 'sources/tool/main.py']; p['script'] = ''
        broken = {'entrypoint': 'python', 'args': ['-c', "print('actual\nnewline')"], 'expected_exit': 0}
        p['tests'][0]['case_json'] = json.dumps(broken)
        index = planner.inventory(self.root / 'handoff', planner.options({}))
        messages = []
        for name in ('first_case', 'second_case'):
            p['tests'][0]['name'] = name
            with self.assertRaises(planner.PlanningError) as caught:
                planner.validate_plan(p, index, self.root / 'handoff')
            messages.append(str(caught.exception)); self.assertIn(name, messages[-1])
        self.assertNotEqual(*messages)
        self.assertEqual(json.loads(p['tests'][0]['case_json']), broken)

    def test_source_quote_or_independent_rejection_cannot_bind(self):
        self.proposal['quote'] = 'unavailable'
        with self.assertRaises(EntryError): self.associated()
        self.proposal['quote'] = QUOTE
        self.review['review']['binding_verified'] = False
        with self.assertRaisesRegex(EntryError, 'Independent'):
            self.associated()

    def test_joined_source_excerpts_do_not_become_an_exact_citation(self):
        first, second = 'def first_api():', 'def second_api():'
        text = first + '\n    pass\n\n' + second + '\n    pass\n'
        (self.source / 'main.py').write_text(text, encoding='utf-8')
        self.sources[0]['inventory'] = manifest(self.source)
        self.proposal['quote'] = first + '\n\n' + second
        self.assertIn(first, text)
        self.assertIn(second, text)
        with patch('creation_pipeline.runtime.model_call.call', return_value=(self.proposal, {})), \
             patch('creation_pipeline.runtime.review.review_snapshot') as reviewer:
            with self.assertRaisesRegex(EntryError, 'exact source citation'):
                associate(self.record, self.package, self.sources, self.root/'joined', planner.options({}))
            reviewer.assert_not_called()

    def test_model_schema_is_program_checked_before_semantic_review(self):
        self.proposal.pop('invocation')
        with self.assertRaisesRegex(EntryError, 'schema'):
            self.associated()

    def test_explicit_runtime_deadline_applies_before_association(self):
        with patch('creation_pipeline.runtime.model_call.call', side_effect=AssertionError('model called')):
            with self.assertRaisesRegex(EntryError, 'Explicit runtime'):
                associate(self.record, self.package, self.sources, self.root / 'expired', planner.options({}), deadline=0)

    def test_independent_file_defect_is_content_not_unsupported_protocol(self):
        self.review['review'].update(status='fail', resolution='revise_files', findings=[
            {'category': 'file', 'blocking': True, 'problem': 'Unsupported provenance claim'}])
        with self.assertRaises(EntryError) as caught:
            self.associated()
        self.assertEqual(caught.exception.lane, 'content')
        self.assertEqual(caught.exception.kind, 'content_defect')

    def test_host_missing_and_unsupported_entry_do_not_call_models(self):
        with patch('creation_pipeline.runtime.model_call.call', side_effect=AssertionError('model called')), \
             patch.object(LocalExecutor, 'host', return_value={'gaps': [{'code': 'docker_unavailable', 'detail': 'missing Docker'}]}):
            prepare(self.record, self.package, self.sources, self.root / 'blocked', {}, LocalExecutor())
        self.assertEqual(self.record['runtime_preparation']['gaps'][0]['code'], 'docker_unavailable')
        (self.package / 'SKILL.md').write_text('No executable block', encoding='utf-8')
        with patch.object(LocalExecutor, 'host', side_effect=AssertionError('host probed')):
            prepare(self.record, self.package, self.sources, self.root / 'unsupported', {}, LocalExecutor())
        self.assertEqual(self.record['runtime_preparation']['gaps'][0]['blocker_kind'], 'unsupported_contract')

    def test_frozen_markdown_sources_supports_and_locked_checks(self):
        binding = self.associated(); p = plan()
        p.update(script='entry/skill.py', entrypoint=['python', '/opt/skill/entry/skill.py'])
        p['source_files'] = ['entry/skill.py', 'package/SKILL.md', 'sources/tool/main.py']
        with patch('creation_pipeline.runtime.entry.associate', return_value=binding), patch.object(LocalExecutor, 'host', return_value=HOST):
            materials = prepare(self.record, self.package, self.sources, self.root / 'work', {'plan': p}, LocalExecutor())
        self.assertEqual(self.record['runtime_preparation']['status'], 'prepared', self.record['runtime_preparation'])
        freeze = seal(self.root / 'freeze', self.package, self.record, self.sources, materials)
        request = runtime_request(self.record['delivery'], self.root / 'freeze', freeze, self.root / 'attempt')
        self.assertEqual(len(locked_inputs(self.record, request)), 2)
        self.assertFalse(self.record['delivery']['qualification']['accepted'])
        f = self.root / 'freeze/package/SKILL.md'; original = f.read_bytes()
        f.write_bytes(original + b'changed prose')
        with self.assertRaises(ValueError): verify(self.root / 'freeze', freeze)
        f.write_bytes(original)
        (self.root / 'freeze/runtime/context/entry/skill.py').write_bytes(b'print("wrong")')
        with self.assertRaises(ValueError): LocalExecutor().inputs(request)


class SourceIdentityTests(unittest.TestCase):
    def test_pinned_raw_url_has_distinct_upstream_identity(self):
        from creation_pipeline.models import load_config
        from creation_pipeline.resources.intake import Sources
        from creation_pipeline.resources.acquisition import Acquisition
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'document.py'; source.write_text('print(1)', encoding='utf-8')
            url = 'https://raw.githubusercontent.com/org/tool/' + 'a' * 40 + '/code.py'
            config = root / 'config.json'; config.write_text(json.dumps({'sources': [{'url': url}]}), encoding='utf-8')
            with patch.object(Acquisition, 'prepare', side_effect=lambda item: dict(item, path=str(source))):
                entry = Sources(load_config(config), root / 'cache').manifest()[0]
            self.assertEqual(entry['upstream']['commit'], 'a' * 40)
            self.assertEqual(entry['upstream']['sha256'], entry['inventory'][0]['sha256'])
            self.assertNotIn('resolved_ref', entry)

    def test_containing_repository_is_not_upstream(self):
        from creation_pipeline.models import load_config
        from creation_pipeline.resources.intake import Sources
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'input'; source.mkdir()
            (source / 'tool.py').write_text('print(1)', encoding='utf-8')
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.test', 'commit', '-qm', 'source'], check=True)
            config = root / 'config.json'; config.write_text(json.dumps({'sources': [{'path': str(source)}]}), encoding='utf-8')
            material = Sources(load_config(config), root / 'cache').manifest()[0]
            self.assertNotIn('resolved_ref', material)
            self.assertIn('carrier_repository', material)
            self.assertNotIn('upstream', material)


class SavedPlanEntryTests(unittest.TestCase):
    def test_newer_durable_rejection_requires_author_even_if_old_plan_was_approved(self):
        from tests.pipeline.test_discovery import DiscoveryTests, discovery, candidate
        from tests.pipeline.test_delivery_protocol import configure_text, text_artifact
        from tests.pipeline.support import ReplayStages
        from creation_pipeline.pipeline import build
        from creation_pipeline.artifacts import store
        from creation_pipeline.records import read_json, write_json
        from creation_pipeline.runtime.preparation import rebind
        fixture = DiscoveryTests(); fixture.setUp(); self.addCleanup(fixture.tearDown)
        configure_text(fixture); fixture.options['adoption'] = {'enabled': True}; write_json(fixture.config, fixture.options)
        artifact = text_artifact(); artifact['runtime_requirement']['status'] = 'required'
        first, _ = fixture.run_case(discovery(candidate()), artifact)
        library = fixture.root / 'library'; previous = store.get(library, 'add-numbers', include_candidates=True)
        frozen = library / previous['evidence']; record = verify(frozen, previous['freeze_sha256'])
        materials = fixture.root / 'new-materials'
        write_json(materials / 'association/independent-review.json', {'review': {'name': 'content_review',
            'status': 'fail', 'resolution': 'revise_files', 'findings': [{'category': 'file', 'blocking': True,
            'problem': 'Incorrect provenance statement'}]}})
        sources = [dict(s, path=str(frozen / 'sources' / s['id'])) for s in record['delivery']['inputs']['sources']]
        rebind(record, None, {'incomplete': True, 'materials': manifest(materials)}, record['delivery']['inputs']['acceptance']['payload'])
        output = fixture.root / 'later-review'
        digest = seal(output / 'evidence/new', frozen / 'package', record, sources, materials)
        record['durable_evidence'] = {'path': 'evidence/new', 'freeze_sha256': digest}
        record.pop('runtime', None)
        store.adopt(output, [record], {'revision_parents': {'add-numbers': previous['revision_id']},
                    'batch': previous['batch']}, library)
        backend = ReplayStages([copy.deepcopy(artifact)])
        continued = build(state_root=fixture.root / 'continued', plan_path=Path(first['output']) / 'plan.json',
                          library_root=library, keep_debug=True, _session_factory=backend)
        self.assertFalse(continued['errors'], continued)
        self.assertEqual(continued['model_calls'], 2, continued)  # real author/review interfaces, simulated decisions
        self.assertTrue(any('Incorrect provenance statement' in p for p in backend.prompts))

    def test_unchanged_reviewed_blocked_candidate_skips_discovery_and_author(self):
        from tests.pipeline.test_discovery import DiscoveryTests, discovery, candidate
        from tests.pipeline.test_delivery_protocol import configure_text, text_artifact
        from tests.pipeline.support import ReplayStages
        from creation_pipeline.pipeline import build
        fixture = DiscoveryTests(); fixture.setUp(); self.addCleanup(fixture.tearDown)
        configure_text(fixture)
        artifact = text_artifact(); artifact['runtime_requirement']['status'] = 'required'
        first, _ = fixture.run_case(discovery(candidate()), artifact)
        self.assertEqual(first['status'], 'blocked')
        second = build(state_root=fixture.root / 'continued', plan_path=Path(first['output']) / 'plan.json',
                       keep_debug=True, no_adopt=True, _session_factory=ReplayStages([]))
        self.assertEqual(second['model_calls'], 0, second)
        self.assertEqual(second['status'], 'blocked', second)
