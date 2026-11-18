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
   (`&entry/src/main/ets/pages/Index&`) are reduced to their path.
2. **Function level** (default): additionally, the suspect's `symbol` names the location's `symbol`
   (the last component of `Class.method` counts), or the suspect's line range overlaps the location's
   `scope_lines` (functions) or `changed_lines` (fields, constants, module code).
3. A suspect is **correct** if it matches any `primary` or `related` location. A file-level variant
   (rule 1 only) may be reported in addition and must be labelled as such.

A case without an answer scores P = R = F1 = 0 and keeps its measured cost. Report per-case records
and the **macro average** over all 22 cases (and optionally micro averages, pooling
suspects and root causes). Use the same model, budget and inputs for all cases of a run.

## Batch HapRay evaluation

1. Stage **only blind inputs** under `blind/<id>/`. Pin the
   [HapRay Skill](https://gitcode.com/SMAT/HapRay-Skill) revision, model,
   scene, prompt and budget for a comparison. Use a separate agent environment
   without access to the evaluator checkout. The runner changes directory; it
   is not a security sandbox.
2. Run one agent invocation per staged case. For example, on an evaluation
   host with the skill installed in Codex and unfixed captures already staged:

   ```sh
   python3 tools/evaluate/run_batch.py blind runs/v1 codex exec --skip-git-repo-check \
     -o '{output}/answer.json' \
     'Use the HapRay skill to analyze the unfixed captures for prompt.json. Do not edit the app. Return only JSON with suspects sorted by rank. For each give rank, file, symbol, line_start, line_end, root_cause and fix (concrete recommendation).'
   ```

   Other agents can use the same argv interface; `{input}` and `{output}`
   are absolute directories. Use a fresh output root. Failed commands are
   recorded per case and do not stop later cases.
3. Score the batch on the evaluator host:

   ```sh
   python3 tools/evaluate/hapray.py runs/v1 --report '{case}/answer.json' \
     --out results.json --review-packet private-review.json
   ```

   The default report pattern reads existing
   `{case}/report/root_cause_agent_result.json`. For native HapRay-Skill
   [v1.3 fix plans](https://gitcode.com/SMAT/HapRay-Skill/blob/a8e53f853528513ddbca60abc3ed8213a1ecc985/skills/optimize/hapray-fix-planning/references/fix-plan-template.json), pass `--report '{case}/fix-plan.json'` (or the actual path
   under each exported workspace). These plans score **selected proposals
   in file order**; they are not the whole scene analysis. Keep selection
   scope and ordering consistent across revisions. For Markdown scene reports,
   have the agent export its ranked findings in the JSON format above.
   File/function localization uses the first five answers. A missing, invalid
   or failed run earns zero; inspecting a subset requires explicit `--cases`.
4. The review packet places each first answer beside the actual `fix.patch`,
   reference mechanism and fix summary. **Location overlap is not repair
   correctness.** Mark `diagnosis_correct` only for the causal operation and
   mechanism; mark `repair_correct` for a specific, behavior-preserving repair
   of that cost, including equivalent alternatives. For manual review create
   a JSON object keyed by case ID, each value containing the packet's
   `fingerprint` and both boolean judgments. Alternatively run a separate
   model judge (the chosen model receives the evaluator-only packet):

   ```sh
   python3 tools/evaluate/judge.py private-review.json verdicts.json --model MODEL
   python3 tools/evaluate/hapray.py runs/v1 --report '{case}/answer.json' \
     --reviews verdicts.json --out reviewed-results.json
   ```

   Report judge identity and audit its rationales; these are estimates of
   recommendation correctness, not evidence an applied repair builds or meets
   its device oracle. Top-1 diagnosis and repair accuracies use **all selected
   cases**, with missing answers counted as misses. Until all outstanding
   judgments are supplied, accuracy is null and the pending count is shown.
   Changed reports or reference patches invalidate prior verdicts. Never
   stage the private packet or verdicts in the diagnosis workspace.
