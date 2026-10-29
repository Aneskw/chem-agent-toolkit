# run71 historical SDF and terminal-newline observation

Source data from the failed run71 batch (20261029T183610-192d1953). It is not a current execution result or permission to omit checks. Reproduce all conversion, structure, format-rejection, environment and byte-preservation obligations in the next fresh batch.

run71 prepared after four planner attempts and built its bound Docker image. Eleven of twelve records passed. All six native checks passed in isolated containers. The only failed record was the planned normal direct-entry case: actual conversion exited zero, stdout reported ok:true and the retained SDF was valid ethanol. Its full-match text_regex ended immediately after the literal $$$$ delimiter, while the actual source fixture ends with a newline. The same historical pattern matches only if that final newline is removed; the runner correctly did not remove it.

observed-ethanol.sdf is the actual retained artifact, including its final newline. The V2000 counts line declares three atoms and two bonds; the atom records are C,C,O, with two single bonds in C-C-O topology. The SDF delimiter line ends with LF. Header date/time may vary in new executions. Generate source-grounded assertions that handle the actual line endings and preserve the numeric, atom, bond and terminator obligations. Do not trim output in the runner, remove structure assertions, reuse historical pass flags or modify the original entry/input to make a faulty predicate pass.

The original CCO+CRLF input and original entry remained unchanged. Every native check now performs its own conversion before artifact inspection or before/after hash comparison; no shared mutable /output or undeclared /input is needed. Keep these successful design properties, while executing every check fresh.
