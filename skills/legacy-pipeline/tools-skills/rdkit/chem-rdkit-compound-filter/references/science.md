# Scientific choices

- PAINS filters flag substructures associated with frequent assay interference; they are alerts rather than experimental conclusions.
- Brenk filters flag structural motifs often considered undesirable in medicinal-chemistry triage.
- Morgan fingerprints encode circular atom environments. This skill defaults to radius 2 and 2048 bits.
- Tanimoto similarity is computed against every valid active reference. The maximum value determines whether a candidate meets the novelty threshold.
- The acceptance rule is strict: `maximum_similarity < threshold`.

References:

- Baell and Holloway, *J. Med. Chem.* 2010, DOI: 10.1021/jm901137j.
- Brenk et al., *ChemMedChem* 2008, DOI: 10.1002/cmdc.200700139.
- Rogers and Hahn, *J. Chem. Inf. Model.* 2010, DOI: 10.1021/ci100050t.
- RDKit FilterCatalog and Morgan fingerprint documentation.
