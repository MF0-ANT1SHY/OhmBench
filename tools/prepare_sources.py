#!/usr/bin/env python3
"""Reconstruct the unfixed and fixed source of each case from its public upstream.

For every case: clone host_app.repository into host_app.local_path (once per app),
check out host_app.upstream_base_commit, apply source.patch (unfixed), then
fix.patch (fixed). Each tree is checked against case.json and tagged
case/<case-id>/<variant>.
"""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = ["-c", "user.name=OhmBench", "-c", "user.email=benchmark@localhost"]


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def prepare(case):
    cid, host, source = case["id"], case["host_app"], case["source"]
    repo = ROOT / host["local_path"]
    if not repo.exists():
        repo.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", host["repository"], str(repo)], check=True)
    if git(repo, "status", "--porcelain"):
        raise RuntimeError(f"refusing to modify a dirty repository: {repo}")
    git(repo, "checkout", "-q", "--detach", host["upstream_base_commit"])
    for variant, patch in (("unfixed", source["patch"]), ("fixed", source["fix_patch"])):
        git(repo, "apply", "--index", str(ROOT / "cases" / cid / patch))
        tree = git(repo, "write-tree")
        if tree != source[variant]["tree"]:
            raise RuntimeError(f"{cid}/{variant}: tree {tree} != {source[variant]['tree']}")
        git(repo, *IDENTITY, "commit", "-q", "--no-verify", "-m", f"{cid}: {variant}")
        git(repo, "tag", "-f", f"case/{cid}/{variant}", "HEAD")
        print(f"{cid}/{variant}: {tree}", flush=True)
    git(repo, "checkout", "-q", "--detach", host["upstream_base_commit"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", nargs="*", help="case ids (default: all)")
    args = parser.parse_args()
    failed = False
    for path in sorted((ROOT / "cases").glob("*/case.json")):
        case = json.loads(path.read_text())
        if args.cases and case["id"] not in args.cases:
            continue
        try:
            prepare(case)
        except Exception as exc:
            print(f"{case['id']}: FAILED {exc}", flush=True)
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
