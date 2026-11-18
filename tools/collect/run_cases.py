#!/usr/bin/env python3
"""Collect included cases sequentially on one device with HapRay-Skill's perf CLI."""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


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
    ap.add_argument('--cases', nargs='+', metavar='CASE_ID')
    ap.add_argument('--candidates', action='store_true', help='collect unscored candidates instead of included cases')
    ap.add_argument('--variant', choices=['unfixed', 'fixed'], default='unfixed')
    ap.add_argument('--hapray', default='hapray', help='HapRay-Skill bin/hapray executable')
    args = ap.parse_args()
    case_root = ROOT / ('candidates' if args.candidates else 'cases')
    status = 'candidate' if args.candidates else 'included'
    selected = {}
    for path in sorted(case_root.glob('*/case.json')):
        case = json.loads(path.read_text())
        # Failed gates stay out of batch runs; allow an explicit reproduction.
        requested_exclusion = (args.candidates and args.cases and case['id'] in args.cases
                               and case['status'] == 'excluded')
        if case['status'] == status or requested_exclusion:
            selected[case['id']] = (path.parent, case)
    if args.cases:
        unknown = set(args.cases).difference(selected)
        if unknown:
            ap.error(f"not in {case_root.name}: {', '.join(sorted(unknown))}")
        selected = {cid: selected[cid] for cid in args.cases}
    if not selected:
        ap.error(f'no eligible cases in {case_root.name}')
    args.out.mkdir(parents=True, exist_ok=False)
    failed = False
    for directory, case in selected.values():
        for trial in range(1, case['collection']['rounds'] + 1):
            work = (args.out / case['id'] / args.variant / f'round-{trial}').resolve()
            work.mkdir(parents=True)
            try:
                reports = collect(directory, case, work, args, trial)
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
