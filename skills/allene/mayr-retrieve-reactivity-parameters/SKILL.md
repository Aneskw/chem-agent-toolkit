---
name: mayr-retrieve-reactivity-parameters
description: Retrieve solvent-specific Mayr nucleophilicity and electrophilicity parameters, compound identities and cited sources from the official database for reactivity comparisons.
---

# Retrieve Mayr reactivity parameters

## Access and inputs

Open the official [Mayr database](https://www.cup.uni-muenchen.de/oc/mayr/reaktionsdatenbank/) in a browser with JavaScript enabled. Use the unnumbered production web interface inspected on 2026-11-10; the [introduction](https://www.cup.uni-muenchen.de/oc/mayr/DBintro.html) separately links Database 2.0 as beta. No local installation or account is needed. Record the access date because entries can change and this service exposes no immutable release identifier.

Start with a compound identity or compound class and the desired solvent, including mixture composition when relevant. For a pair comparison, obtain both identities. The result is a referenced parameter record for each matching entry, optionally followed by a semiquantitative rate estimate. This workflow does not determine missing parameters or predict catalytic yields.

## Search and inspect

1. Open **Advanced Search** and set the relevant controls:

   | Control | Use |
   |---|---|
   | Search In | Select Nucleophiles, Electrophiles or a narrower compound class. |
   | Solvent | Select the required solvent; use Search all solvents to discover available records. |
   | Keywords | Enter a name fragment, molecular formula or SMILES. Leave Exact search unchecked for the initial fragment search. A formula or keyword hit still requires identity verification. |
   | N/E-Parameter Range | Optional range filter, using N for nucleophiles or E for electrophiles. It is initially checked; uncheck it for an unrestricted identity lookup. |

2. Click **Search**. Alternatively, follow the compound-class links, such as [P-Nucleophiles](https://www.cup.uni-muenchen.de/oc/mayr/reaktionsdatenbank/fe/showclass/61). Read the results table, including solvent, parameters, classification and reference. Use pagination or Results per page to inspect all relevant matches; table headings support sorting.
3. Open the compound name. Verify the displayed structure, SMILES and formula, rather than relying on the name alone. Read the Information panel, especially the solvent, calibration comment and reference DOI.
4. Return one record per compound/solvent/reference combination. Preserve these fields together:

   | Fields | Content |
   |---|---|
   | Identity | Displayed name, SMILES, formula and detail-page URL |
   | Conditions | Solvent and any composition/conditions stated in the entry or cited source |
   | Parameters | N and sN together for a nucleophile; E for an electrophile |
   | Provenance | Calibration comment, quality stars if visible, full reference/DOI and access date |

If the search has no match, broaden the name fragment or remove class/range filters and browse the class. Report a missing requested-solvent record explicitly; another solvent's N and sN are separate data, not substitutes. A failed page load is an access failure, not evidence that parameters are absent. If quality stars appear only graphically, inspect the page image rather than inferring a rating from missing extracted text.

## Example: tributylphosphine in dichloromethane

Starting request: retrieve Bu3P parameters in CH2Cl2.

Select **Search In: P-Nucleophiles**, **Solvent: dichloromethane**, **Keywords: butyl**; leave Exact search unchecked, disable the parameter-range filter and click Search. Alternatively browse P-Nucleophiles and select **tri-n-butylphosphane**. Open its [detail page](https://www.cup.uni-muenchen.de/oc/mayr/reaktionsdatenbank/fe/details/202).

The inspected entry provides the following source data; re-read the current page when using it:

```text
name: tri-n-butylphosphane
SMILES: CCCCP(CCCC)CCCC
formula: C12H27P
solvent: dichloromethane
N: 15.49
sN: 0.69
comment: N and sN were determined with reference electrophiles.
reference: Chem. Eur. J. 2005, 11, 917-927
doi: 10.1002/chem.200400696
```

Attach the detail URL and your retrieval date to the delivered record. Keep calibration-specific values distinct: [Chem. Commun. 2022, 58, 3358-3361](https://doi.org/10.1039/D1CC06786A), p. 3360/Fig. 6, reports N = 19.11 and sN = 0.48 for Bu3P from a broader electrophile calibration. Those values are not the displayed database pair above; do not combine N from one calibration with sN from the other.

## Interpret a comparison

For an applicable electrophile/nucleophile pair, retrieve the electrophile's E with its reference and use the nucleophile's solvent-specific N and sN:

```text
log10(k at 20 degrees C) = sN * (N + E)
k_estimate = 10 ** (sN * (N + E))   # second-order k in M^-1 s^-1
```

Label this as an estimate and retain both parameter records alongside it. Comparing N alone omits differences in sN; use the full expression for a specified electrophile.

The database introduction limits this equation to reactions with at least one carbon reaction center and excludes bulky reagents, apart from documented exceptions such as tritylium entries. Steric effects are not included. It reports typical deviations below a factor of two for reference-electrophile reactions, but factors of 10-100 when both partners are outside the reference sets. Avoid unsupported long extrapolation beyond the calibration range; inspect the cited parameter paper when that range matters.

Stars describe calibration support: 5 = reference, 4 = quasi-reference, 3 = at least three reference partners, 2 = two reference partners, 1 = one reference partner with sN estimated. They are not uncertainty intervals. Cite each compound's parameter reference, not just the database homepage.
