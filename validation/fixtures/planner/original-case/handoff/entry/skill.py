import json
import sys
from rdkit import Chem
from rdkit.Chem import Recap

smiles = sys.argv[1] if len(sys.argv) == 2 else 'C1CC1Oc1ccccc1-c1ncc(OC)cc1'
if len(sys.argv) > 2 or not smiles.strip():
    raise SystemExit('Provide exactly one nonempty SMILES argument, or no arguments for the example.')
try:
    mol = Chem.MolFromSmiles(smiles)
except Exception as exc:
    raise SystemExit(f'SMILES parsing failed: {exc}')
if mol is None or mol.GetNumAtoms() == 0:
    raise SystemExit('SMILES did not produce a nonempty molecule.')
root = Recap.RecapDecompose(mol)
leaves = root.GetLeaves()
print(json.dumps(sorted(leaves)))
