# Data

## Repository layout

```
cases/
  collection.yaml          reference HapRay/hiprofiler collection configuration
  <case-id>/
    case.json              metadata: status, host app, source trees, testcase, collection
    prompt.json            prompt given to a diagnosis tool
    groundtruth.json       oracle: mechanism, root-cause locations, performance oracle
    source.patch           upstream base commit -> unfixed source
    fix.patch              repair diff, unfixed -> fixed
    testcase/              HapRay testcase, UI workload plan and shared UI driver
docs/                      documentation linked from README.md
tools/                     reconstruction, build and bytecode audit
```

## Source + patch

Each case is self-contained. Its source is reconstructed from the **public upstream repository**
(`case.json#host_app.repository`) and two patches in the case directory:

| Variant | How it is obtained |
|---|---|
| unfixed | `host_app.upstream_base_commit` + `source.patch` |
| fixed | unfixed + `fix.patch` |

`source.patch` contains everything that differs from upstream in the unfixed variant: build
adaptations (e.g. SDK 5.1 project settings, lockfiles), adaptations needed to install and run the
workload on a device, and the bug. `fix.patch` contains only the repair. `case.json#source.<variant>.tree`
is the git tree hash of each variant; the root-cause line numbers in `groundtruth.json` refer to
the unfixed tree.

```bash
python3 tools/prepare_sources.py [case-id ...]   # -> hosts/<app>, tags case/<case-id>/{unfixed,fixed}
```

The script verifies every tree against its recorded hash. Done by hand, one variant is:

```bash
git clone <host_app.repository> app && cd app
git checkout --detach <host_app.upstream_base_commit>
git apply --index ../cases/<case-id>/source.patch       # unfixed; git write-tree == source.unfixed.tree
git apply --index ../cases/<case-id>/fix.patch          # fixed;   git write-tree == source.fixed.tree
```

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
| `performance_oracle` | `metric`, `definition`, pass criterion `comparison`, and the reference `evidence` measured on the unfixed/fixed pair (three rounds per variant) |

## Workload

`testcase/` holds a HapRay `PerfTestCase` (`*.py` + `*.json`), its UI plan `*.workload.json`
(`setup`, `measured`, `verify` actions) and `workload_driver.py`. Copy all files to
`case.json#testcase.install_dir` of an
[ArkAnalyzer-HapRay](https://github.com/SMAT-Lab/ArkAnalyzer-HapRay) checkout. Only `measured` is profiled.
