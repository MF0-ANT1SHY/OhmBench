#!/usr/bin/env python3
"""Obtain the case HAPs listed in data/binaries.json and verify their SHA-256.

    python3 tools/fetch_binaries.py                 # all available included cases
    python3 tools/fetch_binaries.py --variant unfixed --cases <id> ...
    python3 tools/fetch_binaries.py --from-build artifacts/clean   # use local builds

HAPs are unsigned release builds; sign them with your own identity before
installing. Binaries of host apps without an open-source licence are not
redistributed ("published": false); build them with tools/extend/build_clean_cases.py
and import them with --from-build, which checks the same reference hash.
Output: artifacts/binaries/<case>.<variant>.hap
"""
import argparse
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", nargs="*")
    ap.add_argument("--variant", choices=("unfixed", "fixed", "both"), default="both")
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "binaries")
    ap.add_argument("--from-build", type=Path, help="build_clean_cases.py output (<dir>/<case>/<variant>/app-unsigned.hap)")
    args = ap.parse_args()
    manifest = json.loads((ROOT / "data" / "binaries.json").read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    failed = 0
    for a in manifest["assets"]:
        if (args.cases and a["case"] not in args.cases) or args.variant not in ("both", a["variant"]):
            continue
        dest = args.out / a["file"]
        if dest.exists() and sha256(dest) == a["sha256"]:
            print(f"ok       {a['file']}")
            continue
        if args.from_build:
            src = args.from_build / a["case"] / a["variant"] / "app-unsigned.hap"
            if not src.exists():
                print(f"missing  {a['file']}: no local build at {src}")
                failed += 1
                continue
            shutil.copyfile(src, dest)
        elif a["published"]:
            url = f"{manifest['download_base']}/{a['file']}"
            print(f"download {url}")
            with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
                shutil.copyfileobj(r, f)
        else:
            print(f"skip     {a['file']}: {a['reason']}")
            continue
        actual = sha256(dest)
        if actual != a["sha256"]:
            print(f"MISMATCH {a['file']}: {actual} != {a['sha256']}"
                  + (" (local builds are not byte-reproducible; trees are)" if args.from_build else ""))
            failed += 1
        else:
            print(f"ok       {a['file']}")
    return int(failed > 0)


if __name__ == "__main__":
    raise SystemExit(main())