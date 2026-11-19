---
name: copasi-simulate-competing-reaction-selectivity
description: Use COPASI to simulate competing reaction pathways from a supplied parameterized .cps model and export concentration trajectories for product-selectivity comparisons.
---

# Competing-reaction selectivity with COPASI

Run a deterministic time course, retain the competing products in one report, and compare their evolution at a declared time. The input must already contain the reaction network, rate laws, parameters, initial conditions and units. Deriving kinetics from energy barriers is a separate preparation step.

## Tool and inputs

Use **COPASI 4.48 Build 311**, available from the [official release](https://github.com/copasi/COPASI/releases/tag/Build-311). Follow the [platform installation instructions](https://copasi.org/Support/Installation/). CopasiUI provides interactive configuration; CopasiSE runs saved tasks in batch mode. On Windows, launch CopasiUI from the Start menu and resolve CopasiSE.exe from the installed distribution. In shell examples below, `CopasiSE` denotes that executable on PATH; otherwise substitute its full path.

Prepare a working directory containing a copy of the supplied model, called `model.cps` below.

| Input | Required information |
| --- | --- |
| Model | Parameterized COPASI .cps file, including compartments and initial species values |
| Product mapping | Actual species names for the two competing products; called `P_CC` and `P_CN` in this example |
| Simulation request | Duration and sampling interval or count, expressed in the model's time units |
| Comparison | Evaluation time and product concentration units; direct concentration ratios require a common concentration basis, such as the same compartment |

Keep the original input available. Configure and save the working model before running it; reopen that saved configuration for independent repetitions.

## Configure the trajectory and report

1. Open `model.cps` in CopasiUI. Inspect **Model → Biochemical → Reactions**; double-click a reaction to inspect its rate law and local or global parameter mappings. Preserve the supplied kinetics. In a single compartment, kinetics describe concentration change; across compartments they describe substance change. Do not assume every rate constant uses the same units.
2. Open **Tasks → Time Course** and select deterministic **LSODA** integration. Set duration and interval count for the intended horizon. For an illustrative model with time in seconds and initial time zero, duration `3600` and `360` intervals request output every 10 seconds; these are example choices. The simulation actually starts at the model's initial time, which need not be zero. Leave delayed **Start Output Time** disabled to retain the early competition.
3. Inspect the solver settings in the loaded model. The documented LSODA defaults are relative tolerance `1e-6`, absolute tolerance `1e-12` (concentration for chemical species), and **Max Internal Steps** `10000` between output times. A loaded model may override them. Record the settings used; output spacing and internal integration steps serve different purposes.
4. Under **Output Specifications → Reports**, double-click an empty row to create a report. Choose task **Time-Course**, keep table layout, tab separator and **Title Row**, and use **Item** to add time followed by the transient **Concentration** of `P_CC` and `P_CN`. Substitute the actual product names. In Expert Mode, time is under the model branch and each concentration is under its species. Use the arrows to put time first. Report precision defaults to six significant digits; increase it when small concentrations or ratios need more retained digits.
5. Return to **Time Course → Report**, select this report and attach an output filename. Leave **Append** unchecked for a separate trajectory: an existing destination is overwritten. A report definition alone does not write a file. **Save Result in Memory** is optional for the GUI result dialog; the attached report retains the trajectory even when that option is off.

The [report documentation](https://copasi.org/Support/User_Manual/Output/Manual_Definition/Reports/) explains object selection if the desired transient concentration is difficult to locate.

## Run the configured model

For interactive execution, click **Run** in Time Course and inspect the attached report afterward. The **Result** child under Time Course is also available when results were retained in memory; it can display concentrations or particle numbers.

For batch execution, mark Time Course as executable in the task configuration, ensure unrelated tasks are not scheduled, and save `model.cps`. From the working directory, invoke:

```sh
CopasiSE model.cps --report-file trajectory.tsv --verbose > run.log 2>&1
```

On PowerShell, a quoted executable path needs the call operator, for example `& "C:\path\to\CopasiSE.exe" model.cps --report-file trajectory.tsv --verbose > run.log 2>&1`; replace that illustrative path with the installed executable.

This runs the saved executable task and overrides its report destination. Read `run.log` to verify the intended Time Course task, model and report destination, and inspect integration diagnostics before interpreting `trajectory.tsv`. `--verbose` adds execution details; it does not validate the chemistry or choose a task. The relative paths above refer to the working directory. The command does not request a saved post-run model. See the [official CLI reference](https://copasi.org/Support/User_Manual/Model_Creation/Commandline_Version_and_Commandline_Options/) for executable and report options. Use a new report/log pair for each independent run.

For a second supplied scenario, configure its model with the same product mapping, time horizon and output schedule, save it separately, and run with a distinct report filename.

## Interpret the output

Open `trajectory.tsv` as a tab-separated table. Its title row identifies the selected model objects; subsequent rows contain time and the two transient concentrations in the configured order. Use model units rather than inferring units from the filename.

Let `c_CC(t)` and `c_CN(t)` be the reported concentrations of `P_CC` and `P_CN` at time `t`. On a common concentration basis, calculate:

`R(t) = c_CC(t) / c_CN(t)`

A zero denominator makes the ratio undefined; report both concentrations instead. Inspect early-time trajectories as well as the chosen endpoint. A ratio at the requested end time is an endpoint prediction, not evidence that the system reached steady state. These are predictions conditional on the supplied model and initial conditions, not measured yields.

A missing or empty report is not evidence of zero product: check task scheduling, report attachment, output destination and delayed output settings. If COPASI reports an integration failure, retain the diagnostic and treat the trajectory as incomplete; do not interpret its last available row as the requested endpoint. Compare scenarios only at matching times and with compatible concentration units.
