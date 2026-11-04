# Extension standard

A new case is a self-contained directory `cases/<case-id>/`. The contributor provides
**prompt**, **source + patch** and **oracle**; follow the existing cases for the exact format.

| Item | Required content |
|---|---|
| `case-id` | `<app>_<short_description>` in snake_case |
| **Source + patch** | `source.patch` = `git diff --binary --full-index <upstream_base_commit> <unfixed>` on a **public** upstream repository; it may contain build and device adaptations besides the bug. `fix.patch` = `git diff --binary --full-index <unfixed> <fixed>` and must contain **only** the repair. Both variants must build from these two patches alone. |
| `case.json` | `id`, `status`, `host_app` (`name`, `repository` = public upstream URL, `upstream_base_commit` = full SHA, `bundle_name`, `local_path` = `hosts/<app>`), `category`, `perf_scenarios`, `source` (`patch`, `fix_patch`, and per variant `tree` = `git write-tree` of that variant), `testcase`, `collection` |
| **Prompt** `prompt.json` | `case`, `bundle_name`, `ability`, `symptom` (what a user observes, without cause or fix), `scenario`, `perf_scenarios` |
| **Oracle** `groundtruth.json` | `case`, `status`, `mechanism`, `fix_summary`, `root_causes` (at least one `primary`; line numbers in the unfixed app source), `performance_oracle` (`metric`, `definition`, `comparison`, `evidence` with ≥ 3 rounds per variant) |
| `testcase/` | a HapRay testcase and UI workload that reach the faulty code path in **both** variants, with identical data and actions |

Rules:

- `python3 tools/prepare_sources.py <case-id>` must succeed: both trees reproduce from upstream.

- No benchmark code in the app: no counters, custom traces, test entry points or instrumentation
  (`tools/audit_clean_app.py` enforces known patterns).
- A case is added only if the clean unfixed/fixed pair meets `performance_oracle.comparison`
  on a real device with the recorded workload; `status` is then `included`. Cases that do not meet
  their oracle are not added.
- Any workload input data (databases, preferences, backend responses) must be described so that it
  can be prepared outside the app, identically for both variants.
