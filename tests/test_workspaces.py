"""Saved-work discovery uses selection metadata; opening still enforces source basis."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.graph import save_run
from biograph_steward.questions import answer_question, save_answer
from biograph_steward.workspaces import saved_workspaces
from test_questions import fixture


class SavedWorkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.graph = save_run(fixture(), self.root / 'source')
        self.answer = answer_question(self.graph, 'UniProtKB:P04637', view='candidates', source_run='source')
        save_answer(self.answer, self.root / 'question_saved')

    def test_discovers_reopen_links_without_mutating_source_or_answer(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = saved_workspaces(self.root)
        self.assertEqual(len(result['runs']), 1)
        run = result['runs'][0]
        self.assertEqual(run['url'], '/?run=source')
        self.assertEqual(run['questions'][0]['url'], '/?run=source&question=question_saved')
        self.assertEqual(run['questions'][0]['question'], self.answer['question'])
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_corrupt_questions_and_external_symlinks_are_withheld(self):
        (self.root / 'linked_source').symlink_to(self.root / 'source', target_is_directory=True)
        linked = self.root / 'linked_question'; linked.mkdir()
        (linked / 'question.json').symlink_to(self.root / 'question_saved' / 'question.json')
        corrupt = deepcopy(self.answer); corrupt['question'] = 'Modified after sealing'
        (self.root / 'question_saved' / 'question.json').write_text(json.dumps(corrupt))
        result = saved_workspaces(self.root)
        self.assertEqual([r['run_id'] for r in result['runs']], ['source'])
        self.assertEqual(result['runs'][0]['questions'], [])
        self.assertEqual(result['withheld'], 2)

    def test_comparisons_go_to_history_and_missing_parents_do_not_get_links(self):
        (self.root / 'source' / 'refresh_comparison.json').write_text('{}')
        result = saved_workspaces(self.root)
        self.assertEqual(result['runs'], [])
        self.assertIsNone(result['example_url'])

    def test_synthetic_run_is_never_labeled_a_real_example(self):
        path = self.root / 'source' / 'run_manifest.json'
        manifest = json.loads(path.read_text()); manifest['data_kind'] = 'synthetic_demo'
        path.write_text(json.dumps(manifest))
        result = saved_workspaces(self.root)
        self.assertEqual(result['runs'][0]['data_kind'], 'synthetic_demo')
        self.assertIsNone(result['example_url'])


if __name__ == '__main__':
    unittest.main()
