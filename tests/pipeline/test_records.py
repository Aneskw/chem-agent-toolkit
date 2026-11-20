"""Atomic JSON publication survives readers and concurrent staging writes."""
from concurrent.futures import ThreadPoolExecutor
import errno
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from creation_pipeline.paths import ROOT
from creation_pipeline.records import read_json, write_json
import creation_pipeline.records as records


class JsonPublicationTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.pipeline/test-tmp'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name)
        self.path = self.root / 'state.json'

    def tearDown(self):
        self.temp.cleanup()

    def test_short_windows_read_lock_does_not_lose_publication(self):
        replace = records.os.replace
        error = PermissionError(errno.EACCES, 'Sharing violation')
        error.winerror = 32
        calls = []
        def occupied_once(source, destination):
            calls.append(source)
            if len(calls) == 1:
                raise error
            return replace(source, destination)
        with patch.object(records.os, 'replace', side_effect=occupied_once), patch.object(records.time, 'sleep'):
            write_json(self.path, {'value': 2})
        self.assertEqual(read_json(self.path), {'value': 2})
        self.assertEqual([p.name for p in self.root.iterdir()], ['state.json'])

    def test_persistent_failure_preserves_old_document_and_cleans_staging(self):
        write_json(self.path, {'old': True})
        error = PermissionError(errno.EACCES, 'Persistent access failure')
        error.winerror = 5
        with patch.object(records.os, 'replace', side_effect=error), patch.object(records.time, 'sleep'):
            with self.assertRaises(PermissionError):
                write_json(self.path, {'new': True})
        self.assertEqual(read_json(self.path), {'old': True})
        self.assertEqual([p.name for p in self.root.iterdir()], ['state.json'])

    def test_concurrent_writers_do_not_share_a_staging_file(self):
        replace = records.os.replace
        barrier, lock, seen = threading.Barrier(2), threading.Lock(), set()
        def overlap(source, destination):
            identity = threading.get_ident()
            with lock:
                first = identity not in seen
                seen.add(identity)
            if first:
                barrier.wait(timeout=5)
            return replace(source, destination)
        with patch.object(records.os, 'replace', side_effect=overlap):
            with ThreadPoolExecutor(max_workers=2) as workers:
                futures = [workers.submit(write_json, self.path, {'value': value}) for value in (1, 2)]
                for future in futures:
                    future.result(timeout=10)
        self.assertIn(read_json(self.path), ({'value': 1}, {'value': 2}))
        self.assertEqual([p.name for p in self.root.iterdir()], ['state.json'])
