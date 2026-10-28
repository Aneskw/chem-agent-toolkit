# Ideal dilution calculator, source release 1.0

Original small source fixture created for integration verification; MIT licensed.
This is source software, not a prewritten Skill. Python 3.11 standard library only,
Linux amd64 CPU; no network, GPU, weights, credentials or external service required.
Run dilution.py using Python. Preserve the source script unchanged when distributing.

Concentrations use the same arbitrary unit; final volume is in mL. The ideal model is
C_stock * V_stock = C_target * V_final. Diluent volume is V_final - V_stock.
This is arithmetic, not a protocol for handling chemicals or a nonideal mixing model.

Contract fixed before model generation:
- --stock 10 --target 2 --volume 50 prints JSON with stock_volume_ml=10 and diluent_volume_ml=40, exit 0.
- --stock 5 --target 5 --volume 12 gives 12 and 0, exit 0.
- Zero, negative, nonfinite values or target above stock are rejected with exit 2.
- --input cases.json accepts a nonempty array of objects with stock, target, volume.
- --output result.json writes exactly the same JSON result printed to stdout.
- cases.json contains two valid records whose expected outputs are [10,40] and [12,0].
- Missing arguments, malformed JSON, empty arrays, and mixed scalar/input mode fail with exit 2.
- --help exits 0 and describes the actual CLI.

The executable delivery must be tested, including invalid input and file input/output.
