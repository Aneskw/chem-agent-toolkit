---
name: easyspin-simulate-solution-epr-hyperfine
description: Simulate isotropic solution cw EPR spectra with EasySpin in MATLAB and compare hyperfine patterns with measured spectra when a proposed doublet-radical spin system and acquisition settings are available.
---

# Solution EPR hyperfine simulation and comparison

Use `garlic` for isotropic solution spectra of S=1/2 radicals with small hyperfine couplings. Start with a proposed g value, coupled nuclei, coupling constants, linewidth estimate and experimental settings. A matching spectrum supports consistency with that model; it does not uniquely identify a radical.

## Environment

Use **EasySpin 6.0.15** with **MATLAB R2021b or later** on Windows, Linux or macOS. A basic MATLAB installation suffices; EasySpin does not run on Octave.

Obtain the packaged ZIP from the [official download page](https://easyspin.org/easyspin/download.html). Unpack it, remove older EasySpin directories from MATLAB's search path, and add only the distribution's `easyspin` subfolder through **Home > Set Path > Add Folder**, then save the path. Run `easyspin` to confirm the version. Precompiled native components ship with the distribution; if compilation is required, follow the [official installation instructions](https://easyspin.org/documentation/installation.html) for a compatible C compiler.

## Prepare the model

| Field | Meaning for a field-swept spectrum |
| --- | --- |
| `Sys.g` | Scalar isotropic g value, dimensionless. |
| `Sys.Nucs` | Comma-separated isotope labels, e.g. `'1H,1H'`. |
| `Sys.A` | Isotropic couplings in MHz, in the same order as the nuclei. |
| `Sys.n` | Optional counts of equivalent nuclei; omitted means one of each listed nucleus. |
| `Sys.lwpp` | Peak-to-peak widths in mT: `[Gaussian Lorentzian]`. A scalar specifies Gaussian broadening. |
| `Exp.mwFreq` | Measured microwave frequency in GHz. |
| `Exp.Range` | Lower and upper magnetic fields in mT. |
| `Exp.nPoints` | Number of simulation samples; default 1024. |
| `Exp.Harmonic` | 1 for first derivative (default), 0 for absorption, 2 for second derivative. |

Convert field-unit couplings with `unitconvert(A_mT,'mT->MHz',g)`; divide gauss values by 10 first. Supplying g avoids the conversion's default free-electron g value. Two inequivalent protons require two entries with different couplings; `Nucs='1H', n=2` instead represents two equivalent protons.

Use either `Sys.lwpp` or `Sys.lw`. The latter specifies absorption FWHM, also in mT, and is not interchangeable with derivative peak-to-peak width. If including modulation broadening, set `Exp.ModAmp` to the measured peak-to-peak modulation amplitude in mT.

## Simulate

This is an illustrative two-proton model. Replace the parameters with those appropriate to the intended spectrum, especially the acquisition frequency, range and linewidth.

```matlab
Sys = struct();
Sys.g = 2.0020;
Sys.Nucs = '1H,1H';
A_mT = [1.32 0.57];
Sys.A = unitconvert(A_mT,'mT->MHz',Sys.g);
Sys.lwpp = [0 0.05];       % Lorentzian peak-to-peak width, mT

Exp = struct();
Exp.mwFreq = 9.5;          % GHz
Exp.Range = [336 342];     % mT
Exp.nPoints = 2048;
Exp.Harmonic = 1;

[B,sim] = garlic(Sys,Exp);
plot(B,sim);
xlabel('Magnetic field (mT)');
ylabel('Simulated signal (arbitrary units)');
```

`B` and `sim` are the field-axis and spectral arrays retained in the MATLAB workspace. Requesting outputs suppresses automatic plotting; `garlic(Sys,Exp)` without outputs plots directly. Two resolved inequivalent proton splittings give a doublet-of-doublets pattern, although broadening and overlapping lines can obscure it.

## Compare with a measured spectrum

For Bruker BES3T input, keep the matching binary `sample.DSC` and `sample.DTA` files together. Use the actual file path below. `eprload` returns the axis, signal and acquisition parameters; its DSC/DTA axis retains the units specified in the parameter file. Confirm these units from the descriptor/acquisition record.

The following continuation assumes a **real, one-dimensional field sweep whose imported axis is confirmed to be in gauss**. If it is already in mT, use `Bexp=x(:)` instead. Select the intended trace and signal channel before using this block for multidimensional or complex data.

Before simulating, update `Exp.mwFreq`, harmonic and any modulation settings to the measured acquisition values. Do not infer microwave frequency from the nominal band name.

```matlab
[x,y,Params] = eprload('sample.DSC');
assert(isvector(x) && isvector(y) && isreal(y));
assert(numel(x)==numel(y));
Bexp = x(:)/10;              % ONLY for a confirmed gauss axis
y = y(:);
[Bexp,order] = sort(Bexp);
y = y(order);

Exp.Range = [min(Bexp) max(Bexp)];
Exp.nPoints = numel(Bexp);
[B,sim] = garlic(Sys,Exp);
% Align physical fields, including a nonuniform measured grid.
simOnData = interp1(B(:),sim(:),Bexp,'linear');
scaledSim = rescaledata(simOnData,y,'lsq');
residual = y-scaledSim;

plot(Bexp,y,Bexp,scaledSim);
xlabel('Magnetic field (mT)');
legend('Measured','Simulated, amplitude scaled');
figure;
plot(Bexp,residual);
xlabel('Magnetic field (mT)');
ylabel('Measured minus simulated');
```

This scales amplitude only, with a positive factor; it does not optimize g, hyperfine couplings, linewidths, baseline or field calibration. Align the physical axes explicitly: rescaling does not establish field correspondence. Retain `Params`, `Bexp`, `scaledSim` and `residual` alongside the model for interpretation.

## Interpret mismatches and failures

Compare line positions and spacings before linewidths and relative intensities. Check baseline and acquisition phase when the residual contains broad structure or the signal polarity disagrees; positive amplitude scaling cannot invert the spectrum. An unexplained component remains unresolved without independent evidence.

A zero or nearly empty trace can reflect a sweep range excluding the resonances; check the frequency, g value and field units before interpreting it as absence of a radical. If peaks are poorly sampled relative to linewidth, increase `Exp.nPoints`. Automatic ranging is available by omitting `Exp.Range`, but can fail and should not replace matching the measured range during comparison.

The default `garlic` method uses single-nucleus Breit-Rabi solutions and neglects cross-nuclear terms. Large couplings can cause it to refuse a calculation; important cross-nuclear effects require a matrix-diagonalization approach such as `pepper`. Slow-motion spectra also require a different model. Do not compensate for these regime failures by changing couplings solely to force agreement.

Consult the [garlic guide](https://easyspin.org/documentation/userguide_garlic.html) for model details and the [eprload reference](https://easyspin.org/documentation/eprload.html) for other import formats.
