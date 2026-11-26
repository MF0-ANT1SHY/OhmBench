# Overview

**23 included cases from 8 apps** (1 more case is excluded; [list](cases.md)).

## Prerequisite

To use this benchmark, users are expected to provide two things: 1) a HarmonyOS signing certificate for **signing apps and installing them on the device**, and 2) a device running apps.

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
