# Refine a supplied transition-state guess

Use this mode only with a prepared TS guess and a declared correspondence to reactants/products. Use the same environment, per-species directory and input layout as minimum mode. Replace the route in `optfreq.gjf` with:

```text
#p M062X/6-31G(d) Opt=(TS,CalcFC) Freq SCRF=(SMD,Solvent=Water) Temperature=298.0 Pressure=1.0 Units=Ang
```

This is an intentional route-section excerpt. Retain the resource/checkpoint directives and blank-separated title and molecule section from the main template, replacing the latter with the supplied TS geometry, charge and multiplicity. `TS` requests a saddle optimization; `CalcFC` computes an initial Hessian at this method. A minimum optimization can relax a TS guess into a stable structure, losing the intended saddle.

Run `g16 < optfreq.gjf > optfreq.log`. Require completed optimization, normal termination and exactly one imaginary projected vibrational mode for a first-order saddle. Inspect the displacement vectors under that mode to check that the atomic motion matches the proposed reaction coordinate. Count the projected `Frequencies --` modes, not translations/rotations in the initial diagnostic. Zero imaginary modes describes a minimum; multiple imaginary modes do not characterize the intended first-order saddle. A wrong mode or failed saddle search needs a revised supplied guess or a separately justified optimization strategy before proceeding. Do not disable curvature checks merely to force completion.

A chemically plausible mode supports assignment but does not prove which minima are connected. Carry supplied connectivity evidence into the ledger; otherwise mark connectivity unverified. Establishing connectivity, for example through a separately planned [Gaussian IRC calculation](https://gaussian.com/irc/) and endpoint characterization, is outside this skill's promised calculation modes.

For an accepted saddle, run the main skill's larger-basis SMD-water single point using its `optfreq.chk`, and combine that energy with its own lower-level frequency correction. Gaussian thermochemistry excludes the imaginary mode from the vibrational partition function; do not replace it with its absolute frequency. Form the barrier against the declared separated-species or complex reference using the common accounting instructions. Keep a connectivity-unverified saddle energy distinct from an assigned reaction barrier.