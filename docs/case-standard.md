# Case standard

This page states what qualifies a case and how a case is built, verified, catalogued and evaluated.
Every rule names the file that enforces it.
Rules marked **(manual)** are checked by the contributor and the reviewer, not by a script.
The reasons behind the rules are in [design.md](design.md).

## 1. Inclusion criteria

A case qualifies only if all of the following hold.

| # | Criterion | Enforced by |
|---|---|---|
| 1 | The host app is an open-source HarmonyOS (ArkTS) app in a **public** repository. | (manual) |
| 2 | The bug is a performance problem on a path a user reaches through the UI. | (manual) |
| 3 | Both variants rebuild from the public upstream commit plus the two patches alone. | `tools/prepare_sources.py` (tree hash check) |
| 4 | `fix.patch` contains only the repair. | (manual) |
| 5 | No benchmark code is compiled into the app: no counters, custom traces, test entry points or instrumentation. | `tools/audit_app.py`, run by `tools/build_cases.py` |
| 6 | The same workload and input data reach the faulty code in both variants. | (manual) |
| 7 | On a real device, the unfixed/fixed pair meets `performance_oracle.comparison` over at least three rounds per variant. | (manual); evidence recorded in `groundtruth.json` |
| 8 | The workload's input data can be prepared outside the app, identically for both variants. | `tools/catalog.py check` (requires `runnability.prepare`) |
| 9 | The case can be run today. | `tools/catalog.py check` (an `included` case must have `runnability.runnable: true`) |
| 10 | At least one `primary` root cause is recorded. | `tools/catalog.py check` |

Cases that miss their oracle are not added.
Cases that stop meeting criterion 9 are kept with `status: excluded` and an `exclusion_reason`.

## 2. Directory layout and required artifacts

```
cases/<case-id>/
  case.json            metadata (schema below)
  prompt.json          what the tool under test is told
  groundtruth.json     oracle: mechanism, root causes, performance oracle (evaluator only)
  source.patch         upstream base commit -> unfixed source
  fix.patch            unfixed -> fixed source (repair only; evaluator only)
  testcase/
    <Testcase>.py              HapRay PerfTestCase
    <Testcase>.json            HapRay testcase descriptor
    <Testcase>.workload.json   UI plan: setup, measured, verify
    workload_driver.py         shared UI driver
```

`tools/catalog.py check` fails if `case.json`, `prompt.json`, `groundtruth.json`, `source.patch`, `fix.patch`, or the testcase files named in `case.json#testcase` (`py_file`, `descriptor`, `workload`) are missing.
Input-data scripts and replay services go in `tools/collect/fixtures/`, not in the case directory.

### Patches

- `source.patch` = `git diff --binary --full-index <upstream_base_commit> <unfixed>`.
  It may hold build adaptations (for example SDK 5.1 project settings and lockfiles), device adaptations and the bug.
- `fix.patch` = `git diff --binary --full-index <unfixed> <fixed>`.
  It holds only the repair.

### prompt.json

| Field | Content |
|---|---|
| `case` | the case id |
| `bundle_name`, `ability` | the app bundle and the ability to start |
| `symptom` | what a user observes; never the cause or the fix |
| `scenario` | the user scenario |
| `perf_scenarios` | scenario labels, same as `case.json#perf_scenarios` |

### groundtruth.json

| Field | Content |
|---|---|
| `case`, `status` | must equal `case.json` (`tools/catalog.py check`) |
| `mechanism`, `fix_summary` | root cause and repair in prose |
| `root_causes[]` | `id`, `role` (`primary` or `related`), `kind` (`function`, `class_member`, `constant`, `module`), `file`, `class`, `symbol`, `changed_lines`, `scope_lines`, optional `aliases[]`; lines refer to the **unfixed** tree |
| `performance_oracle.metric` | for example `hiperf_instructions`, `trace_cpu_ms`, `app_pss_bytes` |
| `performance_oracle.definition` | how the metric is measured |
| `performance_oracle.comparison` | the pass criterion, for example `unfixed >= 1.2 * fixed over >= 3 rounds per variant` |
| `performance_oracle.evidence` | `unfixed[]` and `fixed[]` (at least three values each), `rounds_per_variant`, optional `median_ratio`; newer cases also record `device`, `date`, `collection`, `round_order`, `fixture_sha256` |

