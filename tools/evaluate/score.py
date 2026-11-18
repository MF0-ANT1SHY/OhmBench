#!/usr/bin/env python3
"""Score a batch of HapRay outputs against the benchmark ground truth and fix.patch.

  python3 tools/evaluate/score.py RUNS_DIR [--tier strong] [--scene load] [--verdicts v.json]
                                  [--out results.json] [--md results.md] [--review-packet packet.json]

RUNS_DIR/<case-id>/ is one case's output directory (for run_hapray.py runs, only its
output/ subdirectory is read). The first file found is scored:

  answer.json                      ranked suspects (format in docs/evaluation.md)
  **/fix-plan.json                 HapRay-Skill fix-planning output (proposals in order)
  **/root_cause_agent_result.json  HapRay root-cause agent output (suspects)
  **/hapray-analysis-*.md          HapRay-Skill scene report (findings parsed by heading)

Per case it reports:
  localization   top1 / top5: a primary root cause is among the first 1 / 5 suspects;
                 precision, recall, f1 over the top-5 suspects (docs/evaluation.md rules)
  fix target     the first suggestion edits a file changed by fix.patch (fix_file_hit) and
                 its location lies in or next to a changed hunk / root-cause function (fix_hunk_hit)
  scene          the scene HapRay analyzed equals the case's HapRay scene (or a secondary one)
  verdicts       optional human or model judgments of the first diagnosis and repair
                 (diagnosis_correct, repair_correct); see tools/evaluate/judge.py
Missing or unreadable output scores 0 for that case; averages always use all selected cases.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import catalog  # noqa: E402

TOP = 5
HUNK_SLACK = 10
EXT = re.compile(r'\.(ets|ts|js)$')
LOC = re.compile(r'([\w./\\-]+\.(?:ets|ts|js))(?::(\d+)(?:-(\d+))?)?')


# ---------------------------------------------------------------- reading outputs

def _find(case_dir, pattern):
    hits = sorted(case_dir.rglob(pattern))
    return hits[0] if hits else None


def read_output(case_dir):
    """Return (format, path, suspects, scene). Suspects are dicts in rank order."""
    for fmt, pattern in (('answer', 'answer.json'), ('fix-plan', 'fix-plan.json'),
                         ('root-cause', 'root_cause_agent_result.json'), ('scene-report', 'hapray-analysis-*.md')):
        path = _find(case_dir, pattern)
        if path is None:
            continue
        if fmt == 'scene-report':
            text = path.read_text(encoding='utf-8', errors='replace')
            m = re.search(r'-(load|memory|jank|latency)-', path.name)
            return fmt, path, parse_markdown(text), m[1] if m else None
        data = json.loads(path.read_text(encoding='utf-8'))
        if fmt == 'fix-plan':
            rows, scene = [], None
            for p in data.get('proposals', []):
                f, loc = p.get('finding', {}), p.get('finding', {}).get('locator', {})
                scene = scene or f.get('domain')
                rows.append(dict(file=loc.get('source_file'), symbol=loc.get('symbol'), line_start=loc.get('line'),
                                 root_cause=json.dumps(f.get('evidence'), ensure_ascii=False),
                                 fix=p.get('patch_strategy'), target_files=p.get('target_files', [])))
            return fmt, path, rows, scene
        suspects = data.get('suspects')
        if not isinstance(suspects, list):
            raise ValueError('expected a "suspects" list')
        suspects = [s for s in suspects if isinstance(s, dict)]
        suspects.sort(key=lambda s: s.get('rank') if isinstance(s.get('rank'), int) else 10 ** 6)
        return fmt, path, suspects, data.get('scene')
    return None, None, [], None


def parse_markdown(text):
    """Findings of a scene report, in order: each '#'-heading section with a source location."""
    rows = []
    sections = re.split(r'\n(?=#{2,4} )', '\n' + text)
    for sec in sections:
        head = sec.strip().split('\n', 1)[0]
        if not re.search(r'P[0-3]|BUG|根因|finding|问题|嫌疑', head, re.I):
            continue
        m = LOC.search(sec)
        if not m:
            continue
        sym = re.search(r'`([A-Za-z_$][\w$]*(?:[.#][A-Za-z_$][\w$]*)+)\(?\)?`', sec)
        fix = re.search(r'(?:修复建议|修复方案|Fix)[^\n]*\n?([^\n]+)', sec)
        rows.append(dict(file=m[1], line_start=int(m[2]) if m[2] else None,
                         line_end=int(m[3]) if m[3] else None, symbol=sym[1] if sym else None,
                         root_cause=head, fix=fix[1].strip() if fix else None))
    return rows


# ---------------------------------------------------------------- matching

def parts(path):
    # ABC record names ("&entry/src/main/ets/pages/Index&", "phone|@x/home|1.0.0|src/main/ets/a.ts")
    # are reduced to their source path.
    p = str(path or '').strip().strip('&').replace('\\', '/').split('|')[-1]
    return [s for s in EXT.sub('', p).split('/') if s and s != '.']


def same_file(a, b):
    x, y = parts(a), parts(b)
    if not x or not y:
        return False
    # At least two trailing segments agree, or the whole name of a one-segment location path.
    n = min(2, len(x), len(y))
    return x[-n:] == y[-n:] and (n == 2 or len(y) == 1)


def lines_of(s):
    a = s.get('line_start')
    b = s.get('line_end') or a
    return (a, b) if type(a) is int and type(b) is int and 0 < a <= b else None


def matches(s, loc):
    if not same_file(s.get('file'), loc['file']):
        return False
    sym, target = s.get('symbol') or '', loc.get('symbol')
    if target and re.split(r'[.#]', sym)[-1] == re.split(r'[.#]', target)[-1]:
        return True
    span = loc.get('scope_lines') if loc.get('kind') == 'function' else loc.get('changed_lines')
    ln = lines_of(s)
    return bool(span and ln and ln[0] <= span[-1] and ln[1] >= span[0])


def patch_hunks(patch):
    """{file: [(start, end)]} of changed lines on the unfixed side of fix.patch."""
    hunks, cur = {}, None
    for line in patch.splitlines():
        if line.startswith('--- a/'):
            cur = line[6:]
        elif line.startswith('@@') and cur:
            m = re.match(r'@@ -(\d+)(?:,(\d+))?', line)
            start, n = int(m[1]), int(m[2] or 1)
            hunks.setdefault(cur, []).append((start, start + max(n, 1) - 1))
    return hunks


def fix_target(suggestion, hunks, roots):
    """(file_hit, hunk_hit) for one suggestion."""
    files = [suggestion.get('file'), *(suggestion.get('target_files') or [])]
    changed = [f for f in hunks if any(same_file(x, f) for x in files if x)]
    if not changed:
        return False, False
    ln = lines_of(suggestion)
    near = ln and any(ln[0] <= b + HUNK_SLACK and ln[1] >= a - HUNK_SLACK
                      for f in changed for a, b in hunks[f] if same_file(suggestion.get('file'), f))
    in_root = any(matches(suggestion, loc) for r in roots for loc in [r, *r.get('aliases', [])])
    return True, bool(near or in_root)


# ---------------------------------------------------------------- scoring

def score_case(case, case_dir, verdicts):
    gt = case['_gt']
    roots = gt['root_causes']
    patch = (case['_dir'] / 'fix.patch').read_text(encoding='utf-8', errors='replace')
    row = dict(case=case['id'], tier=case['quality']['tier'], scene=case['hapray']['scene'])
    if (case_dir / 'output').is_dir():
        # Layout of run_hapray.py: score only what the agent wrote, never the staged input.
        run = case_dir / 'run.json'
        if run.is_file():
            row['run'] = json.loads(run.read_text())
        case_dir = case_dir / 'output'
    try:
        fmt, path, suspects, scene = read_output(case_dir) if case_dir.is_dir() else (None, None, [], None)
        row['status'] = 'ok' if fmt else 'missing'
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        fmt, path, suspects, scene = None, None, [], None
        row['status'] = f'invalid: {exc}'
    top = suspects[:TOP]
    primary = {r['id'] for r in roots if r['role'] == 'primary'}
    found, correct, first_primary = set(), 0, None
    for i, s in enumerate(top):
        hit = {r['id'] for r in roots if any(matches(s, loc) for loc in [r, *r.get('aliases', [])])}
        found |= hit
        correct += bool(hit)
        if first_primary is None and hit & primary:
            first_primary = i + 1
    p = correct / len(top) if top else 0.0
    r = len(found & primary) / len(primary)
    file_hit, hunk_hit = fix_target(top[0], patch_hunks(patch), roots) if top else (False, False)
    digest = hashlib.sha256(b''.join(x.read_bytes() for x in (path, case['_dir'] / 'fix.patch') if x)).hexdigest()
    v = verdicts.get(case['id'])
    if v is not None and v.get('fingerprint') != digest:
        v = None  # stale: the output or reference changed after review
    row.update(format=fmt, output=str(path) if path else None, suspects=len(suspects),
               top1=first_primary == 1, top5=first_primary is not None, first_hit_rank=first_primary,
               precision=round(p, 4), recall=round(r, 4), f1=round(2 * p * r / (p + r), 4) if p + r else 0.0,
               fix_file_hit=file_hit, fix_hunk_hit=hunk_hit,
               reported_scene=scene,
               scene_match=None if scene is None else scene in (case['hapray']['scene'], *case['hapray']['also']),
               diagnosis_correct=(v or {}).get('diagnosis_correct') if top else False,
               repair_correct=(v or {}).get('repair_correct') if top else False,
               fingerprint=digest)
    packet = dict(case=case['id'], fingerprint=digest, first_suggestion=top[0] if top else None,
                  reference_mechanism=gt['mechanism'], reference_fix=gt['fix_summary'], reference_patch=patch)
    return row, packet


def summarize(rows):
    n = len(rows)
    if not n:
        return dict(cases=0)
    mean = lambda k: round(sum(float(x[k] or 0) for x in rows) / n, 4)
    out = dict(cases=n, answered=sum(x['status'] == 'ok' for x in rows),
               top1=mean('top1'), top5=mean('top5'), precision=mean('precision'), recall=mean('recall'),
               f1=mean('f1'), fix_file_hit=mean('fix_file_hit'), fix_hunk_hit=mean('fix_hunk_hit'))
    scened = [x for x in rows if x['scene_match'] is not None]
    out['scene_match'] = round(sum(x['scene_match'] for x in scened) / len(scened), 4) if scened else None
    for k in ('diagnosis_correct', 'repair_correct'):
        vals = [x[k] for x in rows]
        out[k] = None if None in vals else mean(k)
        out[k + '_pending'] = vals.count(None)
    return out


def markdown(summary, rows):
    cols = ['cases', 'answered', 'top1', 'top5', 'precision', 'recall', 'f1', 'fix_file_hit', 'fix_hunk_hit',
            'scene_match', 'diagnosis_correct', 'repair_correct']
    L = ['| Group | ' + ' | '.join(cols) + ' |', '|---' * (len(cols) + 1) + '|']
    for name, s in summary.items():
        L.append(f'| {name} | ' + ' | '.join('–' if s.get(c) is None else str(s.get(c)) for c in cols) + ' |')
    L += ['', '| Case | tier | scene | status | top1 | top5 | P | R | F1 | fix file | fix hunk | scene ok |',
          '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for x in rows:
        L.append(f"| `{x['case']}` | {x['tier']} | {x['scene']} | {x['status']} | {int(x['top1'])} | "
                 f"{int(x['top5'])} | {x['precision']:.2f} | {x['recall']:.2f} | {x['f1']:.2f} | "
                 f"{int(x['fix_file_hit'])} | {int(x['fix_hunk_hit'])} | "
                 f"{'–' if x['scene_match'] is None else int(x['scene_match'])} |")
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('runs', type=Path, help='directory with one output directory per case')
    ap.add_argument('--scene', choices=catalog.SCENES)
    ap.add_argument('--tier', choices=['strong', 'weak'])
    ap.add_argument('--cases', nargs='+', help='score only these case ids')
    ap.add_argument('--verdicts', type=Path, help='judgments from judge.py or a reviewer')
    ap.add_argument('--out', type=Path, help='write per-case rows and summary as JSON')
    ap.add_argument('--md', type=Path, help='write a Markdown table')
    ap.add_argument('--review-packet', type=Path, help='write first suggestions beside the references (for judge.py)')
    a = ap.parse_args()
    cases = catalog.select(catalog.load(), a.scene, a.tier)
    if a.cases:
        unknown = set(a.cases) - {c['id'] for c in cases}
        if unknown:
            ap.error('not selected: ' + ', '.join(sorted(unknown)))
        cases = [c for c in cases if c['id'] in a.cases]
    verdicts = json.loads(a.verdicts.read_text()) if a.verdicts else {}
    rows, packets = [], []
    for c in cases:
        row, packet = score_case(c, a.runs / c['id'], verdicts)
        rows.append(row)
        packets.append(packet)
    summary = {'all': summarize(rows), 'strong only': summarize([x for x in rows if x['tier'] == 'strong'])}
    for s in catalog.SCENES:
        group = [x for x in rows if x['scene'] == s]
        if group:
            summary[f'scene {s}'] = summarize(group)
    text = markdown(summary, rows)
    print(text)
    if a.out:
        a.out.write_text(json.dumps(dict(summary=summary, cases=rows), indent=2, ensure_ascii=False) + '\n')
    if a.md:
        a.md.write_text(text)
    if a.review_packet:
        a.review_packet.write_text(json.dumps(packets, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
