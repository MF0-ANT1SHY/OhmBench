# Data

## Repository layout

```
cases/
  collection.yaml          reference HapRay/hiprofiler collection configuration
  <case-id>/
    case.json              metadata: status, host app, source trees, testcase, collection
    prompt.json            prompt given to a diagnosis tool
    groundtruth.json       oracle: mechanism, root-cause locations, performance oracle
    fix.patch              repair diff, unfixed -> fixed
    testcase/              HapRay testcase, UI workload plan and shared UI driver
hosts_patches/
  host-reconstruction.json expected source tree of every case variant
  <app>/0001-*.patch ...   patch series on top of the upstream base commit
  <app>/<case-id>-<variant>.patch   build/run adaptation of one case variant
docs/                      documentation linked from README.md
tools/                     reconstruction, build and bytecode audit
```

## Source + patch

The source of every variant is reconstructed from the **public upstream repository** plus the
patches in this repository:

1. `hosts_patches/<app>/0001-*.patch …` — a `git am` series on the upstream base commit;
2. `cases/<id>/fix.patch` — the repair diff between the two variants of a case;
3. `hosts_patches/<app>/<case-id>-<variant>.patch` — the adaptation of one variant (listed in its
   `production_patches`), needed for the app to install and run its workload on a device; it is
   the diff from `tree` to `app_tree`, applied with `git apply`;
4. `hosts_patches/host-reconstruction.json` — the git tree hash of every variant, before
   (`tree`) and after (`app_tree`) production adaptations.

```bash
python3 tools/reconstruct_clean_hosts.py     # -> hosts/<app> with clean/<id>/<variant> and clean-app/... refs
```

Every reconstructed tree is verified against its recorded hash. All 60 variants (120 refs)
reconstruct from the public upstreams.

## Prompt

`prompt.json`: `bundle_name`, `ability`, the user-visible `symptom` (Chinese), the `scenario` and
`perf_scenarios`. It never mentions the cause or the fix.

## Oracle (groundtruth)

`groundtruth.json` is evaluator-only:

| Field | Meaning |
|---|---|
| `mechanism`, `fix_summary` | root cause and repair in prose |
| `root_causes[]` | code locations in the **unfixed** source: `file`, `class`, `symbol` (function, field or constant), `kind` (`function`, `class_member`, `constant`, `module`), `changed_lines`, `scope_lines` |
| `root_causes[].role` | `primary`: must be found (counts for recall). `related`: also touched by the fix (imports, fields, helpers); a correct suspect but not required |
| `root_causes[].aliases[]` | alternative locations accepted for that root cause (e.g. the caller of a slow SQL constant) |
| `performance_oracle` | `metric`, `definition`, pass criterion `comparison`, and the reference `evidence` measured on the clean unfixed/fixed pair (three rounds per variant) |

## Workload

`testcase/` holds a HapRay `PerfTestCase` (`*.py` + `*.json`), its UI plan `*.workload.json`
(`setup`, `measured`, `verify` actions) and `workload_driver.py`. Copy all files to
`case.json#testcase.install_dir` of an
[ArkAnalyzer-HapRay](https://github.com/SMAT-Lab/ArkAnalyzer-HapRay) checkout. Only `measured` is profiled.
