# OhmBench

A benchmark of real performance bugs in open-source HarmonyOS (ArkTS) applications, for
evaluating performance-diagnosis tools.

OhmBench consists of **data** and **code**:

| | Contents | Where |
|---|---|---|
| **Data 1** | App binaries with a performance bug (unfixed HAP, plus the fixed HAP as a control) | [`data/binaries.json`](data/binaries.json), GitHub release, `tools/fetch_binaries.py` |
| **Data 2** | Problem-description prompt given to a diagnosis tool | `cases/<id>/prompt.json`, [`tools/evaluate/prompt_template.md`](tools/evaluate/prompt_template.md) |
| **Data 3** | Groundtruth / oracle: root-cause code locations and the performance oracle | `cases/<id>/groundtruth.json` |
| **Code: extend** | Automation for benchmark developers to add cases | [`tools/extend/`](tools/extend) |
| **Code: collect** | Collection of each case's dynamic data as HapRay dynamic-data objects | [`tools/collect/`](tools/collect) |
| **Code: evaluate** | Measurement of diagnosis tools: time, memory, tokens, recall, precision, F1 | [`tools/evaluate/`](tools/evaluate) |

Each case is a pair of business-source states of a real app (**unfixed** / **fixed**) with the
repair diff, a neutral UI workload and a system-level performance oracle measured on a real
device. No benchmark code, counters, custom traces or instrumentation are compiled into the apps.

