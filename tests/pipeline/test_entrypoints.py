"""Check relocated helpers from a caller directory outside the repository."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from creation_pipeline.paths import PACKAGE_ROOT


class EntrypointTests(unittest.TestCase):
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
