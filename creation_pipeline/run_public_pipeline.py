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
    parser.add_argument("--max-jobs", type=int, default=None)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", action="append", help="Local document/directory or public URL; repeatable")
    source.add_argument("--catalog", type=Path, help="Generic JSON items[]/jobs[]; no fixed paper IDs required")
    source.add_argument("--table", type=Path, help="CSV/TSV/XLSX table with papers or resources")
    parser.add_argument("--source-type", choices=['paper','database','tool','model'], default='paper')
    parser.add_argument("--target-candidates", type=int, default=20)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--skip-acquire", action="store_true")
    args = parser.parse_args()
    prefix = f"public-{datetime.now():%Y%m%d-%H%M%S}"
    manifest = HERE / 'acquired_manifest.json'
    if args.table:
        table_catalog=HERE/'intakes'/prefix/'table-catalog.json'
        table_catalog.parent.mkdir(parents=True,exist_ok=True)
        result=subprocess.run([sys.executable,str(HERE/'table_to_catalog.py'),
                               '--input',str(args.table.resolve()),'--output',str(table_catalog)],check=False)
        if result.returncode:return result.returncode
        args.catalog=table_catalog
    if args.input or args.catalog:
        out=HERE / 'intakes' / prefix
        command=[sys.executable,str(HERE/'ingest_sources.py'),'--out',str(out),'--source-type',args.source_type]
        if args.catalog:command += ['--catalog',str(args.catalog.resolve())]
        for value in args.input or []:command += ['--input',value]
        result=subprocess.run(command,check=False)
        if result.returncode:return result.returncode
        manifest=out/'manifest.json'
    elif not args.skip_acquire:
        acquire = subprocess.run([sys.executable, str(HERE / "acquire_catalog_sources.py")], check=False)
        if acquire.returncode:
            return acquire.returncode
    if not manifest.is_file():
        parser.error("acquired_manifest.json is missing; run acquisition first")
    if not (args.input or args.catalog):
        out=HERE/'intakes'/prefix
        result=subprocess.run([sys.executable,str(HERE/'ingest_sources.py'),
                               '--catalog',str(manifest),'--out',str(out)],check=False)
        if result.returncode:return result.returncode
        manifest=out/'manifest.json'
    cmd = [sys.executable, str(HERE / "batch_pipeline.py"),
           "--manifest", str(manifest),
           "--model", args.model,
           "--rounds", str(args.rounds), "--target-candidates", str(args.target_candidates),
           "--prefix", prefix]
    if args.max_jobs is not None:cmd += ['--max-jobs',str(args.max_jobs)]
    if args.push:
        cmd.append("--push")
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
