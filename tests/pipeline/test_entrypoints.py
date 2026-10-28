"""Check relocated helpers from a caller directory outside the repository."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from creation_pipeline.paths import PACKAGE_ROOT


class EntrypointTests(unittest.TestCase):
    def test_review_required_is_not_cli_success(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from creation_pipeline.cli import main
        with patch('creation_pipeline.runtime.service.resume_build', return_value={'status': 'review_required'}), redirect_stdout(StringIO()):
            self.assertEqual(main(['runtime-resume', 'library', '--candidate', 'probe']), 1)

    def test_cli_has_one_runtime_path_and_no_host_execution_opt_in(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from creation_pipeline.cli import main
        for operation in ('build', 'resume'):
            output = StringIO()
            with redirect_stdout(output), self.assertRaises(SystemExit) as stopped:
                main([operation, '--help'])
            self.assertEqual(stopped.exception.code, 0)
            self.assertNotIn('--execute-generated-checks', output.getvalue())
            self.assertIn('--draft-only', output.getvalue())
            self.assertIn('--library-dir', output.getvalue())

    def test_helper_router_works_outside_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(PACKAGE_ROOT / "agent/tools.py"), "--help"],
                cwd=directory, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("supplement", result.stdout)
        self.assertIn("finish", result.stdout)

    def test_document_converter_works_outside_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "source.md", Path(directory) / "view.txt"
            source.write_text("# Original research\nUseful method", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(PACKAGE_ROOT / "resources/documents.py"), str(source), str(target)],
                cwd=directory, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Useful method", target.read_text(encoding="utf-8"))

    def test_example_runner_works_outside_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "skill"
            package.mkdir()
            (package / "SKILL.md").write_text("```python\nprint(2 + 3)\n```\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(PACKAGE_ROOT / "validation/example_runner.py"), str(package)],
                cwd=directory, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("5", result.stdout)
