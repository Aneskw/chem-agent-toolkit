"""Record an ordinary public CLI invocation, without preparing/injecting pipeline state.

Each label is a new evidence directory. Failed invocations remain immutable; this
wrapper neither resumes them nor supplies plans, contracts or qualification flags.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from creation_pipeline.records import now, redact, sanitized, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('label')
    parser.add_argument('argv', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.label or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in args.label):
        parser.error('label must use lowercase letters, digits, hyphen or underscore')
    argv = args.argv[1:] if args.argv[:1] == ['--'] else args.argv
    if not argv:
        parser.error('supply public creation_pipeline CLI arguments after --')
    destination = args.root / 'operations' / args.label
    destination.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-m', 'creation_pipeline', *argv]
    receipt = {'command': command, 'cwd': str(REPO), 'started_at': now(),
               'scope': 'public_cli_subprocess_only_no_pipeline_state_injection'}
    write_json(destination/'command.json', sanitized(receipt))
    started = time.monotonic()
    result = subprocess.run(command, cwd=REPO, capture_output=True, encoding='utf-8', errors='replace')
    (destination/'stdout.json').write_text(redact(result.stdout), encoding='utf-8')
    (destination/'stderr.log').write_text(redact(result.stderr), encoding='utf-8')
    try:
        response = json.loads(result.stdout or result.stderr)
    except ValueError:
        response = None
    receipt.update(finished_at=now(), seconds=time.monotonic()-started,
                   exit_code=result.returncode, response=response)
    write_json(destination/'result.json', sanitized(receipt))
    print(json.dumps({'exit_code': result.returncode, 'status': (response or {}).get('status'),
                      'evidence': str(destination)}, ensure_ascii=False))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
