# OhmBench

A benchmark of performance bugs in HarmonyOS applications, for evaluating performance-diagnosis abilities.

- [Overview](docs/overview.md): prerequisites, and what the benchmark provides
- [Data](docs/data.md): repository layout, source + patch, prompt, oracle, workload
- [Building and signing](docs/build.md): reconstruct sources and build the unfixed/fixed HAPs
- [Extension standard](docs/extending.md): requirements for adding a case
- [Collection and evaluation standard](docs/evaluation.md): inputs, per-case record, metrics, matching,
  and the [batch HapRay evaluation](docs/evaluation.md#batch-hapray-evaluation) (collect, run, score)
- [Evaluating HapRay-Skill: step by step](docs/hapray-eval.md): checklist for a batch run
- [Cases](docs/cases.md): host apps and cases, effect size (weak cases), input data and backends,
  HapRay scene of each case
- [Known limitations](docs/limitations.md)
