import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "preflight.py"
spec = importlib.util.spec_from_file_location("retroprime_preflight", MODULE)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class PreflightTests(unittest.TestCase):
    def test_missing_resources_are_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = preflight.inspect(Path(tmp), check_environment=False)
            self.assertFalse(result["ok"])
            self.assertEqual(set(result["missing_weights"]), {"p2s", "s2r"})
            self.assertFalse(result["execution_performed"])

    def test_complete_layout_and_readme_discrepancy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in (*preflight.SCRIPTS, *preflight.WEIGHTS.values()):
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("placeholder")
            (root / "run_example.sh").write_text("\n".join(preflight.WEIGHTS.values()))
            (root / "README.md").write_text("USPTO-50K_pos_pred_model.pt")
            products = root / "products.txt"
            products.write_text("CCO\nCCC\n")
            result = preflight.inspect(root, products, check_environment=False)
            self.assertTrue(result["ok"])
            self.assertEqual(result["product_count"], 2)
            self.assertTrue(any("README" in x for x in result["warnings"]))

    def test_blank_input_line_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            products = root / "products.txt"
            products.write_text("CCO\n\nCCC\n")
            result = preflight.inspect(root, products, check_environment=False)
            self.assertIn("input must contain one nonempty product SMILES per line", result["input_errors"])


if __name__ == "__main__":
    unittest.main()