**30 cases from 9 apps: 21 included, 9 excluded** (the excluded cases build and run but
did not meet their performance oracle; they are kept for reference and must not be used for
evaluation). See [Not yet supported](#not-yet-supported) for everything the benchmark does not
provide yet.

## Repository layout

```
cases/
  collection.yaml            HapRay/hiprofiler collection configuration
  <case-id>/
    case.json                metadata: status, host app, source trees, testcase, collection
    prompt.json              [data 2] symptom prompt (included cases only)
    groundtruth.json         [data 3] mechanism, root-cause locations, performance oracle
    fix.patch                repair diff, unfixed -> fixed
    testcase/                HapRay testcase + UI workload plan + shared UI driver
data/binaries.json           [data 1] HAP manifest: file names, SHA-256, availability
hosts_patches/               patch series and production adaptations per host app,
  host-reconstruction.json   expected source tree of every case variant
tools/
  fetch_binaries.py          [data 1] download / import HAPs and verify hashes
  extend/                    [code: extend]
  collect/                   [code: collect]   (fixtures/: workload data generators)
  evaluate/                  [code: evaluate]
tests/                       unit tests (python3 -m unittest discover -s tests)
```

Requirements: Python 3.10+ and git. Building needs the HarmonyOS command-line tools
(SDK 5.1.0 was used); collecting needs a HarmonyOS device, `hdc` and an
[ArkAnalyzer-HapRay](https://github.com/SMAT-Lab/ArkAnalyzer-HapRay) checkout.

## Data

### 1. App binaries

```bash
python3 tools/fetch_binaries.py [--variant unfixed] [--cases <id> ...]   # -> artifacts/binaries/<id>.<variant>.hap
```

Binaries are **unsigned** release HAPs built from the recorded source trees; sign them with your
own HarmonyOS identity before installing (bundle names must stay unchanged). Every file is
checked against the SHA-256 in `data/binaries.json`.

Binaries of the three host apps without an open-source licence (browser, interviewapp, ytmusic)
are not redistributed. Build them from source and import them:

```bash
python3 tools/extend/reconstruct_clean_hosts.py           # clone upstreams, apply patches, verify trees
python3 tools/extend/build_clean_cases.py <id> ...        # -> artifacts/clean/<id>/<variant>/app-unsigned.hap
python3 tools/fetch_binaries.py --from-build artifacts/clean --cases <id> ...
```

### 2. Prompts

`prompt.json` holds what a diagnosis tool is told: bundle name, entry ability, the user-visible
symptom (Chinese) and the scenario. `tools/evaluate/prompt_template.md` renders it into the task
text, including the required output format. Prompts never mention the cause or the fix.

### 3. Groundtruth / oracle

`groundtruth.json` (evaluator-only) contains:

- `mechanism`, `fix_summary` — the root cause and repair in prose;
- `root_causes` — machine-checkable code locations in the unfixed source:
  `file`, `class`, `symbol` (function, field or constant), `changed_lines`, `scope_lines`.
  `role: primary` locations must be found (recall); `role: related` locations (imports, fields,
  helpers touched by the fix) count as correct suspects but are not required. `aliases` are
  alternative locations accepted for a root cause (e.g. the caller of a slow SQL constant);
- `performance_oracle` — `metric`, `definition`, pass criterion `comparison` and the reference
  `evidence` measured on the clean unfixed/fixed pair (three rounds per variant).

Root causes were derived from `fix.patch` with `tools/extend/derive_groundtruth.py` and then
reviewed by hand.

## Code

### Extend (benchmark developers)

| Tool | Purpose |
|---|---|
| `extend/reconstruct_clean_hosts.py` | Clone each upstream app into `hosts/<app>`, apply the patch series, recover every case variant and verify its tree hash |
| `extend/build_clean_cases.py` | Build release HAPs of both variants in isolated worktrees; reuse only hash-verified artifacts |
| `extend/audit_clean_app.py` | Reject benchmark injection in source trees and disassembled HAP bytecode (used by the build) |
| `extend/new_case.py` | Scaffold a case from an unfixed and a fixed commit: `fix.patch`, patch-series extension, tree records, refs, `case.json`, `prompt.json`, testcase skeleton, derived groundtruth |
| `extend/derive_groundtruth.py` | Map a repair diff onto the unfixed source and attribute changes to classes/functions |

```bash
python3 tools/extend/new_case.py jingmo jingmo_new_case --unfixed <rev> --fixed <rev> \
    --category latency --symptom "打开列表时响应变慢。" --scenario "列表页面操作"
```

New commits must be created on top of the host's patch-series tip. A new case starts with
`"status": "candidate"`; complete its workload and groundtruth, build it, collect data and set
`"included"` only after the oracle is met on a device.

### Collect (developers and users)

`collect/collect_case.py` installs a case's testcase into a HapRay checkout and runs HapRay's own
`perf` command, so the output **is** a HapRay dynamic-data object: the `reports/<timestamp>/`
tree (`<testcase>_round<N>/hiperf|htrace/step*/…`, merged `<testcase>/report/…`) and HapRay's
`hapray-tool-result.json` (tool-result v1). It can be read directly by the HapRay skill and CLI.

```bash
# preconditions (manual): device attached, signed variant installed, workload data prepared
python3 tools/collect/collect_case.py <id> --variant unfixed --hapray /path/to/ArkAnalyzer-HapRay
python3 tools/collect/collect_case.py <id> --variant fixed   --hapray /path/to/ArkAnalyzer-HapRay
python3 tools/collect/validate_hapray_data.py collected/<id>/unfixed     # layout + contract check
python3 tools/collect/oracle_metrics.py <id>                              # oracle check from HapRay data
```

`oracle_metrics.py` computes `hiperf_instructions` (app-process hiperf sample periods from
`perf.db`) and `trace_cpu_ms` (app-process scheduler time from `trace.db`) per round and checks
`unfixed >= X * fixed` on the median and on every paired round.

Workload data generators are in `collect/fixtures/` (SQLite databases, preferences, and HTTP
services that serve ordinary backend responses). Installing data into an app sandbox needs a
debuggable test device; services are reached from the device via `hdc rport`. UI plans that
configure an app's server URL are `collect/fixtures/*.workload.json`.

### Evaluate (tool users)

```bash
python3 tools/evaluate/prepare_input.py inputs/ [--collected collected/] [--include-source]
python3 tools/evaluate/run_tool.py --inputs inputs/ --out runs/mytool -- \
    mytool --input {input_dir} --output {prediction}
python3 tools/evaluate/score.py --predictions runs/mytool/predictions --runs runs/mytool --output report.json
```

- `prepare_input.py` builds the blind input per case: unfixed `app.hap`, `prompt.json`/`prompt.md`,
  `testcase/`, optionally the unfixed HapRay data (`hapray/`) and source (`source/`). It never copies
  `case.json`, `groundtruth.json`, `fix.patch`, fixed builds or `hosts_patches/`.
- `run_tool.py` runs any tool command per case and records **wall time**, **CPU time**, **peak memory**
  (RSS of the tool's process tree) and **tokens** (from the prediction's `usage` object or `usage.json`).
- `score.py` matches the top-k suspects (default 5) against `root_causes` and reports per-case and
  macro/micro **precision**, **recall** and **F1**, plus cost statistics.
  - `--level function` (default): same file and same symbol, or overlapping lines;
  - `--level file`: same file only.
  - precision = correct suspects / suspects; recall = primary root causes found / primary root causes.

Predictions follow [`tools/evaluate/prediction.schema.json`](tools/evaluate/prediction.schema.json).

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

`HAP` = binary redistributed in the release; `HapRay oracle` = oracle checkable by
`oracle_metrics.py` from HapRay data.

| Case | App | Category | Oracle metric | Pass criterion | Ref. median ratio | Primary root causes | HAP | HapRay oracle |
|---|---|---|---|---|---|---|---|---|
| `browser_eager_history_load` | browser (小狐狸浏览器) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 1.36 | 1 | no | yes |
| `browser_history_delete_no_transaction` | browser (小狐狸浏览器) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 31.31 | 1 | no | yes |
| `browser_history_list_foreach` | browser (小狐狸浏览器) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 2.71 | 1 | no | yes |
| `cloudmusic_play_time_high_frequency_update` | CloudMusic-HarmonyOSNext (仿网易云音乐) | cpu | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 3.02 | 1 | yes | yes |
| `cloudmusic_search_result_foreach` | CloudMusic-HarmonyOSNext (仿网易云音乐) | latency | `hiperf_instructions` | unfixed >= 2.0 * fixed over >= 3 rounds per variant | 2.22 | 1 | yes | yes |
| `interviewapp_search_history_unbounded` | interview-handbook-project (面试通) | resource_retention | `app_pss_bytes` | unfixed >= 1.3 * fixed over >= 3 rounds per variant | 4.73 | 2 | no | no |
| `jingmo_dataset_import_no_transaction` | jingmo (京墨文库) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 2.18 | 1 | yes | yes |
| `jingmo_random_poem_orderby_random` | jingmo (京墨文库) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 7.85 | 1 | yes | yes |
| `jingmo_sync_page_reimport` | jingmo (京墨文库) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 4.21 | 1 | yes | yes |
| `sepweather_font_register_per_page` | SepWeather | memory | `app_pss_bytes` | unfixed >= 2.0 * fixed and unfixed - fixed >= 64 MiB in each of 3 paired rounds | 2.65 | 2 | yes | no |
| `sheafreader_article_list_foreach` | Sheaf-Reader (束阅 RSS 阅读器) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 2.42 | 1 | yes | yes |
| `sheafreader_extract_tag_tolowercase` | Sheaf-Reader (束阅 RSS 阅读器) | cpu | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 1.24 | 1 | yes | yes |
| `sheafreader_insert_duplicate_exception` | Sheaf-Reader (束阅 RSS 阅读器) | cpu | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 1.50 | 1 | yes | yes |
| `sheafreader_refresh_feeds_sequential` | Sheaf-Reader (束阅 RSS 阅读器) | latency | `startup_refresh_elapsed_s` | unfixed conservative lower bound >= 1.5 * fixed upper bound over 3 paired rounds | 1.84 | 1 | yes | no |
| `sheafreader_unread_counts_n_plus_1` | Sheaf-Reader (束阅 RSS 阅读器) | latency | `trace_cpu_ms` | unfixed >= 2.0 * fixed over >= 3 rounds per variant | 13.44 | 1 | yes | yes |
| `wanharmony_persisted_home_list_growth` | WanHarmony (WanAndroid 客户端) | resource_retention | `app_pss_bytes` | unfixed >= 1.3 * fixed over >= 3 rounds per variant | 1.37 | 2 | yes | no |
| `weatherassistant_http_session_leak` | HarmonyOS-Next-Weather-Assistant | resource_retention | `app_gc_requested_pss_growth_bytes` | each of 3 pairs: unfixed lower growth >= 3 * max(fixed upper growth, 1 MiB), with >= 5 MiB unfixed growth and >= 5 MiB excess growth | 40.29 | 1 | yes | no |
| `weatherassistant_remote_weather_icons` | HarmonyOS-Next-Weather-Assistant | latency | `startup_icons_elapsed_s` | unfixed conservative lower bound >= 2.0 * fixed upper bound over 3 paired rounds | 2.27 | 1 | yes | no |
| `ytmusic_current_playing_timeupdate` | Youtube-Music-ArkTS-Clone | cpu | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 4.95 | 1 | no | yes |
| `ytmusic_history_json_parse_per_row` | Youtube-Music-ArkTS-Clone | cpu | `hiperf_instructions` | unfixed >= 1.3 * fixed over >= 3 rounds per variant | 3.30 | 1 | no | yes |
| `ytmusic_search_no_debounce` | Youtube-Music-ArkTS-Clone | network | `search_response_body_bytes` | unfixed >= 5.0 * fixed successful search response bytes over 3 paired rounds | 5.50 | 1 | no | no |

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

## Not yet supported

The following parts of the definition above are **not** provided yet.

**Data**

- **Binaries of unlicensed apps.** The 14 HAPs of browser, interviewapp and ytmusic cases are not
  redistributed; build them locally (`data/binaries.json` records the reference hashes). Local builds
  are not byte-identical to the reference builds; source trees are.
- **Signed binaries.** HAPs are unsigned; signing is device/identity specific and left to the user.
- **Prompts for excluded cases.** Only the 21 included cases have `prompt.json`. Two included cases
  (`sheafreader_extract_tag_tolowercase`, `sheafreader_insert_duplicate_exception`) share the same
  workload and therefore the same symptom text.
- **Mechanism-level groundtruth.** `mechanism` is prose; whether a tool explains the mechanism
  correctly is not scored automatically (only code locations are). Root-cause locations of the
  excluded cases are derived but not reviewed.

**Collect**

- **No collected dynamic data is shipped.** Collection requires a device; run `collect_case.py` yourself.
- **Device preparation is manual**: signing, installation, installing workload data into the app
  sandbox, starting fixture services and port forwarding. Earlier automation depended on a specific
  lab setup and was removed.
- **Oracle check for 7 included cases.** Their oracles use metrics that HapRay `perf` does not produce
  (`app_pss_bytes`, `app_gc_requested_pss_growth_bytes`, `startup_refresh_elapsed_s`,
  `startup_icons_elapsed_s`, `search_response_body_bytes`). The external collectors used for the
  reference evidence are not part of the repository, so these oracles cannot be re-verified with the
  included code; `oracle_metrics.py` reports them as `unsupported`.
- **Absolute values.** Reference evidence was captured with the original collectors, not HapRay
  `perf`; compare unfixed/fixed ratios, not absolute numbers.

**Evaluate**

- **Mechanism / explanation scoring** (e.g. an LLM judge) is not implemented.
- **Token usage** is only recorded when the tool reports it; it is never estimated. Peak memory covers
  the tool's local process tree only (not remote model servers or the device).
- **Baseline results** for existing tools are not included.

**Extend**

- `new_case.py` requires new commits on top of the host's patch-series tip; it does not scaffold
  production adaptations, write the UI workload, the mechanism text or the performance evidence, and it
  does not decide inclusion (that needs on-device collection and the oracle check).
- Adding a new host app (upstream repository) to `host-reconstruction.json` is manual.
