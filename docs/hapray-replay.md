# Choosing and replaying a HapRay case

**Quality gate.** The default cohort is the directories whose `case.json` says
`included`. Each has a clean, real-device reference in `groundtruth.json`.
The [nine failed pairs](https://github.com/MF0-ANT1SHY/OhmBench/blob/2863a47/README.md#excluded-cases)
were removed in `8a5e4e7`; do not count them as misses or restore them to increase the case count.
A small but passing effect is not a failed gate: for example, the parser case
below passed its 1.20× criterion at 1.24×. Use the case's own metric and
comparison, not a universal cutoff.

**Scene selection.** Load = 负载, memory = 内存, jank = 卡顿丢帧, latency = 时延.
The table maps the *workload*, not just the category: latency-labelled cases
often have an instruction-count oracle. A second scene is an analysis opportunity,
not a claim that FPS, native allocations or input latency were measured.
There is no frame-loss acceptance oracle in the current cohort.

| Case | Category → HapRay scene(s) | Required input / reachability check before profiling |
|---|---|---|
| browser_eager_history_load | latency → latency, load | Seed populated multi-day Histories.db; cold launch. Empty history misses the startup work. |
| browser_history_delete_no_transaction | latency → latency, load | Same database; verify history exists before confirming clear. Restore it **each round**. |
| browser_history_list_foreach | latency → load, jank | Populate history; open the dialog and scroll visible Article rows. |
| cloudmusic_play_time_high_frequency_update | cpu → load, jank | Local library must show 10,000 songs and playable Track 9999 (60 s audio); check slider advances. The search service alone does not seed the library. |
| cloudmusic_search_result_foreach | latency → load, latency | Music API on 18490; configure server URL, search “music”, check Track 1 and its artists on the 1,000-song result page. |
| interviewapp_search_history_unbounded | resource_retention → memory | Reach 热门题库 and the normal search screen; seed historyStore from the same 2,500 submissions using the variant-specific XML. The app uses api-harmony-teach.itheima.net for online content; verify access to the normal home screen, or use an already initialized test profile. |
| jingmo_dataset_import_no_transaction | latency → load, latency | Poetry service on 18492; start not imported, sync and verify rows imported. |
| jingmo_random_poem_orderby_random | latency → load, latency | Populate the classic-poem database; random refresh must display 山水诗 titles. No sync backend needed once populated. |
| jingmo_sync_page_reimport | latency → load, latency | Same sync service and version on each check; prime the dataset before the repeated checks. |
| sepweather_font_register_per_page | memory → memory | Prepare the same saved city (北京); visit and return from city manager 40 times. Font work is local; check identical title and city, not weather API latency. |
| sheafreader_article_list_foreach | latency → load, jank | Populate native reader DB; confirm 300 articles in the first loaded page, then scroll. |
| sheafreader_extract_tag_tolowercase | cpu → load | Reach subscribed RSS on 18491; F5 must actually parse full article bodies. |
| sheafreader_insert_duplicate_exception | cpu → load | Same RSS service; import once, then F5 with unchanged GUIDs and bodies so articles are duplicates. |
| sheafreader_refresh_feeds_sequential | latency → latency | Multiple due subscriptions; use 1.5 s feed delay. Check cold launch **through completion** of automatic refresh. |
| sheafreader_unread_counts_n_plus_1 | latency → load, latency | Preload 100 recently fetched feeds × 1,000 articles; verify all unread badges. Do not measure network refresh instead. |
| wanharmony_persisted_home_list_growth | resource_retention → memory | **External API dependent**: initialized preferences and successful new WanAndroid pages during scrolling. See disposition below. |
| weatherassistant_http_session_leak | resource_retention → memory | Hourly weather API on 18496; ten supported cities, successful 7-day hourly replies, ten warmup returns before forty measured refreshes. |
| weatherassistant_remote_weather_icons | latency → latency | Forecast + four matching icon assets on 18492; cold cache, four-second image delay, check all nine icon regions. |
| ytmusic_current_playing_timeupdate | cpu → load, jank | Play bundled “Welcome to the Black Parade”; verify actual playback, not just cover art. |
| ytmusic_history_json_parse_per_row | cpu → load, jank | Seed 1,000 native history entries, open viewing history and scroll. |
| ytmusic_search_no_debounce | network → load | Search API on 18493; ten key changes and submit, verify final catalogue. Load is the closest route; score bytes, not CPU. |

**Disposition.** This is a dependency audit of the measured path, not a new
21-case device run. Historical clean evidence is not proof of fresh-install
replay today. For WanHarmony, a host GET of
`https://www.wanandroid.com/article/list/0/json` on 2026-11-18 returned
`errorCode: -1`, `data: null`. A cached 首页 screen is **not** a successful
replay. Skip live collection if page fetches fail; record the case and reason,
and report live coverage separately. Prior captures remain valid for offline
diagnosis. Local-library, login and database-dependent cases likewise need their
listed state before a run; do not silently score a blank screen as evidence.

## Preparing inputs

The [fixture tools](../tools/collect/fixtures/) run on the host, not in the HAP.
For local HTTP services start the indicated Python file, then use
`hdc rport tcp:PORT tcp:PORT` on the host connected to the device (substitute
the numeric port on both sides). Run Jingmo and the weather icon service separately:
they share 18492. Inspect responses from the device before collecting.

| Workload | Tool / preparation |
|---|---|
| Browser / random poetry | `seed_browser.py Histories.db` (set days/rows with `--days`, `--per-day`); `seed_classic_poems.py` to generate a fresh poetry database. Restore into the test app's own database with the app stopped. |
| Jingmo sync / CloudMusic search | `jingmo_data_service.py` / `cloudmusic_data_service.py`; Jingmo's setup enters the URL itself. Use `cloudmusic-api-setup.workload.json` before searching. |
| RSS | `rss_data_service.py`, import its `/subscriptions.opml` or subscribe to its feed URLs. Use `--feed-delay 1.5` **only** for sequential refresh. `rss_database_fixture.inspect` checks the ten-feed, 1,000-article dataset; `seed_reader_count_workload.py` builds the separate unread-count dataset from an initialized DB. |
| Weather | `weather_hourly_data_service.py` for session retention; for icons run `weather_data_service.py --icons DIR` where DIR contains the four .img files from the fixed tree's `alatus/src/main/resources/rawfile/weather/`. |
| Preferences | `seed_search_history.py DIR --count 2500`; `seed_ytmusic_history.py --help` takes initialized preferences and song records; `seed_wan_home_cache.py --help` requires initialized preferences and successful real API pages. Installing native app data needs sandbox access on a test device. |
| YTMusic search | `ytsearch_data_service.py` (18493); returns ordinary search results and cover art. |

Restore the same logical starting data before each variant and each repetition;
run setup outside the measured window. Use the testcase's verify phase and the
case-specific oracle notes; a listening TCP socket alone does not establish
that the app reached the faulty path.

## Batch collection on a prepared device

```sh
python3 tools/collect/run_cases.py collected/unfixed --device SERIAL \
  --hapray /opt/HapRay-Skill/bin/hapray --prepare /path/to/lab-setup \
  --cases jingmo_dataset_import_no_transaction jingmo_sync_page_reimport
```

`--prepare` is your executable for the device-specific part: it receives
`CASE_ID VARIANT ROUND SERIAL`, installs the signed variant, restores the
starting data above, configures services, and exits nonzero on setup failure.
It is called **before every round**, including repeats of destructive UI
operations. The collector stages the case's DeviceTest files in a separate
HAPRAY_WORKSPACE for each round, runs the named testcase, checks the CLI
receipt and report directory, and records failures without attributing them
to the diagnosis model. Omit `--cases` for the full included cohort; use a
fresh output root with `--variant fixed` for the comparison. Raw capture
success does not replace the non-HapRay oracle measurements.
