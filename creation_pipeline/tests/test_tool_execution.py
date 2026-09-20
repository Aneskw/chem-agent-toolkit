import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validate_tool_execution import validate
import publish_run


class ToolExecutionTests(unittest.TestCase):
    def test_text_only_is_not_applicable(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'text-skill';path.mkdir()
            (path/'SKILL.md').write_text('# Procedure\n')
            self.assertEqual(validate(path)['status'],'not_applicable')

    def test_script_without_fixture_is_untested(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'tool-skill'/'scripts';path.mkdir(parents=True)
            (path/'tool.py').write_text('print(1)\n')
            self.assertEqual(validate(path.parent)['status'],'untested_no_fixture')

    def test_executable_output_and_failure_are_checked(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'tool-skill';(path/'scripts').mkdir(parents=True)
            (path/'execution').mkdir()
            (path/'scripts'/'tool.py').write_text('import json; print(json.dumps({"ok": True, "value": 3}))\n')
            fixture={'cases':[{'name':'value','script':'scripts/tool.py','expected_json_lines':[{'ok':True,'value':3}]}]}
            (path/'execution'/'fixtures.json').write_text(json.dumps(fixture))
            self.assertEqual(validate(path)['status'],'passed')
            fixture['cases'][0]['expected_json_lines'][0]['value']=4
            (path/'execution'/'fixtures.json').write_text(json.dumps(fixture))
            self.assertEqual(validate(path)['status'],'failed')

    def test_fixture_cannot_escape_scripts_directory(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'tool-skill';(path/'scripts').mkdir(parents=True)
            (path/'execution').mkdir()
            (path/'scripts'/'tool.py').write_text('print(1)\n')
            (path/'execution'/'fixtures.json').write_text(json.dumps({'cases':[{'name':'escape','script':'../other.py'}]}))
            self.assertEqual(validate(path)['status'],'failed')

    def test_publisher_records_execution_status(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);here=root/'creation_pipeline';run=here/'runs'/'sample'
            package=run/'drafts-v03'/'tool-skill'
            (package/'scripts').mkdir(parents=True)
            (package/'execution').mkdir()
            (package/'SKILL.md').write_text('# Tool skill\n')
            (package/'scripts'/'tool.py').write_text('import json; print(json.dumps({"ok": True}))\n')
            (package/'execution'/'fixtures.json').write_text(json.dumps({'cases':[
                {'name':'works','script':'scripts/tool.py','expected_json_lines':[{'ok':True}]}
            ]}))
            (here/'results').mkdir()
            (here/'results'/'sample.json').write_text(json.dumps({'status':'method_drafts_created','paper_id':'paper'}))
            with patch.object(publish_run,'HERE',here),patch.object(publish_run,'ROOT',root),patch('sys.argv',['publish_run.py','--run-id','sample']):
                self.assertEqual(publish_run.main(),0)
            manifest=json.loads((root/'skills'/'generated'/'sample'/'PUBLISHING.json').read_text())
            self.assertTrue(manifest['execution_validated'])
            self.assertEqual(manifest['execution_checks']['tool-skill'],'passed')


if __name__=='__main__':unittest.main()
