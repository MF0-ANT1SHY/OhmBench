"""Tests for the case catalog and HapRay scoring.  Run: python3 -m unittest discover tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools' / 'evaluate'))
import catalog  # noqa: E402
import score  # noqa: E402

CASE = 'sheafreader_search_no_debounce'


def case(cid=CASE):
    return next(c for c in catalog.load() if c['id'] == cid)


class CatalogTest(unittest.TestCase):
    def test_all_cases_valid(self):
        self.assertEqual(catalog.check(catalog.load()), [])

    def test_docs_up_to_date(self):
        text = catalog.DOC.read_text(encoding='utf-8')
        self.assertIn(catalog.render(catalog.load()), text, 'run: python3 tools/catalog.py docs')

    def test_excluded_cases_are_not_selected(self):
        ids = {c['id'] for c in catalog.select(catalog.load())}
        self.assertNotIn('wanharmony_persisted_home_list_growth', ids)
        self.assertIn(CASE, ids)

    def test_weak_tier(self):
        weak = {c['id'] for c in catalog.select(catalog.load(), tier='weak')}
        self.assertEqual(weak, {'browser_eager_history_load', 'sheafreader_extract_tag_tolowercase',
                                'sheafreader_insert_duplicate_exception'})

    def test_scene_selection_includes_secondary(self):
        jank = {c['id'] for c in catalog.select(catalog.load(), scene='jank')}
        self.assertIn('browser_history_list_foreach', jank)


class ScoreTest(unittest.TestCase):
    def run_case(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / CASE
            for name, content in files.items():
                p = d / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content if isinstance(content, str) else json.dumps(content), encoding='utf-8')
            row, packet = score.score_case(case(), d, {})
            return row, packet

    def test_answer_hits_root_cause_and_fix(self):
        row, packet = self.run_case({'answer.json': {'scene': 'load', 'suspects': [
            {'rank': 1, 'file': 'entry/src/main/ets/state/AppStore.ets', 'symbol': 'AppStore.search',
             'line_start': 546, 'line_end': 549, 'root_cause': 'scan per key', 'fix': 'debounce'}]}})
        self.assertEqual((row['top1'], row['top5'], row['recall'], row['precision']), (True, True, 1.0, 1.0))
        self.assertTrue(row['fix_file_hit'] and row['fix_hunk_hit'])
        self.assertTrue(row['scene_match'])
        self.assertEqual(packet['first_suggestion']['fix'], 'debounce')

    def test_alias_counts_and_wrong_file_does_not(self):
        row, _ = self.run_case({'answer.json': {'suspects': [
            {'rank': 1, 'file': 'pages/Index.ets', 'symbol': 'search'},
            {'rank': 2, 'file': 'components/ArticleListView.ets', 'symbol': 'onChange'}]}})
        self.assertFalse(row['top1'])
        self.assertEqual(row['first_hit_rank'], 2)
        self.assertEqual(row['precision'], 0.5)

    def test_one_segment_suspect_does_not_match_deep_path(self):
        self.assertFalse(score.same_file('AppStore.ets', 'entry/src/main/ets/state/AppStore.ets'))
        self.assertTrue(score.same_file('phone|@x/home|1.0.0|src/main/ets/state/AppStore.ts',
                                        'entry/src/main/ets/state/AppStore.ets'))

    def test_fix_plan(self):
        plan = {'proposals': [{'finding': {'domain': 'jank', 'locator': {
            'source_file': 'entry/src/main/ets/data/DatabaseManager.ets', 'line': 500, 'symbol': 'getArticles'},
            'evidence': {}}, 'patch_strategy': 'select fewer columns',
            'target_files': ['entry/src/main/ets/data/DatabaseManager.ets']}]}
        row, _ = self.run_case({'ws/.hapray/fix/fix-plan.json': plan})
        self.assertEqual(row['format'], 'fix-plan')
        self.assertEqual(row['precision'], 1.0)     # related root cause is a correct suspect
        self.assertEqual(row['recall'], 0.0)        # but not the primary one
        self.assertFalse(row['fix_file_hit'])       # fix.patch does not touch DatabaseManager
        self.assertFalse(row['scene_match'])        # load case analyzed as jank

    def test_scene_report_markdown(self):
        md = ('# 报告\n\n## 根因分析\n\n### P0 搜索每次按键全量扫描\n'
              'HapRay 证据 ... 源码根因 `AppStore.search` at entry/src/main/ets/state/AppStore.ets:547\n'
              '修复建议：\n对搜索做防抖\n\n### P1 其他\n无源码定位\n')
        row, _ = self.run_case({'reports/hapray-analysis-20261118-sheaf-load-pre.md': md})
        self.assertEqual((row['format'], row['reported_scene'], row['top1']), ('scene-report', 'load', True))

    def test_missing_output_scores_zero(self):
        row, _ = self.run_case({})
        self.assertEqual((row['status'], row['f1'], row['top5'], row['diagnosis_correct']), ('missing', 0.0, False, False))

    def test_run_layout_reads_only_output(self):
        leaked = {'suspects': [{'rank': 1, 'file': 'entry/src/main/ets/state/AppStore.ets', 'symbol': 'search'}]}
        row, _ = self.run_case({'input/capture/answer.json': leaked, 'output/notes.txt': 'no answer',
                                'run.json': {'exit_code': 1}})
        self.assertEqual(row['status'], 'missing')

    def test_batch_runner_with_fake_agent(self):
        agent = ('import json,pathlib,sys; i,o=map(pathlib.Path,sys.argv[1:3]);'
                 'assert (i/"prompt.json").is_file() and (i/"capture"/"report"/"summary.json").is_file();'
                 'assert not (i/"groundtruth.json").exists();'
                 '(o/"answer.json").write_text(json.dumps({"scene":"load","suspects":[{"rank":1,'
                 '"file":"entry/src/main/ets/state/AppStore.ets","symbol":"search","fix":"debounce"}]}))')
        with tempfile.TemporaryDirectory() as tmp:
            cap = Path(tmp) / 'captures' / CASE / 'report'
            cap.mkdir(parents=True)
            (cap / 'summary.json').write_text('{}')
            runs = Path(tmp) / 'runs'
            subprocess.run([sys.executable, str(ROOT / 'tools/evaluate/run_hapray.py'), str(Path(tmp) / 'captures'),
                            str(runs), '--cases', CASE, '--', sys.executable, '-c', agent, '{input}', '{output}'],
                           check=True, capture_output=True)
            self.assertEqual(json.loads((runs / CASE / 'run.json').read_text())['exit_code'], 0)
            self.assertEqual([p.name for p in runs.iterdir()], [CASE])
            row, _ = score.score_case(case(), runs / CASE, {})
            self.assertEqual((row['status'], row['top1'], row['run']['exit_code']), ('ok', True, 0))

    def test_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'r.json'
            subprocess.run([sys.executable, str(ROOT / 'tools/evaluate/score.py'), tmp, '--out', str(out)],
                           check=True, capture_output=True)
            data = json.loads(out.read_text())
            self.assertEqual(data['summary']['all']['cases'], len(catalog.select(catalog.load())))
            self.assertEqual(data['summary']['all']['f1'], 0.0)


if __name__ == '__main__':
    unittest.main()
