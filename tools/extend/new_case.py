#!/usr/bin/env python3
"""Scaffold a new benchmark case from an unfixed and a fixed commit of a host app.

    python3 tools/extend/new_case.py <app> <case-id> --unfixed <rev> --fixed <rev> \
        --category latency --symptom "打开列表时响应变慢。" --scenario "列表页面操作"

<app> must be a host in hosts_patches/host-reconstruction.json, cloned at
hosts/<app> (tools/extend/reconstruct_clean_hosts.py) and containing both
revisions. The tool:
  1. writes cases/<id>/fix.patch (git diff --binary --full-index unfixed fixed);
  2. if neither variant's tree is reproducible from the upstream base plus the
     current patch series, appends the commits from the series tip to the
     unfixed revision as new numbered patches in hosts_patches/<app>/;
  3. records both variants' trees in host-reconstruction.json and creates the
     clean/ and clean-app/ refs via reconstruct_clean_hosts.py;
  4. writes case.json (status "candidate"), prompt.json and a HapRay testcase
     skeleton whose UI workload (testcase/*.workload.json) must be completed;
  5. derives groundtruth.json root causes (derive_groundtruth.py).
Then: complete the workload, review groundtruth.json, build both variants
(build_clean_cases.py), collect data and check the oracle (tools/collect/), and
set "status": "included" only once the performance oracle is met.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import derive_groundtruth  # noqa: E402
import reconstruct_clean_hosts  # noqa: E402

TESTCASE_PY = '''from pathlib import Path
import json
import importlib.util

from hapray.core.perf_testcase import PerfTestCase

# DeviceTest may load testcase files without a Python package context.
_spec = importlib.util.spec_from_file_location('external_workload_driver',
    Path(__file__).with_name('workload_driver.py'))
_driver_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_driver_module)
UI = _driver_module.UI


class {name}(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._plan = json.loads(Path(__file__).with_suffix('.workload.json').read_text())
        self._app_package = self._plan['bundle']
        self._app_name = {app_name!r}
        self.source_screen_width = 1260
        self.source_screen_height = 2844

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        ui = UI(self.driver.shell, self._app_package, self._plan['ability'])
        ui.run([{{'op': 'stop'}}, {{'op': 'launch'}}])
        ui.run(self._plan['setup'])
        ui.profiled(self.execute_performance_step,
            {scenario!r}, {duration}, self._plan['measured'])
        ui.run(self._plan['verify'])
'''


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def bundle_name(repo, rev):
    for path in ("AppScope/app.json5", "AppScope/app.json"):
        try:
            text = git(repo, "show", f"{rev}:{path}")
        except subprocess.CalledProcessError:
            continue
        m = re.search(r'"?bundleName"?\s*:\s*"([^"]+)"', text)
        if m:
            return m.group(1)
    return None


def series_tip(repo, host):
    series = sorted((ROOT / "hosts_patches" / host).glob("[0-9]*.patch"))
    if not series:
        return None, 0
    subject = series[-1].read_text(errors="replace").split("Subject: ", 1)[1].split("\n\n", 1)[0]
    subject = " ".join(subject.split()).split("] ", 1)[-1]
    for line in git(repo, "log", "--all", "--format=%H %s").splitlines():
        h, s = line.split(" ", 1)
        if s == subject:
            return h, len(series)
    raise SystemExit(f"series tip '{subject}' not found in hosts/{host}; run reconstruct_clean_hosts.py first")


def reachable_trees(repo, base, tip):
    revs = [r for r in (base, tip) if r]
    return set(git(repo, "log", "--format=%T", *revs).splitlines())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("host")
    ap.add_argument("case_id")
    ap.add_argument("--unfixed", required=True)
    ap.add_argument("--fixed", required=True)
    ap.add_argument("--category", required=True, choices=("latency", "cpu", "memory", "resource_retention", "network"))
    ap.add_argument("--symptom", required=True, help="user-visible symptom given to diagnosis tools")
    ap.add_argument("--scenario", required=True, help="short description of the measured UI scenario")
    ap.add_argument("--perf-scenario", action="append", default=[], help="HapRay scenario tag (repeatable)")
    ap.add_argument("--ability", default="EntryAbility")
    ap.add_argument("--module", default="entry")
    ap.add_argument("--duration", type=int, default=15, help="profiled step duration in seconds")
    ap.add_argument("--metric", default="hiperf_instructions", choices=("hiperf_instructions", "trace_cpu_ms"))
    ap.add_argument("--factor", type=float, default=1.2, help="oracle: unfixed >= factor * fixed")
    args = ap.parse_args()

    if not re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)+", args.case_id):
        raise SystemExit("case id must look like <app>_<short_description> in snake_case")
    case_dir = ROOT / "cases" / args.case_id
    if case_dir.exists():
        raise SystemExit(f"{case_dir} already exists")
    meta_path = ROOT / "hosts_patches" / "host-reconstruction.json"
    meta = json.loads(meta_path.read_text())
    if args.host not in meta["hosts"]:
        raise SystemExit(f"unknown host {args.host}; add the upstream app to host-reconstruction.json first")
    info, repo = meta["hosts"][args.host], ROOT / "hosts" / args.host
    unfixed, fixed = git(repo, "rev-parse", f"{args.unfixed}^{{commit}}"), git(repo, "rev-parse", f"{args.fixed}^{{commit}}")
    trees = {v: git(repo, "rev-parse", f"{c}^{{tree}}") for v, c in (("unfixed", unfixed), ("fixed", fixed))}

    # 2. reproducibility from public upstream + patch series
    base = git(repo, "rev-parse", info["upstream_base_commit"])
    tip, count = series_tip(repo, args.host)
    if not ({trees["unfixed"], trees["fixed"]} & reachable_trees(repo, base, tip)):
        start = tip or base
        if subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", start, unfixed]).returncode:
            raise SystemExit("neither variant is reproducible and the unfixed revision does not descend from the "
                             f"patch-series tip {start[:12]}; create the new commits on top of that tip")
        out = subprocess.check_output(["git", "-C", str(repo), "format-patch", "--binary", "--full-index",
                                       "--start-number", str(count + 1), "-o", str(ROOT / "hosts_patches" / args.host),
                                       f"{start}..{unfixed}"], text=True).split()
        print("appended to patch series:", *[Path(p).name for p in out])

    # 1. repair diff
    case_dir.mkdir(parents=True)
    patch = subprocess.check_output(["git", "-C", str(repo), "diff", "--binary", "--full-index", unfixed, fixed])
    (case_dir / "fix.patch").write_bytes(patch)

    # 3. reconstruction metadata and refs
    for v, c in (("unfixed", unfixed), ("fixed", fixed)):
        info["case_tags"][f"case/{args.case_id}/{v}"] = {"state": git(repo, "log", "-1", "--format=%s", c), "tree": trees[v]}
    meta["totals"]["case_tags"] = sum(len(h["case_tags"]) for h in meta["hosts"].values())
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    reconstruct_clean_hosts.reconstruct(args.host, info)

    # 4. case metadata, prompt, testcase skeleton
    bundle = bundle_name(repo, unfixed)
    app_short = args.host
    existing = sorted((ROOT / "cases").glob(f"*/testcase/*_{app_short}_*.py"))
    number = 10 * (len(existing) + 1)
    tc_name = f"PerfLoad_{app_short}_{number:04d}"
    tdir = case_dir / "testcase"
    tdir.mkdir()
    drivers = sorted((ROOT / "cases").glob("*/testcase/workload_driver.py"))
    counts = {}
    for d in drivers:
        counts.setdefault(d.read_bytes(), d)
    common = max(counts, key=lambda b: sum(d.read_bytes() == b for d in drivers))
    (tdir / "workload_driver.py").write_bytes(common)
    (tdir / f"{tc_name}.py").write_text(TESTCASE_PY.format(name=tc_name, app_name=args.host,
                                                           scenario=args.scenario, duration=args.duration))
    (tdir / f"{tc_name}.json").write_text(json.dumps({
        "description": args.case_id, "environment": [{"type": "device", "label": "phone"}],
        "driver": {"type": "DeviceTest", "py_file": [f"{tc_name}.py"]}, "kits": []}, indent=4) + "\n")
    (tdir / f"{tc_name}.workload.json").write_text(json.dumps({
        "bundle": bundle, "ability": args.ability, "description": args.scenario,
        "setup": [], "measured": [{"op": "launch"}], "verify": [],
        "_todo": "Replace with the UI actions that reach the faulty business path; see existing cases."},
        indent=2, ensure_ascii=False) + "\n")
    host_name = next((json.loads(p.read_text())["host_app"]["name"] for p in (ROOT / "cases").glob("*/case.json")
                      if json.loads(p.read_text())["host_app"]["local_path"] == f"hosts/{args.host}"), args.host)
    case = {
        "id": args.case_id, "status": "candidate",
        "host_app": {"name": host_name, "repository": info["upstream_repository"],
                     "upstream_base_commit": info["upstream_base_commit"], "bundle_name": bundle,
                     "local_path": f"hosts/{args.host}"},
        "category": args.category, "perf_scenarios": args.perf_scenario,
        "source": {v: {"ref": f"clean-app/{args.case_id}/{v}", "tree": trees[v], "production_patches": [],
                       "reference_unsigned_hap_sha256": None} for v in ("unfixed", "fixed")},
        "testcase": {"name": tc_name, "py_file": f"testcase/{tc_name}.py", "descriptor": f"testcase/{tc_name}.json",
                     "install_dir": f"perf_testing/hapray/testcases/{bundle}", "driver": "DeviceTest",
                     "module": args.module, "ability": args.ability, "trigger": "external_ui",
                     "workload": f"testcase/{tc_name}.workload.json"},
        "collection": {"config": "../collection.yaml", "modes": ["htrace", "hiperf"],
                       "step_duration_s": args.duration, "rounds": 3},
    }
    (case_dir / "case.json").write_text(json.dumps(case, indent=2, ensure_ascii=False) + "\n")
    (case_dir / "prompt.json").write_text(json.dumps({
        "case": args.case_id, "bundle_name": bundle, "ability": args.ability, "symptom": args.symptom,
        "scenario": args.scenario, "perf_scenarios": args.perf_scenario}, indent=2, ensure_ascii=False) + "\n")

    # 5. groundtruth
    gt = {"case": args.case_id, "status": "candidate", "mechanism": "TODO: describe the root-cause mechanism",
          "fix_summary": git(repo, "log", "-1", "--format=%B", fixed),
          "root_causes": derive_groundtruth.derive(case_dir, ROOT / "hosts"),
          "performance_oracle": {"metric": args.metric,
                                 "comparison": f"unfixed >= {args.factor} * fixed over >= 3 rounds per variant",
                                 "evidence": {}}}
    (case_dir / "groundtruth.json").write_text(json.dumps(gt, indent=2, ensure_ascii=False) + "\n")
    print(f"created {case_dir.relative_to(ROOT)} ({len(gt['root_causes'])} derived root-cause location(s))")
    print("next: complete testcase/*.workload.json and groundtruth.json, then build, collect and check the oracle")


if __name__ == "__main__":
    main()