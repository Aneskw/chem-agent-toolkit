---
name: easyspin-simulate-frozen-solution-epr
description: Simulate high-spin frozen-solution CW EPR spectra with EasySpin and compare line shapes against supplied measurements using anisotropic tensors, zero-field splitting and strain.
---

# Frozen-solution EPR simulation with EasySpin

Use `pepper` for the rigid-limit spectrum of an unoriented frozen solution. Start with a proposed spin model and acquisition conditions; a simulation predicts the spectrum of that model. Signal absence alone cannot establish an oxidation state.

## Setup and inputs

Use **EasySpin 6.0.15** with licensed **MATLAB R2021b or later** on Windows, Linux or macOS. Download the ZIP from the [official download page](https://easyspin.org/easyspin/download.html), unpack it, and add only `easyspin-6.0.15/easyspin` to MATLAB's search path through Home → Set Path. Remove older EasySpin folders from the path. Type `easyspin` to check the version. If precompiled components fail, follow the [official installation instructions](https://easyspin.org/documentation/installation.html) for a MATLAB-compatible C compiler.

Prepare a spin model and the actual experimental conditions. Optional measured data should be a baseline-corrected, headerless numeric CSV with two columns: ascending field in **mT**, then intensity. Preserve the original data separately; use matching detection harmonic and phase.

| Field | Meaning |
| --- | --- |
| `Sys.S`, `Sys.Nucs` | Electron spin and isotope identifiers, e.g. `3/2`, `'59Co'`. |
| `Sys.g`, `Sys.A` | Principal g values (unitless) and hyperfine values (MHz). |
| `Sys.D = [D E]` | Rhombic zero-field splitting parameters, both in MHz; convert cm⁻¹ by multiplying by 29979. The second entry is E, not E/D. |
| `Sys.gStrain` | Unitless Gaussian FWHM widths of g principal-value distributions. |
| `Exp.mwFreq`, `Exp.Range` | Microwave frequency in GHz and field limits `[lo hi]` in mT. |
| `Exp.Temperature` | Kelvin; enables equilibrium population weighting. |
| `Exp.Harmonic`, `Exp.ModAmp` | Detection harmonic (1 for first derivative); peak-to-peak modulation amplitude in mT. |

Use tensor-frame fields such as `AFrame` and `DFrame` when principal axes are misaligned; their angles use radians. See the [spin-system reference](https://easyspin.org/documentation/spinsystem.html) for conventions. Avoid retaining `Exp.CenterSweep` from another model: it overrides `Exp.Range`.

## Simulate and retain the result

This is an **illustrative Co(II)-like model**, with aligned tensor axes. Replace its parameters and acquisition settings with those justified for the sample. The chosen D, narrow strain, field range and numerical resolution are example choices, not fitted values.

```matlab
Sys = struct();
Sys.S = 3/2;
Sys.Nucs = '59Co';
Sys.g = [2.17 2.15 2.06];
Sys.A = [200 30 30];                 % MHz
D = 1.0 * 29979;                     % illustrative 1 cm^-1
Sys.D = [D 0.13*D];                  % [D E], MHz
Sys.gStrain = [0.02 0.02 0.02];       % Gaussian FWHM in g

Exp = struct();
Exp.mwFreq = 9.35;                   % GHz
Exp.Range = [10 1200];               % mT
Exp.Temperature = 10;                % K
Exp.Harmonic = 1;
Exp.ModAmp = 0.05;                   % peak-to-peak mT; replace from record
Exp.mwMode = 'perpendicular';
Exp.nPoints = 4096;

Opt = struct();
Opt.Method = 'matrix';
Opt.GridSize = [61 0];               % orientation grid, no interpolation

[B,spec] = pepper(Sys,Exp,Opt);
B = B(:);
spec = spec(:);
plot(B,spec);
xlabel('Magnetic field (mT)');
ylabel('Simulated intensity (arbitrary units)');
save('epr-simulation.mat','B','spec','Sys','Exp','Opt');
```

`B` and `spec` are corresponding vectors for this single-component calculation. The MAT file in the current directory retains the raw simulation and all settings; choose a different filename to preserve an existing result. `matrix` handles the high-spin Hamiltonian; the perturbative methods limited to S=1/2 are unsuitable here.

For a supplied measurement, compare shapes without treating amplitude as concentration:

```matlab
measured = readmatrix('measured-epr.csv');
Bexp = measured(:,1);
yexp = measured(:,2);
sSim = max(abs(spec));
sExp = max(abs(yexp));
if sSim == 0 || sExp == 0
    error('A zero trace cannot be normalized; inspect raw data and model.');
end
plot(Bexp,yexp/sExp,'k-',B,spec/sSim,'r-');
xlabel('Magnetic field (mT)');
ylabel('Independently normalized intensity');
legend('Measured','Simulated');
```

This overlay leaves field positions intact and discards relative amplitude. Compare only the common field interval. Match acquisition phase rather than arbitrarily reversing a trace.

## Interpret discrepancies

- Check field/frequency units, harmonic, temperature and microwave mode before changing spin parameters. With `ModAmp=0` or omitted, EasySpin differentiates the spectrum without explicit modulation broadening.
- For jagged features, increase `Opt.GridSize` and confirm that the line shape stabilizes; increase `nPoints` if the field sampling is too coarse.
- Model substantial anisotropic broadening with strain or physically appropriate anisotropic widths. Isotropic convolutional `lw`/`lwpp` can be inappropriate for large zero-field splitting. Built-in strain is a narrow-distribution approximation; for broad distributions, follow the [explicit-averaging guidance](https://easyspin.org/documentation/broadenings.html).
- A zero or very weak prediction warrants checking the sweep window, state populations, units and transition selection. For a complicated spin system, `Opt.Threshold=0` can diagnose omitted weak transitions; it includes all transitions and can increase cost.
- Agreement supports model consistency, not parameter uniqueness. If changing D leaves the predicted trace effectively unchanged, report the constrained range rather than a precise D. Independent normalization cannot support spin quantification; that requires a separately justified experimental calibration.

Use the [pepper reference](https://easyspin.org/documentation/pepper.html) for simulation controls and the [experimental-settings reference](https://easyspin.org/documentation/cwepr_exp.html) for acquisition-field definitions.
