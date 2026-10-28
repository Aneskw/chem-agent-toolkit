# RECAP reaction indices

The indices below refer to RDKit `rdkit.Chem.Recap.reactionDefs` and are the
values accepted by `onlyUseReactions`.

- 0 urea: `[#7;+0;D2,D3:1]!@C(!@=O)!@[#7;+0;D2,D3:2]>>*[#7:1].[#7:2]*`
- 1 amide: `[C;!$(C([#7])[#7]):1](=!@[O:2])!@[#7;+0;!D1:3]>>*[C:1]=[O:2].*[#7:3]`
- 2 ester: `[C:1](=!@[O:2])!@[O;+0:3]>>*[C:1]=[O:2].[O:3]*`
- 3 amines: `[N;!D1;+0;!$(N-C=[#7,#8,#15,#16])](-!@[*:1])-!@[*:2]>>*[*:1].[*:2]*`
- 4 cyclic amines: `[#7;R;D3;+0:1]-!@[*:2]>>*[#7:1].[*:2]*`
- 5 ether: `[#6:1]-!@[O;+0]-!@[#6:2]>>[#6:1]*.*[#6:2]`
- 6 olefin: `[C:1]=!@[C:2]>>[C:1]*.*[C:2]`
- 7 aromatic nitrogen - aliphatic carbon: `[n;+0:1]-!@[C:2]>>[n:1]*.[C:2]*`
- 8 lactam nitrogen - aliphatic carbon: `[O:3]=[C:4]-@[N;+0:1]-!@[C:2]>>[O:3]=[C:4]-[N:1]*.[C:2]*`
- 9 aromatic carbon - aromatic carbon: `[c:1]-!@[c:2]>>[c:1]*.*[c:2]`
- 10 aromatic nitrogen - aromatic carbon (not part of the standard recap set): `[n;+0:1]-!@[c:2]>>[n:1]*.*[c:2]`
- 11 sulphonamide: `[#7;+0;D2,D3:1]-!@[S:2](=[O:3])=[O:4]>>[#7:1]*.*[S:2](=[O:3])=[O:4]`
