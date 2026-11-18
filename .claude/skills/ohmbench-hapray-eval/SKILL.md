---
name: ohmbench-hapray-eval
description: Run HapRay-Skill on OhmBench cases in batch and score its diagnoses and fix suggestions against the benchmark ground truth (fix.patch). Use when asked to evaluate, benchmark or regression-test HapRay / HapRay-Skill on OhmBench.
---

# Evaluate HapRay-Skill on OhmBench

Work from the OhmBench checkout. Never show `groundtruth.json`, `fix.patch`, `case.json`, the fixed
build, the review packet or verdicts to the agent that does the diagnosis.

1. **Pick cases.** `python3 tools/catalog.py list [--scene load|memory|jank|latency] [--tier strong]`.
   `docs/cases.md` shows each case's HapRay scene and the input data it needs.
2. **Get HapRay data** for the unfixed variant. If captures exist, use them (`CAPTURES/<case-id>/`).
   Otherwise, on a prepared phone:
   `python3 tools/collect/run_cases.py CAPTURES --device SERIAL --prepare PREPARE_SCRIPT --cases ...`
   (the user provides signed builds and the prepare script; see docs/evaluation.md).
3. **Run HapRay-Skill per case** with a fresh agent per case and the same model, budget and inputs:
   `python3 tools/evaluate/run_hapray.py CAPTURES runs/NAME --with-source -- <agent CLI> "$(cat tools/evaluate/agent_prompt.md)"`.
   Record the HapRay-Skill commit and the model.
4. **Score:** `python3 tools/evaluate/score.py runs/NAME --out runs/NAME/results.json --md runs/NAME/results.md`.
5. **Optionally judge** the first diagnosis and repair of each case:
   `score.py runs/NAME --review-packet P.json`, `judge.py P.json V.json -- <judge CLI>`,
   `score.py runs/NAME --verdicts V.json --md runs/NAME/results.md`. Use a different model from step 3.
6. **Report** the summary table (all cases, strong only, per scene), the number of cases without an
   answer, the HapRay-Skill commit, the model and the judge. To compare two HapRay-Skill versions,
   run steps 3–5 for both on the same captures and show both tables.
