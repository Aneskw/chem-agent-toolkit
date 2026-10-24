"""Stable package/project locations independent of module depth or process cwd."""
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
ROOT = PACKAGE_ROOT.parent
PROMPTS = PACKAGE_ROOT / "generation" / "prompts"
