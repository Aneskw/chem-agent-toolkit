"""Author and independent reviewer receive the same host execution layout truth."""
import copy
from types import SimpleNamespace
import unittest
from creation_pipeline.generation.context import candidate_context
from tests.pipeline.test_shared_tool import declaration


class SharedExecutionContextTests(unittest.TestCase):
    def setUp(self):
        self.session=SimpleNamespace(sources=SimpleNamespace(index=lambda:[],validate_evidence=lambda e:e),
                                     workspace={'resource_index':[]})
        self.config={'prompt':'Deliver exactly SKILL.md, main.py and rules.json;', 'notes':'','constraints':{},
                     'runtime_defaults':{'shared_tool':declaration(),'resource_refs':{'private':'do not forward'}}}
        self.plan={'name':'probe','evidence':[]}

    def test_shared_image_layout_is_explicit_and_not_business_evidence(self):
        result=candidate_context(self.session,self.config,self.plan)['tool_execution_layout']
        self.assertEqual(result['tool_image_excluded_files'],['SKILL.md'])
        self.assertIn('SKILL.md',result['current_skill_package']['required_files'])
        self.assertIn('not a business oracle',result['authority'])
        self.assertNotIn('private',str(result))

    def test_legacy_and_explicit_disable_do_not_inherit_shared_layout(self):
        config=copy.deepcopy(self.config);config['runtime_defaults']={}
        self.assertNotIn('tool_execution_layout',candidate_context(self.session,config,self.plan))
        config=copy.deepcopy(self.config);config['runtime']={'probe':{'shared_tool':None}}
        self.assertNotIn('tool_execution_layout',candidate_context(self.session,config,self.plan))

    def test_candidate_override_matches_effective_runtime_spec(self):
        config=copy.deepcopy(self.config);d=declaration();d['interface']['entrypoint'][0]='python3'
        config['runtime']={'probe':{'shared_tool':d}}
        actual=candidate_context(self.session,config,self.plan)['tool_execution_layout']
        self.assertEqual(actual['entrypoint'],d['interface']['entrypoint'])
