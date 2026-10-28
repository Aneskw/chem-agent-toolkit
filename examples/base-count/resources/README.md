# DNA base counts: original source release 1.0

MIT licensed verification fixture, not a prewritten Skill. Requires Python 3.11
standard library, local Linux amd64 CPU. No third-party dependency, GPU, weights,
credentials, external data mount, network or service. Distribute base_count.py unchanged.
This tool only counts literal characters: it does not infer biological function,
validate experiments, parse FASTA, accept ambiguous bases or normalize lower case.

Fixed contract (written before any model generation):
- python base_count.py --sequence ACGTA prints JSON {"length":5,"A":2,"C":1,"G":1,"T":1}, exit 0.
- python base_count.py --sequence GGG prints JSON {"length":3,"A":0,"C":0,"G":3,"T":0}, exit 0.
- All result values are JSON integers from len() and str.count(); JSON key order is irrelevant.
- Empty strings, lowercase, whitespace within the sequence and any character outside ACGT are invalid; exit 2 with stderr containing 'expected a nonempty uppercase ACGT sequence'.
- --input sequence.txt reads UTF-8 text, removes one final newline, then applies the same validation.
- The supplied sequence.txt contains ACGTA followed by a newline and therefore has the first result above.
- --output result.json writes the same JSON printed to stdout, with a final newline. Parent directory must exist. Input is never modified.
- Missing input, or supplying both --input and --sequence, is rejected by argparse with exit 2.
- --help exits 0 and lists --sequence, --input, --output.

Executable acceptance must test the real delivered script: both normal sequences,
invalid input rejection and the supplied file with retained output content. Tests
must assert these fixed results, not merely successful installation or exit zero.
