# record-count (upstream source)

`count(path)` returns the number of non-empty lines in a UTF-8 text file.
Lines that are empty or contain only whitespace are not counted.

The command line wrapper prints exactly one JSON object:

    {"path": "<argument>", "records": <integer>}

The tool has no third-party dependencies and reads no network resources.
It never modifies its input file.

Supported interpreters: Python 3.9 and newer (uses only `json`, `sys`).