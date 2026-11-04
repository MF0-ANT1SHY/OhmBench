import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'collect'))
from oracle_metrics import app_cpu_ms, app_instructions, round_values  # noqa: E402
from validate_hapray_data import validate  # noqa: E402

BUNDLE = "com.example.longbundlename"


def make_round(root, instructions, cpu_ns):
    perf = root / "hiperf" / "step1"
    trace = root / "htrace" / "step1"
    perf.mkdir(parents=True)
    trace.mkdir(parents=True)
    c = sqlite3.connect(perf / "perf.db")
    c.execute("create table perf_thread (id, thread_id, process_id, thread_name)")
    c.execute("create table perf_sample (id, callchain_id, timeStamp, thread_id, event_count)")
    c.executemany("insert into perf_thread values (?,?,?,?)",
                  [(0, 100, 100, BUNDLE[-15:]), (1, 101, 100, "worker"), (2, 7, 7, "other")])
    c.executemany("insert into perf_sample values (?,?,?,?,?)",
                  [(0, 0, 0, 100, instructions // 2), (1, 0, 0, 101, instructions // 2), (2, 0, 0, 7, 999)])
    c.commit()
    t = sqlite3.connect(trace / "trace.db")
    t.execute("create table process (id, ipid, pid, name)")
    t.execute("create table sched_slice (id, ts, dur, ipid)")
    t.executemany("insert into process values (?,?,?,?)", [(1, 1, 100, BUNDLE[-15:]), (2, 2, 7, "other")])
    t.executemany("insert into sched_slice values (?,?,?,?)", [(0, 0, cpu_ns, 1), (1, 0, 5, 2)])
    t.commit()


class CollectTest(unittest.TestCase):
    def test_metrics_and_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "20260101000000"
            for i, (ins, ns) in enumerate([(1000, 2_000_000), (1200, 3_000_000), (1100, 4_000_000)]):
                make_round(base / f"PerfLoad_x_0010_round{i}", ins, ns)
            (base / "PerfLoad_x_0010" / "report").mkdir(parents=True)
            (base / "PerfLoad_x_0010" / "report" / "summary.json").write_text("[]")
            self.assertEqual(validate(base), [])
            self.assertEqual(app_instructions(base / "PerfLoad_x_0010_round1", BUNDLE), 1200)
            self.assertEqual(app_cpu_ms(base / "PerfLoad_x_0010_round2", BUNDLE), 4.0)
            self.assertEqual([v for _, v in round_values(base, "hiperf_instructions", BUNDLE)], [1000, 1200, 1100])

    def test_invalid_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "hiperf" / "step1").mkdir(parents=True)
            problems = validate(tmp)
            self.assertTrue(any("perf.data" in p for p in problems))
            self.assertTrue(any("summary.json" in p for p in problems))


if __name__ == "__main__":
    unittest.main()