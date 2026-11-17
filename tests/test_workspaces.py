"""Saved-work discovery uses selection metadata; opening still enforces source basis."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest
from biograph_steward.graph import save_run
from biograph_steward.questions import answer_question, save_answer
from biograph_steward.workspaces import saved_workspaces, reviewer_entry
from test_questions import fixture
from test_civic import fixture as civic_fixture
import test_native_pathway_question as native_fixture


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


class ReviewerEntryTests(unittest.TestCase):
    """Catalogue routing fixtures only; these records are not biological labels."""

    def run_row(self, name, *, synthetic=False, qualified=False, template='native_string_physical.v1', view='candidates', snapshot='a'*64):
        url='/?run='+name
        return {'run_id':name, 'url':url, 'snapshot_sha256':snapshot, 'data_kind':'synthetic_demo' if synthetic else 'live_pharos',
                'qualified_view':qualified, 'questions':[{'question_id':name+'_answer',
                'template':template, 'view':view, 'url':url+'&question='+name+'_answer'}]}

    def test_root_prefers_real_native_question_and_keeps_qualification_separate(self):
        native=self.run_row('native')
        retained=self.run_row('retained',qualified=True,template='qualified_pathway_source_context.v1')
        rows=[self.run_row('invented',synthetic=True),retained,native]
        before=deepcopy(rows)
        result=reviewer_entry(rows,retained['questions'][0]['url'],native_question_ids={'retained_answer'})
        self.assertEqual(result['example_url'],native['questions'][0]['url'])
        self.assertEqual(result['data_kind'],'live_pharos')
        self.assertEqual([e['url'] for e in result['guided_examples']],
                         [native['questions'][0]['url'],retained['questions'][0]['url']])
        self.assertEqual(rows,before)

    def test_companion_must_share_snapshot_and_have_native_source_support(self):
        native=self.run_row('native')
        unrelated=self.run_row('newer_unrelated',qualified=True,template='qualified_pathway_source_context.v1',snapshot='b'*64)
        unsupported=self.run_row('same_snapshot_unresolved',qualified=True,template='qualified_pathway_source_context.v1')
        retained=self.run_row('matched',qualified=True,template='qualified_pathway_source_context.v1')
        result=reviewer_entry([native,unrelated,unsupported,retained],native_question_ids={'newer_unrelated_answer','matched_answer'})
        self.assertEqual([item['url'] for item in result['guided_examples']],
                         [native['questions'][0]['url'],retained['questions'][0]['url']])

    def test_missing_snapshot_does_not_assume_same_cohort(self):
        native=self.run_row('native',snapshot=None)
        retained=self.run_row('retained',qualified=True,template='qualified_pathway_source_context.v1',snapshot=None)
        result=reviewer_entry([native,retained],native_question_ids={'retained_answer'})
        self.assertEqual(len(result['guided_examples']),1)

    def test_synthetic_only_install_has_no_real_entry_even_with_example_url(self):
        invented=self.run_row('invented',synthetic=True)
        self.assertIsNone(reviewer_entry([invented],invented['questions'][0]['url']))

    def test_explicit_accepted_or_unknown_native_view_does_not_replace_real_fallback(self):
        retained=self.run_row('retained',qualified=True,template='qualified_pathway_source_context.v1')
        for view in ['accepted','future']:
            with self.subTest(view=view):
                result=reviewer_entry([self.run_row('native',view=view),retained],retained['questions'][0]['url'])
                self.assertEqual(result['example_url'],retained['questions'][0]['url'])
                self.assertEqual(len(result['guided_examples']),1)

    def test_no_eligible_entry_does_not_invent_one(self):
        self.assertIsNone(reviewer_entry([]))
        self.assertIsNone(reviewer_entry([self.run_row('real',template='other')], '/?run=missing'))


class QualifiedExampleSelectionTests(unittest.TestCase):
    """Saved live-labelled software fixtures, never biological gold labels."""

    def setUp(self):
        native_fixture.NativePathwayQuestionTests.setUp(self)
        pharos, civic = civic_fixture()
        self.civic_graph = save_run(pharos, self.root / 'old_civic', civic_snapshot=civic)
        old = answer_question(self.civic_graph, 'P01116', view='candidates', source_run='old_civic')
        save_answer(old, self.root / 'old_civic_question')
        self.date('baseline', '2019-01-01T00:00:00Z')
        self.date('old_civic', '2020-01-01T00:00:00Z')
        self.date('qualified', '2021-01-01T00:00:00Z')

    def date(self, run_id, value):
        path = self.root / run_id / 'run_manifest.json'
        metadata = json.loads(path.read_text()); metadata['created_at'] = value
        path.write_text(json.dumps(metadata))

    def native_question(self, question_id, *, view='candidates', source_support='native_supported', source_run='qualified'):
        answer = answer_question(self.graph, self.protein, template='qualified_pathway_source_context.v1',
            view=view, source_run=source_run, source_support=source_support, pathway_history_source=self.packet)
        save_answer(answer, self.root / question_id)
        return answer

    def test_native_qualified_example_precedes_civic_without_source_reads_or_writes(self):
        self.native_question('native_candidate')
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch('biograph_steward.reviews.read_run', side_effect=AssertionError('Catalogue read source run')), \
             patch('biograph_steward.wiki_history.query_history', side_effect=AssertionError('Catalogue reopened source history')), \
             patch('biograph_steward.client.PharosClient._http', side_effect=AssertionError('Catalogue used network')):
            result = saved_workspaces(self.root)
        self.assertEqual(result['example_url'], '/?run=qualified&question=native_candidate')
        qualified = next(r for r in result['runs'] if r['run_id'] == 'qualified')
        civic = next(r for r in result['runs'] if r['run_id'] == 'old_civic')
        self.assertFalse(qualified['has_civic']); self.assertTrue(civic['has_civic'])
        self.assertEqual(set(qualified['questions'][0]), {'question_id', 'question', 'view', 'template', 'url'})
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_native_candidates_precede_newer_accepted_and_all_source_questions(self):
        self.native_question('question_100_native_candidate')
        self.native_question('question_200_native_accepted', view='accepted')
        self.native_question('question_300_all_source_candidate', source_support='all_source_annotations')
        self.assertEqual(saved_workspaces(self.root)['example_url'],
                         '/?run=qualified&question=question_100_native_candidate')

    def test_latest_qualified_run_with_native_question_wins(self):
        self.native_question('question_100_candidate')
        shutil.copytree(self.root / 'qualified', self.root / 'qualified_new')
        self.date('qualified_new', '2022-01-01T00:00:00Z')
        self.native_question('question_200_new_accepted', view='accepted', source_run='qualified_new')
        self.assertEqual(saved_workspaces(self.root)['example_url'],
                         '/?run=qualified_new&question=question_200_new_accepted')
        (self.root / 'question_200_new_accepted/question.json').unlink()
        self.assertEqual(saved_workspaces(self.root)['example_url'],
                         '/?run=qualified&question=question_100_candidate')

    def test_bad_and_incomplete_questions_do_not_displace_verified_example(self):
        original = self.native_question('question_100_good')
        for name, answer in [('question_300_bad_hash', deepcopy(original)),
                             ('question_400_incomplete', deepcopy(original))]:
            folder = self.root / name; folder.mkdir()
            if name.endswith('bad_hash'):
                answer['question'] = 'Modified without a new seal'
            else:
                del answer['plan']['view']
                answer['answer_sha256'] = digest({k: v for k, v in answer.items() if k != 'answer_sha256'})
            (folder / 'question.json').write_text(json.dumps(answer))
        result = saved_workspaces(self.root)
        self.assertEqual(result['example_url'], '/?run=qualified&question=question_100_good')
        self.assertEqual(result['withheld'], 2)

    def test_unknown_native_view_is_not_promoted_as_supported_example(self):
        self.native_question('question_100_good')
        altered = self.native_question('question_900_unknown_view')
        altered['plan']['view'] = 'unsupported_future_view'
        altered['answer_sha256'] = digest({k: v for k, v in altered.items() if k != 'answer_sha256'})
        (self.root / 'question_900_unknown_view/question.json').write_text(json.dumps(altered))
        self.assertEqual(saved_workspaces(self.root)['example_url'],
                         '/?run=qualified&question=question_100_good')

    def test_synthetic_qualified_native_question_is_not_a_real_example(self):
        self.native_question('question_native')
        path = self.root / 'qualified/run_manifest.json'
        metadata = json.loads(path.read_text()); metadata['data_kind'] = 'synthetic_demo'
        path.write_text(json.dumps(metadata))
        self.assertEqual(saved_workspaces(self.root)['example_url'],
                         '/?run=old_civic&question=old_civic_question')

    def test_existing_civic_fallback_remains_when_no_native_question_exists(self):
        self.native_question('all_source_only', source_support='all_source_annotations')
        self.assertEqual(saved_workspaces(self.root)['example_url'],
                         '/?run=old_civic&question=old_civic_question')
        (self.root / 'old_civic_question/question.json').unlink()
        self.assertEqual(saved_workspaces(self.root)['example_url'], '/?run=old_civic')


if __name__ == '__main__':
    unittest.main()
