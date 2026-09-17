# Example: simulated Pd-catalyzed direct arylation

This directory contains a self-contained demonstration with categorical ligand/base/solvent descriptors, continuous temperature/concentration descriptors, and 20 simulated yield observations. The values are synthetic and do not represent a real reaction.

Files:

- `direct_arylation_space.json`: reaction space and yield objective.
- `initial_data.csv`: simulated observations generated with seed 42.
- `make_demo_data.py`: regenerate the demo files.

Run one recommendation batch:

```bash
python ../scripts/recommend_next_batch.py \
  --space direct_arylation_space.json --data initial_data.csv \
  --batch-size 5 --seed 42 --output rec.json --report report.md --plot rec.png
```

The demo is an algorithm smoke test only; it is not evidence about a real chemical system.
