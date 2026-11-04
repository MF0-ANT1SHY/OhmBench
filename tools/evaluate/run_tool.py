#!/usr/bin/env python3
"""Run a diagnosis tool on prepared case inputs and record its cost.

    python3 tools/evaluate/run_tool.py --inputs inputs/ --out runs/mytool -- \
        mytool --input {input_dir} --output {prediction}

Placeholders in the command: {case}, {input_dir}, {prediction}, {output_dir}.
The same values are exported as OHM_CASE, OHM_INPUT_DIR, OHM_PREDICTION and
OHM_OUTPUT_DIR. The tool must write its prediction JSON to {prediction}.

Recorded per case in <out>/<case>/run.json:
  wall_time_s     elapsed wall-clock time of the tool process
  cpu_time_s      user+system CPU time of the tool and its waited-for children
  peak_rss_bytes  peak resident memory of the tool's local process tree, sampled
                  from /proc every --sample-interval seconds (Linux); elsewhere the
                  largest single child reported by getrusage
  tokens          LLM token usage, read from the prediction's "usage" object or from
                  {output_dir}/usage.json ({"input_tokens", "output_tokens"}); null if
                  the tool does not report it (never estimated)
Predictions are copied to <out>/predictions/<case>.json for score.py.
"""
import argparse
import json
import os
import resource
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

PAGE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096


def tree_rss(root_pid):
    children, rss = {}, {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat") as f:
                parts = f.read().rsplit(")", 1)[1].split()
            children.setdefault(int(parts[1]), []).append(int(d))
            rss[int(d)] = int(parts[21]) * PAGE
        except (OSError, IndexError, ValueError):
            continue
    total, stack = 0, [root_pid]
    while stack:
        pid = stack.pop()
        total += rss.get(pid, 0)
        stack.extend(children.get(pid, []))
    return total


def run_one(cmd, env, timeout, interval):
    have_proc = Path("/proc/self/stat").exists()
    peak, stop = [0], threading.Event()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.monotonic()
    proc = subprocess.Popen(cmd, env=env)

    def sample():
        while not stop.is_set():
            if have_proc:
                peak[0] = max(peak[0], tree_rss(proc.pid))
            stop.wait(interval)

    t = threading.Thread(target=sample, daemon=True)
    t.start()
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        code = "timeout"
    wall = time.monotonic() - start
    stop.set()
    t.join()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    if not peak[0]:
        peak[0] = after.ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    return code, wall, cpu, peak[0]


def tokens(prediction, output_dir):
    usage = None
    if prediction.exists():
        try:
            usage = json.loads(prediction.read_text()).get("usage")
        except (json.JSONDecodeError, AttributeError):
            usage = None
    if usage is None and (output_dir / "usage.json").exists():
        usage = json.loads((output_dir / "usage.json").read_text())
    if not usage:
        return None
    i, o = usage.get("input_tokens"), usage.get("output_tokens")
    total = usage.get("total_tokens")
    if total is None and (i is not None or o is not None):
        total = (i or 0) + (o or 0)
    return {"input": i, "output": o, "total": total}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inputs", type=Path, required=True, help="directory written by prepare_input.py")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cases", nargs="*", help="default: every case directory under --inputs")
    ap.add_argument("--timeout", type=float, default=None, help="per-case timeout in seconds")
    ap.add_argument("--sample-interval", type=float, default=0.2)
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    cmd = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not cmd:
        ap.error("missing tool command after --")
    cases = args.cases or sorted(p.name for p in args.inputs.iterdir() if (p / "prompt.json").exists())
    (args.out / "predictions").mkdir(parents=True, exist_ok=True)
    for cid in cases:
        out_dir = (args.out / cid).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        pred = out_dir / "prediction.json"
        if pred.exists():
            pred.unlink()
        values = {"case": cid, "input_dir": str((args.inputs / cid).resolve()),
                  "prediction": str(pred), "output_dir": str(out_dir)}
        argv = [a.format(**values) for a in cmd]
        env = {**os.environ, "OHM_CASE": cid, "OHM_INPUT_DIR": values["input_dir"],
               "OHM_PREDICTION": str(pred), "OHM_OUTPUT_DIR": str(out_dir)}
        code, wall, cpu, peak = run_one(argv, env, args.timeout, args.sample_interval)
        rec = {"case": cid, "command": argv, "exit_code": code, "wall_time_s": wall, "cpu_time_s": cpu,
               "peak_rss_bytes": peak, "tokens": tokens(pred, out_dir), "prediction_written": pred.exists()}
        (out_dir / "run.json").write_text(json.dumps(rec, indent=2) + "\n")
        if pred.exists():
            shutil.copyfile(pred, args.out / "predictions" / f"{cid}.json")
        print(f"{cid}: exit={code} wall={wall:.1f}s peak_rss={peak / 2**20:.0f}MiB tokens={rec['tokens']}", flush=True)


if __name__ == "__main__":
    main()