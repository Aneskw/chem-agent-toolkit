"""v4 adds only literal sibling JSON reads; prior profiles stay strict."""
import ast
import copy
import tempfile
import unittest
from pathlib import Path
from creation_pipeline.contracts import fingerprint
from creation_pipeline.records import file_digest,write_json
from creation_pipeline.runtime import shared_tool as st,bundled_data as bd
from tests.pipeline.test_shared_tool import declaration
from tests.pipeline import test_shared_tool as fixture
from tests.pipeline.test_runtime_build import plan

CODE='from pathlib import Path\nimport json\nprint(json.loads(Path(__file__).with_name("rules.json").read_text(encoding="utf-8")))\n'


class SiblingDataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.package=self.root/'package';self.package.mkdir();(self.root/'sources').mkdir()
        (self.package/'main.py').write_text(CODE);(self.package/'rules.json').write_text('{"max":50}')
        self.d=declaration();self.d.update(policy=bd.SIBLING_POLICY,bundled_data=[
            {'module':'main.py','path':'rules.json','sha256':file_digest(self.package/'rules.json')}])

    def request(self,d=None):
        return st.describe(self.root,{'entry':'main.py','entry_sha256':file_digest(self.package/'main.py'),'association':'identical'},d or self.d)

    def test_v4_and_prior_profiles_refuse_the_new_form(self):
        self.assertEqual(self.request()['abi'],bd.SIBLING_ABI)
        self.assertEqual(len(bd.reads(ast.parse(CODE),'main.py',self.d['bundled_data'],sibling=True)),1)
        old=copy.deepcopy(self.d);old['policy']=bd.POLICY
        with self.assertRaises(ValueError):self.request(old)
        with self.assertRaises(ValueError):self.request(declaration())

    def test_only_one_literal_sibling_name_and_utf8_read_is_supported(self):
        bad=[CODE.replace('"rules.json"','name'),CODE.replace('"rules.json"','"../rules.json"'),
             CODE.replace('"rules.json"','"data/rules.json"'),CODE.replace('"rules.json"','"/rules.json"'),
             CODE.replace('utf-8','utf-16'),CODE.replace('.read_text(','.write_text('),
             CODE.replace('Path(__file__)','Path(__file__).resolve()'),CODE.replace('.with_name(','.with_suffix('),
             CODE+'\nprint(__file__)\n',CODE.replace('Path(__file__).with_name("rules.json")','Path(__file__) / "rules.json"')]
        for code in bad:
            with self.subTest(code=code):
                (self.package/'main.py').write_text(code)
                with self.assertRaisesRegex(ValueError,'bundled_data|dynamic implementation'):self.request()

    def test_alias_mutation_reflection_and_binding_unknowns_are_named(self):
        for head in ('Path=other\n','def f(Path): pass\n','Path.with_name=other\n',
                     'try:\n    pass\nexcept Exception as Path:\n    pass\n','getattr(Path,"with_name")\n',
                     'import sys\nsys.modules["pathlib"]=other\n','async def Path(): pass\n'):
            (self.package/'main.py').write_text(head+CODE)
            with self.assertRaisesRegex(ValueError,'path binding'):self.request()

    def test_file_identity_cannot_be_import_rebound_in_either_json_profile(self):
        for policy,code in ((bd.SIBLING_POLICY,CODE),(bd.POLICY,CODE.replace('Path(__file__).with_name("rules.json")',
                                                                                 '(Path(__file__).resolve().parent / "rules.json")'))):
            d=copy.deepcopy(self.d);d['policy']=policy
            for head in ('import os as __file__\n','from os import fspath as __file__\n'):
                (self.package/'main.py').write_text(head+code)
                with self.assertRaisesRegex(ValueError,'__file__ import binding'):self.request(d)

    def test_resource_must_be_declared_used_present_and_byte_identical(self):
        for field,value in [('path','missing.json'),('module','missing.py'),('sha256','0'*64)]:
            d=copy.deepcopy(self.d);d['bundled_data'][0][field]=value
            with self.assertRaisesRegex(ValueError,'expected file|expected sha256='):self.request(d)
        (self.package/'main.py').write_text('print(1)')
        with self.assertRaisesRegex(ValueError,'expected literal reads'):self.request()

    def test_registered_version_refuses_each_identity_change_and_is_unchanged(self):
        request=self.request();p=st.environment_plan(plan());p['resource_assessment']['source_path']='package/main.py'
        p['source_files']=['package/main.py','package/rules.json'];pin={'repo_digest':'python@sha256:'+'1'*64}
        record={'abi':bd.SIBLING_ABI,'request':request,'request_key':fingerprint(request),'plan':p,'base_image':pin,
                'recipe_key':fingerprint({'plan':p,'base_image':pin}),'environment':{'status':'not_applicable'},
                'daemon_id':'daemon','image_id':'sha256:'+'a'*64}
        record['artifact_id']=fingerprint(record);st.validate_record(record)
        root=self.root/'registry';path=root/(record['request_key']+'-'+record['artifact_id']+'.json');write_json(path,record)
        before=file_digest(path);probe=fixture.SharedToolTests.probe(self,record);host={'engine_id':'daemon'}
        reference={k:record[k] for k in ('request_key','artifact_id')}
        self.assertEqual(st.select(request,reference,host,probe,root)[1]['status'],'hit')
        changes=[]
        (self.package/'main.py').write_text(CODE+'\n# module identity changed\n');changes.append(self.request())
        (self.package/'main.py').write_text(CODE)
        (self.package/'rules.json').write_text('{"max":51}');self.d['bundled_data'][0]['sha256']=file_digest(self.package/'rules.json');changes.append(self.request())
        for field,value in [('requirements',{'imports':{'rdkit':'2024.9.6'},'executables':[]}),
                            ('interface',dict(self.d['interface'],entrypoint=['python3','/opt/skill/package/main.py']))]:
            changed=copy.deepcopy(request);changed['declaration'][field]=value;changes.append(changed)
        for changed in changes:
            found,obs=st.select(changed,reference,host,probe,root)
            self.assertIsNone(found);self.assertEqual(obs['reason'],'selected_request_mismatch');self.assertTrue(obs['mismatches'])
            self.assertIsNone(st.resolve(changed,host,probe,root)[0])
        self.assertEqual(file_digest(path),before)
        self.assertEqual(st.select(request,reference,host,probe,root)[1]['status'],'hit')
        downgraded=copy.deepcopy(record);downgraded['abi']=bd.ABI
        with self.assertRaisesRegex(ValueError,'policy'):st.validate_record(downgraded)

    def test_skill_prose_is_excluded_from_identity(self):
        request=self.request();self.assertEqual(request['declaration']['policy'],bd.SIBLING_POLICY)
        (self.package/'SKILL.md').write_text('different operator prose')
        self.assertEqual(request,self.request())
