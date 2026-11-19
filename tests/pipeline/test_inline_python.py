"""Host-parser observations are read-only, with Markdown source locations."""
import tempfile
import unittest
from pathlib import Path

from creation_pipeline.validation.checks import inline_python_diagnostics


class InlinePythonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        return path

    def test_valid_code_is_not_executed_or_imported(self):
        marker = self.root / "must-not-exist"
        path = self.write("SKILL.md", "```python\nimport nonexistent_target_tool\n"
                          f"open({str(marker)!r}, 'w').write('executed')\n"
                          "answer = supplied_input + 1\n```\n")
        before = path.read_bytes()
        result = inline_python_diagnostics(self.root)
        self.assertEqual(result["blocks_checked"], 1)
        self.assertEqual(result["issues"], [])
        self.assertTrue(result["python_version"])
        self.assertFalse(marker.exists())
        self.assertEqual(path.read_bytes(), before)

    def test_error_location_is_relative_to_original_markdown(self):
        self.write("references/usage.md", "# Usage\n\n```py\nanswer = 1\nbroken =\n```\n")
        result = inline_python_diagnostics(self.root)
        self.assertEqual(result["blocks_checked"], 1)
        issue, = result["issues"]
        self.assertEqual((issue["path"], issue["block_line"], issue["line"]),
                         ("references/usage.md", 4, 5))
        self.assertIn("syntax", issue["message"])

    def test_other_languages_and_nested_fence_examples_are_ignored(self):
        self.write("SKILL.md", "```sh\nif shell; then\n```\n"
                   "```pycon\n>>> import target_tool\n```\n"
                   "````text\n```python\nnot Python !!!\n```\n````\n")
        self.write("scripts/not-a-markdown.py", "not Python !!!")
        result = inline_python_diagnostics(self.root)
        self.assertEqual(result["blocks_checked"], 0)
        self.assertEqual(result["issues"], [])

    def test_indented_tilde_fences_crlf_and_longer_closing_fence(self):
        self.write("SKILL.md", "# Usage\r\n  ~~~python\r\n  if ready:\r\n"
                   "      answer = supplied_input\r\n  ~~~~~\r\n")
        result = inline_python_diagnostics(self.root)
        self.assertEqual(result["blocks_checked"], 1)
        self.assertEqual(result["issues"], [])

    def test_shorter_fence_does_not_close_a_longer_fence(self):
        self.write("SKILL.md", "````python\nanswer = '''\n```\n'''\n````\n")
        result = inline_python_diagnostics(self.root)
        self.assertEqual(result["blocks_checked"], 1)
        self.assertEqual(result["issues"], [])

    def test_eof_terminated_fence_keeps_original_error_line(self):
        self.write("SKILL.md", "# Usage\n```python\nanswer =\n")
        result = inline_python_diagnostics(self.root)
        self.assertEqual(result["blocks_checked"], 1)
        self.assertEqual(result["issues"][0]["line"], 3)
