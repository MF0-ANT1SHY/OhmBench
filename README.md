# OhmBenchmark

A benchmark of real performance bugs in open-source HarmonyOS (ArkTS) applications.

Each case is a pair of business-source states of a real app, **unfixed** and **fixed**,
together with the repair diff, a neutral UI workload, and a system-level performance
oracle measured on a real device. No benchmark code, counters, custom traces or
instrumentation are compiled into the applications.

- **30 cases** from **9 apps**: **21 included**, **9 excluded**
  (kept for reference; see [Excluded cases](#excluded-cases)).

## Repository layout

```
cases/
  collection.yaml          system-level profiling configuration (HapRay / hiprofiler)
  <case-id>/
    case.json              evaluator metadata: status, bug description, source trees,
                           testcase, oracle definition and measured evidence
    fix.patch              business-source diff from unfixed to fixed
    testcase/              HapRay testcase, UI workload plan (*.workload.json) and
                           the shared UI driver (workload_driver.py)
hosts_patches/
  host-reconstruction.json expected source tree for every case variant
  <app>/0001-*.patch ...   patch series on top of the upstream base commit
  <app>/*.patch            production adaptations applied to specific variants
tools/                     offline tools: source reconstruction, build, bytecode audit,
                           and generators for workload input data
tests/                     unit tests for the data generators
```

## Host applications

| Host | Upstream repository | Base commit |
|---|---|---|
| browser | https://github.com/langwudong/browser | `f44fff7` |
| wanharmony | https://github.com/zjmok/WanHarmony | `dd45ad2` |
| jingmo | https://github.com/hefengbao/jingmo-for-HarmonyOS | `ddca186` |
| cloudmusic | https://github.com/Chenlvin/CloudMusic-HarmonyOSNext | `724702c` |
| sheafreader | https://github.com/simon2137/Sheaf-Reader | `e04ef65` |
| sepweather | https://github.com/SeaEpoch/SepWeather | `e7b92b4` |
| weatherassistant | https://github.com/AlatusLee/HarmonyOS-Next-Weather-Assistant | `d3c7060` |
| interviewapp | https://github.com/HarmonyOS-Next/interview-handbook-project | `1e05347` |
| ytmusic | https://github.com/Charles-Stark/Youtube-Music-ArkTS-Clone | `f925981` |

## Reconstruct and build

Requirements: Python 3.10+, git, and the HarmonyOS command-line tools
(SDK 5.1.0 was used for the reference builds).

```bash
# 1. Clone each upstream app into hosts/<app>, apply the patch series and create
#    refs for every case variant; every resulting source tree is verified.
python3 tools/reconstruct_clean_hosts.py

# 2. Build release HAPs for both variants of every case (or list case ids) and
#    audit the disassembled bytecode for injected benchmark code.
mkdir -p toolchain && ln -s /path/to/command-line-tools toolchain/command-line-tools  # or pass --toolchain
python3 tools/build_clean_cases.py [case-id ...]
```

Unsigned HAPs are written to `artifacts/clean/<case-id>/<variant>/`. Builds are not
byte-reproducible across machines; `case.json#source.<variant>.tree` is the stable
identity, and `reference_unsigned_hap_sha256` is given for reference only.

## Running a case on a device

Device-side steps are intentionally **not automated**; adapt them to your own device
and signing setup.

1. **Sign** both unsigned HAPs with your own HarmonyOS signing identity
   (bundle names must not be changed).
2. **Prepare workload data** outside of profiling. The case's `bug_description` and
   `test_oracle.workload_notes` describe the required data. Generators in `tools/`
   produce ordinary app data (SQLite databases, preferences) or serve ordinary backend
   responses over HTTP:

   | Tool | Produces |
   |---|---|
   | `seed_browser.py` | browser history database |
   | `seed_classic_poems.py`, `jingmo_data_service.py` | Jingmo poetry database / sync API |
   | `seed_search_history.py` | InterviewApp search-history preferences |
   | `seed_wan_home_cache.py`, `seed_wanharmony_history.py` | WanHarmony cache / history preferences |
   | `seed_ytmusic_history.py`, `ytsearch_data_service.py` | YTMusic history preferences / search API |
   | `seed_reader_count_workload.py`, `rss_dataset.py`, `rss_data_service.py`, `rss_database_fixture.py` | Sheaf-Reader subscriptions, articles and RSS/OPML feeds |
   | `cloudmusic_data_service.py` | CloudMusic music API |
   | `weather_data_service.py`, `weather_session_data_service.py`, `weather_hourly_data_service.py` | Weather-Assistant forecast API |

   Installing files into an app sandbox requires a debuggable/rooted test device;
   services are reached from the device via `hdc rport`. Setup UI plans for configuring
   an app's server URL are in `tools/fixtures/`.
3. **Run the workload**: copy every file in `cases/<id>/testcase/` to the
   `testcase.install_dir` of an [ArkAnalyzer-HapRay](https://github.com/SMAT-Lab/ArkAnalyzer-HapRay)
   checkout and run the testcase. Each plan has `setup`, `measured` and `verify` phases;
   only `measured` is profiled.
4. **Measure** the oracle metric (`test_oracle.metric` / `definition`) for at least three
   rounds per variant with identical data and actions, and check
   `test_oracle.comparison`. Reference values are in `test_oracle.evidence`.

## Blind diagnosis evaluation

When evaluating a diagnosis agent, give it only the **signed unfixed HAP**, a symptom
description, the testcase/workload files, and the system-generated profiles of the
app process. Do **not** give it `case.json`, `fix.patch`, fixed builds, oracle values
or `hosts_patches/`.

## Included cases

| Case | App | Category | Oracle metric | Pass criterion | Median ratio |
|---|---|---|---|---|---|
| `browser_eager_history_load` | browser (小狐狸浏览器) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 1.36 |
| `browser_history_delete_no_transaction` | browser (小狐狸浏览器) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 31.31 |
| `browser_history_list_foreach` | browser (小狐狸浏览器) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 2.71 |
| `cloudmusic_play_time_high_frequency_update` | CloudMusic-HarmonyOSNext (仿网易云音乐) | cpu | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 3.02 |
| `cloudmusic_search_result_foreach` | CloudMusic-HarmonyOSNext (仿网易云音乐) | latency | `hiperf_instructions` | unfixed >= 2.0 * fixed over >= 3 rounds per variant | 2.22 |
| `interviewapp_search_history_unbounded` | interview-handbook-project (面试通) | resource_retention | `app_pss_bytes` | unfixed >= 1.3 * fixed over >= 3 rounds per variant | 4.73 |
| `jingmo_dataset_import_no_transaction` | jingmo (京墨文库) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 2.18 |
| `jingmo_random_poem_orderby_random` | jingmo (京墨文库) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 7.85 |
| `jingmo_sync_page_reimport` | jingmo (京墨文库) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 4.21 |
| `sepweather_font_register_per_page` | SepWeather | memory | `app_pss_bytes` | unfixed >= 2.0 * fixed and unfixed - fixed >= 64 MiB in each of 3 paired rounds | 2.65 |
| `sheafreader_article_list_foreach` | Sheaf-Reader (束阅 RSS 阅读器) | latency | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 2.42 |
| `sheafreader_extract_tag_tolowercase` | Sheaf-Reader (束阅 RSS 阅读器) | cpu | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 1.24 |
| `sheafreader_insert_duplicate_exception` | Sheaf-Reader (束阅 RSS 阅读器) | cpu | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 1.50 |
| `sheafreader_refresh_feeds_sequential` | Sheaf-Reader (束阅 RSS 阅读器) | latency | `startup_refresh_elapsed_s` | unfixed conservative lower bound >= 1.5 * fixed upper bound over 3 paired rounds | 1.84 |
| `sheafreader_unread_counts_n_plus_1` | Sheaf-Reader (束阅 RSS 阅读器) | latency | `trace_cpu_ms` | unfixed >= 2.0 * fixed over >= 3 rounds per variant | 13.44 |
| `wanharmony_persisted_home_list_growth` | WanHarmony (WanAndroid 客户端) | resource_retention | `app_pss_bytes` | unfixed >= 1.3 * fixed over >= 3 rounds per variant | 1.37 |
| `weatherassistant_http_session_leak` | HarmonyOS-Next-Weather-Assistant | resource_retention | `app_gc_requested_pss_growth_bytes` | each of 3 pairs: unfixed lower growth >= 3 * max(fixed upper growth, 1 MiB), with >= 5 MiB unfixed growth and >= 5 MiB excess growth | 40.29 |
| `weatherassistant_remote_weather_icons` | HarmonyOS-Next-Weather-Assistant | latency | `startup_icons_elapsed_s` | unfixed conservative lower bound >= 2.0 * fixed upper bound over 3 paired rounds | 2.27 |
| `ytmusic_current_playing_timeupdate` | Youtube-Music-ArkTS-Clone | cpu | `hiperf_instructions` | unfixed >= 1.2 * fixed over >= 3 rounds per variant | 4.95 |
| `ytmusic_history_json_parse_per_row` | Youtube-Music-ArkTS-Clone | cpu | `hiperf_instructions` | unfixed >= 1.3 * fixed over >= 3 rounds per variant | 3.30 |
| `ytmusic_search_no_debounce` | Youtube-Music-ArkTS-Clone | network | `search_response_body_bytes` | unfixed >= 5.0 * fixed successful search response bytes over 3 paired rounds | 5.50 |

## Excluded cases

These cases build and run correctly, but their clean unfixed/fixed pairs did not meet
the performance oracle on the reference device. They are retained with
`"status": "excluded"` and an `exclusion_reason` in `case.json`, and should not be used
for evaluation.

| Case | App | Category | Oracle metric | Median ratio |
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
