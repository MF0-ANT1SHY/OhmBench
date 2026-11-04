#!/usr/bin/env python3
"""Score diagnosis predictions against groundtruth: recall, precision, F1 and cost.

Inputs
  --predictions DIR   one ``<case-id>.json`` per case (see prediction.schema.json)
  --runs DIR          optional; ``<case-id>/run.json`` files written by run_tool.py
                      (wall time, CPU time, peak memory, token usage)

Matching (default ``--level function``)
  A suspect matches a groundtruth location when its file matches (path suffix on
  segment boundaries, extensions ignored) and either its symbol names the same
  function/field/constant or its line range overlaps the location's lines.
  ``--level file`` only requires the file to match. ``aliases`` of a root cause
  count as that root cause.

Per case
  precision = suspects matching any primary/related location (or alias) / suspects
  recall    = primary root causes matched by at least one suspect / primary root causes
  f1        = harmonic mean of the two (0 if both are 0)
Only the top ``--top-k`` suspects by rank are considered (default 5). Cases
without a prediction file score 0. Macro averages are over cases; micro
averages pool suspects and root causes over all cases.
"""
import argparse
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXT = re.compile(r"\.(ets|ts|js|abc|map|json5?)$")


def norm_path(p):
    if not p:
        return []
    p = str(p).replace("\\", "/").strip().strip("&")
    # ABC record names: "&entry/src/main/ets/pages/Index&", "entry|entry|1.0.0|src/main/ets/pages/Index.ts"
    if re.search(r"[|&]", p):
        p = re.split(r"[|&]", p)[-1] or p
    p = EXT.sub("", p.lstrip("./"))
    return [s for s in p.split("/") if s and s != "."]


def path_match(pred, gt):
    """Trailing path segments agree: >= 2 segments, or the whole of a 1-segment prediction."""
    a, b = norm_path(pred), norm_path(gt)
    if not a or not b:
        return False
    k = 0
    while k < min(len(a), len(b)) and a[-1 - k] == b[-1 - k]:
        k += 1
    return k >= 2 or (k == 1 and (len(a) == 1 or len(b) == 1))


def names(s):
    if not s:
        return set()
    s = str(s)
    out = {s} | {p for p in re.split(r"[.:#/\s();,]+", s) if p}
    out.update(re.findall(r"[\"']([^\"']+)[\"']", s))
    return out


def overlap(a, b):
    return bool(a and b) and a[0] <= b[1] and b[0] <= a[1]


def locations(rc):
    yield rc
    yield from rc.get("aliases", [])


def suspect_matches(s, loc, level):
    if not path_match(s.get("file"), loc.get("file")):
        return False
    if level == "file":
        return True
    gt_sym = loc.get("symbol")
    pred_names = names(s.get("symbol")) | names(s.get("function"))
    if gt_sym:
        gt_names = names(gt_sym)
        key = gt_sym if loc.get("kind", "function") == "function" else None
        if (key and key in pred_names) or gt_sym in pred_names or (
                loc.get("kind") in ("module", "class_member", "constant") and gt_names & pred_names - {"PersistentStorage", "persistProp"}):
            return True
    if s.get("line_start") is not None:
        lines = [int(s["line_start"]), int(s.get("line_end") or s["line_start"])]
        span = loc.get("scope_lines") if loc.get("kind") == "function" and loc.get("scope_lines") else loc.get("changed_lines")
        return overlap(lines, span)
    return False


def score_case(pred, gt, level, top_k):
    suspects = sorted(pred.get("suspects", []), key=lambda s: s.get("rank", 10**9))[:top_k]
    roots = gt["root_causes"]
    primary = [r for r in roots if r["role"] == "primary"]
    correct = [any(suspect_matches(s, loc, level) for r in roots for loc in locations(r)) for s in suspects]
    found = [r["id"] for r in primary if any(suspect_matches(s, loc, level) for s in suspects for loc in locations(r))]
    p = sum(correct) / len(suspects) if suspects else 0.0
    r = len(found) / len(primary) if primary else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"suspects": len(suspects), "correct_suspects": sum(correct), "primary": len(primary),
            "primary_found": found, "precision": p, "recall": r, "f1": f}


def summarize(values):
    values = [v for v in values if isinstance(v, (int, float))]
    if not values:
        return None
    return {"mean": statistics.fmean(values), "median": statistics.median(values), "total": sum(values), "n": len(values)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--predictions", type=Path, required=True)
    ap.add_argument("--runs", type=Path, help="run_tool.py output directory")
    ap.add_argument("--cases", nargs="*", help="default: every included case")
    ap.add_argument("--level", choices=("function", "file"), default="function")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--output", type=Path, help="write the full JSON report here")
    args = ap.parse_args()
    rows = []
    for gt_path in sorted((ROOT / "cases").glob("*/groundtruth.json")):
        gt = json.loads(gt_path.read_text())
        cid = gt["case"]
        if (args.cases and cid not in args.cases) or (not args.cases and gt.get("status") != "included"):
            continue
        pf = args.predictions / f"{cid}.json"
        pred = json.loads(pf.read_text()) if pf.exists() else {"suspects": []}
        row = {"case": cid, "prediction_present": pf.exists(), **score_case(pred, gt, args.level, args.top_k)}
        run = (args.runs / cid / "run.json") if args.runs else None
        if run and run.exists():
            rec = json.loads(run.read_text())
            row.update({k: rec.get(k) for k in ("wall_time_s", "cpu_time_s", "peak_rss_bytes", "exit_code")})
            tok = rec.get("tokens") or {}
            row.update({"input_tokens": tok.get("input"), "output_tokens": tok.get("output"), "total_tokens": tok.get("total")})
        rows.append(row)
    s = sum(r["suspects"] for r in rows)
    c = sum(r["correct_suspects"] for r in rows)
    pa = sum(r["primary"] for r in rows)
    fo = sum(len(r["primary_found"]) for r in rows)
    mp, mr = (c / s if s else 0.0), (fo / pa if pa else 0.0)
    report = {
        "level": args.level, "top_k": args.top_k, "cases": len(rows),
        "macro": {k: statistics.fmean(r[k] for r in rows) if rows else 0.0 for k in ("precision", "recall", "f1")},
        "micro": {"precision": mp, "recall": mr, "f1": 2 * mp * mr / (mp + mr) if mp + mr else 0.0},
        "cost": {k: summarize([r.get(k) for r in rows]) for k in
                 ("wall_time_s", "cpu_time_s", "peak_rss_bytes", "input_tokens", "output_tokens", "total_tokens")},
        "rows": rows,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print("| case | P | R | F1 | time (s) | peak RSS (MiB) | tokens |\n|---|---|---|---|---|---|---|")
    for r in rows:
        mem = f"{r['peak_rss_bytes'] / 2**20:.0f}" if r.get("peak_rss_bytes") else "-"
        t = f"{r['wall_time_s']:.1f}" if r.get("wall_time_s") is not None else "-"
        print(f"| {r['case']} | {r['precision']:.2f} | {r['recall']:.2f} | {r['f1']:.2f} | {t} | {mem} | {r.get('total_tokens') or '-'} |")
    m, mi = report["macro"], report["micro"]
    print(f"\nmacro P/R/F1 = {m['precision']:.3f} / {m['recall']:.3f} / {m['f1']:.3f}; "
          f"micro P/R/F1 = {mi['precision']:.3f} / {mi['recall']:.3f} / {mi['f1']:.3f} over {len(rows)} cases")


if __name__ == "__main__":
    main()