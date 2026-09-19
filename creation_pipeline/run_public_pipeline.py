#!/usr/bin/env python3
"""Acquire all public catalog sources, then extract a bounded batch of skills."""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-6-astra")
    parser.add_argument("--max-jobs", type=int, default=20)
    parser.add_argument("--target-candidates", type=int, default=20)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--skip-acquire", action="store_true")
    args = parser.parse_args()
    if not args.skip_acquire:
        acquire = subprocess.run([sys.executable, str(HERE / "acquire_catalog_sources.py")], check=False)
        if acquire.returncode:
            return acquire.returncode
    if not (HERE / "acquired_manifest.json").is_file():
        parser.error("acquired_manifest.json is missing; run acquisition first")
    prefix = f"public-{datetime.now():%Y%m%d-%H%M%S}"
    cmd = [sys.executable, str(HERE / "batch_pipeline.py"),
           "--manifest", str(HERE / "acquired_manifest.json"),
           "--model", args.model, "--max-jobs", str(args.max_jobs),
           "--rounds", str(args.rounds), "--target-candidates", str(args.target_candidates),
           "--prefix", prefix]
    if args.push:
        cmd.append("--push")
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
