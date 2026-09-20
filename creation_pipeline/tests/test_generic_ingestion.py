import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ingest_sources import prepare, split_text, download
from core.creation_sources import make_bundle, read_documents

class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_long_source_has_no_dropped_text(self):
        text=('Methods: evaluate alternatives using held-out error.\n'*2000)
        p=self.root/'paper.txt';p.write_text(text)
        manifest,report=prepare([{'path':str(p),'title':'Unseen paper'}],self.root,self.root/'out',6000)
        joined=''.join(Path(s['path']).read_text() for j in manifest['jobs'] for s in j['sources'])
        self.assertEqual(joined,text)
        self.assertGreater(len(manifest['jobs']),1)
        for job in manifest['jobs']:
            bundle=make_bundle(job,self.root,6000)
            self.assertFalse(bundle['omitted'])
            self.assertTrue(bundle['coverage']['primary_text_supplied'])
    def test_database_docs_and_sqlite(self):
        p=self.root/'db.sqlite'
        with sqlite3.connect(p) as c:
            c.execute('CREATE TABLE molecules (id INTEGER PRIMARY KEY, smiles TEXT)')
            c.execute("INSERT INTO molecules VALUES (1,'private-row-not-to-read')")
        doc=self.root/'api.yaml';doc.write_text('openapi: 3.0.0\ninfo:\n  title: Example API\npaths:\n  /molecules:\n    get:\n      summary: Search molecules by identifier\n')
        before=p.read_bytes()
        manifest,_=prepare([{'id':'db','source_type':'database','sources':[{'path':str(doc)},{'path':str(p)}]}],self.root,self.root/'out')
        bundle=make_bundle(manifest['jobs'][0],self.root)
        text=str(bundle['sources'])
        self.assertIn('CREATE TABLE',text);self.assertNotIn('private-row-not-to-read',text)
        self.assertEqual(p.read_bytes(),before)
    def test_raw_csv_requires_documentation(self):
        p=self.root/'data.csv';p.write_text('id,value\n1,4\n')
        manifest,report=prepare([{'path':str(p),'source_type':'database'}],self.root,self.root/'out')
        self.assertEqual(manifest['jobs'],[]);self.assertIn('Primary documentation',report[0]['error'])
    def test_one_bad_source_does_not_lose_other_jobs(self):
        p=self.root/'ok.md';p.write_text('A documented procedure.\n')
        manifest,report=prepare([{'path':'absent.pdf'},{'path':str(p)}],self.root,self.root/'out')
        self.assertEqual(len(manifest['jobs']),1);self.assertEqual(report[0]['status'],'source_error')
    def test_follow_citation_pdf(self):
        self.root.joinpath('download').mkdir()
        responses=[(b'<html><meta name="citation_pdf_url" content="/full.pdf"></html>','https://example.org/paper','text/html'),
                   (b'%PDF-1.4 example','https://example.org/full.pdf','application/pdf')]
        with patch('ingest_sources.fetch',side_effect=responses):
            path,url,_=download('https://example.org/paper',self.root/'download','paper')
        self.assertEqual(path.suffix,'.pdf');self.assertEqual(url,'https://example.org/full.pdf')
    def test_abstract_is_not_full_text(self):
        with patch('ingest_sources.fetch',return_value=(b'<html>Abstract only</html>','https://example.org','text/html')):
            with self.assertRaisesRegex(ValueError,'Landing/abstract'):
                download('https://example.org',self.root,'paper')
    def test_database_js_links_spec_without_execution(self):
        html=b"<html><script>spore.create('/api/spore',function(a){});</script>API</html>"
        responses=[(html,'https://example.org/docs','text/html'),
                   (b'{"methods":{"query":{"path":"/query"}}}', 'https://example.org/api/spore','application/json')]
        with patch('ingest_sources.fetch',side_effect=responses):
            path,url,_=download('https://example.org/docs',self.root,'database')
        self.assertEqual(path.suffix,'.json');self.assertIn('/api/spore',url)
    def test_empty_database_html_rejected(self):
        with patch('ingest_sources.fetch',return_value=(b'<html>Loading API</html>','https://example.org','text/html')):
            with self.assertRaisesRegex(ValueError,'JavaScript-only'):
                download('https://example.org',self.root,'database')
    def test_namespaced_article(self):
        p=self.root/'article.xml';p.write_text('<article xmlns="urn:jats"><body><sec><title>Methods</title><p>Use held-out evidence.</p></sec></body></article>')
        self.assertIn('held-out',read_documents(p)[0][1])
    def test_long_single_line(self):
        text='x'*18000;parts=split_text(text,3000)
        self.assertEqual(''.join(parts),text);self.assertTrue(all(len(p)<=3000 for p in parts))

if __name__=='__main__':unittest.main()