The matching rules for root causes are in [evaluation.md](evaluation.md#metrics).

### Workload

The `*.workload.json` plan has three action lists.
`setup` brings the app to the starting screen.
`measured` is the profiled part.
`verify` checks that the app reached the expected state.
Copy all `testcase/` files to `case.json#testcase.install_dir` of an [ArkAnalyzer-HapRay](https://github.com/SMAT-Lab/ArkAnalyzer-HapRay) checkout to run them.

## 3. case.json schema

`tools/catalog.py check` validates the fields marked ✓.

| Field | Allowed values / content | Checked |
|---|---|---|
| `id` | `<app>_<short_description>` in snake_case; equals the directory name and `groundtruth.json#case` | ✓ |
| `status` | `included` or `excluded`; equals `groundtruth.json#status` | ✓ |
| `exclusion_reason` | required when `status` is `excluded` | ✓ |
| `host_app.name` | display name of the app | |
| `host_app.repository` | public upstream URL | (`prepare_sources.py` clones it) |
| `host_app.upstream_base_commit` | full commit SHA | (`prepare_sources.py` checks it out) |
| `host_app.bundle_name` | app bundle name; do not change it | |
| `host_app.local_path` | `hosts/<app>` | |
| `category` | free-text bug category from the original collection (`latency`, `cpu`, `resource_retention`, `memory`, `network` today) | |
| `perf_scenarios` | list of scenario labels | |
| `source.patch`, `source.fix_patch` | `source.patch`, `fix.patch` | |
| `source.<variant>.tree` | `git write-tree` of the unfixed / fixed variant | (`prepare_sources.py`) |
| `source.<variant>.reference_unsigned_hap_sha256` | hash of the reference build; informational, builds are not byte-reproducible | |
| `testcase.name` | HapRay testcase class, e.g. `PerfLoad_jingmo_0020` | |
| `testcase.py_file`, `descriptor`, `workload` | paths inside the case directory | ✓ (files exist) |
| `testcase.install_dir`, `driver`, `module`, `ability`, `trigger` | where and how HapRay runs the testcase | |
| `collection` | `config` (`../collection.yaml`), `modes` (`htrace`, `hiperf`, `memory`), `step_duration_s`, `rounds`, `outputs` | |
| `runnability.data` | `offline`, `local_service` or `public_backend` | ✓ |
| `runnability.prepare` | how to prepare the input data (script or steps) | ✓ (non-empty) |
| `runnability.service` | the replay script and port; required for `local_service` | ✓ |
| `runnability.public_backend` | the endpoint and its last check; required for `public_backend` | ✓ |
| `runnability.runnable` | `true` / `false`; must be `true` for an included case | ✓ |
| `runnability.checked` | date of the last dependency check (YYYY-MM-DD) | |
| `hapray.scene` | `load`, `memory`, `jank` or `latency` | ✓ |
| `hapray.also` | other scenes from the same list, not the main scene | ✓ |
| `hapray.collect` | `perf --memory` for the memory scene, `perf` otherwise | ✓ |
| `hapray.oracle_metric_in_hapray` | `true` if HapRay itself reports the oracle metric | |
| `quality` | computed; never edit by hand (below) | ✓ (must equal the computed value) |

## 4. Quality and runnability grading

**Quality** is computed by `tools/catalog.py` from `groundtruth.json#performance_oracle.evidence`.

| Field | Rule |
|---|---|
| `quality.median_ratio` | `evidence.median_ratio` if present, else median(unfixed) / median(fixed); rounded to 2 decimals |
| `quality.tier` | `weak` if the ratio is below 1.5 (`WEAK_RATIO`), else `strong` |

A weak case passed its own oracle and stays in the benchmark.
Every score is also reported on strong cases only (`--tier strong`).

**Runnability** records what the workload needs.

| `runnability.data` | Meaning | Extra requirement |
|---|---|---|
| `offline` | data installed on the device before the run | none |
| `local_service` | a script in `tools/collect/fixtures/` serves recorded API responses; forward its port with `hdc rport` | `service` |
| `public_backend` | the app talks to a real internet service | `public_backend`, with the date it last answered |

`runnable` is a dependency check on the `checked` date.
It is not a fresh device run of every case.
Prefer `offline` or `local_service`.
A case whose public backend stops working is excluded.

## 5. Build, sign, run, verify: checklist

1. **Reconstruct.** `python3 tools/prepare_sources.py <case-id>` succeeds.
   Both trees match `source.<variant>.tree` and are tagged `case/<case-id>/{unfixed,fixed}`.
2. **Build.** `python3 tools/build_cases.py <case-id>` writes `artifacts/<case-id>/<variant>/app-unsigned.hap` and `build.json` with `status: PASS` for both variants.
   The build fails if `ohpm install` changes tracked files or if the audit finds benchmark code.
3. **Sign.** Sign both HAPs with your own certificate, profile and keystore (for example `hap-sign-tool` from the SDK).
   Do not change the bundle name.
4. **Install and prepare.** Install the variant with `hdc install -r` and restore the case's input data exactly as `runnability.prepare` says.
5. **Measure.** Run the workload on both variants, at least three rounds each, with identical data before every round.
   Measure only the `measured` window.
   Alternate the variants between rounds where possible.
6. **Verify.** The `verify` actions pass for both variants (the app still works after the fix).
   The evidence meets `performance_oracle.comparison`.
7. **Record.** Write the values into `groundtruth.json#performance_oracle.evidence`.

The measuring script used for the reference evidence is not part of this repository.
Five oracles use metrics that HapRay does not report; see [limitations.md](limitations.md).

## 6. Acceptance criteria for the catalog

A case enters the catalog with `status: included` when:

- every criterion in section 1 holds;
- `python3 tools/catalog.py docs` has been run, so `quality` is filled and [docs/cases.md](cases.md) is regenerated;
- `python3 tools/catalog.py check` prints `N cases OK`;
- `python3 -m unittest discover tests` passes (it runs the check and fails if `docs/cases.md` is out of date);
- the reviewer has checked the manual criteria, in particular that `fix.patch` holds only the repair and that `prompt.json` does not reveal the cause.

## 7. Naming and versioning

| Item | Convention |
|---|---|
| Case id | `<app>_<short_description>`, snake_case, e.g. `jingmo_random_poem_orderby_random` |
| Host app key | short lowercase name, also used for `hosts/<app>` |
| Testcase class | `PerfLoad_<app>_<NNNN>`; cases collected with the `memory` mode use `MemLoad_<app>_<NNNN>` (convention, not checked) |
| Source variants | git tags `case/<case-id>/unfixed` and `case/<case-id>/fixed`, created by `prepare_sources.py` |
| Build outputs | `artifacts/<case-id>/<variant>/` |
| Variant identity | the git tree hash in `case.json#source.<variant>.tree` |

There are no release tags yet.
To cite a benchmark version, cite the OhmBench commit SHA.
A case is never deleted silently: when it can no longer run, it becomes `excluded` with a reason, and its data stays.
