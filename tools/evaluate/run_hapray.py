#!/usr/bin/env python3
"""Run a HapRay analysis agent on many cases, one case at a time.

  python3 tools/evaluate/run_hapray.py CAPTURES OUT [--scene load] [--tier strong] [--with-source]
                                       -- claude -p "$(cat tools/evaluate/agent_prompt.md)"

CAPTURES/<case-id>/ holds the HapRay data collected from the case's UNFIXED app, either
directly or as written by tools/collect/run_cases.py (<case-id>/unfixed/round-N/, pick N with
--round). For every selected case the runner
  1. stages a blind input directory OUT/<case-id>/input/ with prompt.json (the symptom),
     capture/ (a copy of the HapRay data) and, with --with-source, source/ (the unfixed app
     source without git history; run tools/prepare_sources.py first);
  2. runs the command after `--` inside that directory. In every argument, {input} and
     {output} become the absolute input and output directories and {case} the case id;
  3. writes OUT/<case-id>/run.json with the exit code and wall time.
The agent must leave its result in OUT/<case-id>/output/ (answer.json, or the HapRay-Skill
fix-plan.json / scene report). Then score with tools/evaluate/score.py OUT.
Nothing evaluator-only (case.json, groundtruth.json, fix.patch, the fixed app) is staged.
The working directory is not a sandbox: run the agent where it cannot read this checkout.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import catalog  # noqa: E402


def stage(case, captures, dest, with_source, round_no=1):
    dest.mkdir(parents=True)
    shutil.copyfile(case['_dir'] / 'prompt.json', dest / 'prompt.json')
    src = captures / case['id']
    if (src / 'unfixed').is_dir():  # layout written by tools/collect/run_cases.py
        src = src / 'unfixed' / f'round-{round_no}'
    if not src.is_dir():
        raise FileNotFoundError(f'no captures in {src}')
    shutil.copytree(src, dest / 'capture')
    if with_source:
        repo = ROOT / case['host_app']['local_path']
        ref = f"case/{case['id']}/unfixed"
        (dest / 'source').mkdir()
        archive = subprocess.run(['git', '-C', str(repo), 'archive', ref], check=True, capture_output=True).stdout
        subprocess.run(['tar', '-x', '-C', str(dest / 'source')], input=archive, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('captures', type=Path)
    ap.add_argument('out', type=Path, help='new directory')
    ap.add_argument('--scene', choices=catalog.SCENES)
    ap.add_argument('--tier', choices=['strong', 'weak'])
    ap.add_argument('--cases', nargs='+')
    ap.add_argument('--with-source', action='store_true', help='also give the unfixed source (no history)')
    ap.add_argument('--round', type=int, default=1, help='which collected round to analyze')
    ap.add_argument('--timeout', type=int, default=3600, help='seconds per case')
    argv = sys.argv[1:]
    if '--' not in argv:
        ap.error('give the agent command after --')
    cut = argv.index('--')
    a, cmd = ap.parse_args(argv[:cut]), argv[cut + 1:]
    if not cmd:
        ap.error('give the agent command after --')
    cases = catalog.select(catalog.load(), a.scene, a.tier)
    if a.cases:
        cases = [c for c in cases if c['id'] in a.cases]
    if not cases:
        ap.error('no cases selected')
    a.out.mkdir(parents=True, exist_ok=False)
    failed = 0
    for case in cases:
        base = (a.out / case['id']).resolve()
        inp, out = base / 'input', base / 'output'
        record = dict(case=case['id'], command=cmd)
        try:
            stage(case, a.captures, inp, a.with_source, a.round)
            out.mkdir()
            argv = [x.replace('{input}', str(inp)).replace('{output}', str(out)).replace('{case}', case['id'])
                    for x in cmd]
            started = time.monotonic()
            with (base / 'agent.log').open('w') as log:
                code = subprocess.run(argv, cwd=inp, stdout=log, stderr=subprocess.STDOUT,
                                      timeout=a.timeout).returncode
            record.update(exit_code=code, time_s=round(time.monotonic() - started, 1))
        except (OSError, subprocess.SubprocessError) as exc:
            record.update(exit_code=None, error=str(exc))
        (base / 'run.json').write_text(json.dumps(record, indent=2) + '\n')
        failed += record.get('exit_code') != 0
        print(case['id'], record.get('exit_code'), record.get('time_s', record.get('error')), flush=True)
    print(f'{len(cases) - failed}/{len(cases)} cases finished; score with: '
          f'python3 tools/evaluate/score.py {a.out}')
    return int(bool(failed))


if __name__ == '__main__':
    sys.exit(main())
