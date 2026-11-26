# Overview

**23 included cases from 8 apps** (1 more case is excluded; [list](cases.md)).

## Prerequisites

To use this benchmark, users are expected to provide two things: 1) a HarmonyOS signing certificate for **signing apps and installing them on the device**, and 2) a device running apps.

In detail:

- Python 3.10+ and git.
- HarmonyOS command-line tools (SDK 5.1.0 was used), linked at `toolchain/command-line-tools`. They provide `ohpm`, `hvigorw` and `ark_disasm`.
- Your own HarmonyOS signing certificate, profile and keystore.
- A HarmonyOS phone reachable with `hdc` (the newest reference measurements used a Pura 70 Ultra).
- [ArkAnalyzer-HapRay](https://github.com/SMAT-Lab/ArkAnalyzer-HapRay) for collection, and the tool you want to evaluate (for example [HapRay-Skill](https://gitcode.com/SMAT/HapRay-Skill) with an agent CLI).

## What the benchmark provides

The benchmark provides two parts: 1) Data, and 2) Code.

| Part | Detail |
|---|---|
| **Data** | per case: **source + patch** to build the unfixed and fixed app, the **prompt**, and the **oracle** (groundtruth); a neutral UI workload ([details](data.md)) |
| **Catalog** | per case: effect size and quality tier, required input data / backend, and the matching HapRay scene ([tables](cases.md), `tools/catalog.py`) |
| **Code(build)** | `tools/` — reconstruct the sources from public upstreams and build both variants ([details](build.md)) |
| **Code(extend)** | the [case standard](case-standard.md) every new case must follow |
| **Code(collect / evaluate)** | the [evaluation standard](evaluation.md) and batch tools: collect HapRay data, run HapRay-Skill on every case, score it against `fix.patch` |

No benchmark code, counters, custom traces or instrumentation are compiled into the apps.

## End-to-end run

```bash
# 1. Rebuild both source variants of every case from public upstreams
python3 tools/prepare_sources.py

# 2. Build unsigned HAPs and audit them
mkdir -p toolchain && ln -s /path/to/command-line-tools toolchain/command-line-tools
python3 tools/build_cases.py [case-id ...]
#    -> artifacts/<case-id>/{unfixed,fixed}/app-unsigned.hap; sign them yourself

# 3. Collect HapRay data from the unfixed variant on a phone
python3 tools/collect/run_cases.py captures/ --device SERIAL --prepare ./my_prepare.sh

# 4. Run the tool under test, one blind case at a time
python3 tools/evaluate/run_hapray.py captures/ runs/v1 --with-source -- \
  claude -p "$(cat tools/evaluate/agent_prompt.md)"

# 5. Score
python3 tools/evaluate/score.py runs/v1 --out results.json --md results.md
```

`my_prepare.sh CASE_ID VARIANT ROUND SERIAL` installs your signed build and restores the case's input data.
[tools/collect/prepare_browser.py](../tools/collect/prepare_browser.py) is a complete example.
More on building and signing: [build.md](build.md).
More on each evaluation step: [evaluation.md](evaluation.md).

## Repository tools

| Path | Role |
|---|---|
| `cases/<case-id>/` | the cases ([layout](data.md#repository-layout)) |
| `cases/collection.yaml` | reference HapRay / hiprofiler collection configuration |
| `tools/catalog.py` | validate cases (`check`), select them (`list`), regenerate the case tables (`docs`) |
| `tools/prepare_sources.py` | clone upstream apps into `hosts/`, apply the patches, verify tree hashes |
| `tools/build_cases.py` | build unsigned HAPs for both variants with `ohpm` and `hvigorw` |
| `tools/audit_app.py` | reject benchmark code in the source and the disassembled bytecode |
| `tools/collect/run_cases.py` | batch HapRay collection on one phone |
| `tools/collect/prepare_browser.py` | example prepare hook (install + restore input data) |
| `tools/collect/fixtures/` | input-data seed scripts and local replay services |
| `tools/evaluate/run_hapray.py` | stage blind inputs and run any tool command per case |
| `tools/evaluate/agent_prompt.md` | the reference prompt for an agent with HapRay-Skill |
| `tools/evaluate/score.py` | score answers against the ground truth and `fix.patch` |
| `tools/evaluate/judge.py` | ask a model (or a person) to judge diagnosis and repair |
| `tests/` | unit tests for the catalog, scoring and batch runner |
