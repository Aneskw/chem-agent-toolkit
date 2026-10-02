---
name: chem-reaction-stage-audit
description: Check organic reaction mechanisms and product predictions against the reagents, proton sources, and workup present at each reaction stage. Use when a proposed intermediate or product may belong to the wrong stage or be incompatible with the reaction environment.
---

# Reaction-stage and environment audit

When predicting or reviewing an organic reaction, reconstruct the sequence of conditions and keep it active throughout the reasoning. Distinguish the reaction mixture before quench, each explicitly described change of conditions, the workup, and the reported final product. Evaluate a proposed species in the stage where it is claimed to exist. A species that is reasonable after workup may be wrong as an intermediate in the reaction mixture.

## Maintain the reaction environment

Treat the current mixture as a changing state, not a one-time check at the end. Update it whenever a reagent is added, a reagent is consumed, the solvent or temperature changes, or a quench or workup begins. At every proposed mechanistic step, candidate branch, and final product, check the species against the *current* state before proceeding. Carry forward what remains after competing acid-base reactions and earlier steps; a later reagent cannot react with a species that has already been quenched or consumed.

When a mechanism is long, retain a compact stage record: current stage and conditions, species present, reagents consumed, plausible proton donors/acceptors, and unresolved assumptions. Revisit that record after each transition so an apparently reasonable local step does not contradict the overall sequence.

## Decision procedure

1. Extract the starting materials, reagent equivalents if known, solvent, temperature, order of addition, atmosphere, and any quench or workup. Mark missing conditions as unknown rather than supplying them as facts.
2. At each stage, identify plausible proton donors and acceptors, nucleophiles and electrophiles, and reagents that may consume one another. Consider acid-base competition before assigning the intended bond-forming step. Use relative acidity/basicity and stoichiometry where they matter; do not turn a contextual tendency into a universal prohibition.
3. Check each proposed intermediate against the conditions *at that point*. Ask whether its charge, protonation state, and coexisting reagents are plausible; whether it would be consumed promptly; whether its precursor survived earlier stages; and whether it requires a reagent introduced only later. A transient species need not be an isolable or major species.
4. Apply each stated quench or workup only when that stage is reached. Account for protonation, deprotonation, hydrolysis, salt formation, or other changes supported by the actual conditions. Do not silently move a workup transformation into the mechanism before quench.
5. For the final prediction, state whether the structure represents the pre-workup mixture or a post-workup product. If a dataset or user asks for an isolated product but omits the workup, a conventional neutralized product may be proposed **as an explicit inference**, alongside the unresolved pre-workup form when that distinction affects the answer.

When a candidate fails this audit, identify the first incompatible stage and its competing transformation. Revise the mechanism or product if the conditions support a specific alternative; otherwise explain what condition or reagent information is needed. Preserve viable competing outcomes when the evidence does not rank them.

## Grignard example

For addition of `RMgX` to a carbonyl in anhydrous ether, the immediate addition product is a magnesium alkoxide. An alcohol belongs to the subsequent protonating workup, if one occurs. If water, an alcohol, a carboxylic acid, or another sufficiently acidic proton donor is present when `RMgX` is introduced, assess proton transfer and how much Grignard reagent remains before predicting carbonyl addition. Do not show an active Grignard reagent and its incompatible proton donor as a stable, unreacting pair. Do not reject an alcohol as the *final* product merely because the bond-forming step required anhydrous conditions.

## Reporting

Give the predicted intermediate or product, the stage it belongs to, the condition that supports it, and any consequential uncertainty. Separate stated conditions from inferred workup. Never claim that a negative ion is impossible solely because a solvent is protic, or that a product is experimentally confirmed solely because its proposed mechanism passes this audit.
