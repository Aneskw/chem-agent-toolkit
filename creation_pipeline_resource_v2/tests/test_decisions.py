import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE/'core'))
from creation_schema import reconcile_resources, validate
from creation_sources import make_bundle
from repair_citation_spans import repair
from decision_library import build_library
from render_drafts_v03 import copy_present_resources, render
from validate_skill_format import validate as format_check
from repair_citation_spans import repair


def fixture():
    citation={'source_id':'p','start':1,'end':1,'quote':'Sum precursor costs when a reaction requires all precursors.'}
    claim={'text':'Sum precursor costs.', 'citations':[citation]}
    rule={'when':'Comparing reaction branches.','requires':'All precursor cost estimates.',
          'choose':'Sum costs of required precursors.','avoid':'Choose only the cheapest precursor.',
          'because':'All precursors are required.','check':'Every obligation is included.',
          'stop_or_fallback':'Stop if a required precursor is not accessible.',
          'scope':'AND branches in a synthesis search tree.','support':'direct','citations':[citation]}
    candidate={'name':'sum-route-costs','description':'Compare route costs.','kind':'method_procedure',
               'operation':'route search','inputs':[claim],'outputs':[claim],'steps':[claim],
               'requirements':[],'unknowns':[],'decisions':[rule],'resource_manifest':[]}
    bundle={'paper_id':'test','repo_files':[],'sources':[{'id':'p','role':'paper',
             'lines':[citation['quote']],'url':'https://example.org/paper','path':'paper.pdf','sha256':'a'*64}]}
    return {'schema_version':2,'paper_id':'test','candidates':[candidate],'no_skill_reason':''},bundle


