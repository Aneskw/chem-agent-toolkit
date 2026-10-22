"""Point discovery at installed upstream source, without choosing capabilities."""
from pathlib import Path
import json
import rdkit

root = Path(__file__).resolve().parents[1]
source = Path(rdkit.__file__).resolve().parent / "Chem"
config = {"sources": [{"id": "brics", "path": str(source / "BRICS.py")},
                      {"id": "recap", "path": str(source / "Recap.py")}],
          "network": False, "limits": {"max_candidates": 5, "max_builds": 2}}
path = root / ".pipeline/example-configs/rdkit-sources.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
print(path)
