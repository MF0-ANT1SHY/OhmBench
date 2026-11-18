#!/usr/bin/env python3
"""Run one installed HapRay agent/adapter per prepared blind case directory."""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('inputs', type=Path, help='one directory per case with prompt.json and unfixed inputs')
    ap.add_argument('out', type=Path, help='fresh directory for run records and reports')
    ap.add_argument('command', nargs=argparse.REMAINDER, help='argv; {input} and {output} expand to absolute paths')
    args = ap.parse_args()
    cmd = args.command
    if not cmd:
        ap.error('missing adapter command')
    cases = sorted(p.parent.resolve() for p in args.inputs.glob('*/prompt.json'))
    if not cases:
        ap.error('no prepared case directories')
    args.out.mkdir(parents=True, exist_ok=False)
    failed = False
    for case in cases:
        output = (args.out / case.name).resolve()
        output.mkdir()
        argv = [a.replace('{input}', str(case)).replace('{output}', str(output)) for a in cmd]
        started = time.monotonic()
        with (output / 'run.log').open('w') as log:
            try:
                code = subprocess.run(argv, cwd=case, stdout=log, stderr=subprocess.STDOUT,
                                      env={**os.environ, 'OHM_OUTPUT_DIR': str(output)}).returncode
            except OSError as exc:
                print(exc, file=log)
                code = 127
        record = dict(exit_code=code, time_s=time.monotonic()-started)
        (output / 'run.json').write_text(json.dumps(record) + '\n')
        print(case.name, code, flush=True)
        failed |= code != 0
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
