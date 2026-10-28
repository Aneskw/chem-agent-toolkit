# record-count

Delivered entry: `tool.py`.

Usage:

```sh
python tool.py DATA.txt
```

Prints one JSON object with `path` and the number of non-empty lines
(`records`). Standard library only; requires Python 3.9 or newer.
Exit status is 0 on success and non-zero when the file cannot be read.