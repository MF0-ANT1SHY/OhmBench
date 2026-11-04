# 性能问题诊断任务

应用 `{bundle_name}`（入口 Ability：`{ability}`）存在性能问题。

- 用户反馈：{symptom}
- 复现场景：{scenario}（相关场景：{perf_scenarios_text}）

本目录提供：未修复版本的应用包 `app.hap`、中立的 UI 复现脚本 `testcase/`，以及可能提供的
HapRay 动态数据 `hapray/` 和源码 `source/`。

请定位导致该问题的源码位置，按可能性从高到低给出最多 5 个嫌疑位置，并以 JSON 写入输出文件：

```json
{{
  "case": "{case}",
  "suspects": [
    {{
      "rank": 1,
      "file": "模块内源码路径，例如 entry/src/main/ets/pages/Index.ets",
      "class": "类或组件名（可省略）",
      "symbol": "函数、方法、字段或常量名",
      "line_start": 0,
      "line_end": 0,
      "description": "问题机制与依据"
    }}
  ],
  "usage": {{"input_tokens": 0, "output_tokens": 0}}
}}
```

`line_start`/`line_end` 无法确定时可省略；`usage` 填写本次诊断实际消耗的 token（无法统计时省略）。