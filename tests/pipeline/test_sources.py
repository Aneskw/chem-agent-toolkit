"""Resource adapters and provider protocol tests without external services."""
import json
import io
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from creation_pipeline.acquisition import Acquisition
from creation_pipeline.documents import read_text, table_rows
from creation_pipeline.intake import Sources
from creation_pipeline.models import BlockedError, load_config
from creation_pipeline.providers import APIBackend
from creation_pipeline.records import write_json


class SourceTests(unittest.TestCase):
    def setUp(self):
        parent = Path(__file__).resolve().parents[2] / ".pipeline/test-tmp"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name)
        self.doc = self.root / "doc.md"
        self.doc.write_text("# Actual source", encoding="utf-8")
        self.config_path = self.root / "config.json"
        write_json(self.config_path, {"sources": [{"id": "doc", "path": "doc.md"}]})
        self.config = load_config(self.config_path)

    def tearDown(self):
        self.temp.cleanup()

    def test_docx_extracts_text(self):
        path = self.root / "sample.docx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>API example</w:t></w:r></w:p></w:body></w:document>')
        self.assertIn("API example", read_text(path, 10000))

    def test_notebook_excludes_outputs(self):
        path = self.root / "sample.ipynb"
        write_json(path, {"cells": [{"cell_type": "code", "source": ["add(2,3)"], "outputs": ["untrusted result"]}]})
        text = read_text(path, 10000)
        self.assertIn("add(2,3)", text)
        self.assertNotIn("untrusted result", text)

    def test_html_and_xml_cleaning(self):
        path = self.root / "article.html"
        path.write_text("<html><script>bad()</script><p>Actual API</p></html>")
        self.assertEqual(read_text(path, 10000), "Actual API")
        path.write_text("<html>verify you are human</html>")
        with self.assertRaises(BlockedError):
            read_text(path, 10000)
        path = self.root / "article.xml"
        path.write_text("<article><body><p>Actual paper</p></body></article>")
        self.assertIn("Actual paper", read_text(path, 10000))

    def test_sqlite_schema_not_rows(self):
        path = self.root / "sample.sqlite"
        connection = sqlite3.connect(path)
        connection.execute("CREATE TABLE molecule(name TEXT)")
        connection.execute("INSERT INTO molecule VALUES ('hidden-row-value')")
        connection.commit()
        connection.close()
        text = read_text(path, 10000)
        self.assertIn("CREATE TABLE", text)
        self.assertNotIn("hidden-row-value", text)

    def test_xlsx_sparse_columns_preserved(self):
        path = self.root / "sources.xlsx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1" t="inlineStr"><is><t>title</t></is></c><c r="C1" t="inlineStr"><is><t>url</t></is></c></row><row><c r="A2" t="inlineStr"><is><t>Paper</t></is></c><c r="C2" t="inlineStr"><is><t>https://example.org/paper</t></is></c></row></sheetData></worksheet>')
        self.assertEqual(table_rows(path, 10000)[0]["url"], "https://example.org/paper")

    def test_table_expands_local_paths_and_reports_unmapped(self):
        path = self.root / "sources.csv"
        path.write_text("title,path\nA,doc.md\nB,\n", encoding="utf-8")
        self.config["sources"] = [{"id": "catalog", "table": str(path)}]
        sources = Sources(self.config, self.root / "cache")
        self.assertEqual(len(sources.entries), 1)
        self.assertEqual(sources.errors[0]["row"], 2)

    def test_partial_source_failure_does_not_drop_valid_source(self):
        self.config["sources"].append({"id": "missing", "path": str(self.root / "missing")})
        sources = Sources(self.config, self.root / "cache")
        self.assertIn("doc", sources.entries)
        self.assertEqual(sources.errors[0]["source"], "missing")

    def test_snapshot_does_not_change_with_original(self):
        sources = Sources(self.config, self.root / "cache")
        self.doc.write_text("changed", encoding="utf-8")
        text = sources.request({"action": "read", "source": "doc", "path": "doc.md"})
        self.assertIn("Actual source", text["excerpt"])
        sources.verify()

    def test_fetch_budget_and_disabled_network(self):
        self.config["network"] = False
        acquisition = Acquisition(self.config, self.root / "cache")
        with self.assertRaises(BlockedError):
            acquisition.download("https://example.org/doc")
        self.config["network"] = True
        self.config["limits"]["network_requests"] = 1
        acquisition.requests = 1
        with self.assertRaises(BlockedError):
            acquisition.download("https://example.org/doc")

    def test_download_respects_explicit_size_and_xml_type(self):
        class Response(io.BytesIO):
            url = "https://example.org/fullTextXML"
            headers = {"Content-Type": "application/xml"}
        acquisition = Acquisition(self.config, self.root / "cache")
        with patch("creation_pipeline.acquisition.urllib.request.urlopen", return_value=Response(b"<article/>")):
            path, _ = acquisition.download(Response.url)
            self.assertEqual(path.suffix, ".xml")
        self.config["limits"]["source_bytes"] = 10
        with patch("creation_pipeline.acquisition.urllib.request.urlopen", return_value=Response(b"x" * 11)), self.assertRaises(BlockedError):
            acquisition.download("https://example.org/oversized.xml")

    def test_provider_envelope_and_usage_chat_and_ollama(self):
        for kind in ("chat_completions", "ollama"):
            backend = APIBackend({"backend": kind, "name": "fixture", "base_url": "http://localhost:1234", "api_key_env": ""})
            answer = {"action": "complete", "payload": {"candidates": []}}
            body = ({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(answer)}}], "usage": {"prompt_tokens": 5}}
                    if kind == "chat_completions" else {"done": True, "done_reason": "stop", "message": {"content": json.dumps(answer)}, "eval_count": 3})
            mock = MagicMock()
            mock.__enter__.return_value = mock
            mock.read.return_value = json.dumps(body).encode()
            with patch("creation_pipeline.providers.urllib.request.build_opener") as opener:
                opener.return_value.open.return_value = mock
                value, receipt = backend.call("test", 1)
                sent = json.loads(opener.return_value.open.call_args.args[0].data)
                self.assertEqual(sent["model"], "fixture")
                self.assertEqual(value, answer)
                self.assertTrue(receipt["usage"])

    def test_provider_rejects_remote_plain_http(self):
        with self.assertRaises(ValueError):
            APIBackend({"backend": "chat_completions", "name": "x", "base_url": "http://example.org/v1"}).call("test", 1)

    def test_github_export_pins_commit_and_retains_binary_assets(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('tool-abc/api.py', 'def add(a,b): return a+b')
            archive.writestr('tool-abc/weights.pt', b'not-source')
        metadata = MagicMock()
        metadata.__enter__.return_value = metadata
        metadata.read.return_value = json.dumps({'sha': 'a' * 40}).encode()
        zipped = MagicMock()
        zipped.__enter__.return_value = zipped
        zipped.read.side_effect = io.BytesIO(stream.getvalue()).read
        zipped.url = "https://codeload.github.com/example/tool/zip/" + "a" * 40
        zipped.headers = {}
        acquisition = Acquisition(self.config, self.root / 'cache')
        with patch('creation_pipeline.acquisition.urllib.request.urlopen', side_effect=[metadata, zipped]):
            path, origin = acquisition.repository('https://github.com/example/tool.git', 'v1')
        self.assertEqual(origin['resolved_ref'], 'a' * 40)
        self.assertTrue((path / 'api.py').exists())
        self.assertTrue((path / 'weights.pt').exists())

    def test_snapshot_added_files_are_detected(self):
        source = self.root / 'code'
        source.mkdir()
        (source / 'api.py').write_text('print(5)', encoding='utf-8')
        self.config['sources'] = [{'id': 'code', 'path': str(source)}]
        sources = Sources(self.config, self.root / 'cache')
        (Path(sources.entries['code']['path']) / 'extra.py').write_text('print(6)', encoding='utf-8')
        with self.assertRaises(ValueError):
            sources.verify()

    def test_remote_commit_not_replaced_by_pipeline_parent_repository(self):
        exported = self.root / 'export'
        exported.mkdir()
        (exported / 'api.py').write_text('print(5)', encoding='utf-8')
        prepared = {'id': 'code', 'path': str(exported), 'repo': 'https://github.com/example/tool.git',
                    'resolved_ref': 'a' * 40, 'repository_export': True}
        self.config['sources'] = [{'id': 'code', 'repo': prepared['repo']}]
        with patch('creation_pipeline.acquisition.Acquisition.prepare', return_value=prepared):
            sources = Sources(self.config, self.root / 'cache')
        self.assertEqual(sources.entries['code']['resolved_ref'], 'a' * 40)
