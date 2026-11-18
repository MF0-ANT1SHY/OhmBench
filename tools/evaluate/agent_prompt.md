You are diagnosing a performance problem in a HarmonyOS app with the HapRay skill.

The current directory contains:
- prompt.json: the app bundle and the symptom a user reported;
- capture/: HapRay data collected while reproducing the symptom on the unfixed app;
- source/ (only if present): the app's source code.

Use the HapRay skill (scene analysis: load, memory, jank or latency, whichever fits the
symptom and data; then fix planning) to find the cause. Do not change any files outside
the output directory {output}. Keep HapRay's own reports and fix-plan.json in {output}.

Finally write {output}/answer.json exactly in this form, most likely cause first, at most 5:

{"scene": "load|memory|jank|latency",
 "suspects": [
  {"rank": 1, "file": "entry/src/main/ets/...ets", "symbol": "Class.method",
   "line_start": 10, "line_end": 20,
   "root_cause": "what operation is costly and why",
   "fix": "the concrete code change you recommend"}
 ]}
