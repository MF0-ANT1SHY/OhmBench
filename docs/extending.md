# Extension standard

A new case is a self-contained directory `cases/<case-id>/`. The contributor provides
**prompt**, **source + patch** and **oracle**; follow the existing cases for the exact format.

| Item | Required content |
|---|---|
| `case-id` | `<app>_<short_description>` in snake_case |
| **Source + patch** | `source.patch` = `git diff --binary --full-index <upstream_base_commit> <unfixed>` on a **public** upstream repository; it may contain build and device adaptations besides the bug. `fix.patch` = `git diff --binary --full-index <unfixed> <fixed>` and must contain **only** the repair. Both variants must build from these two patches alone. |
| `case.json` | `id`, `status`, `host_app` (`name`, `repository` = public upstream URL, `upstream_base_commit` = full SHA, `bundle_name`, `local_path` = `hosts/<app>`), `category`, `perf_scenarios`, `source` (`patch`, `fix_patch`, and per variant `tree` = `git write-tree` of that variant), `testcase`, `collection`, `runnability` (input data: `offline` / `local_service` / `public_backend`, how to prepare it, the service or backend, whether it runs, date checked), `hapray` (`scene`: `load` / `memory` / `jank` / `latency`, secondary scenes `also`, `collect`, `oracle_metric_in_hapray`). `quality` is computed: run `python3 tools/catalog.py docs` |
| **Prompt** `prompt.json` | `case`, `bundle_name`, `ability`, `symptom` (what a user observes, without cause or fix), `scenario`, `perf_scenarios` |
| **Oracle** `groundtruth.json` | `case`, `status`, `mechanism`, `fix_summary`, `root_causes` (at least one `primary`; line numbers in the unfixed app source), `performance_oracle` (`metric`, `definition`, `comparison`, `evidence` with ≥ 3 rounds per variant) |
| `testcase/` | a HapRay testcase and UI workload that reach the faulty code path in **both** variants, with identical data and actions |

Rules:

- `python3 tools/prepare_sources.py <case-id>` must succeed: both trees reproduce from upstream.

- No benchmark code in the app: no counters, custom traces, test entry points or instrumentation
  (`tools/audit_app.py` enforces known patterns).
- A case is added only if the unfixed/fixed pair meets `performance_oracle.comparison`
  on a real device with the recorded workload; `status` is then `included`. Cases that do not meet
  their oracle are not added.
- Any workload input data (databases, preferences, backend responses) must be described so that it
  can be prepared outside the app, identically for both variants. Prefer offline fixtures or a local
  replay service in `tools/collect/fixtures/` over a public backend; a case whose public backend stops
  working is excluded (`status: excluded` with `exclusion_reason`).
- A passing case whose median unfixed/fixed ratio is below 1.5x is marked `weak` automatically; it
  counts, but results are also reported without weak cases.
- Finish with `python3 tools/catalog.py docs` (regenerates [the case tables](cases.md)) and
  `python3 -m unittest discover tests`.
