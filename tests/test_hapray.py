import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/evaluate'))
from hapray import CASES, score


class HapRayEvaluationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.report = Path(temp.name) / 'answer.json'
        self.case = CASES / 'browser_history_delete_no_transaction'

    def grade(self, reviews=None, run=None):
        return score(self.case, self.report, reviews or {}, run)

    def test_repair_review_is_separate_from_localization(self):
        plan = {'proposals': [{'finding': {'locator': {'source_file': 'utils/RdbUtils.ts',
                                                       'symbol': 'deleteAll'},
                                          'evidence': {'root_cause_l2': 'One commit per deletion'}},
                               'patch_strategy': 'Cache images'}]}
        self.report.write_text(json.dumps(plan))
        row, packet = self.grade()
        self.assertEqual(row['f1'], 1)
        self.assertIsNone(row['repair_correct'])
        self.assertEqual(packet['reference_patch'], (self.case / 'fix.patch').read_text())
        reviews = {self.case.name: dict(fingerprint=row['fingerprint'], diagnosis_correct=True,
                                        repair_correct=False)}
        self.assertIs(self.grade(reviews)[0]['repair_correct'], False)
        self.report.write_text(json.dumps(plan, indent=2))
        with self.assertRaisesRegex(ValueError, 'different report'):
            self.grade(reviews)

    def test_missing_invalid_and_failed_are_not_successes(self):
        self.assertEqual(self.grade()[0]['status'], 'missing')
        self.report.write_text('{"suspects": {}}')
        self.assertTrue(self.grade()[0]['status'].startswith('invalid:'))
        self.report.write_text('{"suspects": [{"file":"utils/RdbUtils.ts","symbol":"deleteAll"}]}')
        row, _ = self.grade(run={'exit_code': 1})
        self.assertEqual((row['status'], row['f1'], row['repair_correct']), ('run_failed', 0, False))

    def test_correct_sixth_suspect_is_a_miss(self):
        bad = [{'rank': i, 'file': 'pages/Index.ts', 'symbol': 'noMatch'} for i in range(1, 6)]
        self.report.write_text(json.dumps({'suspects': [
            {'rank': 6, 'file': 'utils/RdbUtils.ts', 'symbol': 'deleteAll'}, *bad]}))
        self.assertEqual(self.grade()[0]['recall'], 0)
