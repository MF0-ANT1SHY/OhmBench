#!/usr/bin/env python3
"""Collect HapRay data for many cases on one prepared device, one case and round at a time.

  python3 tools/collect/run_cases.py OUT --device SERIAL --prepare ./my_prepare.sh
                                     [--variant unfixed] [--scene load] [--tier strong] [--cases ID ...]

For every selected case and round:
  1. runs your --prepare program with arguments CASE_ID VARIANT ROUND SERIAL. It must install
     the signed variant and restore the case's input data (see docs/cases.md "Input data and
     backends"; tools/collect/prepare_browser.py is an example for the browser cases) and exit
     non-zero on failure;
  2. copies the case's testcase/ into a fresh HapRay workspace and runs
     `hapray perf` for that testcase, adding --memory for memory-scene cases;
  3. records OUT/<case-id>/<variant>/round-N/collection.json (collected / failed, with reason).
A failed round stops that case and the batch continues with the next case.
tools/evaluate/run_hapray.py reads this layout directly (OUT as its CAPTURES, --round N).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import catalog  # noqa: E402


def collect(case, work, args, trial):
    tc = case['testcase']['name']
    bundle = case['host_app']['bundle_name']
    shutil.copytree(case['_dir'] / 'testcase', work / 'testcases' / bundle)
    env = {**os.environ, 'HAPRAY_WORKSPACE': str(work)}
    result = work / 'hapray-tool-result.json'
    perf = [args.hapray, 'perf', '--run_testcases', f'^{tc}$', '--devices', args.device,
            '--round', '1', '--result-file', str(result)]
    if case['hapray']['collect'] == 'perf --memory':
        perf.append('--memory')
    with (work / 'collect.log').open('w') as log:
        prepare = [sys.executable, args.prepare] if args.prepare.endswith('.py') else [args.prepare]
        subprocess.run([*prepare, case['id'], args.variant, str(trial), args.device],
                       env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(perf, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    receipt = json.loads(result.read_text())
    reports = receipt.get('outputs', {}).get('reports_path')
    if not receipt.get('success') or not reports or not (Path(reports) / tc / 'report').is_dir():
        raise ValueError('HapRay did not produce a successful testcase report')
    return reports


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out', type=Path, help='new output directory')
    ap.add_argument('--device', required=True)
    ap.add_argument('--prepare', required=True, help='program: install the variant and reset its input data')
    ap.add_argument('--variant', choices=['unfixed', 'fixed'], default='unfixed')
    ap.add_argument('--scene', choices=catalog.SCENES)
    ap.add_argument('--tier', choices=['strong', 'weak'])
    ap.add_argument('--cases', nargs='+', metavar='CASE_ID')
    ap.add_argument('--rounds', type=int, help='default: case.json collection.rounds')
    ap.add_argument('--hapray', default='hapray', help='HapRay-Skill bin/hapray executable')
    args = ap.parse_args()
    cases = catalog.select(catalog.load(), args.scene, args.tier)
    if args.cases:
        unknown = set(args.cases) - {c['id'] for c in cases}
        if unknown:
            ap.error('not an included, selected case: ' + ', '.join(sorted(unknown)))
        cases = [c for c in cases if c['id'] in args.cases]
    args.out.mkdir(parents=True, exist_ok=False)
    failed = False
    for case in cases:
        for trial in range(1, (args.rounds or case['collection']['rounds']) + 1):
            work = (args.out / case['id'] / args.variant / f'round-{trial}').resolve()
            work.mkdir(parents=True)
            try:
                record = dict(status='collected', reports_path=collect(case, work, args, trial))
            except (OSError, subprocess.CalledProcessError, ValueError) as exc:
                record = dict(status='failed', error=str(exc))
                failed = True
            (work / 'collection.json').write_text(json.dumps(record, indent=2) + '\n')
            print(case['id'], args.variant, trial, record['status'], flush=True)
            if record['status'] == 'failed':
                break
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
