#!/usr/bin/env python3
"""Collect included cases sequentially on one device with HapRay-Skill's perf CLI."""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

CASES = Path(__file__).resolve().parents[2] / 'cases'


def collect(case_dir, case, work, args, trial):
    tc = case['testcase']['name']
    bundle = case['host_app']['bundle_name']
    shutil.copytree(case_dir / 'testcase', work / 'testcases' / bundle)
    env = {**os.environ, 'HAPRAY_WORKSPACE': str(work)}
    result = work / 'hapray-tool-result.json'
    perf = [args.hapray, 'perf', '--run_testcases', f'^{tc}$', '--devices', args.device,
            '--round', '1', '--result-file', str(result)]
    if 'memory' in case['collection']['modes']:
        perf.append('--memory')
    with (work / 'collect.log').open('w') as log:
        subprocess.run([args.prepare, case['id'], args.variant, str(trial), args.device],
                       env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(perf, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    receipt = json.loads(result.read_text())
    reports = receipt.get('outputs', {}).get('reports_path')
    if not receipt.get('success') or not reports or not (Path(reports) / tc / 'report').is_dir():
        raise ValueError('HapRay did not produce a successful testcase report')
    return reports


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('out', type=Path, help='new output directory')
    ap.add_argument('--device', required=True)
    ap.add_argument('--prepare', required=True, help='local executable: install signed variant and reset fixture')
    ap.add_argument('--cases', nargs='+', choices=sorted(p.parent.name for p in CASES.glob('*/case.json')))
    ap.add_argument('--variant', choices=['unfixed', 'fixed'], default='unfixed')
    ap.add_argument('--hapray', default='hapray', help='HapRay-Skill bin/hapray executable')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    failed = False
    for path in sorted(CASES.glob('*/case.json')):
        case = json.loads(path.read_text())
        if case['status'] != 'included' or (args.cases and case['id'] not in args.cases):
            continue
        for trial in range(1, case['collection']['rounds'] + 1):
            work = (args.out / case['id'] / args.variant / f'round-{trial}').resolve()
            work.mkdir(parents=True)
            try:
                reports = collect(path.parent, case, work, args, trial)
                record = dict(status='collected', reports_path=reports)
            except (OSError, subprocess.CalledProcessError, ValueError) as exc:
                record = dict(status='failed', error=str(exc))
                failed = True
            (work / 'collection.json').write_text(json.dumps(record, indent=2) + '\n')
            print(case['id'], trial, record['status'], flush=True)
            if record['status'] == 'failed':
                break
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
