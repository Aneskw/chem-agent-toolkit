import copy
import unittest
from pathlib import Path
from unittest.mock import patch
from tests.pipeline import test_discovery as f
from tests.pipeline.test_components import ARTIFACT, ReplayBackend, response
from creation_pipeline.pipeline import build
from creation_pipeline.records import read_json, write_json
from creation_pipeline.intake import Sources
from creation_pipeline.models import load_config


class SkillLibraryTests(unittest.TestCase):
    def setUp(self):
        self.case = f.DiscoveryTests()
        self.case.setUp()

    def tearDown(self):
        self.case.tearDown()

    def test_blocking_issue_prevents_ready(self):
        artifact = copy.deepcopy(ARTIFACT)
        artifact['issues'] = [{'id': 'missing', 'description': 'critical source gap', 'blocking': True, 'resolution': ''}]
        result, _ = self.case.run_case(f.discovery(f.candidate()), artifact)
        self.assertEqual(result['status'], 'draft')

    def test_notes_need_review_confirmation(self):
        result, _ = self.case.run_case(f.discovery(f.candidate()), ARTIFACT,
            {'status': 'pass', 'resolution': 'none', 'findings': [], 'issues_complete': False})
        self.assertEqual(result['status'], 'draft')

    def test_unready_adoption_is_not_eligible_rather_than_disabled(self):
        self.case.options['adoption'] = {'enabled': True}
        write_json(self.case.config, self.case.options)
        artifact = copy.deepcopy(ARTIFACT)
        artifact['issues'] = [{'id': 'gap', 'description': 'missing evidence', 'blocking': True, 'resolution': ''}]
        result, _ = self.case.run_case(f.discovery(f.candidate()), artifact)
        self.assertEqual(result['adoption'][0]['status'], 'not_eligible')

    def test_reviewer_can_reject_an_unchecked_wrong_example(self):
        artifact = copy.deepcopy(ARTIFACT)
        artifact['files'][0]['content'] = artifact['files'][0]['content'].replace('print(2 + 3)', 'print(99)')
        artifact['coverage']['usage'] = 'print(99)'
        review = {"status":"fail","resolution":"supply_evidence","findings":["Source expects 5, actual example prints 99"]}
        result, _ = self.case.run_case(f.discovery(f.candidate()), artifact, review)
        self.assertEqual(result['status'], 'draft')

    def test_explicit_delivered_example_check_executes(self):
        artifact = copy.deepcopy(ARTIFACT)
        artifact['files'][0]['content'] = artifact['files'][0]['content'].replace('print(2 + 3)', 'print(sum([2, 3]))')
        artifact['coverage']['usage'] = 'print(sum([2, 3]))'
        artifact["tests"] = [{"name":"delivered-example", "argv":["{python}", str(Path(__file__).resolve().parents[2] / "creation_pipeline/example_runner.py"), "{package}"], "stdout_contains":["5"], "evidence":"e1", "purpose":"Actual source-backed example"}]
        result, _ = self.case.run_case(f.discovery(f.candidate()), artifact, execute_generated=True)
        self.assertEqual(result['status'], 'ready')
        record = read_json(Path(result['output']) / 'records' / 'add-numbers.json')
        self.assertTrue(any(c['name'] == 'delivered-example' and c['status'] == 'pass'
                            for c in record['checks']))

    def test_host_example_failure_prevents_ready(self):
        artifact = copy.deepcopy(ARTIFACT)
        artifact['files'][0]['content'] = artifact['files'][0]['content'].replace('print(2 + 3)', 'raise RuntimeError("broken")')
        artifact['coverage']['usage'] = 'raise RuntimeError("broken")'
        artifact["tests"] = [{"name":"broken-example", "argv":["{python}", str(Path(__file__).resolve().parents[2] / "creation_pipeline/example_runner.py"), "{package}"], "stdout_contains":["5"], "evidence":"e1", "purpose":"Actual example"}]
        result, _ = self.case.run_case(f.discovery(f.candidate()), artifact, artifact, execute_generated=True)
        self.assertEqual(result['status'], 'failed')

    def test_unexecuted_generated_check_cannot_claim_example_coverage(self):
        artifact = copy.deepcopy(ARTIFACT)
        artifact['files'][0]['content'] = artifact['files'][0]['content'].replace('print(2 + 3)', 'print(sum([2, 3]))')
        artifact['coverage']['usage'] = 'print(sum([2, 3]))'
        artifact['tests'] = [{'name': 'unexecuted', 'argv': ['{python}', '-c', 'print(sum([2, 3]))'],
            'stdout_contains': ['5'], 'evidence': 'e1', 'purpose': 'source example'}]
        result, _ = self.case.run_case(f.discovery(f.candidate()), artifact)
        self.assertEqual(result['status'], 'ready')
        record = read_json(Path(result['output']) / 'records/add-numbers.json')
        self.assertTrue(any(c['name'] == 'unexecuted' and c['status'] == 'not_run' for c in record['checks']))

    def test_revise_preserves_parent_and_passes_feedback(self):
        result, _ = self.case.run_case(f.discovery(f.candidate()), plan_only=True)
        parent = Path(result['output']) / 'plan.json'
        before = parent.read_bytes()
        revised = f.discovery(f.candidate(scope='Narrow numeric scope'))
        backend = ReplayBackend([response(revised)])
        result = build(state_root=self.case.state, plan_path=parent, plan_only=True,
                       feedback='Narrow numeric scope', backend=backend)
        self.assertEqual(result['status'], 'planned')
        self.assertEqual(parent.read_bytes(), before)
        self.assertTrue((Path(result['output']) / 'revision.json').exists())
        self.assertIn('Narrow numeric scope', backend.prompts[0])

    def test_partial_adoption_idempotence_and_conflict(self):
        c = self.case
        c.options['adoption'] = {'enabled': True}
        write_json(c.config, c.options)
        library = c.root / 'library'
        plan = f.discovery(f.candidate(), f.candidate('unavailable', readiness='blocked', gaps=['weights']))
        first, _ = c.run_case(plan, ARTIFACT, library_root=library)
        self.assertEqual(first['status'], 'partial')
        self.assertEqual(first['adoption'][0]['status'], 'adopted')
        second, _ = c.run_case(plan, ARTIFACT, library_root=library)
        self.assertEqual(second['adoption'][0]['status'], 'already_present')
        changed = copy.deepcopy(ARTIFACT)
        changed['files'][0]['content'] += '\nAdditional supported note.\n'
        third, _ = c.run_case(plan, changed, library_root=library)
        self.assertEqual(third['adoption'][0]['status'], 'conflict')
        self.assertEqual(len(read_json(library / 'catalog.json')['skills']), 1)

    def test_catalog_failure_rolls_back_new_package(self):
        c = self.case
        c.options['adoption'] = {'enabled': True}
        write_json(c.config, c.options)
        library = c.root / 'library'
        with patch('creation_pipeline.library.write_json', side_effect=OSError('disk full')):
            result, _ = c.run_case(f.discovery(f.candidate()), ARTIFACT, library_root=library)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(list(library.rglob('SKILL.md')), [])
        self.assertFalse((library / '.catalog.lock').exists())

    def test_directory_search_locates_but_does_not_fabricate_evidence(self):
        c = self.case
        directory = c.root / 'code'
        directory.mkdir()
        (directory / 'entry.py').write_text('def real_entry(): pass')
        c.options['sources'] = [{'id': 'code', 'path': str(directory)}]
        write_json(c.config, c.options)
        sources = Sources(load_config(c.config), c.state / 'cache')
        result = sources.request({'action': 'search', 'source': 'code', 'query': 'real_entry', 'path': ''})
        self.assertEqual(result['matches'][0]['path'], 'entry.py')
        self.assertEqual(sources.evidence, [])

    def test_handoff_reaches_author(self):
        plan = f.discovery(f.candidate())
        plan['handoff'] = [{'fact': 'Use numeric inputs only', 'evidence': 'e1'}]
        result, _ = self.case.run_case(plan, ARTIFACT)
        self.assertEqual(result['status'], 'ready')
        self.assertIn('Use numeric inputs only', self.case.last_backend.prompts[1])

    def test_batch_reads_preserve_evidence(self):
        import json
        c = self.case
        sources = Sources(load_config(c.config), c.state / "cache")
        result = sources.request({"action": "read_many", "query": json.dumps([
            {"source": "tool", "path": "api.py", "start": 1, "limit": 1},
            {"source": "tool", "path": "api.py", "start": 2, "limit": 1}])})
        self.assertEqual([r["id"] for r in result["reads"]], ["e1", "e2"])

    def test_handoff_multiple_real_read_ids_are_validated(self):
        from creation_pipeline.analyze import validate_discovery
        c = self.case
        sources = Sources(load_config(c.config), c.state / "cache")
        for _ in range(2):
            sources.request({"action": "read", "source": "tool", "path": "api.py"})
        plan = f.discovery(f.candidate())
        plan["handoff"] = [{"fact": "Two excerpts support this fact", "evidence": "e1; e2"}]
        validate_discovery(plan, load_config(c.config), sources)
        plan["handoff"][0]["evidence"] = "e1,e999"
        with self.assertRaises(ValueError):
            validate_discovery(plan, load_config(c.config), sources)

    def test_example_statements_allow_inserted_assertions(self):
        from creation_pipeline.checks import covers_example
        self.assertTrue(covers_example("x = 2\nprint(x)", "x = 2\nassert x == 2\nprint(x)"))
        self.assertFalse(covers_example("x = 2\nprint(x)", "x = 2\nx = 3\nprint(x)"))

    def test_context_limit_preserves_external_read_evidence(self):
        from creation_pipeline.model_backend import Session
        c = self.case
        c.source.write_text("documented statement " * 900, encoding="utf-8")
        config = load_config(c.config)
        config['limits']['context_chars'] = 5000
        sources = Sources(config, c.state / 'cache')
        work = c.root / 'context-run'
        work.mkdir()
        backend = ReplayBackend([{'action': 'read', 'source': 'tool', 'path': 'api.py', 'start': 1, 'limit': 160}, response({'ok': True})])
        session = Session(backend, sources, config['limits'], work)
        self.assertEqual(session.stage('Read sources and answer.', {}), {'ok': True})
        self.assertEqual(len(sources.evidence), 1)
        self.assertEqual(session.receipts[-1]['history_omissions'], 1)
        self.assertLessEqual(session.receipts[-1]['context_chars'], 5000)
