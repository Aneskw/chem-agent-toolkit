"""Delivered entry: count non-empty records in a newline-delimited text file."""
import json
import sys


def count(path):
    with open(path, encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    target = argv[0] if argv else "input.txt"
    print(json.dumps({"path": target, "records": count(target)}))


if __name__ == "__main__":
    main()