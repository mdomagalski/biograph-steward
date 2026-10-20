"""Prospective packets use invented records; no live inference or expert labels."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.__main__ import main
from biograph_steward.client import digest
from biograph_steward.evaluation import freeze_suite
from biograph_steward.graph import save_run
from biograph_steward.planning import ModelPlanner, catalogue
from biograph_steward.planning_comparison import (PLANNER_FILES, audit_cases, load_packet,
                                                prepare_comparison, read_scope_reviews,
                                                run_comparison, scope_audit)
from test_civic import fixture
from test_evaluation import cases, edit_sheet
from test_planning import abstain_plan, civic_plan, response


class ProspectiveComparisonTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True); self.env.start(); self.addCleanup(self.env.stop)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.p, self.c = fixture()
        self.base, self.enriched = self.root / 'base', self.root / 'enriched'
        save_run(self.p, self.base)
        self.graph = save_run(self.p, self.enriched, civic_snapshot=self.c)
        self.prior = self.root / 'prior'
        self.prior_manifest = freeze_suite(self.base, self.enriched, self.prior, cases=cases())
        self.fresh = [
            {'id': 'new-scope-query', 'group': 'new-scope-family', 'split': 'test',
             'question': 'Inspect candidate CIViC response for INVENTED KRAS profile containing cetuximab in DOID:9256.',
             'reference_plan': civic_plan()},
            {'id': 'new-scope-unsupported', 'group': 'new-scope-family', 'split': 'test',
             'question': 'Prescribe a drug for the INVENTED KRAS profile containing cetuximab.',
             'reference_plan': abstain_plan()}]
        self.packet = self.root / 'packet'

    def prepare(self):
        return prepare_comparison(self.base, self.enriched, self.packet, cases=self.fresh, prior_suite=self.prior)

    def approved_sheet(self):
        path = self.root / 'approved.tsv'
        path.write_bytes((self.packet / 'case_reviews.tsv').read_bytes())
        edit_sheet(path, lambda rows: [r.update(reference_plan_correct='yes', reviewer='INVENTED SOFTWARE QA',
                                               notes='Invented fixture scope only; not expert scientific review.') for r in rows])
        return path

    def test_preparation_freezes_controls_and_leaves_every_scope_judgment_pending(self):
        with patch('biograph_steward.planning.configured_planner', side_effect=AssertionError('No model during preparation')):
            p = self.prepare()
        loaded, suite = load_packet(self.packet)
        self.assertEqual(p, loaded)
        self.assertTrue(p['planner_unchanged_from_prior'])
        self.assertEqual(p['planner_files'], {n: self.prior_manifest['engine_files'][n] for n in PLANNER_FILES})
        self.assertEqual(suite['sources']['enriched']['files'], self.prior_manifest['sources']['enriched']['files'])
        self.assertEqual(suite['budgets'], self.prior_manifest['budgets'])
        review = read_scope_reviews(self.fresh, self.packet / 'case_reviews.tsv')
        self.assertEqual(review['approved'], 0); self.assertEqual(review['pending'], 2)
        self.assertFalse(p['model_evaluation_run']); self.assertFalse(p['independent_scope_review_verified'])
        self.assertIn('No model inference has run', (self.packet / 'review.html').read_text())

    def test_reuse_audit_rejects_ids_groups_normalized_questions_and_mixed_splits(self):
        for change in [lambda cs: cs[0].update(id='candidate-case'),
                       lambda cs: cs[0].update(group='profile-81'),
                       lambda cs: cs[0].update(question=cases()[0]['question'].upper().replace(' ', '\n')),
                       lambda cs: cs[0].update(split='development'),
                       lambda cs: cs[1].update(question=cs[0]['question'].upper())]:
            cs = deepcopy(self.fresh); change(cs)
            with self.assertRaises(ValueError): audit_cases(cs, self.prior_manifest)
        a = audit_cases(self.fresh, self.prior_manifest)
        self.assertFalse(a['semantic_independence_verified'])

    def test_changed_sources_or_planner_cannot_be_mislabeled_as_unchanged_controls(self):
        target = self.enriched / 'snapshot.json'
        original = target.read_bytes(); target.write_bytes(original + b'\n')
        with self.assertRaisesRegex(ValueError, 'Source bytes'):
            self.prepare()
        self.assertFalse(self.packet.exists())
        target.write_bytes(original)
        changed = deepcopy(self.prior_manifest); changed['engine_files']['planning_scope.py'] = 'wrong'
        changed['suite_sha256'] = digest({k: v for k, v in changed.items() if k != 'suite_sha256'})
        (self.prior / 'suite.json').write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, 'Planner code differs'):
            self.prepare()

    def test_packet_and_result_outputs_cannot_modify_source_or_control_directories(self):
        for output in [self.base / 'packet', self.enriched / 'packet', self.prior / 'packet']:
            with self.assertRaisesRegex(ValueError, 'outside source'):
                prepare_comparison(self.base, self.enriched, output, cases=self.fresh, prior_suite=self.prior)
            self.assertFalse(output.exists())
        self.prepare()
        with self.assertRaisesRegex(ValueError, 'outside the immutable'):
            run_comparison(self.packet, self.packet / 'results')

    def test_review_gating_happens_before_factory_construction_or_any_model_call(self):
        self.prepare()
        with patch('biograph_steward.planning.configured_planner') as factory:
            with self.assertRaisesRegex(ValueError, 'Approve every scope'):
                run_comparison(self.packet, self.root / 'live', live=True)
            factory.assert_not_called()
        self.assertFalse((self.root / 'live').exists())
        sheet = self.approved_sheet()
        for verdict in ['', 'no', 'uncertain']:
            edit_sheet(sheet, lambda rows: rows[0].update(reference_plan_correct=verdict))
            with patch('biograph_steward.planning.configured_planner') as factory:
                with self.assertRaisesRegex(ValueError, 'Approve every scope'):
                    run_comparison(self.packet, self.root / 'live', live=True, scope_reviews=sheet)
                factory.assert_not_called()

    def test_review_import_checks_question_and_plan_not_only_the_claimed_hash(self):
        self.prepare(); sheet = self.approved_sheet(); original = sheet.read_bytes()
        for edit in [lambda rows: rows[0].update(question='Changed question'),
                     lambda rows: rows[0].update(reference_plan=json.dumps(abstain_plan())),
                     lambda rows: rows[0].update(case_sha256='changed'),
                     lambda rows: rows.append(deepcopy(rows[0])),
                     lambda rows: rows[0].update(reviewer=''),
                     lambda rows: rows[0].update(notes='')]:
            sheet.write_bytes(original); edit_sheet(sheet, edit)
            with self.assertRaises(ValueError): read_scope_reviews(self.fresh, sheet)

    def test_packet_tampering_and_editing_original_worksheet_fail_before_inference(self):
        self.prepare()
        target = self.packet / 'case_reviews.tsv'; original = target.read_bytes()
        edit_sheet(target, lambda rows: rows[0].update(reference_plan_correct='yes', reviewer='QA', notes='Test'))
        with self.assertRaisesRegex(ValueError, 'artifact changed'): load_packet(self.packet)
        target.write_bytes(original)
        p = json.loads((self.packet / 'packet.json').read_text()); p['planner_protocol'] = 'catalogue_v1'
        (self.packet / 'packet.json').write_text(json.dumps(p))
        with self.assertRaisesRegex(ValueError, 'integrity'): load_packet(self.packet)

    def test_offline_comparison_is_not_reported_as_a_model_success(self):
        self.prepare()
        with patch('biograph_steward.planning.configured_planner', side_effect=AssertionError('No model offline')):
            summary = run_comparison(self.packet, self.root / 'offline')
        self.assertEqual(summary['planner_kind'], 'not_run')
        self.assertEqual(summary['reported_model_calls'], 0)
        self.assertEqual(summary['draft_plan_comparisons'], 0)
        self.assertIsNone(summary['draft_plan_agreement'])
        self.assertEqual(summary['statuses'], {'planner_not_run': 2})
        self.assertEqual(summary['query_output_pairs'], 0)
        self.assertIsNone(summary['groups']['new-scope-family']['all_scope_plans_matched'])
        self.assertFalse(summary['scientific_improvement_established'])

    def test_injected_one_call_plans_use_no_references_and_match_deterministic_answers(self):
        self.prepare(); sheet = self.approved_sheet(); calls = []
        def transport(payload):
            calls.append(payload)
            return response(civic_plan() if len(calls) == 1 else abstain_plan())
        planner = ModelPlanner(model='test', endpoint='http://localhost:9999', transport=transport, protocol='tool_shapes_v3')
        summary = run_comparison(self.packet, self.root / 'injected', planner=planner, scope_reviews=sheet)
        self.assertEqual(summary['planner_kind'], 'injected_test_model')
        self.assertEqual(len(calls), 2); self.assertEqual(summary['draft_plan_matches'], 2)
        self.assertEqual(summary['query_output_pairs'], 1); self.assertEqual(summary['query_outputs_equal_to_enriched'], 1)
        self.assertTrue(summary['groups']['new-scope-family']['all_scope_plans_matched'])
        for forbidden in ['reference_plan', 'new-scope-query', 'INVENTED SOFTWARE TEST statement']:
            self.assertNotIn(forbidden, json.dumps(calls))
        metrics = json.loads((self.root / 'injected/metrics.json').read_text())
        self.assertEqual(metrics['approved_reference_plans'], 2)
        self.assertIsNone(metrics['arms']['planner']['judged_precision'])
        self.assertEqual((self.root / 'injected/scope_reviews_submitted.tsv').read_bytes(), sheet.read_bytes())

    def test_protocol_mismatch_is_rejected_before_any_generation(self):
        self.prepare(); sheet = self.approved_sheet()
        planner = ModelPlanner(model='test', endpoint='http://localhost:9999', transport=lambda p: self.fail('No request'), protocol='catalogue_v1')
        with self.assertRaisesRegex(ValueError, 'protocol differs'):
            run_comparison(self.packet, self.root / 'mismatch', planner=planner, scope_reviews=sheet)
        self.assertFalse((self.root / 'mismatch').exists())

    def test_wrong_model_scope_and_first_run_artifacts_are_preserved_without_retry(self):
        self.prepare(); sheet = self.approved_sheet(); calls = []
        def transport(payload):
            calls.append(payload)
            return response(civic_plan())
        planner = ModelPlanner(model='test', endpoint='http://localhost:9999', transport=transport, protocol='tool_shapes_v3')
        folder = self.root / 'failed'
        summary = run_comparison(self.packet, folder, planner=planner, scope_reviews=sheet)
        self.assertEqual(summary['statuses'], {'answered': 1, 'invalid_plan': 1})
        self.assertEqual(summary['draft_plan_comparisons'], 2)
        self.assertEqual(summary['draft_plan_matches'], 1)
        self.assertFalse(summary['groups']['new-scope-family']['all_scope_plans_matched'])
        self.assertEqual(len(calls), 2)
        original = (folder / 'evaluation.json').read_bytes()
        with self.assertRaises(ValueError): run_comparison(self.packet, folder, planner=planner, scope_reviews=sheet)
        self.assertEqual((folder / 'evaluation.json').read_bytes(), original)
        self.assertEqual(len(calls), 2)

    def test_diagnostics_report_a_blocked_draft_query_without_changing_the_reference(self):
        fresh = deepcopy(self.fresh)
        fresh[0]['question'] = 'Prove INVENTED KRAS profile causes cancer with cetuximab.'
        before = deepcopy(fresh)
        audit = scope_audit(fresh, self.graph, 'tool_shapes_v3')
        self.assertEqual(audit['query_references_blocked_by_application'], 1)
        self.assertFalse(audit['is_model_performance']); self.assertFalse(audit['model_called'])
        self.assertEqual(fresh, before)

    def test_diagnostics_check_generation_shape_as_well_as_post_validation(self):
        fresh = deepcopy(self.fresh)
        fresh[0]['question'] = ('Do not query all molecular profiles. Inspect candidate CIViC response for '
                                'INVENTED KRAS profile containing cetuximab in DOID:9256.')
        audit = scope_audit(fresh, self.graph, 'tool_shapes_v3')
        row = audit['cases'][0]
        # The exact resolver detects the words "all molecular profiles" even in
        # this negated clause. That restricts the schema to all, while the post
        # validator by itself still permits the explicitly named profile.
        self.assertTrue(row['reference_passes_application_validation'])
        self.assertFalse(row['reference_fits_output_schema'])
        self.assertFalse(row['reference_admissible'])
        self.assertEqual(audit['query_references_blocked_by_application'], 1)

    def test_cli_prepares_and_runs_offline_without_remote_compute(self):
        source = self.root / 'cases.json'; source.write_text(json.dumps(self.fresh))
        with redirect_stdout(StringIO()):
            self.assertEqual(main(['planning-prepare', '--baseline', str(self.base), '--enriched', str(self.enriched),
                                   '--cases', str(source), '--prior-suite', str(self.prior), '--out', str(self.packet)]), 0)
            self.assertEqual(main(['planning-compare', '--packet', str(self.packet), '--out', str(self.root / 'cli-offline')]), 0)
        self.assertTrue((self.root / 'cli-offline/comparison.json').is_file())
        self.assertEqual(json.loads((self.root / 'cli-offline/comparison.json').read_text())['reported_model_calls'], 0)

    def test_packaged_challenge_cases_have_no_simple_reuse_and_are_balanced_by_family(self):
        source = Path(__file__).resolve().parents[1] / 'biograph_steward/planning_challenge_cases.json'
        cs = json.loads(source.read_text())
        prior = {'suite_sha256': 'test', 'cases': json.loads(source.with_name('evaluation_cases.json').read_text())}
        audit = audit_cases(cs, prior)
        self.assertEqual(audit['cases'], 32); self.assertEqual(audit['question_groups'], 16)
        self.assertTrue(all(sum(c['group'] == group for c in cs) == 2 for group in {c['group'] for c in cs}))


if __name__ == '__main__': unittest.main()
