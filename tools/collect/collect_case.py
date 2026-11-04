#!/usr/bin/env python3
"""Collect HapRay dynamic data for one case variant on a locally attached device.

The case's testcase files are installed into an ArkAnalyzer-HapRay checkout and
HapRay's own ``perf`` command collects the data, so the result is exactly a
HapRay report tree (``<testcase>_round<N>/{hiperf,htrace}/step*/...`` and the
merged ``<testcase>/report/``) plus HapRay's ``hapray-tool-result.json``.

    python3 tools/collect/collect_case.py <case-id> --variant unfixed \
        --hapray /path/to/ArkAnalyzer-HapRay --out collected/

Preconditions (not automated; see README "Collecting dynamic data"):
  * one device attached and visible to ``hdc``;
  * the signed variant is installed (``hdc install``);
  * the case's workload data is prepared (tools/collect/fixtures/);
  * HapRay's own environment is set up (``perf_testing`` dependencies).
Output: <out>/<case>/<variant>/ with the HapRay report tree and collection.json.
"""
import argparse
import datetime
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_hapray_data import validate  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case")
    ap.add_argument("--variant", choices=("unfixed", "fixed"), default="unfixed")
    ap.add_argument("--hapray", type=Path, required=True, help="ArkAnalyzer-HapRay checkout (or release runtime root)")
    ap.add_argument("--hapray-cmd", default="uv run python -m scripts.main",
                    help="command that starts the HapRay CLI, run inside --hapray-cwd")
    ap.add_argument("--hapray-cwd", help="working directory for --hapray-cmd (default <hapray>/perf_testing)")
    ap.add_argument("--testcases-dir", type=Path,
                    help="HapRay testcases directory (default <hapray>/perf_testing/hapray/testcases)")
    ap.add_argument("--rounds", type=int, help="default: case.json#collection.rounds")
    ap.add_argument("--device", help="device serial, passed to HapRay --devices")
    ap.add_argument("--memory", action="store_true", help="also pass --memory (nativehook) to HapRay")
    ap.add_argument("--out", type=Path, default=ROOT / "collected")
    ap.add_argument("--dry-run", action="store_true", help="print the actions without running HapRay")
    ap.add_argument("extra", nargs="*", help="extra arguments appended to the HapRay perf command (after --)")
    args = ap.parse_args()

    case_dir = ROOT / "cases" / args.case
    case = json.loads((case_dir / "case.json").read_text())
    tc, bundle = case["testcase"], case["host_app"]["bundle_name"]
    rounds = args.rounds or case["collection"].get("rounds", 3)
    tdir = args.testcases_dir or args.hapray / "perf_testing" / "hapray" / "testcases"
    install = tdir / bundle
    cwd = Path(args.hapray_cwd) if args.hapray_cwd else args.hapray / "perf_testing"
    dest = (args.out / args.case / args.variant).resolve()
    result_file = dest / "hapray-tool-result.json"
    cmd = shlex.split(args.hapray_cmd) + ["perf", "--run_testcases", tc["name"], "--round", str(rounds),
                                          "--result-file", str(result_file)]
    if args.device:
        cmd += ["--devices", args.device]
    if args.memory:
        cmd.append("--memory")
    cmd += args.extra
    print(f"install testcase: {case_dir / 'testcase'} -> {install}")
    print(f"run in {cwd}: {shlex.join(cmd)}")
    if args.dry_run:
        return 0
    install.mkdir(parents=True, exist_ok=True)
    for f in (case_dir / "testcase").iterdir():
        shutil.copyfile(f, install / f.name)
    if dest.exists():
        raise SystemExit(f"refusing to overwrite existing collection: {dest}")
    dest.mkdir(parents=True)
    started = datetime.datetime.now().astimezone().isoformat()
    code = subprocess.run(cmd, cwd=cwd).returncode
    if not result_file.exists():
        raise SystemExit(f"HapRay did not write {result_file} (exit {code})")
    result = json.loads(result_file.read_text())
    reports = Path(result.get("outputs", {}).get("reports_path") or "")
    if not result.get("success") or not reports.is_dir():
        raise SystemExit(f"HapRay perf failed: exit={result.get('exit_code')} error={result.get('error')}")
    for item in reports.iterdir():
        target = dest / item.name
        (shutil.copytree if item.is_dir() else shutil.copyfile)(item, target)
    try:
        version = subprocess.check_output(["git", "-C", str(args.hapray), "describe", "--always", "--tags"],
                                          text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        version = None
    manifest = {"case": args.case, "variant": args.variant, "bundle_name": bundle, "testcase": tc["name"],
                "rounds": rounds, "hapray_version": version, "hapray_command": cmd, "started": started,
                "finished": datetime.datetime.now().astimezone().isoformat(), "hapray_reports_path": str(reports)}
    (dest / "collection.json").write_text(json.dumps(manifest, indent=2) + "\n")
    problems = validate(dest)
    print(f"collected {args.case}/{args.variant} -> {dest}")
    for p in problems:
        print(f"  warning: {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())