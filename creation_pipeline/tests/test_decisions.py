import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE/'core'))
from creation_schema import validate
from decision_library import build_library
from render_drafts_v03 import render
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
               'requirements':[],'unknowns':[],'decisions':[rule]}
    bundle={'paper_id':'test','repo_files':[],'sources':[{'id':'p','role':'paper',
             'lines':[citation['quote']],'url':'https://example.org/paper','path':'paper.pdf','sha256':'a'*64}]}
    return {'schema_version':2,'paper_id':'test','candidates':[candidate],'no_skill_reason':''},bundle


class DecisionTests(unittest.TestCase):
    def test_legacy_response_still_works(self):
        response,bundle=fixture();response['schema_version']=1
        del response['candidates'][0]['decisions']
        self.assertEqual(validate(response,bundle)[0]['state'],'draft_unexecuted')

    def test_method_without_decision_rejected(self):
        response,bundle=fixture();response['candidates'][0]['decisions']=[]
        with self.assertRaisesRegex(ValueError,'change at least one'):validate(response,bundle)

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
