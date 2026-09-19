# Why atom-map identity matters

Local reaction-template extraction compares mapped reactants and products to
locate changing atoms and bonds. A product map ID absent from reactants, or a
duplicate ID on one side, makes that comparison ambiguous. Reactant-only IDs
can represent leaving groups, so their absence from products is permitted.

This is an input-integrity rule for a computational workflow. It does not prove
that atom mapping is chemically correct, and it cannot validate a proposed
synthesis. Source: Wang et al., *JACS Au* 2021,
https://doi.org/10.1021/jacsau.1c00246; pinned LocalRetro code at
https://github.com/kaist-amsg/LocalRetro/tree/eba83e72efabeb854fec86c865e8743c295a8a1e.
