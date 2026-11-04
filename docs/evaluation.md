# Collection and evaluation standard

## Blind input

A tool under evaluation may receive, per case: the **signed unfixed HAP**, `prompt.json`, the
`testcase/` files, optionally dynamic data collected from the unfixed variant (recommended format:
a HapRay `perf` report tree with `hapray-tool-result.json`), and optionally the unfixed source
without git history. It must **not** receive `case.json`, `groundtruth.json`, `fix.patch`, the fixed
variant, oracle values or `hosts_patches/`. Report which inputs were given.

## Per-case record

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

## Metrics

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
