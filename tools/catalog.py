#!/usr/bin/env python3
"""Case catalog: check case metadata, select cases, and regenerate docs/cases.md tables.

  python3 tools/catalog.py check                    # validate every case (used by tests)
  python3 tools/catalog.py list [--scene load] [--tier strong] [--data offline] [--all]
  python3 tools/catalog.py docs                     # rewrite the generated part of docs/cases.md

Each case.json carries three fields used here:
  quality      effect size of the reference measurement: median unfixed/fixed ratio and a tier
               ("weak" when the ratio is below WEAK_RATIO, i.e. the fix changes the metric by
               less than half; such cases still pass their own oracle)
  runnability  what input data the workload needs (offline fixture, local replay service or
               public backend), whether it can be run today, and when that was checked
  hapray       which HapRay scene the case exercises (load / memory / jank / latency),
               secondary scenes, the HapRay collection mode, and whether HapRay itself
               reports the oracle metric
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'cases'
DOC = ROOT / 'docs' / 'cases.md'
WEAK_RATIO = 1.5
SCENES = {'load': '负载', 'memory': '内存', 'jank': '卡顿丢帧', 'latency': '时延'}
DATA = {'offline': 'offline fixture', 'local_service': 'local replay service', 'public_backend': 'public backend'}
START, END = '<!-- catalog:start -->', '<!-- catalog:end -->'


def load():
    cases = []
    for path in sorted(CASES.glob('*/case.json')):
        case = json.loads(path.read_text(encoding='utf-8'))
        case['_gt'] = json.loads((path.parent / 'groundtruth.json').read_text(encoding='utf-8'))
        case['_dir'] = path.parent
        cases.append(case)
    return cases


def quality(gt):
    """Median unfixed/fixed ratio of the reference evidence, and its tier."""
    ev = gt['performance_oracle']['evidence']
    ratio = ev.get('median_ratio')
    if ratio is None:
        ratio = statistics.median(ev['unfixed']) / statistics.median(ev['fixed'])
    return dict(median_ratio=round(ratio, 2), tier='weak' if ratio < WEAK_RATIO else 'strong')


def check(cases):
    errors = []
    for c in cases:
        cid, gt = c['id'], c['_gt']
        def err(msg):
            errors.append(f'{cid}: {msg}')
        if c['_dir'].name != cid or gt['case'] != cid:
            err('directory, case.json and groundtruth.json ids differ')
        if c['status'] not in ('included', 'excluded') or gt['status'] != c['status']:
            err('status must be included/excluded and equal in case.json and groundtruth.json')
        if c['status'] == 'excluded' and not c.get('exclusion_reason'):
            err('excluded case needs exclusion_reason')
        q = c.get('quality')
        if q != quality(gt):
            err(f'quality {q} != computed {quality(gt)} (run: tools/catalog.py docs)')
        r = c.get('runnability') or {}
        if r.get('data') not in DATA or not r.get('prepare') or not isinstance(r.get('runnable'), bool):
            err('runnability needs data, prepare and runnable')
        if r.get('data') == 'local_service' and not r.get('service'):
            err('local_service case must name its service')
        if r.get('data') == 'public_backend' and not r.get('public_backend'):
            err('public_backend case must name the backend and its last check')
        if c['status'] == 'included' and not r.get('runnable'):
            err('a case that cannot be run must be excluded')
        h = c.get('hapray') or {}
        if h.get('scene') not in SCENES or any(s not in SCENES or s == h.get('scene') for s in h.get('also', [])):
            err('hapray.scene/also must be load, memory, jank or latency')
        if h.get('collect') != ('perf --memory' if h.get('scene') == 'memory' else 'perf'):
            err('memory scene needs collect "perf --memory", others "perf"')
        for name in ('case.json', 'prompt.json', 'groundtruth.json', 'source.patch', 'fix.patch'):
            if not (c['_dir'] / name).is_file():
                err(f'missing {name}')
        for key in ('py_file', 'descriptor', 'workload'):
            if not (c['_dir'] / c['testcase'][key]).is_file():
                err(f'missing testcase {key}')
        if not any(rc['role'] == 'primary' for rc in gt['root_causes']):
            err('needs a primary root cause')
    return errors


def select(cases, scene=None, tier=None, data=None, include_excluded=False):
    out = []
    for c in cases:
        if c['status'] != 'included' and not include_excluded:
            continue
        if scene and scene != c['hapray']['scene'] and scene not in c['hapray']['also']:
            continue
        if tier and c['quality']['tier'] != tier:
            continue
        if data and c['runnability']['data'] != data:
            continue
        out.append(c)
    return out


def scenes(c):
    h = c['hapray']
    text = f"**{h['scene']}** {SCENES[h['scene']]}"
    if h['also']:
        text += ' (also ' + ', '.join(f'{s} {SCENES[s]}' for s in h['also']) + ')'
    return text


def render(cases):
    inc = [c for c in cases if c['status'] == 'included']
    exc = [c for c in cases if c['status'] != 'included']
    weak = [c for c in inc if c['quality']['tier'] == 'weak']
    L = [START, '<!-- Generated by `python3 tools/catalog.py docs` from case.json; do not edit by hand. -->', '',
         f'**{len(inc)} included cases** ({len(inc) - len(weak)} strong, {len(weak)} weak) and {len(exc)} excluded.', '',
         '## Case list', '',
         '| Case | App | HapRay scene | Oracle metric | Effect (unfixed/fixed) | Quality | Input data |',
         '|---|---|---|---|---|---|---|']
    for c in inc:
        q, r = c['quality'], c['runnability']
        metric = c['_gt']['performance_oracle']['metric']
        if not c['hapray']['oracle_metric_in_hapray']:
            metric += ' †'
        L.append(f"| `{c['id']}` | {c['host_app']['name']} | {scenes(c)} | `{metric}` | {q['median_ratio']:.2f}x | "
                 f"{q['tier']} | {DATA[r['data']]} |")
    L += ['', f'† HapRay does not report this metric itself; the reference values were measured externally. '
          f'Compare unfixed/fixed ratios.', '',
          f'**Quality.** "weak" = the fix changes the oracle metric by less than {WEAK_RATIO}x (median of three '
          f'paired rounds). Weak cases pass their own oracle and stay in the benchmark, but report scores with '
          f'and without them (`--tier strong`).', '',
          '## Which cases test which HapRay scene', '',
          'HapRay-Skill analyzes four scenes. A case is listed under its primary scene and, in parentheses, '
          'under scenes it also exercises (an analysis opportunity, not a measured oracle).', '',
          '| HapRay scene | Collection | Primary cases | Also relevant |', '|---|---|---|---|']
    for s, zh in SCENES.items():
        prim = [c['id'] for c in inc if c['hapray']['scene'] == s]
        also = [c['id'] for c in inc if s in c['hapray']['also']]
        coll = 'perf --memory' if s == 'memory' else 'perf'
        L.append(f"| {s} {zh} | `{coll}` | {len(prim)}: " + (', '.join(f'`{x}`' for x in prim) or '–') +
                 f" | {len(also)}: " + (', '.join(f'`{x}`' for x in also) or '–') + ' |')
    L += ['', 'No case has a frame-drop (stutter rate) oracle yet; jank cases are scrolling/animation workloads '
          'whose oracle is CPU instructions.', '',
          '## Input data and backends', '',
          '"offline fixture" = data installed before the run; "local replay service" = a script in this '
          'repository serves ordinary API responses to the app (forward the port with `hdc rport`); '
          '"public backend" = the app talks to the real internet service.', '',
          '"Runnable" is a dependency check on the date shown, not a fresh device run of every case: offline and '
          'local-service cases need nothing outside this repository, and every public endpoint was requested on '
          'that date. A case whose backend no longer works is excluded.', '',
          '| Case | Input data | Preparation | Service / backend | Runnable |', '|---|---|---|---|---|']
    for c in cases:
        r = c['runnability']
        svc = r.get('service') or r.get('public_backend') or '–'
        ok = f"yes ({r['checked']})" if r['runnable'] else f"**no**, backend down ({r['checked']})"
        L.append(f"| `{c['id']}` | {DATA[r['data']]} | {r['prepare']} | {svc} | {ok} |")
    if exc:
        L += ['', '## Excluded cases', '', '| Case | Reason |', '|---|---|']
        L += [f"| `{c['id']}` | {c['exclusion_reason']} |" for c in exc]
        L += ['', 'Nine further cases were removed earlier (commit `8a5e4e7`) because their unfixed/fixed pair '
              'did not pass the clean performance gate.']
    L.append(END)
    return '\n'.join(L)


def write_docs(cases):
    for c in cases:
        q = quality(c['_gt'])
        if c.get('quality') != q:
            data = json.loads((c['_dir'] / 'case.json').read_text(encoding='utf-8'))
            data['quality'] = c['quality'] = q
            (c['_dir'] / 'case.json').write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n',
                                                 encoding='utf-8')
    text = DOC.read_text(encoding='utf-8')
    head = text.split(START)[0] if START in text else text.split('## Case list')[0]
    tail = text.split(END, 1)[1] if END in text else '\n'
    DOC.write_text(head.rstrip('\n') + '\n\n' + render(cases) + tail, encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('check')
    sub.add_parser('docs')
    ls = sub.add_parser('list')
    ls.add_argument('--scene', choices=SCENES)
    ls.add_argument('--tier', choices=['strong', 'weak'])
    ls.add_argument('--data', choices=DATA)
    ls.add_argument('--all', action='store_true', help='include excluded cases')
    args = ap.parse_args()
    cases = load()
    if args.cmd == 'docs':
        write_docs(cases)
        cases = load()
    if args.cmd in ('check', 'docs'):
        errors = check(cases)
        print('\n'.join(errors) if errors else f'{len(cases)} cases OK')
        return int(bool(errors))
    for c in select(cases, args.scene, args.tier, args.data, args.all):
        print(c['id'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
