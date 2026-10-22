"""Execute delivered Python examples; the optional marker proves completion only."""
import re
import ast
import argparse
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("package")
parser.add_argument("--smiles", help="Replace the explicitly requested sample input variable")
parser.add_argument("--expect-rejection", action="store_true")
parser.add_argument("--completion-marker", action="store_true")
args = parser.parse_args()
# Match `python -c` imports when a check declares an upstream source cwd.
sys.path.insert(0, str(Path.cwd()))
text = (Path(args.package) / "SKILL.md").read_text(encoding="utf-8")
blocks = re.findall(r"```python\s*\n(.*?)```", text, re.S)
if not blocks:
    raise SystemExit("No Python usage example found")
namespace = {"__name__": "__main__"}
for index, block in enumerate(blocks):
    tree = ast.parse(block)
    if args.smiles is not None:
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "smiles" for t in node.targets):
                node.value = ast.Constant(value=args.smiles)
                found = True
        if not found:
            raise SystemExit("The configured test requires a smiles input variable in the example")
        ast.fix_missing_locations(tree)
    # A documented standalone example must not inherit this verifier's flags/paths.
    prior_argv = sys.argv
    sys.argv = [f"skill-example-{index + 1}.py"]
    try:
        exec(compile(tree, f"SKILL.md:python-example-{index + 1}", "exec"), namespace)
    except ValueError:
        if not args.expect_rejection:
            raise
        print("input-rejected")
        raise SystemExit(0)
    finally:
        sys.argv = prior_argv
if args.expect_rejection:
    raise SystemExit("Expected input rejection, but the example completed")
if args.completion_marker:
    print("skill-example-completed")
