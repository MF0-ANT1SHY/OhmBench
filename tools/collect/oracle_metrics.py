#!/usr/bin/env python3
"""Compute oracle metrics from collected HapRay data and check the performance oracle.

Supported metrics (groundtruth.json#performance_oracle.metric):
  hiperf_instructions  sum of hiperf sample periods (event_count) of the app
                       process, over every step's hiperf/step*/perf.db
  trace_cpu_ms         CPU time of the app process from scheduler slices in
                       htrace/step*/trace.db
Each HapRay round directory yields one value. The oracle ``unfixed >= X * fixed``
is checked on the median of the rounds and on every rank-paired round.

    python3 tools/collect/oracle_metrics.py <case-id> --collected collected/
    python3 tools/collect/oracle_metrics.py --metric hiperf_instructions \
        --bundle com.example.app <hapray-round-or-report-dir>
Other oracle metrics (PSS, latency, payload bytes) were measured with external
collectors that are not part of this repository; they are reported as unsupported.
"""
import argparse
import json
import re
import sqlite3
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_hapray_data import rounds  # noqa: E402

SUPPORTED = ("hiperf_instructions", "trace_cpu_ms")


def name_matches(name, bundle):
    # Kernel thread/process names are truncated to their last 15 characters.
    return bool(name) and (name == bundle or (len(name) >= 15 and bundle.endswith(name)) or bundle.startswith(name))


def app_instructions(round_dir, bundle):
    total, seen = 0, False
    for db in sorted(Path(round_dir).glob("hiperf/step*/perf.db")):
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        pids = [pid for tid, pid, name in c.execute("select thread_id, process_id, thread_name from perf_thread")
                if tid == pid and name_matches(name, bundle)]
        if pids:
            q = ",".join("?" * len(pids))
            total += c.execute(f"select coalesce(sum(s.event_count),0) from perf_sample s join perf_thread t "
                               f"on s.thread_id = t.thread_id where t.process_id in ({q})", pids).fetchone()[0]
            seen = True
        c.close()
    return total if seen else None


def app_cpu_ms(round_dir, bundle):
    total, seen = 0, False
    for db in sorted(Path(round_dir).glob("htrace/step*/trace.db")):
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cols = [r[1] for r in c.execute("pragma table_info(process)")]
        key = "ipid" if "ipid" in cols else "id"
        ipids = [ip for ip, name in c.execute(f"select {key}, name from process") if name_matches(name, bundle)]
        if ipids:
            q = ",".join("?" * len(ipids))
            ns = c.execute(f"select coalesce(sum(dur),0) from sched_slice where ipid in ({q}) and dur > 0", ipids).fetchone()[0]
            total += ns / 1e6
            seen = True
        c.close()
    return total if seen else None


METRICS = {"hiperf_instructions": app_instructions, "trace_cpu_ms": app_cpu_ms}


def round_values(root, metric, bundle):
    vals = []
    for r in rounds(root):
        v = METRICS[metric](r, bundle)
        if v is not None:
            vals.append((str(r.relative_to(root)) if r != Path(root) else ".", v))
    return vals


def check(cid, collected):
    gt = json.loads((ROOT / "cases" / cid / "groundtruth.json").read_text())
    case = json.loads((ROOT / "cases" / cid / "case.json").read_text())
    oracle, bundle = gt["performance_oracle"], case["host_app"]["bundle_name"]
    metric = oracle["metric"]
    if metric not in SUPPORTED:
        return {"case": cid, "metric": metric, "status": "unsupported"}
    m = re.match(r"\s*unfixed\s*>=\s*([\d.]+)\s*\*\s*fixed", oracle["comparison"])
    factor = float(m.group(1))
    vals = {v: [x for _, x in round_values(collected / cid / v, metric, bundle)] for v in ("unfixed", "fixed")}
    if not vals["unfixed"] or not vals["fixed"]:
        return {"case": cid, "metric": metric, "status": "no_data", "values": vals}
    mu, mf = statistics.median(vals["unfixed"]), statistics.median(vals["fixed"])
    pairs = [u / f if f else float("inf") for u, f in zip(sorted(vals["unfixed"]), sorted(vals["fixed"]))]
    need = min(len(vals["unfixed"]), len(vals["fixed"])) >= 3
    ok = need and mf > 0 and mu / mf >= factor and all(p >= factor for p in pairs)
    return {"case": cid, "metric": metric, "required_factor": factor, "values": vals,
            "median_ratio": mu / mf if mf else None, "paired_ratios": pairs,
            "status": "pass" if ok else ("insufficient_rounds" if not need else "fail"),
            "reference_median_ratio": oracle.get("evidence", {}).get("median_ratio")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="*", help="case ids, or data directories with --metric/--bundle")
    ap.add_argument("--collected", type=Path, default=ROOT / "collected")
    ap.add_argument("--metric", choices=SUPPORTED)
    ap.add_argument("--bundle")
    args = ap.parse_args()
    if args.metric:
        if not args.bundle:
            ap.error("--metric needs --bundle")
        for d in args.targets:
            for r, v in round_values(Path(d), args.metric, args.bundle):
                print(f"{d}/{r}: {args.metric} = {v}")
        return 0
    cases = args.targets or sorted(p.name for p in (args.collected).iterdir() if p.is_dir())
    for cid in cases:
        print(json.dumps(check(cid, args.collected), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())