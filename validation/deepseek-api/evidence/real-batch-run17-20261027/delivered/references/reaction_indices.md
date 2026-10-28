# RECAP reaction indices

`onlyUseReactions` accepts zero-based indices into `rdkit.Chem.Recap.reactions`, matching `reactionDefs` in the source module.

| Index | Description |
| ---: | --- |
| 0 | urea |
| 1 | amide |
| 2 | ester |
| 3 | amines |
| 4 | cyclic amines |
| 5 | ether |
| 6 | olefin |
| 7 | aromatic nitrogen - aliphatic carbon |
| 8 | lactam nitrogen - aliphatic carbon |
| 9 | aromatic carbon - aromatic carbon |
| 10 | aromatic nitrogen - aromatic carbon |
| 11 | sulphonamide |

Index 10 is marked in the source as not part of the standard RECAP set. To inspect the exact reaction SMARTS, open `rdkit.Chem.Recap.reactionDefs` in Python.
