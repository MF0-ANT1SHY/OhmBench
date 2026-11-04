#!/usr/bin/env python3
"""Check that a directory is a HapRay dynamic-data object.

Accepted layouts (both produced by HapRay ``perf``):
  * a ``reports/<timestamp>/`` tree: ``<testcase>_round<N>/`` round directories
    plus the merged ``<testcase>/report/``;
  * a single round/case directory with ``hiperf/``, ``htrace/`` and ``report/``.

Checks: every round has ``hiperf/step*/`` and/or ``htrace/step*/`` with raw
(perf.data / trace.htrace) or converted (perf.db / trace.db) data; a
``report/summary.json`` exists; ``hapray-tool-result.json``, when present,
satisfies HapRay tool-result v1 (schema_version, tool_id, success, exit_code,
outputs, error).
"""
import argparse
import json
from pathlib import Path

TOOL_IDS = {"perf_testing", "optimization_detector", "static_analyzer", "symbol_recovery"}


def rounds(root):
    root = Path(root)
    return sorted({p.parent for p in root.rglob("*") if p.is_dir() and p.name in ("hiperf", "htrace")})


def steps(round_dir, kind):
    return sorted(p for p in (Path(round_dir) / kind).glob("step*") if p.is_dir())


def validate(root):
    root, problems = Path(root), []
    rs = rounds(root)
    if not rs:
        problems.append("no round directory with hiperf/ or htrace/")
    for r in rs:
        for kind, files in (("hiperf", ("perf.data", "perf.db")), ("htrace", ("trace.htrace", "trace.db"))):
            st = steps(r, kind)
            if (r / kind).exists() and not st:
                problems.append(f"{r.relative_to(root)}/{kind}: no step directories")
            for s in st:
                if not any((s / f).exists() for f in files):
                    problems.append(f"{s.relative_to(root)}: none of {files}")
    if not list(root.rglob("report/summary.json")):
        problems.append("no report/summary.json")
    for res in root.rglob("hapray-tool-result.json"):
        try:
            d = json.loads(res.read_text())
        except json.JSONDecodeError as e:
            problems.append(f"{res.relative_to(root)}: invalid JSON ({e})")
            continue
        missing = [k for k in ("schema_version", "tool_id", "success", "exit_code", "outputs", "error") if k not in d]
        if missing:
            problems.append(f"{res.relative_to(root)}: missing {missing}")
        if d.get("schema_version") != "1.0" or d.get("tool_id") not in TOOL_IDS:
            problems.append(f"{res.relative_to(root)}: not a HapRay tool-result v1 contract")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="+", type=Path)
    args = ap.parse_args()
    bad = 0
    for d in args.dirs:
        problems = validate(d)
        print(f"{d}: {'OK' if not problems else 'INVALID'} ({len(rounds(d))} round dir(s))")
        for p in problems:
            print(f"  - {p}")
        bad += bool(problems)
    return int(bad > 0)


if __name__ == "__main__":
    raise SystemExit(main())