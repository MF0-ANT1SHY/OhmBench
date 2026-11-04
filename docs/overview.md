# Overview

**30 cases from 9 apps: 21 included, 9 excluded** ([list](cases.md)). Excluded cases build and run but
did not meet their performance oracle; they are kept for reference and must not be used for
evaluation.

## Prerequisite

To use this benchmark, users are expected to provide two things: 1) a HarmonyOS signing certificate for **signing apps and installing them on the device**, and 2) a device running apps.

## What the benchmark provides

The benchmark provides two parts: 1) Data, and 2) Code.

| Part | Detail |
|---|---|
| **Data** | per case: **source + patch** to build the unfixed and fixed app, the **prompt**, and the **oracle** (groundtruth); a neutral UI workload ([details](data.md)) |
| **Code(build)** | `tools/` — reconstruct the sources from public upstreams and build both variants ([details](build.md)) |
| **Code(extend)** | the [case standard](extending.md) every new case must follow |
| **Code(collect / evaluate)** | the [evaluation standard](evaluation.md): what to measure per case and how |

No benchmark code, counters, custom traces or instrumentation are compiled into the apps.
