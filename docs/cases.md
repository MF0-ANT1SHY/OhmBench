# Cases

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

## Case list

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
