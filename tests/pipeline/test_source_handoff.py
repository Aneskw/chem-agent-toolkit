"""Real source handoff, delivery and archive behavior; no network or model calls."""
import unittest
import sys
import io
from urllib.error import URLError
from pathlib import Path
from unittest.mock import patch

from tests.pipeline import test_research as fixtures
from creation_pipeline.records import read_json, write_json
from creation_pipeline.resources.supplements import receive, register, restore, supplement
from creation_pipeline.resources.workspace import prepare, sync_sources
from creation_pipeline.validation.basis import validate_basis
from creation_pipeline.artifacts.content_delivery import finish
from creation_pipeline.shared.resources import archive_sources


class SourceHandoffTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.ResearchTests()
        self.case.setUp()
        self.case.config['network'] = True
        prepare(self.case.sources, self.case.work)

    def tearDown(self):
        self.case.tearDown()

    def saved(self, **updates):
        c = self.case
        content = c.work / 'research/inbox/api.txt'
        content.write_text('Official API: add(a, b) returns the sum. Section: Returns.', encoding='utf-8')
        data = dict(path='research/inbox/api.txt', url='https://example.org/api',
                    reason='Confirm output', related_to=['tool'], representation='excerpt')
        data.update(updates)
        sidecar = content.with_suffix('.source.json')
        write_json(sidecar, data)
        return content, sidecar

    def test_relative_paths_are_ingested_and_ids_remain_stable(self):
        content, _ = self.saved()
        before = restore(self.case.work).evidence.copy()
        first = receive(self.case.work)
        self.assertEqual(first, receive(self.case.work))
        sources = restore(self.case.work)
        self.assertEqual(sources.evidence[:len(before)], before)
        self.assertEqual(len(sources.entries), 2)
        basis = validate_basis([dict(location='Usage', claim='Returns sum', source=str(content),
                                    locator='Returns', origin='upstream')], sources)
        self.assertEqual(basis[0]['source_id'], first['sources'][0]['source'])
        sync_sources(self.case.sources, self.case.work)
        self.assertEqual(len(self.case.sources.entries), 2)

    def test_empty_remote_content_is_unavailable_without_registry_pollution(self):
        class Response(io.BytesIO):
            url = 'https://example.org/empty'
            headers = {'Content-Type': 'text/html'}
        with patch('creation_pipeline.resources.acquisition.urllib.request.urlopen', return_value=Response(b'')):
            result = supplement(self.case.work, {'url': Response.url}, 'Need interface details')
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['error_kind'], 'content')
        sources = restore(self.case.work)
        self.assertEqual(list(sources.entries), ['tool'])
        self.assertEqual(sources.errors[-1]['error_kind'], 'content')

    def test_transport_failure_and_constraint_remain_distinct(self):
        with patch('creation_pipeline.resources.acquisition.Acquisition.download', side_effect=URLError('TLS failed')):
            result = supplement(self.case.work, {'url': 'https://example.org/manual'}, 'Need interface')
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['error_kind'], 'transport')
        self.case.config['network'] = False
        prepare(self.case.sources, self.case.work)
        result = supplement(self.case.work, {'url': 'https://example.org/manual'}, 'Need interface')
        self.assertEqual(result['error_kind'], 'constraint')
        self.assertEqual(list(restore(self.case.work).entries), ['tool'])

    def test_input_local_io_and_programming_errors_are_not_remote_unavailable(self):
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            supplement(self.case.work, {'url': 'http://example.org/manual'}, 'Need interface')
        for error in (OSError('Cannot write cache'), RuntimeError('Unexpected implementation failure')):
            with self.subTest(error=type(error).__name__):
                with patch('creation_pipeline.resources.acquisition.Acquisition.download', side_effect=error):
                    with self.assertRaises(type(error)):
                        supplement(self.case.work, {'url': 'https://example.org/manual'}, 'Need interface')
        sources = restore(self.case.work)
        self.assertEqual(list(sources.entries), ['tool'])
        self.assertFalse(sources.errors)

    def test_incomplete_sidecars_ignored_and_committed_errors_repairable(self):
        _, definition = self.saved(path='../outside')
        temporary = definition.with_suffix('.tmp')
        definition.rename(temporary)
        self.assertEqual(receive(self.case.work)['sources'], [])
        temporary.rename(definition)
        with self.assertRaisesRegex(ValueError, 'Repair committed'):
            receive(self.case.work)
        self.saved()
        self.assertEqual(len(receive(self.case.work)['sources']), 1)

    def test_missing_empty_and_network_disabled_content_rejected(self):
        content, _ = self.saved()
        content.write_text('')
        with self.assertRaisesRegex(ValueError, 'nonempty'):
            receive(self.case.work)
        content.unlink()
        with self.assertRaises(ValueError):
            receive(self.case.work)
        self.saved()
        self.case.config['network'] = False
        prepare(self.case.sources, self.case.work)
        with self.assertRaisesRegex(ValueError, 'network=false'):
            receive(self.case.work)

    def second_input(self):
        c = self.case
        sources = restore(c.work)
        extra = c.root / 'second.py'
        extra.write_text('def other(): pass')
        sources.add(dict(id='other-input', path=str(extra)))
        prepare(sources, c.work)

    def test_duplicate_native_and_downloaded_sources_merge_input_purposes(self):
        _, definition = self.saved()
        first = register(self.case.work, definition)
        self.second_input()
        data = read_json(definition)
        data.update(related_to=['other-input'], reason='Second input output')
        write_json(definition, data)
        self.assertEqual(first['source'], register(self.case.work, definition)['source'])
        entry = restore(self.case.work).entries[first['source']]
        self.assertEqual(entry['related_to'], ['other-input', 'tool'])
        self.assertEqual(len(entry['acquisition_uses']), 2)
        with self.assertRaisesRegex(ValueError, 'explicit related_to'):
            supplement(self.case.work, {'url': 'https://example.org/download'}, 'Ambiguous')
        download = self.case.root / 'download.txt'
        download.write_text('Official file')
        with patch('creation_pipeline.resources.acquisition.Acquisition.download', return_value=(download, {})) as fetch:
            a = supplement(self.case.work, {'url': 'https://example.org/download'}, 'First', related_to=['tool'])
            b = supplement(self.case.work, {'url': 'https://example.org/download'}, 'Second', related_to=['other-input'])
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(a['source'], b['source'])
        self.assertEqual(restore(self.case.work).entries[a['source']]['related_to'], ['other-input', 'tool'])

    def test_author_finish_ingests_before_basis_validation(self):
        content, _ = self.saved()
        metadata = self.case.work / 'metadata.json'
        write_json(metadata, {'basis': [dict(location='Usage', claim='Returns sum', source=str(content),
                                            locator='Returns', origin='upstream')]})
        result = finish(self.case.work, self.case.package, 'delivery-token', metadata)
        self.assertEqual(result['status'], 'saved')
        self.assertEqual(len(restore(self.case.work).entries), 2)

    def test_invalid_scope_evidence_is_repairable_before_delivery_receipt(self):
        content, _ = self.saved()
        metadata = self.case.work / 'metadata.json'
        data = {'basis': [dict(location='Usage', claim='Returns sum', source=str(content),
                               locator='Returns', origin='upstream')],
                'candidate_update': {'reason': 'Clarify output', 'entrypoint': 'api.add',
                                     'evidence': ['e2 Returns section']}}
        write_json(metadata, data)
        with self.assertRaisesRegex(ValueError, 'not strings'):
            finish(self.case.work, self.case.package, 'token', metadata)
        self.assertFalse((self.case.work / 'deliveries/add-numbers.json').exists())
        data['candidate_update']['evidence'] = [{'id': 'e2', 'claim': 'Returns section establishes sum'}]
        write_json(metadata, data)
        self.assertEqual(finish(self.case.work, self.case.package, 'token', metadata)['status'], 'saved')

    def test_archived_evidence_survives_source_removal(self):
        content, _ = self.saved()
        sid = receive(self.case.work)['sources'][0]['source']
        sources = restore(self.case.work)
        dest = self.case.root / 'records'
        archive_sources(self.case.work, dest)
        entries = read_json(dest / 'sources.json')
        entry = next(e for e in entries if e['id'] == sid)
        archived = Path(entry['path'])
        self.assertTrue(archived.is_relative_to(dest))
        self.assertEqual(content.read_bytes(), archived.read_bytes())
        content.unlink()
        Path(sources.entries[sid]['path']).unlink()
        self.assertIn('Official API', archived.read_text())

    def test_turn_boundary_errors_are_returned_to_agent_for_repair(self):
        from creation_pipeline.agent.backend import NativeSession
        fake = self.case.root / 'fake-agent.py'
        fake.write_text('''import json,sys
from pathlib import Path
prompt=sys.stdin.read()
run=Path.cwd()
p=run/'research/inbox/api.txt'
p.write_text('Official API content')
d={'path':'research/inbox/api.txt','url':'https://example.org/api',
   'related_to':['tool'],'reason':'Check return'}
if 'resource_handoff_error' not in prompt: d['path']='research/inbox/missing.txt'
(p.with_suffix('.source.json')).write_text(json.dumps(d))
print(json.dumps({'type':'thread.started','thread_id':'fake-handoff'}))
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'{"done":true}'}}))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':1}}))
''', encoding='utf-8')
        session = NativeSession(self.case.config, self.case.sources,
                                self.case.config['limits'].copy(), self.case.work)
        with patch('creation_pipeline.agent.backend.codex_command', return_value=[sys.executable, str(fake)]):
            self.assertEqual(session.stage('Complete', {}, {}), {'done': True})
        self.assertEqual(len(session.receipts), 2)
        self.assertEqual(len(restore(self.case.work).entries), 2)


    def test_native_supplement_is_reused_by_another_group(self):
        from creation_pipeline.shared.resources import lookup, adopt
        from creation_pipeline.resources.intake import Sources
        self.case.config['workflow'] = 'shared-environments'
        prepare(self.case.sources, self.case.work)
        content, _ = self.saved()
        registered = receive(self.case.work)['sources'][0]['source']
        first = restore(self.case.work)
        second = Sources(self.case.config, self.case.sources.cache)
        other_run = self.case.root / 'other-group'
        prepare(second, other_run)
        matches = lookup(other_run, 'https://example.org/api')
        self.assertEqual(len(matches), 1)
        result = adopt(other_run, matches[0]['snapshot_id'], 'Verify the same API', ['tool'])
        entry = restore(other_run).entries[result['source']]
        self.assertEqual(entry['snapshot_id'], first.entries[registered]['snapshot_id'])
        self.assertEqual(entry['related_to'], ['tool'])
        self.assertEqual(Path(entry['path']).read_bytes(), content.read_bytes())

    def test_shared_delivery_ingests_before_basis_validation(self):
        from creation_pipeline.artifacts.content_delivery import finish as shared_finish
        content, _ = self.saved()
        metadata = self.case.work / 'metadata.json'
        write_json(metadata, {'basis': [dict(location='Usage', claim='Returns sum', source=str(content),
                                            locator='Returns', origin='upstream')]})
        self.assertEqual(shared_finish(self.case.work, self.case.package, 'delivery-token', metadata)['status'], 'saved')
        self.assertEqual(len(restore(self.case.work).entries), 2)

    def test_unchanged_handoff_failure_stops_without_connection_error(self):
        from creation_pipeline.agent.backend import NativeSession
        from creation_pipeline.resources.supplements import SourceHandoffError
        session = NativeSession(self.case.config, self.case.sources,
                                self.case.config['limits'].copy(), self.case.work)
        with patch.object(session, '_stage_once', side_effect=SourceHandoffError('Missing content')) as stage:
            with self.assertRaisesRegex(SourceHandoffError, 'Repeated unchanged'):
                session.stage('Complete', {})
        self.assertEqual(stage.call_count, 2)


if __name__ == '__main__':
    unittest.main()
