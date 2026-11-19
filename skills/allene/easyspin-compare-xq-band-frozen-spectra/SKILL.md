---
name: easyspin-compare-xq-band-frozen-spectra
description: Simulate field-swept frozen-solution cw EPR spectra with EasySpin and compare a supplied spin model with measured X- and Q-band spectra.
---

# Frozen-solution EPR simulation with EasySpin

Use `pepper` for the solid-state limit of cw EPR, including randomly oriented frozen solutions. Start with a supplied spin Hamiltonian and experimental settings. This workflow calculates spectra and supports visual comparison; parameter fitting and preparation of measured data are separate tasks.

## Setup

Use **EasySpin 6.0.15** with licensed **MATLAB R2021b or later** on Windows, Linux or Mac. No additional MATLAB toolboxes are required; Octave is unsupported.

Download the distribution from the [official download page](https://easyspin.org/easyspin/download.html). Unpack it, remove older EasySpin folders from the MATLAB path, and add only `easyspin-6.0.15/easyspin` using Home > Set Path. Run `easyspin info` to confirm the active version. If compiled components fail to load, follow the compiler instructions in the [installation guide](https://easyspin.org/documentation/installation.html).

## Prepare the model and experiments

| Input | Meaning |
| --- | --- |
| `Sys.S` | Electron spin quantum number; explicitly set it for the supplied model. |
| `Sys.g` | Dimensionless g-tensor principal values; three entries for a rhombic tensor. |
| `Sys.lwpp` | Gaussian peak-to-peak linewidth in mT for a scalar; `[Gaussian Lorentzian]` for both contributions. |
| `Sys.Nucs`, `Sys.A` | Optional coupled nuclei and hyperfine principal values in MHz. |
| `Exp.mwFreq` | Actual spectrometer frequency in GHz, separately for each band. |
| `Exp.Range` | Lower and upper field limits `[lo hi]` in mT. |
| `Exp.Harmonic` | 1 for first harmonic (default); 0 for direct absorption. Match the measured detection convention. |
| `Exp.Temperature` | Temperature in kelvin for Boltzmann population weighting. If omitted, all transition population differences are taken as 1. |

Use a fresh experiment structure for each band. If both `CenterSweep` and `Range` exist, `CenterSweep` takes precedence. For disordered frozen solutions, leave crystal orientation and symmetry settings unset.

## Calculate both bands

All numeric settings below are illustrative. Replace them with the supplied model, actual frequencies, temperatures and sweep limits. Keep the same spin Hamiltonian when assessing one model across both bands; change broadening assumptions only when justified.

```matlab
Sys = struct('S',1/2,'g',[1.95 1.96 1.97],'lwpp',0.5);

ExpX = struct('mwFreq',9.5,'Range',[330 365], ...
              'Harmonic',1,'Temperature',100,'nPoints',2048);
ExpQ = struct('mwFreq',34.0,'Range',[1200 1280], ...
              'Harmonic',1,'Temperature',100,'nPoints',2048);

[BX,specX] = pepper(Sys,ExpX);
[BQ,specQ] = pepper(Sys,ExpQ);

figure;
subplot(1,2,1); plot(BX,specX);
xlabel('Field (mT)'); ylabel('Simulated intensity'); title('X band');
subplot(1,2,2); plot(BQ,specQ);
xlabel('Field (mT)'); ylabel('Simulated intensity'); title('Q band');

save('epr-simulation.mat','Sys','ExpX','ExpQ', ...
     'BX','specX','BQ','specQ');
```

`BX` and `BQ` are field vectors in mT; `specX` and `specQ` are the corresponding simulated intensity arrays. Requesting outputs suppresses EasySpin's automatic plot. The example saves the model, settings and raw spectra in `epr-simulation.mat` in MATLAB's current directory.

If hyperfine coupling is part of the model, add its `Nucs` and `A` fields before both calls. For tensors with different principal axes, use the documented frame fields; `AFrame` angles are in radians. Consult the [spin-system examples](https://easyspin.org/documentation/userguide_pepper.html) for that conditional case.

## Overlay prepared measurements

Optional input: a user-prepared `measured-epr.mat` file in the current directory containing `BXobs,yXobs,BQobs,yQobs`. Each field/intensity pair must have matching lengths, finite real values, and increasing field values in mT. Supply baseline-prepared intensities with the same detection convention as the simulation. The measured grids may differ from the simulation grids.

```matlab
obs = load('measured-epr.mat','BXobs','yXobs','BQobs','yQobs');
assert(max(abs(specX))>0 && max(abs(specQ))>0, ...
       'Inspect zero simulated spectra before normalization.');
assert(max(abs(obs.yXobs))>0 && max(abs(obs.yQobs))>0, ...
       'Measured spectra must have nonzero signal for this overlay.');

figure;
subplot(1,2,1);
plot(obs.BXobs,obs.yXobs/max(abs(obs.yXobs)),'k', ...
     BX,specX/max(abs(specX)),'r');
xlabel('Field (mT)'); ylabel('Normalized intensity'); title('X band');
legend('Measured','Simulated');
subplot(1,2,2);
plot(obs.BQobs,obs.yQobs/max(abs(obs.yQobs)),'k', ...
     BQ,specQ/max(abs(specQ)),'r');
xlabel('Field (mT)'); ylabel('Normalized intensity'); title('Q band');
legend('Measured','Simulated');
```

This display divides each spectrum by its own maximum absolute intensity, preserves its sign and within-spectrum relative intensities, and leaves raw arrays unchanged. It discards absolute amplitude comparisons between bands. It performs no field alignment, interpolation or fit.

## Interpret and troubleshoot

Compare resonance positions, widths and relative component intensities at both frequencies. Agreement supports compatibility with the supplied model; it does not uniquely identify an electronic structure. Persistent intensity discrepancies can indicate inadequate model assumptions even when line positions agree.

For coarse or bumpy spectra, increase the orientation grid and capture both updated results:

```matlab
Opt = struct('GridSize',91);
[BX,specX] = pepper(Sys,ExpX,Opt);
[BQ,specQ] = pepper(Sys,ExpQ,Opt);
```

Repeat the plot or measured-data overlay above using these updated arrays. Inspect grid convergence before attributing numerical texture to the sample, then save the updated arrays and options, replacing the earlier simulation file:

```matlab
save('epr-simulation.mat','Sys','ExpX','ExpQ','Opt', ...
     'BX','specX','BQ','specQ');
```

Keep the default transition-intensity calculation enabled: `Opt.Intensity='off'` gives physically incorrect relative intensities.

A zero or clipped trace requires checking the field window, frequency, spin model and detection settings before normalization or interpretation. A missing signal is not evidence that the sample lacks spins. For settings beyond this path, use the [pepper reference](https://easyspin.org/documentation/pepper.html) and [cw experimental parameters](https://easyspin.org/documentation/cwepr_exp.html).
