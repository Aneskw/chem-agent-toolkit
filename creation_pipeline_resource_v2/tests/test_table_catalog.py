import csv
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from table_to_catalog import convert

class TableCatalogTests(unittest.TestCase):
    def test_zotero_like_columns(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'papers.csv';out=Path(td)/'catalog.json'
            with p.open('w',newline='') as h:
                w=csv.DictWriter(h,fieldnames=['Key','Title','DOI','Url','Code','Type']);w.writeheader()
                w.writerow({'Key':'a1','Title':'A method','DOI':'10.1/example','Url':'https://example.org/paper.pdf','Code':'https://github.com/a/b','Type':'journalArticle'})
            result=convert(p,out)
            self.assertEqual(result['items'][0]['source_type'],'paper')
            self.assertEqual(len(result['items'][0]['sources']),3)
            self.assertEqual(result['items'][0]['sources'][2]['url'],'https://github.com/a/b')
    def test_missing_source_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'papers.csv';out=Path(td)/'catalog.json';p.write_text('Title\nNo link\n')
            result=convert(p,out);self.assertEqual(result['items'],[]);self.assertEqual(len(result['issues']),1)

if __name__=='__main__':unittest.main()