class DecisionTests(unittest.TestCase):
    def test_legacy_response_still_works(self):
        response,bundle=fixture();response['schema_version']=1
        del response['candidates'][0]['decisions'];del response['candidates'][0]['resource_manifest']
        self.assertEqual(validate(response,bundle)[0]['state'],'draft_unexecuted')

    def test_method_without_decision_rejected(self):
        response,bundle=fixture();response['candidates'][0]['decisions']=[]
        with self.assertRaisesRegex(ValueError,'change at least one'):validate(response,bundle)

    def test_external_resource_requires_recovery_manifest(self):
        response,bundle=fixture()
        response['candidates'][0]['requirements']=[{
            'path':'models/model.pt','kind':'external_asset',
            'reason':{'text':'A checkpoint is required.','citations':[{
                'source_id':'p','start':1,'end':1,
                'quote':'Sum precursor costs when a reaction requires all precursors.'}]}}]
        with self.assertRaisesRegex(ValueError,'resource_manifest'):
            validate(response,bundle)

    def test_resource_manifest_is_rendered(self):
        response,bundle=fixture();candidate=response['candidates'][0]
        candidate['resource_manifest']=[{
            'path':'models/model.pt','kind':'checkpoint','source_url':'https://example.org/model.pt',
            'source_revision':'v1','sha256':'a'*64,
            'restore_command':'curl -L https://example.org/model.pt -o models/model.pt',
            'status':'download_required','citations':[{
                'source_id':'p','start':1,'end':1,
                'quote':'Sum precursor costs when a reaction requires all precursors.'}]}]
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/candidate['name']/'SKILL.md';path.parent.mkdir()
            path.write_text(render(candidate,bundle,validate(response,bundle)[0]))
            self.assertIn('Resource recovery manifest',path.read_text())

    def test_render_reports_packaged_resources_and_external_acquisitions(self):
        response,bundle=fixture();candidate=response['candidates'][0]
        candidate['resource_manifest']=[
            {'path':'data.csv','kind':'dataset','source_url':'local://data.csv',
             'source_revision':'v1','sha256':'a'*64,'restore_command':'included',
             'status':'present','citations':candidate['inputs'][0]['citations']},
            {'path':'weights.pt','kind':'checkpoint','source_url':'https://example.org/weights.pt',
             'source_revision':'v1','sha256':'','restore_command':'download weights.pt',
             'status':'download_required','citations':candidate['inputs'][0]['citations']}]
        skill=render(candidate,bundle,{'state':'draft_unexecuted'}, {'data.csv'})
        self.assertIn('Bundled resources: 1; external acquisitions: 1',skill)
        self.assertIn('allowed-tools: Read, Bash',skill)
        self.assertNotIn('data requirements below are not bundled',skill)

    def test_resource_manifest_citations_are_repaired(self):
        response,bundle=fixture()
        response['candidates'][0]['resource_manifest']=[{
            'path':'models/model.pt','kind':'checkpoint','source_url':'https://example.org/model.pt',
            'source_revision':'v1','sha256':'','restore_command':'download model.pt',
            'status':'download_required','citations':[{
                **response['candidates'][0]['inputs'][0]['citations'][0], 'start':2,'end':2}]}]
        repaired,changes=repair(response,bundle)
        self.assertEqual(changes[0]['new'],(1,1))
        self.assertEqual(validate(repaired,bundle)[0]['state'],'draft_unexecuted')

    def test_remote_checkpoint_is_downloadable_not_present(self):
        response,bundle=fixture()
        bundle['repo_files']=['checkpoints/model.pt']
        bundle['local_repo_files']=[]
        bundle['resource_catalog']=[{'path':'checkpoints/model.pt',
            'source_url':'https://raw.githubusercontent.com/org/repo/abc/checkpoints/model.pt',
            'git_blob_sha1':'b'*40,'local_present':False,'local_sha256':''}]
        entry={'path':'checkpoints/model.pt','kind':'checkpoint',
            'source_url':bundle['resource_catalog'][0]['source_url'],'source_revision':'abc',
            'sha256':'a'*64,'restore_command':'curl -L pinned-url -o checkpoints/model.pt',
            'status':'present','citations':response['candidates'][0]['inputs'][0]['citations']}
        response['candidates'][0]['resource_manifest']=[entry]
        with self.assertRaisesRegex(ValueError,'not verified in local intake'):
            validate(response,bundle)
        bundle['commit']='abc'
        reconciled,changes=reconcile_resources(response,bundle)
        self.assertEqual(changes[0]['availability'],'download_required')
        self.assertEqual(reconciled['candidates'][0]['resource_manifest'][0]['sha256'],'')
        self.assertEqual(validate(reconciled,bundle)[0]['state'],'draft_unexecuted')
        entry['status']='download_required';entry['sha256']=''
        self.assertEqual(validate(response,bundle)[0]['state'],'draft_unexecuted')
        entry['source_url']='https://example.org/unpinned.pt'
        with self.assertRaisesRegex(ValueError,'pinned commit'):validate(response,bundle)

    def test_model_supplied_hash_does_not_prove_local_presence(self):
        response,bundle=fixture()
        response['candidates'][0]['resource_manifest']=[{
            'path':'invented/model.pt','kind':'checkpoint','source_url':'https://example.org/model.pt',
            'source_revision':'v1','sha256':'a'*64,'restore_command':'download model.pt',
            'status':'present','citations':response['candidates'][0]['inputs'][0]['citations']}]
        with self.assertRaisesRegex(ValueError,'not verified in local intake'):
            validate(response,bundle)
        reconciled,changes=reconcile_resources(response,bundle)
        self.assertEqual(changes[0]['availability'],'unverified')
        self.assertEqual(reconciled['candidates'][0]['resource_manifest'][0]['sha256'],'')
        self.assertEqual(validate(reconciled,bundle)[0]['state'],'blocked_resources')

    def test_model_inference_requires_code_preprocessing_and_checkpoint(self):
        response,bundle=fixture();bundle['model_capability']='single_step_inference'
        response['candidates'][0]['name']='predict-reactants'
        check=validate(response,bundle)[0]
        self.assertEqual(check['state'],'blocked_resources')
        self.assertEqual(check['missing_model_resources'],['source_code','preprocessing','checkpoint'])
        citation=response['candidates'][0]['inputs'][0]['citations']
        response['candidates'][0]['resource_manifest']=[{
            'path':kind,'kind':kind,'source_url':'https://example.org/'+kind,
            'source_revision':'v1','sha256':'','restore_command':'download '+kind,
            'status':'download_required','citations':citation}
            for kind in ('source_code','preprocessing','checkpoint')]
        self.assertEqual(validate(response,bundle)[0]['state'],'draft_unexecuted')

    def test_database_requires_dataset_or_endpoint(self):
        response,bundle=fixture();bundle['source_type']='database'
        bundle['primary_role']='database_doc';bundle['sources'][0]['role']='database_doc'
        check=validate(response,bundle)[0]
        self.assertEqual(check['missing_category_resources'],['dataset_or_endpoint'])
        self.assertEqual(check['state'],'blocked_resources')
        response['candidates'][0]['resource_manifest']=[{
            'path':'https://example.org/activity','kind':'endpoint',
            'source_url':'https://example.org/docs','source_revision':'v1','sha256':'',
            'restore_command':'','status':'download_required',
            'citations':response['candidates'][0]['inputs'][0]['citations']}]
        self.assertEqual(validate(response,bundle)[0]['state'],'draft_unexecuted')

    def test_dataset_mode_needs_data_file_not_just_api_docs(self):
        response,bundle=fixture();bundle['source_type']='database'
        bundle['data_capability']='downloadable_dataset'
        bundle['primary_role']='database_doc';bundle['sources'][0]['role']='database_doc'
        response['candidates'][0]['resource_manifest']=[{
            'path':'https://example.org/activity','kind':'endpoint',
            'source_url':'https://example.org/docs','source_revision':'v1','sha256':'',
            'restore_command':'','status':'download_required',
            'citations':response['candidates'][0]['inputs'][0]['citations']}]
        self.assertEqual(validate(response,bundle)[0]['missing_category_resources'],
                         ['downloadable_dataset'])
        response['candidates'][0]['resource_manifest'].append({
            'path':'data.csv','kind':'dataset','source_url':'https://example.org/data.csv',
            'source_revision':'v1','sha256':'',
            'restore_command':'curl -L https://example.org/data.csv -o data.csv',
            'status':'download_required',
            'citations':response['candidates'][0]['inputs'][0]['citations']})
        self.assertEqual(validate(response,bundle)[0]['state'],'draft_unexecuted')

    def test_paper_dataset_mode_rejects_landing_page(self):
        response,bundle=fixture();bundle['data_capability']='downloadable_dataset'
        citation=response['candidates'][0]['inputs'][0]['citations']
        entry={'path':'data.csv','kind':'dataset','source_url':'https://example.org/datasets/record',
               'source_revision':'v1','sha256':'',
               'restore_command':'curl -L https://example.org/datasets/record -o data.csv',
               'status':'download_required','citations':citation}
        response['candidates'][0]['resource_manifest']=[entry]
        self.assertEqual(validate(response,bundle)[0]['missing_category_resources'],
                         ['downloadable_dataset'])
        entry['source_url']='https://example.org/files/data.csv'
        entry['restore_command']='curl -L https://example.org/files/data.csv -o data.csv'
        self.assertEqual(validate(response,bundle)[0]['state'],'draft_unexecuted')

    def test_bundled_dataset_satisfies_paper_dataset_mode(self):
        response,bundle=fixture();bundle['data_capability']='downloadable_dataset'
        bundle['resource_catalog']=[{'path':'data.csv','source_url':'local://data.csv',
            'local_present':True,'local_sha256':'a'*64}]
        response['candidates'][0]['resource_manifest']=[{
            'path':'data.csv','kind':'dataset','source_url':'local://data.csv',
            'source_revision':'local','sha256':'a'*64,'restore_command':'included at data.csv',
            'status':'present','citations':response['candidates'][0]['inputs'][0]['citations']}]
        self.assertEqual(validate(response,bundle)[0]['state'],'draft_unexecuted')

    def test_other_skill_name_does_not_satisfy_model_preprocessing(self):
        response,bundle=fixture();bundle['model_capability']='single_step_inference'
        citation=response['candidates'][0]['inputs'][0]['citations']
        response['candidates'][0]['resource_manifest']=[{
            'path':kind,'kind':kind,'source_url':url,'source_revision':'v1',
            'sha256':'','restore_command':command,'status':status,'citations':citation}
            for kind,url,command,status in (
                ('source_code','https://example.org/infer.py','download infer.py','download_required'),
                ('preprocessing','','see other skill','blocked_resources'),
                ('checkpoint','https://example.org/model.pt','download model.pt','download_required'))]
        check=validate(response,bundle)[0]
        self.assertEqual(check['state'],'blocked_resources')
        self.assertEqual(check['missing_model_resources'],['preprocessing'])

    def test_tool_requires_usable_code_or_acquisition(self):
        response,bundle=fixture();bundle['source_type']='tool'
        bundle['primary_role']='tool_doc';bundle['sources'][0]['role']='tool_doc'
        self.assertEqual(validate(response,bundle)[0]['missing_category_resources'],
                         ['tool_code_or_acquisition'])
        bundle['commit']='local-snapshot'
        bundle['resource_catalog']=[{'path':'scripts/tool.py','source_url':'local://scripts/tool.py',
            'git_blob_sha1':'','local_present':True,'local_sha256':'a'*64}]
        response['candidates'][0]['resource_manifest']=[{
            'path':'scripts/tool.py','kind':'source_code','source_url':'',
            'source_revision':'','sha256':'','restore_command':'','status':'unverified',
            'citations':response['candidates'][0]['inputs'][0]['citations']}]
        reconciled,_=reconcile_resources(response,bundle)
        self.assertEqual(validate(reconciled,bundle)[0]['state'],'draft_unexecuted')

    def test_local_selected_source_enters_resource_catalog(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'doc.md').write_text('A tool document with enough text.')
            (root/'tool.py').write_text('print("tool")\n')
            job={'paper_id':'test','title':'Tool','repo_root':'.','source_type':'tool',
                 'sources':[{'path':'doc.md','role':'tool_doc'},
                            {'path':'tool.py','role':'repo_code'}]}
            bundle=make_bundle(job,root)
            entry=next(item for item in bundle['resource_catalog'] if item['path']=='tool.py')
            self.assertTrue(entry['local_present'])
            self.assertEqual(len(entry['local_sha256']),64)

    def test_present_source_is_packaged_with_generated_skill(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'source'/'predict.py'
            source.parent.mkdir();source.write_text('print("predict")\n')
            import hashlib
            digest=hashlib.sha256(source.read_bytes()).hexdigest()
            candidate={'resource_manifest':[{'path':'predict.py','kind':'source_code',
                'status':'present','sha256':digest}]}
            out=root/'draft';out.mkdir()
            packaged=copy_present_resources(candidate,{'repo_root':str(source.parent)},out)
            self.assertEqual(packaged,{'predict.py'})
            self.assertEqual((out/'resources'/'predict.py').read_bytes(),source.read_bytes())

    def test_manifest_distinguishes_git_tree_from_local_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);repo=root/'repo';repo.mkdir()
            (repo/'predict.py').write_text('print("predict")\n')
            import hashlib
            data=(repo/'predict.py').read_bytes()
            blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            (root/'repo.json').write_text(json.dumps({'repo':'org/repo','commit':'abc',
                'tree':[{'path':'predict.py','type':'blob','sha':blob},
                        {'path':'checkpoints/model.pt','type':'blob','sha':'b'*40}]}))
            job={'paper_id':'test','title':'Model','repo_root':'repo','repo_manifest':'repo.json',
                 'sources':[{'path':'repo/predict.py','role':'repo_code'}]}
            bundle=make_bundle(job,root)
            self.assertIn('checkpoints/model.pt',bundle['repo_files'])
            self.assertNotIn('checkpoints/model.pt',bundle['local_repo_files'])
            checkpoint=next(item for item in bundle['resource_catalog'] if item['path']=='checkpoints/model.pt')
            self.assertFalse(checkpoint['local_present'])
            self.assertEqual(checkpoint['source_url'],
                'https://raw.githubusercontent.com/org/repo/abc/checkpoints/model.pt')

    def test_each_rule_is_grounded_independently(self):
        response,bundle=fixture()
        bundle['sources'].append({**bundle['sources'][0],'id':'r','role':'repo_doc'})
        rule=copy.deepcopy(response['candidates'][0]['decisions'][0]);rule['citations'][0]['source_id']='r'
        response['candidates'][0]['decisions']=[rule]
        with self.assertRaisesRegex(ValueError,'Each decision'):validate(response,bundle)

    def test_pinned_code_can_ground_an_implementation_decision(self):
        response,bundle=fixture()
        code={**bundle['sources'][0],'id':'c','role':'repo_code','path':'method.py'}
        bundle['sources']=[code]
        for claim in (response['candidates'][0]['inputs']+response['candidates'][0]['outputs']+
                      response['candidates'][0]['steps']+response['candidates'][0]['decisions']):
            claim['citations'][0]['source_id']='c'
        self.assertEqual(validate(response,bundle)[0]['state'],'draft_unexecuted')

    def test_readme_alone_cannot_ground_a_method_step(self):
        response,bundle=fixture()
        readme={**bundle['sources'][0],'id':'r','role':'repo_doc','path':'README.md'}
        bundle['sources']=[readme]
        for claim in (response['candidates'][0]['inputs']+response['candidates'][0]['outputs']+
                      response['candidates'][0]['steps']+response['candidates'][0]['decisions']):
            claim['citations'][0]['source_id']='r'
        with self.assertRaisesRegex(ValueError,'source-document or pinned-code'):validate(response,bundle)

    def test_fabricated_rule_quote_is_rejected(self):
        response,bundle=fixture()
        rule=copy.deepcopy(response['candidates'][0]['decisions'][0]);rule['citations'][0]['quote']='Invented chemistry result'
        response['candidates'][0]['decisions']=[rule]
        with self.assertRaisesRegex(ValueError,'quote not found'):validate(response,bundle)

    def test_simple_dedup_preserves_scope_and_citations(self):
        response,_=fixture();other=copy.deepcopy(response);other['paper_id']='second'
        report=build_library([response,other])
        self.assertEqual(report['unique_rules'],1);self.assertEqual(len(report['rules'][0]['origins']),2)
        other['candidates'][0]['decisions'][0]['scope']='Shared intermediates in a DAG, not a tree.'
        report=build_library([response,other]);self.assertEqual(report['unique_rules'],2)
        self.assertEqual(report['related'][0]['action'],'retain_scoped_variants')

    def test_render_matches_user_format_without_invented_license(self):
        response,bundle=fixture();c=response['candidates'][0]
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/c['name']/'SKILL.md';path.parent.mkdir()
            path.write_text(render(c,bundle,validate(response,bundle)[0]))
            self.assertEqual(format_check(path),[])
            self.assertIn('license: undetermined',path.read_text())
            self.assertIn('Stop / fallback',path.read_text())

    def test_rules_participate_in_bounded_citation_repair(self):
        response,bundle=fixture()
        bundle['sources'][0]['lines']=['Heading',bundle['sources'][0]['lines'][0]]
        revised,changes=repair(response,bundle)
        self.assertTrue(changes);validate(revised,bundle)

    def test_relocation_does_not_fabricate_or_choose_ambiguous_quotes(self):
        response,bundle=fixture();quote=bundle['sources'][0]['lines'][0]
        bundle['sources'][0]['lines']=['Heading']*10+[quote]
        revised,changes=repair(copy.deepcopy(response),bundle)
        self.assertTrue(changes);validate(revised,bundle)
        bundle['sources'][0]['lines'] += [quote]
        with self.assertRaisesRegex(ValueError,'ambiguous'):repair(copy.deepcopy(response),bundle)

if __name__=='__main__':unittest.main()
