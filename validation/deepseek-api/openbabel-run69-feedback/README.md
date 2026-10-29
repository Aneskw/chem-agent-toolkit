# Historical Open Babel observations (run69)

This registered experimental feedback supplements the original source; it is not a current-run pass.
The original convert_molecule.py must remain byte-identical. All required conversion, file persistence,
input-preservation and unknown-format rejection checks still need fresh Docker execution.

The real successful conversion writes a non-JSON SDF file, while stdout is JSON metadata. Test these
channels separately: the runner acceptance assertion reads output_file when declared. A JSON predicate
on that file is wrong. For non-JSON files the pipeline now supports source-grounded kind=text_regex,
pattern=full-match regular expression, in addition to separate stdout checks and optional validators.
The saved SDF is a format fixture: the line containing V2000 IS the counts line. Its first three
columns are atom count, next three columns bond count. The next lines are atom records, then bonds.
Do not advance to the following atom line to parse counts. Preserve C-C-O topology, not only a banner.
The title/date is variable metadata; the required 3 heavy atoms and 2 bonds come from the CCO input.

The original wrapper's argparse required=True requires all four FLAGS to be supplied. It does not
check string nonemptiness. Passing --output "" was actually observed to exit 0 with ok:true; do not
invent a promise or rejection case that empty string is rejected. Document this limitation honestly.
Do not change the wrapper to create a new contract. The caller-required rejection is the unknown
output-format token nonexistent_format_xyz, which was observed to return exit 2 and ok:false.

observations.json retains original commands/status/outputs and hashes; observed-ethanol.sdf is actual
retained output from the failed historical batch. That batch stays failed (6/9 cases passed).
