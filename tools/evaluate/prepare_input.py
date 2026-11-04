#!/usr/bin/env python3
"""Prepare the blind input a diagnosis tool may see, one folder per case.

<out>/<case>/
  app.hap        unfixed HAP, unsigned (from --binaries; see tools/fetch_binaries.py)
  prompt.json    symptom prompt (cases/<id>/prompt.json)
  prompt.md      prompt text including the required output format
  testcase/      neutral HapRay testcase and UI workload
  hapray/        optional: HapRay dynamic data of the unfixed variant (--collected)
  source/        optional: unfixed source tree without git history (--include-source)

Never copied: case.json, groundtruth.json, fix.patch, fixed builds, hosts_patches/.
"""
import argparse
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "tools" / "evaluate" / "prompt_template.md"


def render(prompt):
    return TEMPLATE.read_text().format(**prompt, perf_scenarios_text="、".join(prompt.get("perf_scenarios", [])))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--cases", nargs="*", help="default: every included case")
    ap.add_argument("--binaries", type=Path, default=ROOT / "artifacts" / "binaries",
                    help="directory with <case>.unfixed.hap")
    ap.add_argument("--collected", type=Path, help="collect_case.py output root (<root>/<case>/unfixed/)")
    ap.add_argument("--include-source", action="store_true", help="also export the unfixed source (needs hosts/)")
    args = ap.parse_args()
    for case_dir in sorted((ROOT / "cases").iterdir()):
        prompt_path = case_dir / "prompt.json"
        if not prompt_path.exists() or (args.cases and case_dir.name not in args.cases):
            continue
        case = json.loads((case_dir / "case.json").read_text())
        if not args.cases and case["status"] != "included":
            continue
        dest = args.out / case_dir.name
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        prompt = json.loads(prompt_path.read_text())
        shutil.copyfile(prompt_path, dest / "prompt.json")
        (dest / "prompt.md").write_text(render(prompt))
        shutil.copytree(case_dir / "testcase", dest / "testcase")
        hap = args.binaries / f"{case_dir.name}.unfixed.hap"
        if hap.exists():
            shutil.copyfile(hap, dest / "app.hap")
        else:
            print(f"{case_dir.name}: warning: {hap} not found; app.hap omitted")
        if args.collected:
            src = args.collected / case_dir.name / "unfixed"
            if src.exists():
                shutil.copytree(src, dest / "hapray")
            else:
                print(f"{case_dir.name}: warning: no collected data at {src}")
        if args.include_source:
            repo = ROOT / case["host_app"]["local_path"]
            blob = subprocess.check_output(["git", "-C", str(repo), "archive", "--format=tar",
                                            case["source"]["unfixed"]["ref"]])
            with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
                tar.extractall(dest / "source")
        print(f"{case_dir.name}: {dest}")


if __name__ == "__main__":
    main()