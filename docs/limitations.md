# Known limitations

- The [replay matrix](hapray-replay.md) lists workload inputs. Device-specific installation, login state and some media or initialized app data still require preparation.
- **Some oracles need non-HapRay measurements.** Seven cases use `app_pss_bytes`,
  `app_gc_requested_pss_growth_bytes`, `startup_refresh_elapsed_s`, `startup_icons_elapsed_s` or
  `search_response_body_bytes`, which HapRay `perf` does not report; the reference values were taken
  with external collectors that are not part of this repository. Compare unfixed/fixed ratios, not
  absolute values.
- Automatic location matching cannot establish semantic correctness; the [HapRay evaluation workflow](evaluation.md#batch-hapray-evaluation) separates these scores.
- Two cases (`sheafreader_extract_tag_tolowercase`,
  `sheafreader_insert_duplicate_exception`) share one workload and therefore one symptom text.
- Three host apps (browser, interviewapp, ytmusic) have no licence upstream.
