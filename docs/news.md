# News

The README keeps a short version of this list.

- **2026-11** The HapRay evaluation checklist moved to [hapray-eval.md](hapray-eval.md) (`9941f2d`).
- **2026-11** PR #3 merged: weak-case marking, input-data audit, mapping of cases to HapRay scenes, and batch collection and scoring tools. It closes issue #1.
- **2026-11** Three new measured cases added; one case excluded because its public backend stopped answering. The benchmark now has 23 included cases (`d31b05f`, `59b52af`).
- **2026-11** Input-data fixtures and local replay services restored in `tools/collect/fixtures/` (`9f8b553`).
- **2026-11** Two versions of the HapRay analysis skill were evaluated on the 21 cases included at the time, with three paired runs.
- **2026-11** Issue #1 opened with improvement requests for evaluating HapRay-Skill on OhmBench: weak cases, backend dependencies, scene mapping, more cases and batch scoring.
- **2026-11** Each case made self-contained as `source.patch` + `fix.patch` on a public upstream commit (`225e358`). Nine cases that failed the performance gate were removed, leaving 21 (`8a5e4e7`).
- **2026-11** Project renamed from OhmBenchmark to OhmBench (`11d4fbc`).
- **2026-11** First version: 30 candidate cases with host patches and offline tools (`2863a47`).
