"""Finite JSON resource reads; all offline, no model or Docker."""
import copy
from pathlib import Path
import tempfile
import unittest
from creation_pipeline.records import file_digest
from creation_pipeline.contracts import fingerprint
from creation_pipeline.runtime import shared_tool as st, bundled_data as bd
from tests.pipeline.test_shared_tool import declaration

CODE='from pathlib import Path\nimport json\nprint(json.loads((Path(__file__).resolve().parent / "data" / "rules.json").read_text(encoding="utf-8")))\n'


class BundledDataTests(unittest.TestCase):
    def test_failed_quote_diagnostic_shows_actual_source_without_approving_it(self):
        from creation_pipeline.runtime.acceptance import grounding_problem, grounded
        text='Invalid or empty inputs exit 2.\nValid CCO input reports a selected descriptor result.\n'
        (self.package/'README.md').write_text(text,encoding='utf-8')
        citation={'source_path':'package/README.md','source_quote':'Invalid SMILES always exit 2.'}
        index={'files':['package/README.md'],'read_files':['package/README.md']}
        before=copy.deepcopy(citation)
        reason=grounding_problem(citation,index,self.root)
        self.assertIn('Invalid or empty inputs exit 2.',reason)
        self.assertIn('diagnostic only',reason)
        self.assertFalse(grounded(citation,index,self.root));self.assertEqual(citation,before)
        self.assertEqual((self.package/'README.md').read_text(encoding='utf-8'),text)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.package=self.root/'package';self.package.mkdir()
        (self.root/'sources').mkdir();(self.package/'data').mkdir()
        (self.package/'main.py').write_text(CODE,encoding='utf-8')
        (self.package/'data/rules.json').write_text('{"max":50}',encoding='utf-8')
        self.d=declaration();self.d['policy']=bd.POLICY
        self.d['bundled_data']=[{'module':'main.py','path':'data/rules.json','sha256':file_digest(self.package/'data/rules.json')}]

    def request(self,d=None):
        return st.describe(self.root,{'entry':'main.py','entry_sha256':file_digest(self.package/'main.py'),'association':'identical'},d or self.d)

    def test_new_profile_and_old_rejection(self):
        r=self.request();self.assertEqual(r['abi'],bd.ABI)
        self.assertIn('package/data/rules.json',[x['path'] for x in r['files']])
        with self.assertRaisesRegex(ValueError,'dynamic implementation'):self.request(declaration())

    def test_exception_match_and_attribute_rebinding_are_rejected(self):
        for head in ('try:\n    raise ValueError()\nexcept ValueError as Path:\n    pass\n',
                     'match obj:\n    case {"path": Path}:\n        pass\n',
                     'import sys\nsys.modules["pathlib"].Path = other\n'):
            (self.package/'main.py').write_text(head+CODE,encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'path binding'):self.request()

    def test_data_bytes_must_match_explicit_identity(self):
        (self.package/'data/rules.json').write_text('{"max":51}')
        with self.assertRaisesRegex(ValueError,'expected sha256=.*actual='):self.request()

    def test_missing_data_or_module_is_named(self):
        for field,value in [('path','data/missing.json'),('module','missing.py')]:
            d=copy.deepcopy(self.d);d['bundled_data'][0][field]=value
            with self.assertRaisesRegex(ValueError,'expected file '+value):self.request(d)

    def test_dynamic_escape_write_encoding_and_alias_forms_rejected(self):
        bad=[CODE.replace('"data"','".."'),CODE.replace('"rules.json"','filename'),
             CODE.replace('.read_text(','.write_text('),CODE.replace('utf-8','utf-16'),
             CODE.replace('Path(__file__)','Path(__file__).absolute()'),
             CODE+'\nprint(__file__)\n',CODE+'\nPath = something\n',
             CODE+'\ngetattr(Path,"read_text")\n',CODE.replace('from pathlib import Path','from other import Path')]
        for code in bad:
            with self.subTest(code=code):
                (self.package/'main.py').write_text(code,encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'shared_tool.bundled_data|dynamic implementation'):self.request()

    def test_module_data_dependency_interface_changes_never_keep_request_key(self):
        original=self.request();old=fingerprint(original)
        (self.package/'helper.py').write_text('VALUE=1')
        self.assertNotEqual(old,fingerprint(self.request()))
        (self.package/'helper.py').unlink()
        (self.package/'data/rules.json').write_text('{"max":51}')
        self.d['bundled_data'][0]['sha256']=file_digest(self.package/'data/rules.json')
        self.assertNotEqual(old,fingerprint(self.request()))
        (self.package/'data/rules.json').write_text('{"max":50}');self.d['bundled_data'][0]['sha256']=file_digest(self.package/'data/rules.json')
        for field in ('requirements','constraints'):
            changed=copy.deepcopy(original);changed[field]=['changed']
            self.assertNotEqual(old,fingerprint(changed))
        changed=copy.deepcopy(self.d);changed['interface']['entrypoint'].append('--different')
        try:result=self.request(changed)
        except ValueError:return
        self.assertNotEqual(old,fingerprint(result))

    def test_undeclared_and_unused_resources_rejected(self):
        d=copy.deepcopy(self.d);d['bundled_data'][0]['path']='data/other.json'
        (self.package/'data/other.json').write_text('{"max":50}')
        with self.assertRaisesRegex(ValueError,'expected declared path'):self.request(d)
        (self.package/'main.py').write_text('print("no data read")')
        with self.assertRaisesRegex(ValueError,'expected literal reads'):self.request()

    def test_unsafe_or_corrupt_declarations_rejected(self):
        for key,value in [('path','../rules.json'),('path','/etc/data.json'),('path','data/code.py'),('sha256','wrong')]:
            d=copy.deepcopy(self.d);d['bundled_data'][0][key]=value
            with self.assertRaises(ValueError):st.validate_declaration(d)

    def test_skill_prose_does_not_enter_tool_identity(self):
        (self.package/'SKILL.md').write_text('operator A');a=self.request()
        (self.package/'SKILL.md').write_text('operator B');self.assertEqual(a,self.request())

    def test_registered_v3_resolver_reports_changes_and_preserves_old_version(self):
        from tests.pipeline.test_runtime_build import plan
        from tests.pipeline.test_shared_tool import SharedToolTests
        from creation_pipeline.records import write_json
        request=self.request();p=st.environment_plan(plan());p['resource_assessment']['source_path']='package/main.py'
        p['source_files']=['package/main.py','package/data/rules.json']
        pin={'repo_digest':'python@sha256:'+'1'*64}
        record={'abi':bd.ABI,'request':request,'request_key':fingerprint(request),'plan':p,'base_image':pin,
                'recipe_key':fingerprint({'plan':p,'base_image':pin}),'environment':{'status':'not_applicable'},
                'daemon_id':'daemon','image_id':'sha256:'+'a'*64}
        record['artifact_id']=fingerprint(record);st.validate_record(record)
        root=self.root/'registry';path=root/(record['request_key']+'-'+record['artifact_id']+'.json')
        write_json(path,record);before=file_digest(path)
        probe=SharedToolTests.probe(self,record)
        self.assertEqual(st.resolve(request,{'engine_id':'daemon'},probe,root)[1]['status'],'hit')
        changes=[]
        (self.package/'main.py').write_text(CODE+'\n# changed module\n');changes.append(self.request())
        (self.package/'main.py').write_text(CODE)
        (self.package/'data/rules.json').write_text('{"max":51}');self.d['bundled_data'][0]['sha256']=file_digest(self.package/'data/rules.json');changes.append(self.request())
        for field,value in [('requirements',{'imports':{'rdkit':'2024.9.6'},'executables':[]}),
                            ('interface',dict(self.d['interface'],entrypoint=['python3','/opt/skill/package/main.py']))]:
            changed=copy.deepcopy(request);changed['declaration'][field]=value;changes.append(changed)
        for changed in changes:
            found,observation=st.resolve(changed,{'engine_id':'daemon'},probe,root)
            self.assertIsNone(found);self.assertEqual(observation['status'],'miss')
            self.assertTrue(observation['other_versions'][0]['mismatched_objects'])
        self.assertEqual(file_digest(path),before)
        self.assertEqual(st.resolve(request,{'engine_id':'daemon'},probe,root)[1]['status'],'hit')
