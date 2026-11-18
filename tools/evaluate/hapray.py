#!/usr/bin/env python3
"""Score a batch of HapRay reports, keeping missing cases in the denominator."""
import argparse
import hashlib
import json
import re
import statistics
from pathlib import Path

CASES = Path(__file__).resolve().parents[2] / 'cases'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def locations_match(suspect, location):
    def parts(path):
        path = re.sub(r'\.(ets|ts|js)$', '', path.strip('&').replace('\\', '/'))
        return path.split('/') if path else []

    a, b = parts(suspect.get('file') or ''), parts(location['file'])
    n = min(2, len(a), len(b))
    if not n or a[-n:] != b[-n:]:
        return False
    symbol = suspect.get('symbol') or ''
    target = location.get('symbol')
    if target and re.split(r'[.#]', symbol)[-1] == re.split(r'[.#]', target)[-1]:
        return True
    start = suspect.get('line_start')
    end = suspect.get('line_end') or start
    span = location.get('scope_lines') if location.get('kind') == 'function' else location.get('changed_lines')
    return bool(span and type(start) is int and type(end) is int and
                0 < start <= end and start <= span[-1] and end >= span[0])


def predictions(report):
    if not isinstance(report, dict):
        raise ValueError('expected a report object')
    if 'proposals' in report:
        if not isinstance(report['proposals'], list):
            raise ValueError('expected proposals array')
        # Native fix-plan: order is proposal order, not issue severity.
        rows = []
        for proposal in report['proposals']:
            finding = proposal['finding']
            loc = finding['locator']
            rows.append(dict(file=loc.get('source_file'), symbol=loc.get('symbol'),
                             line_start=loc.get('line'), root_cause=finding.get('evidence'),
                             fix=proposal.get('patch_strategy'), target_files=proposal.get('target_files', [])))
        return rows
    if not isinstance(report.get('suspects'), list):
        raise ValueError('expected suspects array')
    return sorted(report['suspects'], key=lambda s: s.get('rank', float('inf')))


def score(case, report_path, verdicts, run=None):
    gt = read(case / 'groundtruth.json')
    patch = (case / 'fix.patch').read_text()
    roots = gt['root_causes']
    state = 'missing'
    suspects = []
    if run and run['exit_code'] != 0:
        state = 'run_failed'
    elif report_path.is_file():
        try:
            suspects = predictions(read(report_path))[:5]
            for s in suspects:
                if not isinstance(s, dict) or any(s.get(k) is not None and not isinstance(s[k], str)
                                                  for k in ('file', 'symbol')):
                    raise ValueError('invalid suspect location')
            state = 'ok'
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            state = f'invalid: {exc}'
            suspects = []
    found = set()
    correct = 0
    for s in suspects:
        hits = {r['id'] for r in roots if any(locations_match(s, loc) for loc in [r, *r.get('aliases', [])])}
        found.update(hits)
        correct += bool(hits)
    primary = {r['id'] for r in roots if r['role'] == 'primary'}
    p = correct / len(suspects) if suspects else 0
    r = len(primary & found) / len(primary)
    # Bind judgments to the actual report AND both reference artifacts.
    digest = hashlib.sha256()
    for path in (report_path, case / 'groundtruth.json', case / 'fix.patch'):
        digest.update(hashlib.sha256(path.read_bytes() if path.is_file() else b'').digest())
    key = digest.hexdigest()
    verdict = verdicts.get(case.name)
    if verdict is not None and verdict['fingerprint'] != key:
        raise ValueError(f'{case.name}: review is for a different report or reference')
    row = dict(case=case.name, status=state, precision=p, recall=r, f1=2*p*r/(p+r) if p+r else 0,
               matched_primary=sorted(primary & found), fingerprint=key)
    review = dict(case=case.name, fingerprint=key, top1=suspects[0] if suspects else None,
                  reference_mechanism=gt['mechanism'], reference_fix=gt['fix_summary'], reference_patch=patch)
    for field, answer in [('diagnosis_correct', 'root_cause'), ('repair_correct', 'fix')]:
        if not suspects or not suspects[0].get(answer):
            value = False
        else:
            value = verdict[field] if verdict else None
            if verdict and type(value) is not bool:
                raise ValueError(f'{case.name}: {field} must be true or false')
        row[field] = value
    return row, review


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('reports', type=Path)
    ap.add_argument('--report', default='{case}/report/root_cause_agent_result.json',
                    help='relative path pattern, e.g. {case}/.hapray/fix/fix-plan.json')
    ap.add_argument('--cases', nargs='+', choices=sorted(p.parent.name for p in CASES.glob('*/case.json')))
    ap.add_argument('--reviews', type=Path, help='reviewer verdicts keyed by case ID')
    ap.add_argument('--review-packet', type=Path, help='write private side-by-side evidence for review')
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    verdicts = read(args.reviews) if args.reviews else {}
    rows, packet = [], []
    for path in sorted(CASES.glob('*/case.json')):
        if read(path)['status'] != 'included' or (args.cases and path.parent.name not in args.cases):
            continue
        report = args.reports / args.report.format(case=path.parent.name)
        run_path = args.reports / path.parent.name / 'run.json'
        run = read(run_path) if run_path.exists() else None
        row, evidence = score(path.parent, report, verdicts, run)
        if run:
            row['run'] = run
        rows.append(row)
        packet.append(evidence)
    summary = {k: statistics.mean(row[k] for row in rows) for k in ('precision', 'recall', 'f1')}
    for field in ('diagnosis_correct', 'repair_correct'):
        values = [row[field] for row in rows]
        summary[field] = dict(correct=values.count(True), pending=values.count(None), cases=len(rows),
                              top1_accuracy=None if None in values else values.count(True)/len(rows))
    args.out.write_text(json.dumps(dict(summary=summary, cases=rows), indent=2) + '\n')
    if args.review_packet:
        args.review_packet.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
