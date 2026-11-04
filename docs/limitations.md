# Known limitations

- **Workload data preparation is not specified per case in machine-readable form.** Several workloads
  need prepared data (e.g. large databases, preferences, ordinary backend responses served to the app,
  such as `http://127.0.0.1:18492/api/` in the Jingmo workloads); the requirements are only described
  in prose (`groundtruth.json#mechanism`, `performance_oracle.workload_notes`, testcase `setup`).
- **Some oracles need non-HapRay measurements.** Seven included cases use `app_pss_bytes`,
  `app_gc_requested_pss_growth_bytes`, `startup_refresh_elapsed_s`, `startup_icons_elapsed_s` or
  `search_response_body_bytes`, which HapRay `perf` does not report; the reference values were taken
  with external collectors that are not part of this repository. Compare unfixed/fixed ratios, not
  absolute values.
- **Mechanism correctness is not part of the scoring standard**; only code locations are scored.
- Prompts exist for included cases only; two cases (`sheafreader_extract_tag_tolowercase`,
  `sheafreader_insert_duplicate_exception`) share one workload and therefore one symptom text.
  Root-cause locations of excluded cases were not reviewed.
- Three host apps (browser, interviewapp, ytmusic) have no licence upstream.
