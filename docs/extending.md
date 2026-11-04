# Extension standard

A new case is a directory `cases/<case-id>/` plus host-source records. The contributor provides
**prompt**, **source + patch** and **oracle**; follow the existing cases for the exact format.

| Item | Required content |
|---|---|
| `case-id` | `<app>_<short_description>` in snake_case |
| **Source + patch** | The unfixed and fixed states must be reproducible from a public upstream: either already reachable via `hosts_patches/<app>/` or added as new numbered `git format-patch` files on top of the series tip (with `--binary --full-index`). Add both trees to `host-reconstruction.json` (`case/<id>/unfixed`, `case/<id>/fixed`; plus `app_tree`/`production_patches` if adaptations are needed). `fix.patch` = `git diff --binary --full-index <unfixed> <fixed>` and must contain **only** the repair. A new host app needs a new entry with `upstream_repository` and `upstream_base_commit`. |
| `case.json` | `id`, `status`, `host_app` (`name`, `repository`, `upstream_base_commit`, `bundle_name`, `local_path`), `category`, `perf_scenarios`, `source.<variant>` (`ref`, `tree`, `production_patches`), `testcase`, `collection` |
| **Prompt** `prompt.json` | `case`, `bundle_name`, `ability`, `symptom` (what a user observes, without cause or fix), `scenario`, `perf_scenarios` |
| **Oracle** `groundtruth.json` | `case`, `status`, `mechanism`, `fix_summary`, `root_causes` (at least one `primary`; line numbers in the unfixed app source), `performance_oracle` (`metric`, `definition`, `comparison`, `evidence` with ≥ 3 rounds per variant) |
| `testcase/` | a HapRay testcase and UI workload that reach the faulty code path in **both** variants, with identical data and actions |

Rules:

- No benchmark code in the app: no counters, custom traces, test entry points or instrumentation
  (`tools/audit_clean_app.py` enforces known patterns).
- `status` is `included` only if the clean unfixed/fixed pair meets `performance_oracle.comparison`
  on a real device with the recorded workload; otherwise `excluded` with an `exclusion_reason`.
- Any workload input data (databases, preferences, backend responses) must be described so that it
  can be prepared outside the app, identically for both variants.
