# OhmBench

A benchmark of performance bugs in HarmonyOS applications, for
evaluating performance-diagnosis abilities.

## What the benchmark provides

| Part | Provided by OhmBench | Provided by the user |
|---|---|---|
| **Data** | per case: **source + patch** to build the unfixed and fixed app, the **prompt**, and the **oracle** (groundtruth); a neutral UI workload | a HarmonyOS **signing certificate** (and a device) |
| **Build** | `tools/` — reconstruct the sources from public upstreams and build both variants | — |
| **Extend** | the [case standard](#extension-standard) every new case must follow | the new case's prompt, source + patch and oracle |
| **Collect / evaluate** | the [evaluation standard](#collection-and-evaluation-standard): what to measure per case and how | the code that runs a tool, collects the measurements and scores them |

## Repository layout

```
cases/
  collection.yaml          reference HapRay/hiprofiler collection configuration
  <case-id>/
    case.json              metadata: status, host app, source trees, testcase, collection
    prompt.json            prompt given to a diagnosis tool (included cases)
    groundtruth.json       oracle: mechanism, root-cause locations, performance oracle
    fix.patch              repair diff, unfixed -> fixed
    testcase/              HapRay testcase, UI workload plan and shared UI driver
hosts_patches/
  host-reconstruction.json expected source tree of every case variant
  <app>/0001-*.patch ...   patch series on top of the upstream base commit
  <app>/*.patch            production adaptations applied to specific variants
tools/                     reconstruction, build and bytecode audit
```

## Data

### Source + patch

The source of every variant is reconstructed from the **public upstream repository** plus the
patches in this repository:

1. `hosts_patches/<app>/0001-*.patch …` — a `git am` series on the upstream base commit;
2. `cases/<id>/fix.patch` — the repair diff between the two variants of a case;
3. `hosts_patches/<app>/*.patch` (unnumbered) — production adaptations recorded per variant
   (`production_patches`), needed for the app to build and run its workload;
4. `hosts_patches/host-reconstruction.json` — the git tree hash of every variant, before
   (`tree`) and after (`app_tree`) production adaptations.

```bash
python3 tools/reconstruct_clean_hosts.py     # -> hosts/<app> with clean/<id>/<variant> and clean-app/... refs
```

Every reconstructed tree is verified against its recorded hash. All 60 variants (120 refs)
reconstruct from the public upstreams.

### Prompt

`prompt.json`: `bundle_name`, `ability`, the user-visible `symptom` (Chinese), the `scenario` and
`perf_scenarios`. It never mentions the cause or the fix.

### Oracle (groundtruth)

`groundtruth.json` is evaluator-only:

| Field | Meaning |
|---|---|
| `mechanism`, `fix_summary` | root cause and repair in prose |
| `root_causes[]` | code locations in the **unfixed** source: `file`, `class`, `symbol` (function, field or constant), `kind` (`function`, `class_member`, `constant`, `module`), `changed_lines`, `scope_lines` |
| `root_causes[].role` | `primary`: must be found (counts for recall). `related`: also touched by the fix (imports, fields, helpers); a correct suspect but not required |
| `root_causes[].aliases[]` | alternative locations accepted for that root cause (e.g. the caller of a slow SQL constant) |
| `performance_oracle` | `metric`, `definition`, pass criterion `comparison`, and the reference `evidence` measured on the clean unfixed/fixed pair (three rounds per variant) |

### Workload

`testcase/` holds a HapRay `PerfTestCase` (`*.py` + `*.json`), its UI plan `*.workload.json`
(`setup`, `measured`, `verify` actions) and `workload_driver.py`. Copy all files to
`case.json#testcase.install_dir` of an
[ArkAnalyzer-HapRay](https://github.com/SMAT-Lab/ArkAnalyzer-HapRay) checkout. Only `measured` is profiled.

## Building the binaries

Requirements: Python 3.10+, git and the HarmonyOS command-line tools (SDK 5.1.0 was used).

```bash
python3 tools/reconstruct_clean_hosts.py
mkdir -p toolchain && ln -s /path/to/command-line-tools toolchain/command-line-tools   # or pass --toolchain
python3 tools/build_clean_cases.py [case-id ...]
```

This writes `artifacts/clean/<id>/<variant>/app-unsigned.hap` for both variants and audits the
disassembled bytecode for injected benchmark code. Builds are not byte-reproducible across
machines; the source tree is the stable identity (`case.json#source.<variant>.tree`;
`reference_unsigned_hap_sha256` is the hash of the reference build).

**Signing is up to the user**: sign both HAPs with your own certificate, profile and keystore
(e.g. `hap-sign-tool` from the SDK toolchain) for your device. Do not change bundle names.

## Extension standard

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

## Collection and evaluation standard

### Blind input

A tool under evaluation may receive, per case: the **signed unfixed HAP**, `prompt.json`, the
`testcase/` files, optionally dynamic data collected from the unfixed variant (recommended format:
a HapRay `perf` report tree with `hapray-tool-result.json`), and optionally the unfixed source
without git history. It must **not** receive `case.json`, `groundtruth.json`, `fix.patch`, the fixed
variant, oracle values or `hosts_patches/`. Report which inputs were given.

### Per-case record

Collect one record per (tool, case), e.g. `results/<tool>/<case-id>.json`:

```json
{
  "case": "jingmo_random_poem_orderby_random",
  "tool": "my-tool", "tool_version": "1.0",
  "inputs": ["hap", "prompt", "testcase", "dynamic_data"],
  "suspects": [
    {"rank": 1, "file": "commons/constants/src/main/ets/DbConst.ets", "class": "DbCRUDConst",
      "symbol": "READ_RANDOM_CLASSICPOEM", "line_start": 28, "line_end": 31, "description": "..."}
  ],
  "time_s": 183.2,
  "memory_peak_bytes": 734003200,
  "tokens": {"input": 51234, "output": 3120, "total": 54354},
  "precision": 1.0, "recall": 1.0, "f1": 1.0
}
```

### Metrics

| Metric | Definition |
|---|---|
| `time_s` | wall-clock time of the whole diagnosis of one case, from tool start to final answer |
| `memory_peak_bytes` | peak resident memory of the tool's local process tree during the case |
| `tokens` | LLM tokens consumed for the case (`input`, `output`, `total`), as reported by the model API; `null` for tools without an LLM — do not estimate |
| `precision` | correct suspects / suspects, over the top-5 suspects by rank |
| `recall` | `primary` root causes matched by at least one top-5 suspect / `primary` root causes |
| `f1` | 2·P·R / (P + R); 0 when P + R = 0 |

Matching of a suspect to a groundtruth location (the root cause itself or one of its `aliases`):

1. **File**: the trailing path segments agree (at least two segments, or the whole name of a
   one-segment path); extensions (`.ets`, `.ts`, `.js`) are ignored, and ABC record names
   (`&entry/src/main/ets/pages/Index&`) are reduced to their path.
2. **Function level** (default): additionally, the suspect's `symbol` names the location's `symbol`
   (the last component of `Class.method` counts), or the suspect's line range overlaps the location's
   `scope_lines` (functions) or `changed_lines` (fields, constants, module code).
3. A suspect is **correct** if it matches any `primary` or `related` location. A file-level variant
   (rule 1 only) may be reported in addition and must be labelled as such.

A case without an answer scores P = R = F1 = 0 and keeps its measured cost. Report per-case records
and the **macro average** over all 21 included cases (and optionally micro averages, pooling
suspects and root causes). Use the same model, budget and inputs for all cases of a run.

## Host applications

| Host | Upstream repository | Base commit | Licence |
|---|---|---|---|
| browser | https://github.com/langwudong/browser | `f44fff7` | none |
| wanharmony | https://github.com/zjmok/WanHarmony | `dd45ad2` | GPL-3.0 |
| jingmo | https://github.com/hefengbao/jingmo-for-HarmonyOS | `ddca186` | MIT |
| cloudmusic | https://github.com/Chenlvin/CloudMusic-HarmonyOSNext | `724702c` | GPL-2.0 |
| sheafreader | https://github.com/simon2137/Sheaf-Reader | `e04ef65` | BSD-3-Clause |
| sepweather | https://github.com/SeaEpoch/SepWeather | `e7b92b4` | GPL-3.0 |
| weatherassistant | https://github.com/AlatusLee/HarmonyOS-Next-Weather-Assistant | `d3c7060` | MulanPSL-2.0 |
| interviewapp | https://github.com/HarmonyOS-Next/interview-handbook-project | `1e05347` | none |
| ytmusic | https://github.com/Charles-Stark/Youtube-Music-ArkTS-Clone | `f925981` | none |

## Included cases

| Case | App | Category | Oracle metric | Pass criterion | Ref. median ratio | Primary root causes |
|---|---|---|---|---|---|---|
| `browser_eager_history_load` | browser (小狐狸浏览器) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 1.36 | 1 |
| `browser_history_delete_no_transaction` | browser (小狐狸浏览器) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 31.31 | 1 |
| `browser_history_list_foreach` | browser (小狐狸浏览器) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 2.71 | 1 |
| `cloudmusic_play_time_high_frequency_update` | CloudMusic-HarmonyOSNext (仿网易云音乐) | cpu | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 3.02 | 1 |
| `cloudmusic_search_result_foreach` | CloudMusic-HarmonyOSNext (仿网易云音乐) | latency | `hiperf_instructions` | unfixed >= 2.0 * fixed over >= 3 rounds per variant | 2.22 | 1 |
| `interviewapp_search_history_unbounded` | interview-handbook-project (面试通) | resource_retention | `app_pss_bytes` | unfixed >= 1.3 * fixed over >= 3 rounds per variant | 4.73 | 2 |
| `jingmo_dataset_import_no_transaction` | jingmo (京墨文库) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 2.18 | 1 |
| `jingmo_random_poem_orderby_random` | jingmo (京墨文库) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 7.85 | 1 |
| `jingmo_sync_page_reimport` | jingmo (京墨文库) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 4.21 | 1 |
| `sepweather_font_register_per_page` | SepWeather | memory | `app_pss_bytes` | unfixed >= 2.0 * fixed and unfixed - fixed >= 64 MiB in each of 3 paired rounds | 2.65 | 2 |
| `sheafreader_article_list_foreach` | Sheaf-Reader (束阅 RSS 阅读器) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 2.42 | 1 |
| `sheafreader_extract_tag_tolowercase` | Sheaf-Reader (束阅 RSS 阅读器) | cpu | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 1.24 | 1 |
| `sheafreader_insert_duplicate_exception` | Sheaf-Reader (束阅 RSS 阅读器) | cpu | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 1.50 | 1 |
| `sheafreader_refresh_feeds_sequential` | Sheaf-Reader (束阅 RSS 阅读器) | latency | `startup_refresh_elapsed_s` | unfixed conservative lower bound >= 1.5 * fixed upper bound over 3 paired rounds | 1.84 | 1 |
| `sheafreader_unread_counts_n_plus_1` | Sheaf-Reader (束阅 RSS 阅读器) | latency | `trace_cpu_ms` | unfixed >= 2.0 * fixed over >= 3 rounds per variant | 13.44 | 1 |
| `wanharmony_persisted_home_list_growth` | WanHarmony (WanAndroid 客户端) | resource_retention | `app_pss_bytes` | unfixed >= 1.3 * fixed over >= 3 rounds per variant | 1.37 | 2 |
| `weatherassistant_http_session_leak` | HarmonyOS-Next-Weather-Assistant | resource_retention | `app_gc_requested_pss_growth_bytes` | each of 3 pairs: unfixed lower growth >= 3 * max(fixed upper growth, 1 MiB), with >= 5 MiB unfixed growth and >= 5 MiB excess growth | 40.29 | 1 |
| `weatherassistant_remote_weather_icons` | HarmonyOS-Next-Weather-Assistant | latency | `startup_icons_elapsed_s` | unfixed conservative lower bound >= 2.0 * fixed upper bound over 3 paired rounds | 2.27 | 1 |
| `ytmusic_current_playing_timeupdate` | Youtube-Music-ArkTS-Clone | cpu | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 4.95 | 1 |
| `ytmusic_history_json_parse_per_row` | Youtube-Music-ArkTS-Clone | cpu | `hiperf_instructions` | unfixed >= 1.3 * fixed over >= 3 rounds per variant | 3.30 | 1 |
| `ytmusic_search_no_debounce` | Youtube-Music-ArkTS-Clone | network | `search_response_body_bytes` | unfixed >= 5.0 * fixed successful search response bytes over 3 paired rounds | 5.50 | 1 |

## Excluded cases

| Case | App | Category | Oracle metric | Measured median ratio |
|---|---|---|---|---|
| `browser_insert_date_lookup_cache` | browser (小狐狸浏览器) | latency | `hiperf_instructions` | 1.00 |
| `cloudmusic_indexof_in_render` | CloudMusic-HarmonyOSNext (仿网易云音乐) | cpu | `hiperf_instructions` | 1.01 |
| `cloudmusic_local_song_memory_filter` | CloudMusic-HarmonyOSNext (仿网易云音乐) | latency | `hiperf_instructions` | 1.10 |
| `cloudmusic_songcard_artists_concat` | CloudMusic-HarmonyOSNext (仿网易云音乐) | cpu | `hiperf_instructions` | 1.01 |
| `interviewapp_response_log_full_stringify` | interview-handbook-project (面试通) | cpu | `hiperf_instructions` | 1.04 |
| `interviewapp_search_history_sync_flush` | interview-handbook-project (面试通) | latency | `hiperf_instructions` | 1.01 |
| `wanharmony_history_log_materialization` | WanHarmony (WanAndroid 客户端) | cpu | `trace_cpu_ms` | 1.00 |
| `wanharmony_html_decode_per_render` | WanHarmony (WanAndroid 客户端) | latency | `hiperf_instructions` | 1.04 |
| `wanharmony_web_progress_log_storm` | WanHarmony (WanAndroid 客户端) | cpu | `hiperf_instructions` | 0.99 |

## Known limitations

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
