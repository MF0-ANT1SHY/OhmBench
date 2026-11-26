**English** | [简体中文](README.zh-CN.md)

# OhmBench

OhmBench is a benchmark of real performance bugs in open-source HarmonyOS (ArkTS) apps.
Each case pairs a buggy build with a fixed build of the same app.
A tool under test gets the symptom and runtime data, and must find the costly code and propose a repair.
OhmBench scores the answer against the known root cause and the real fix.
It is for teams that build or compare HarmonyOS performance-diagnosis tools.

Today: **23 included cases from 8 apps** (20 strong, 3 weak), plus 1 excluded ([list](docs/cases.md)).

![OhmBench architecture](docs/architecture.svg)

| Concept | Where it lives |
|---|---|
| Add a case | [docs/case-standard.md](docs/case-standard.md) |
| Case corpus | [`cases/<case-id>/`](cases/), [`tools/catalog.py`](tools/catalog.py) |
| Build & sign | [`tools/prepare_sources.py`](tools/prepare_sources.py), [`tools/build_cases.py`](tools/build_cases.py), [`tools/audit_app.py`](tools/audit_app.py) |
| On-device run | [`tools/collect/run_cases.py`](tools/collect/run_cases.py), [`tools/collect/fixtures/`](tools/collect/fixtures/) |
| Detector under test | [`tools/evaluate/run_hapray.py`](tools/evaluate/run_hapray.py), [`agent_prompt.md`](tools/evaluate/agent_prompt.md) |
| Ground truth | `groundtruth.json`, `fix.patch` in each case |
| Scoring & judging | [`tools/evaluate/score.py`](tools/evaluate/score.py), [`tools/evaluate/judge.py`](tools/evaluate/judge.py) |
| Report | `score.py --out results.json --md results.md` |

## News

- **2026-11** HapRay evaluation checklist moved to [docs/hapray-eval.md](docs/hapray-eval.md) (`9941f2d`).
- **2026-11** PR #3 merged: weak cases, input-data audit, scene mapping, batch tools. Closes issue #1.
- **2026-11** Three cases added, one excluded (backend down): 23 included (`d31b05f`, `59b52af`).
- **2026-11** Input-data fixtures and replay services restored (`9f8b553`).
- **2026-11** Two HapRay skill versions evaluated on 21 cases, three paired runs.
- **2026-11** Issue #1 opened with requests for evaluating HapRay-Skill.
- **2026-11** Cases made self-contained as patches on public commits (`225e358`); nine failed the performance gate, 21 left (`8a5e4e7`).
- **2026-11** Renamed from OhmBenchmark to OhmBench (`11d4fbc`).
- **2026-11** First version: 30 candidate cases (`2863a47`).

Full entries: [docs/news.md](docs/news.md).

## Design

- **Real bugs** on real user paths of public open-source apps.
- **Buggy/fixed pairs** from one upstream commit; `fix.patch` holds only the repair.
- **Measured on a phone**: the buggy build must cost more, over at least three rounds.
- **Blind**: the tool never sees the fix or the ground truth.
- **Weak cases flagged**: every score is also reported without them.

Details: [docs/design.md](docs/design.md).

## Case standard

A case is a directory `cases/<case-id>/` with metadata, prompt, ground truth, two patches and a workload.
[docs/case-standard.md](docs/case-standard.md) defines the criteria, the schema and the checklist.
`python3 tools/catalog.py check` validates every case.

## Evaluation and metrics

Select cases, collect data on a phone, run the tool blind, score, optionally judge.
Metrics: `top1`/`top5`, `precision`/`recall`/`f1`, `fix_file_hit`/`fix_hunk_hit`, `scene_match`, judge verdicts.
Scores are macro averages, also for strong cases only and per HapRay scene.
Details: [docs/evaluation.md](docs/evaluation.md).

## Quick start

Needs Python 3.10+, HarmonyOS command-line tools, a signing certificate, a phone and HapRay ([details](docs/overview.md#prerequisites)).

```bash
python3 tools/prepare_sources.py && python3 tools/build_cases.py    # then sign the HAPs
python3 tools/collect/run_cases.py captures/ --device SERIAL --prepare ./my_prepare.sh
python3 tools/evaluate/run_hapray.py captures/ runs/v1 --with-source -- claude -p "$(cat tools/evaluate/agent_prompt.md)"
python3 tools/evaluate/score.py runs/v1 --out results.json --md results.md
```

Walkthrough: [docs/overview.md](docs/overview.md#end-to-end-run).

## Contributing

- **Add a case:** follow [the case standard](docs/case-standard.md#6-acceptance-criteria-for-the-catalog).
- **Add a detector:** any command that writes `answer.json` ([how](docs/evaluation.md#adding-a-detector)).

## Documentation

[Overview](docs/overview.md) · [Design](docs/design.md) · [Case standard](docs/case-standard.md) · [Data](docs/data.md) · [Build and sign](docs/build.md) · [Evaluation](docs/evaluation.md) · [HapRay-Skill checklist](docs/hapray-eval.md) · [Cases](docs/cases.md) · [Limitations](docs/limitations.md)
