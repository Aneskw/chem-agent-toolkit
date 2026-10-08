import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pair_sources import pair
from core.creation_sources import make_bundle


class PairTests(unittest.TestCase):
    def test_unseen_pdf_repo_pins_git_bytes_not_dirty_worktree(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);repo=base/'repo';repo.mkdir()
            subprocess.run(['git','init','-q',str(repo)],check=True)
            source=repo/'predict.py';source.write_text('def predict():\n    return "original"\n')
            (repo/'translate.py').write_text('def translate():\n    return "prediction"\n')
            (repo/'data.csv').write_text('smiles\nCCO\n')
            subprocess.run(['git','-C',str(repo),'add','predict.py','translate.py','data.csv'],check=True)
            subprocess.run(['git','-C',str(repo),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                            'commit','-qm','fixture'],check=True)
            source.write_text('raise RuntimeError("uncommitted change must not become evidence")\n')
            writer=PdfWriter();page=writer.add_blank_page(300,200)
            font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),
                                   NameObject('/BaseFont'):NameObject('/Helvetica')})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
            stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 20 100 Td (An unseen method uses evidence to choose.) Tj ET')
            page[NameObject('/Contents')]=writer._add_object(stream)
            pdf=base/'unseen.pdf'
            with pdf.open('wb') as f:writer.write(f)
            config=pair(str(pdf),str(repo),base/'pair',files=['predict.py'],paper_id='unseen')
            settings=json.loads(config.read_text())
            bundle=make_bundle(settings['jobs'][0],config.parent)
            self.assertFalse(bundle['omitted']);self.assertNotEqual(bundle['commit'],'unversioned')
            self.assertTrue(any('original' in '\n'.join(s['lines']) for s in bundle['sources']))
            self.assertFalse(any('uncommitted' in '\n'.join(s['lines']) for s in bundle['sources']))
            model_config=pair(str(pdf),str(repo),base/'model-pair',paper_id='model',
                              model_capability='single_step_inference',resources=['data.csv'])
            report=json.loads((model_config.parent/'source_pair.json').read_text())
            self.assertIn('repo/translate.py',report['selected_files'])
            self.assertIn('data.csv',report['copied_resources'])
            self.assertEqual((model_config.parent/'repo'/'data.csv').read_text(),'smiles\nCCO\n')
            model_bundle=make_bundle(json.loads(model_config.read_text())['jobs'][0],model_config.parent)
            resource=next(item for item in model_bundle['resource_catalog'] if item['path']=='data.csv')
            self.assertTrue(resource['local_present'])
            dataset_config=pair(str(pdf),str(repo),base/'dataset-pair',paper_id='dataset',
                                resources=['data.csv'],data_capability='downloadable_dataset')
            dataset_job=json.loads(dataset_config.read_text())['jobs'][0]
            self.assertEqual(dataset_job['data_capability'],'downloadable_dataset')

if __name__=='__main__':unittest.main()
