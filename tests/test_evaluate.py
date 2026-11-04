import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'evaluate'))
from score import path_match, score_case  # noqa: E402

GT = {"root_causes": [
    {"id": "RC1", "role": "primary", "kind": "function", "file": "entry/src/main/ets/utils/RdbUtils.ets",
     "class": "RdbUtils", "symbol": "deleteAll", "changed_lines": [169, 185], "scope_lines": [167, 188],
     "aliases": [{"file": "entry/src/main/ets/utils/RdbUtils.ets", "class": "RdbUtils", "symbol": "deleteHistory"}]},
    {"id": "RC2", "role": "primary", "kind": "constant", "file": "commons/constants/src/main/ets/DbConst.ets",
     "class": "DbCRUDConst", "symbol": "READ_RANDOM", "changed_lines": [28, 32]},
    {"id": "RC3", "role": "related", "kind": "module", "file": "entry/src/main/ets/view/PagesDialog.ets",
     "class": None, "symbol": None, "changed_lines": [3, 4]},
]}


class PathMatchTest(unittest.TestCase):
    def test_suffix_and_record_names(self):
        gt = "entry/src/main/ets/pages/Index.ets"
        self.assertTrue(path_match("source/entry/src/main/ets/pages/Index.ets", gt))
        self.assertTrue(path_match("pages/Index.ts", gt))
        self.assertTrue(path_match("&entry/src/main/ets/pages/Index&", gt))
        self.assertTrue(path_match("entry|entry|1.0.0|src/main/ets/pages/Index.ts", gt))
        self.assertTrue(path_match("Index.ets", gt))
        self.assertFalse(path_match("other/Index.ets", gt))
        self.assertFalse(path_match("libnative_rdb.z.so", gt))


class ScoreTest(unittest.TestCase):
    def test_perfect_and_empty(self):
        pred = {"suspects": [
            {"rank": 1, "file": "utils/RdbUtils.ets", "symbol": "RdbUtils.deleteAll"},
            {"rank": 2, "file": "DbConst.ets", "symbol": "DbCRUDConst.READ_RANDOM"}]}
        s = score_case(pred, GT, "function", 5)
        self.assertEqual((s["precision"], s["recall"], s["f1"]), (1.0, 1.0, 1.0))
        s = score_case({"suspects": []}, GT, "function", 5)
        self.assertEqual((s["precision"], s["recall"], s["f1"]), (0.0, 0.0, 0.0))

    def test_alias_lines_related_and_top_k(self):
        pred = {"suspects": [
            {"rank": 1, "file": "entry/src/main/ets/utils/RdbUtils.ets", "symbol": "deleteHistory"},  # alias of RC1
            {"rank": 2, "file": "entry/src/main/ets/view/PagesDialog.ets", "line_start": 3},          # related
            {"rank": 3, "file": "entry/src/main/ets/pages/Index.ets", "symbol": "aboutToAppear"},     # wrong
            {"rank": 4, "file": "DbConst.ets", "line_start": 30, "line_end": 31}]}                     # RC2 by lines
        s = score_case(pred, GT, "function", 5)
        self.assertEqual(s["primary_found"], ["RC1", "RC2"])
        self.assertAlmostEqual(s["precision"], 0.75)
        s = score_case(pred, GT, "function", 2)
        self.assertEqual((s["recall"], s["precision"]), (0.5, 1.0))

    def test_function_level_requires_symbol_or_lines(self):
        pred = {"suspects": [{"rank": 1, "file": "utils/RdbUtils.ets", "symbol": "insertDate"}]}
        self.assertEqual(score_case(pred, GT, "function", 5)["recall"], 0.0)
        self.assertEqual(score_case(pred, GT, "file", 5)["recall"], 0.5)


class GroundtruthFilesTest(unittest.TestCase):
    def test_every_case_has_valid_groundtruth_and_included_cases_have_prompts(self):
        for case_dir in sorted((ROOT / "cases").iterdir()):
            if not (case_dir / "case.json").exists():
                continue
            case = json.loads((case_dir / "case.json").read_text())
            gt = json.loads((case_dir / "groundtruth.json").read_text())
            self.assertEqual(gt["case"], case["id"])
            self.assertTrue(any(r["role"] == "primary" for r in gt["root_causes"]), case["id"])
            self.assertIn("metric", gt["performance_oracle"])
            if case["status"] == "included":
                prompt = json.loads((case_dir / "prompt.json").read_text())
                self.assertTrue(prompt["symptom"])
                self.assertNotIn("root_causes", prompt)


if __name__ == "__main__":
    unittest.main()