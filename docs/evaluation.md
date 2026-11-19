# Collection and evaluation standard

## Blind input

A tool under evaluation may receive, per case: the **signed unfixed HAP**, `prompt.json`, the
`testcase/` files, optionally dynamic data collected from the unfixed variant (recommended format:
a HapRay `perf` report tree with `hapray-tool-result.json`), and optionally the unfixed source
without git history. It must **not** receive `case.json`, `groundtruth.json`, `fix.patch`, the fixed
variant, oracle values, `source.patch` (its hunks point at the modified code) or the reconstruction repositories under `hosts/`. Report which inputs were given.

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
   (`&entry/src/main/ets/pages/Index&`, `phone|@x/home|1.0.0|src/main/ets/a.ts`) are reduced to their path.
2. **Function level** (default): additionally, the suspect's `symbol` names the location's `symbol`
   (the last component of `Class.method` counts), or the suspect's line range overlaps the location's
   `scope_lines` (functions) or `changed_lines` (fields, constants, module code). An alias only has
   its own lines; it never borrows the line range of the root cause it belongs to.
3. A suspect is **correct** if it matches any `primary` or `related` location. A file-level variant
   (rule 1 only) may be reported in addition and must be labelled as such.

A case without an answer scores P = R = F1 = 0 and keeps its measured cost. Report per-case records
and the **macro average** over all included cases (`python3 tools/catalog.py list`), and the same
average without the weak cases (`--tier strong`, see [cases](cases.md)). Use the same model, budget
and inputs for all cases of a run.

## Batch HapRay evaluation

Three commands take a set of cases from the phone to a score sheet. Each prints what it did per
case and keeps going when one case fails.

**1. Collect HapRay data on the phone** (unfixed variant; you supply the install-and-reset step):

```bash
python3 tools/collect/run_cases.py captures/ --device SERIAL --prepare ./my_prepare.sh [--scene load]
```

`my_prepare.sh CASE_ID VARIANT ROUND SERIAL` installs your signed build of that variant and restores
the case's input data ([what each case needs](cases.md#input-data-and-backends);
`tools/collect/prepare_browser.py` is a complete example for the browser cases). Memory-scene cases
are collected with `hapray perf --memory`.

**2. Run the HapRay skill on every case**, with any agent CLI (example: Claude Code with the
[HapRay-Skill](https://gitcode.com/SMAT/HapRay-Skill) plugin installed):

```bash
python3 tools/evaluate/run_hapray.py captures/ runs/v1 --with-source -- \
  claude -p "$(cat tools/evaluate/agent_prompt.md)"
```

Each case gets a blind input directory (symptom, HapRay data, optionally the unfixed source) and an
empty output directory; `{input}`, `{output}` and `{case}` in the command are replaced by them. The
[prompt](../tools/evaluate/agent_prompt.md) asks the agent to keep HapRay's reports and `fix-plan.json`
and to write `answer.json` (ranked suspects, each with root cause and fix).

**3. Score against the ground truth and `fix.patch`:**

```bash
python3 tools/evaluate/score.py runs/v1 --out results.json --md results.md
```

`score.py` reads `answer.json`, or else HapRay-Skill's own `fix-plan.json`, HapRay's
`root_cause_agent_result.json` or a scene report `hapray-analysis-*-<scene>-*.md`, so HapRay output
can also be scored directly. It prints one table for all cases, for strong cases only and per HapRay
scene, then one row per case:

| Column | Meaning |
|---|---|
| `top1`, `top5` | share of cases whose first suspect / one of the first five suspects is a primary root cause |
| `precision`, `recall`, `f1` | the metrics above, averaged over cases |
| `fix_file_hit` | the first fix suggestion changes a file that `fix.patch` changes |
| `fix_hunk_hit` | ... and its location is within 10 lines of a changed hunk, or in a root-cause function |
| `scene_match` | HapRay analyzed the case's scene (or a secondary one), from [this table](cases.md#which-cases-test-which-hapray-scene) |
| `diagnosis_correct`, `repair_correct` | optional: a judge read the first suggestion beside the real mechanism and `fix.patch` |

A location match does not prove that the explanation or the repair is right. For that, judge the
first suggestion of each case with a model (or write the same JSON by hand):

```bash
python3 tools/evaluate/score.py runs/v1 --review-packet packet.json
python3 tools/evaluate/judge.py packet.json verdicts.json -- claude -p
python3 tools/evaluate/score.py runs/v1 --verdicts verdicts.json --md results.md
```

Accuracy is shown only when every answered case has a verdict; a verdict is ignored once the output
or the reference changes. The packet and verdicts contain the answers: never put them where the
diagnosis agent can read them.

[Evaluating HapRay-Skill: step by step](hapray-eval.md) lists these steps as a checklist, for a
person or an agent.
