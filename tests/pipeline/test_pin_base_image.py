"""Base-image pinning turns a tag into a resolved digest.

A tag is not an identity: the same reference can resolve to different content later.
With ``pin_base_image`` the preparation resolves the reference to a repository digest,
renders ``FROM repo@sha256:...`` into the Dockerfile, freezes the digest in the
environment payload, and execution refuses to build when the pinned image is gone.
Resolution failure blocks instead of silently falling back to the tag.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creation_pipeline.artifacts.package import manifest
from creation_pipeline.records import write_json
from creation_pipeline.runtime import preparation
from creation_pipeline.runtime.local import LocalExecutor, base_image_reference, pinned_base_gap
from tests.pipeline.test_runtime_build import HOST, TEXT, plan

DIGEST = 'sha256:' + 'a' * 64


class ResolveTests(unittest.TestCase):
    def test_the_repository_drops_tag_and_digest(self):
        self.assertEqual(base_image_reference('python:3.11-slim'), 'python')
        self.assertEqual(base_image_reference('registry:5000/library/python:3.11'),
                         'registry:5000/library/python')
        self.assertEqual(base_image_reference('python@sha256:' + 'b' * 64), 'python')

    def test_resolution_prefers_the_digest_of_the_requested_repository(self):
        executor = LocalExecutor()
        responses = {
            ('docker', 'pull'): {'exit_code': 0, 'stdout': '', 'stderr': ''},
            ('docker', 'image', 'inspect'): {
                'exit_code': 0, 'stderr': '',
                'stdout': json.dumps(['other@sha256:' + 'c' * 64, 'python@' + DIGEST])},
        }
        def fake(args, timeout=60, cwd=None):
            key = tuple(args[:3]) if args[:2] == [ 'docker', 'image'] else ('docker', args[1])
            return dict(responses[key], stdout=responses[key]['stdout'])
        with patch.object(preparation, 'render', wraps=preparation.render), \
                patch('creation_pipeline.runtime.local.process', side_effect=fake):
            pin = executor.resolve_base_image('python:3.11-slim', 30)
        self.assertEqual(pin, {'reference': 'python:3.11-slim', 'repository': 'python',
                               'digest': DIGEST, 'repo_digest': 'python@' + DIGEST,
                               'resolved_from': 'registry'})

    def test_an_unreachable_registry_reuses_a_cached_digest(self):
        """Run 46: docker hub timed out, yet the cached image carried the same identity."""
        def fake(args, timeout=60, cwd=None):
            if args[:2] == ['docker', 'pull']:
                return {'exit_code': 1, 'stdout': '',
                        'stderr': 'Head "https://registry-1.docker.io/...": TLS handshake timeout'}
            return {'exit_code': 0, 'stdout': json.dumps(['python@' + DIGEST]), 'stderr': ''}
        with patch('creation_pipeline.runtime.local.process', side_effect=fake):
            pin = LocalExecutor().resolve_base_image('python:3.11-slim', 30)
        self.assertEqual(pin['repo_digest'], 'python@' + DIGEST)
        self.assertEqual(pin['resolved_from'], 'local_cache')

    def test_a_failed_pull_blocks_instead_of_using_the_tag(self):
        def fake(args, timeout=60, cwd=None):
            return {'exit_code': 1, 'stdout': '', 'stderr': 'pull access denied'}
        with patch('creation_pipeline.runtime.local.process', side_effect=fake):
            with self.assertRaises(preparation.RuntimeBlocked) as caught:
                LocalExecutor().resolve_base_image('python:3.11-slim', 30)
        self.assertEqual(caught.exception.code, 'base_image_unresolved')

    def test_a_missing_digest_blocks(self):
        def fake(args, timeout=60, cwd=None):
            if args[:2] == ['docker', 'pull']:
                return {'exit_code': 0, 'stdout': '', 'stderr': ''}
            return {'exit_code': 0, 'stdout': '[]', 'stderr': ''}
        with patch('creation_pipeline.runtime.local.process', side_effect=fake):
            with self.assertRaises(preparation.RuntimeBlocked) as caught:
                LocalExecutor().resolve_base_image('python:3.11-slim', 30)
        self.assertEqual(caught.exception.code, 'base_image_unresolved')

    def test_the_execution_probe_reports_a_missing_pinned_image(self):
        present = {'exit_code': 0, 'stdout': 'sha256:image', 'stderr': ''}
        missing = {'exit_code': 1, 'stdout': '', 'stderr': 'no such image'}
        pin = {'repo_digest': 'python@' + DIGEST}
        with patch('creation_pipeline.runtime.local.process', return_value=present):
            self.assertIsNone(pinned_base_gap(pin, 5))
        with patch('creation_pipeline.runtime.local.process', return_value=missing):
            gap = pinned_base_gap(pin, 5)
        self.assertEqual(gap['code'], 'base_image_unavailable')
        self.assertIsNone(pinned_base_gap(None, 5))


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / 'package'
        self.source = self.root / 'source'
        for path in (self.package / 'main.py', self.source / 'main.py'):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(TEXT, encoding='utf-8')
        self.sources = [{'id': 'tool', 'path': str(self.source),
                         'inventory': manifest(self.source), 'resolved_ref': 'fixed-test-fixture'}]
        from creation_pipeline.contracts import finalize
        self.record = {'name': 'probe', 'status': 'ready', 'files': manifest(self.package),
                       'plan': {'name': 'probe'},
                       'checks': [{'name': 'content_review', 'status': 'pass', 'requirement_assessment': 'confirmed'}]}
        finalize(self.record, self.sources, {'status': 'required', 'reason': 'Executable entry',
                 'citations': [{'source_id': 'tool', 'path': 'main.py', 'quote': 'print("ok")'}]})
        self.assertEqual(self.record['delivery']['inputs']['requirement']['status'], 'required')

    def spec(self, pin):
        # A supplied plan keeps this offline: no planner/model call is involved.
        return {'plan': plan(), 'options': {'pin_base_image': pin}}

    def dockerfile(self, name):
        path = self.root / name / 'materials/context/Dockerfile'
        self.assertTrue(path.is_file(), self.record.get('runtime_preparation'))
        return path.read_text(encoding='utf-8')

    def test_a_pinned_prepare_renders_the_digest_and_freezes_it(self):
        executor = LocalExecutor()
        with patch.object(LocalExecutor, 'host', return_value=HOST), \
                patch.object(LocalExecutor, 'resolve_base_image',
                             return_value={'reference': 'python:3.11-slim', 'repository': 'python',
                                           'digest': DIGEST, 'repo_digest': 'python@' + DIGEST}) as resolve:
            materials = preparation.prepare(self.record, self.package, self.sources,
                                            self.root / 'pinned', self.spec(True), executor)
        self.assertIsNotNone(materials)
        resolve.assert_called_once()
        dockerfile = self.dockerfile('pinned')
        self.assertTrue(dockerfile.startswith('FROM python@' + DIGEST + '\n'), dockerfile.splitlines()[0])
        payload = self.record['delivery']['inputs']['environment']['payload']
        self.assertEqual(payload['base_image']['digest'], DIGEST)
        self.assertEqual(json.loads((self.root / 'pinned/materials/base-image.json').read_text(encoding='utf-8'))['digest'], DIGEST)

    def test_without_the_flag_the_tag_is_kept(self):
        with patch.object(LocalExecutor, 'host', return_value=HOST), \
                patch.object(LocalExecutor, 'resolve_base_image',
                             side_effect=AssertionError('must not resolve')) as resolve:
            preparation.prepare(self.record, self.package, self.sources,
                                self.root / 'tagged', self.spec(False), LocalExecutor())
        resolve.assert_not_called()
        dockerfile = self.dockerfile('tagged')
        self.assertTrue(dockerfile.startswith('FROM ' + plan()['base_image'] + '\n'))
        self.assertNotIn('base_image', self.record['delivery']['inputs']['environment']['payload'])

    def test_resolution_failure_blocks_preparation(self):
        with patch.object(LocalExecutor, 'host', return_value=HOST), \
                patch.object(LocalExecutor, 'resolve_base_image',
                             side_effect=preparation.RuntimeBlocked('base_image_unresolved', 'no digest', 'environment')):
            preparation.prepare(self.record, self.package, self.sources,
                                self.root / 'blocked', self.spec(True), LocalExecutor())
        gaps = self.record['runtime_preparation']['gaps']
        self.assertEqual([g['code'] for g in gaps], ['base_image_unresolved'])
        self.assertIn('no digest', gaps[0]['detail'])
        self.assertEqual(self.record['status'], 'blocked')
        # A blocked pin must not leave a buildable context behind.
        self.assertFalse((self.root / 'blocked/context/Dockerfile').exists())


if __name__ == '__main__':
    unittest.main()
