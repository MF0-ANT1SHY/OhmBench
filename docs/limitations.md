# Known limitations

- **Input data is described per case, but installing it is device-specific.** [docs/cases.md](cases.md#input-data-and-backends)
  lists what each workload needs and the script that prepares it; installing app data needs sandbox
  access on a test device, and some cases need the app's normal setup screens (server URL, subscriptions).
- **One case depends on a public backend.** `interviewapp_search_history_unbounded` loads its home screen
  from `api-harmony-teach.itheima.net`; it answered on 2026-11-18. When it stops answering, exclude the
  case as was done for `wanharmony_persisted_home_list_growth`.
- **Some oracles need non-HapRay measurements.** Five included cases use `app_pss_bytes`,
  `app_gc_requested_pss_growth_bytes`, `startup_refresh_elapsed_s`, `startup_icons_elapsed_s` or
  `search_response_body_bytes` (marked † in the case list), which HapRay `perf` does not report; the
  reference values were taken with external collectors that are not part of this repository. Compare
  unfixed/fixed ratios, not absolute values.
- **No jank oracle.** Six cases exercise scrolling or animation (the jank scene), but every oracle is
  CPU instructions, memory or elapsed time; none measures stutter rate.
- **Location scores are automatic; correctness of the explanation and the repair is not.** `score.py`
  reports location and fix-target matches; the semantic judgment (`judge.py`) uses a model or a person.
- **Shared code and workloads.** `sheafreader_extract_tag_tolowercase` and
  `sheafreader_insert_duplicate_exception` share one workload and one symptom text.
  `sheafreader_reader_body_reparse` and `sheafreader_search_no_debounce` share the same unfixed source
  (upstream Sheaf-Reader); each has its own workload and fix.
- Three host apps (browser, interviewapp, ytmusic) have no licence upstream.
