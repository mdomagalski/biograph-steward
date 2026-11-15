"""Invented-only completeness, scalar-copy and publication-boundary checks."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from . import current_refit_report as module


PRIVATE = 'PRIVATE_ACCESSION_REFERENCE_PATH_AND_DRAW'


def invented():
    plan = json.loads(Path(module.__file__).with_name('current_refit_protocol.json').read_text())
    out = {'format': 'biograph-steward.current-refit-development-assessment.v1', **module.FLAGS,
        'plan_sha256': module.PLAN_SHA, 'target_count': 3300,
        'original_report_sha256': plan['original_raw_report_sha256'],
        'previous_development_report_sha256': module.PREVIOUS_REPORT_SHA,
        'original_public_summary_sha256': plan['original_public_summary_sha256'],
        'original_forecast_seal_sha256': plan['original_forecast_seal_sha256'],
        'new_arm_scopes': {arm: [module.NS] for arm in module.NEW_ARMS},
        'views': {}, 'ids': [PRIVATE], 'files': {'/private/' + PRIVATE: PRIVATE}}
    for view in module.VIEWS:
        dest = {'reference_pins': {'PK': {'file': '/private/' + PRIVATE, 'sha256': 'c' * 64}}, 'cells': {}}
        out['views'][view] = dest
        for setting in module.SETTINGS:
            methods = {}
            for arm in module.LABELS:
                point = .4 if arm == module.REFIT else .8 if arm in (module.UNION_LP, module.UNION_PRIOR) else .6
                methods[arm] = {'native_micro_fmax': point, 'status': 'evaluated',
                    'pre_exclusion_GT_proteins': 40, 'eligible_proteins': 12,
                    'raw_native_reference_proteins': 40,
                    'native_curve_agreement': {'author_point_agreement_passed': True, 'ids': [PRIVATE]},
                    'forecast_projection': {'protein_ids': [PRIVATE]}, 'prediction_file': '/private/' + PRIVATE}
            boot = {'draws': 2000, 'seed': 20261113, 'raw_proteins': 40,
                'original_native_gated_draws_reused_without_recomputation': True,
                'development_followup_on_consumed_reference': True, 'independent_confirmation': False,
                'new_success_gate_or_model_selection': False,
                'scores': {arm: {'bootstrap_mean': .51, 'bootstrap_95_percentile_interval': [.13, .79],
                                 'bootstrap_Fmax': [PRIVATE]} for arm in module.LABELS},
                'comparisons': [{'candidate': a, 'comparator': b, 'difference_mean': -.77,
                    'paired_95_percentile_interval': [-.53, -.17], 'fraction_draws_above_zero': .01,
                    'difference_draws': [PRIVATE], 'case_ids': [PRIVATE]} for a, b in reversed(module.expected_pairs())],
                'ids': [PRIVATE]}
            dest['cells'][setting + '/' + module.NS] = {'setting': setting, 'namespace': module.NS,
                'status': 'evaluated', 'methods': methods, 'bootstrap': boot,
                'reference': {'ids': [PRIVATE]}, 'positive_reference_score_ledger': {'file': '/private/' + PRIVATE},
                'matched_prior_integration_gate': {'private': PRIVATE},
                'development_followup_on_consumed_reference': True, 'independent_confirmation': False}
    return out


class PublicationTests(unittest.TestCase):
    def test_six_cells_all_22_methods_and_192_saved_contrasts_survive(self):
        raw = invented(); before = copy.deepcopy(raw); out = module.aggregate(raw)
        self.assertEqual(raw, before)
        self.assertEqual(out['previous_method_count'], 19);self.assertEqual(out['new_fixed_method_count'], 3)
        self.assertEqual(out['total_declared_method_count'], 22)
        total = 0
        for view in module.VIEWS:
            self.assertEqual(len(out['views'][view]['cells']), 3)
            for key, cell in out['views'][view]['cells'].items():
                self.assertEqual(set(cell['methods']), set(module.LABELS))
                self.assertEqual(len(cell['bootstrap']['comparisons']), 32);total += 32
                for arm, row in cell['methods'].items():
                    self.assertEqual(row['native_micro_fmax'], raw['views'][view]['cells'][key]['methods'][arm]['native_micro_fmax'])
                self.assertEqual(cell['bootstrap']['comparisons'][0]['difference_mean'], -.77)
                self.assertEqual(cell['bootstrap']['comparisons'][0]['paired_95_percentile_interval'], [-.53, -.17])
                self.assertEqual(cell['bootstrap']['scores'][module.REFIT]['bootstrap_mean'], .51)
        self.assertEqual(total, 192)
        text = json.dumps(out)
        self.assertNotIn(PRIVATE, text)
        for field in ('bootstrap_Fmax', 'difference_draws', 'prediction_file', 'forecast_projection', 'positive_reference_score_ledger'):
            self.assertNotIn('"' + field + '"', text)

    def test_exact_contrast_contract_matches_the_assessment(self):
        from .current_refit_assessment import required_pairs
        self.assertEqual(module.expected_pairs(), required_pairs(tuple(module.PREVIOUS_LABELS)))

    def test_a_missing_cell_control_or_contrast_fails_closed(self):
        for kind in ('cell', 'control', 'contrast', 'duplicate', 'unknown'):
            raw = invented(); cell = raw['views']['native']['cells']['PK/' + module.NS]
            if kind == 'cell':del raw['views']['native']['cells']['NK/' + module.NS]
            if kind == 'control':del cell['methods']['localplus']
            if kind == 'contrast':cell['bootstrap']['comparisons'].pop()
            if kind == 'duplicate':cell['bootstrap']['comparisons'][-1] = cell['bootstrap']['comparisons'][0]
            if kind == 'unknown':cell['methods'][PRIVATE] = dict(cell['methods']['localplus'])
            with self.subTest(kind=kind), self.assertRaises(ValueError):module.aggregate(raw)

    def test_consumed_flags_and_original_plan_pins_cannot_be_reinterpreted(self):
        for field, value in [('independent_confirmation', True), ('new_success_gate_or_model_selection', True),
            ('graph_pruning_or_app_promotion', True), ('plan_sha256', 'a' * 64),
            ('original_public_summary_sha256', 'b' * 64), ('previous_development_report_sha256', 'c' * 64)]:
            raw = invented();raw[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):module.aggregate(raw)

    def test_absent_reference_and_unavailable_intervals_remain_explicit(self):
        raw = invented(); absent = raw['views']['native']['cells']['LK/' + module.NS]
        absent.update(status='reference_absent', methods={})
        other = raw['views']['fixed_T0']['cells']['NK/' + module.NS]
        other['bootstrap'] = {'status': 'unavailable', 'reason': PRIVATE}
        no = other['methods'][module.REFIT]
        no.update(status='no_native_coverage', native_micro_fmax=None, eligible_proteins=0)
        no['native_curve_agreement'] = {'status': 'unscorable_no_residual_reference_proteins'}
        out = module.aggregate(raw)
        self.assertEqual(len(out['views']['native']['cells']), 3)
        self.assertEqual(out['views']['native']['cells']['LK/' + module.NS]['status'], 'reference_absent')
        self.assertFalse(out['views']['fixed_T0']['cells']['NK/' + module.NS]['bootstrap']['interval_claimed'])
        self.assertNotIn(PRIVATE, json.dumps(out))

    def test_new_point_requires_native_curve_gate_and_shared_full_frame(self):
        for kind in ('gate', 'frame', 'interval', 'fraction'):
            raw = invented(); cell = raw['views']['native']['cells']['PK/' + module.NS]
            if kind == 'gate':cell['methods'][module.REFIT]['native_curve_agreement']['author_point_agreement_passed'] = False
            if kind == 'frame':cell['methods'][module.UNION_PRIOR]['raw_native_reference_proteins'] = 39
            if kind == 'interval':cell['bootstrap']['comparisons'][0]['paired_95_percentile_interval'] = [.8, .1]
            if kind == 'fraction':cell['bootstrap']['comparisons'][0]['fraction_draws_above_zero'] = 2
            with self.subTest(kind=kind), self.assertRaises(ValueError):module.aggregate(raw)

    def test_render_copies_negative_intervals_and_keeps_original_study_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);source = root/'source.json';source.write_text(json.dumps(invented()))
            public = module.render(source, root/'public')
            md = (root/'public/report.md').read_text();document = (root/'public/report.html').read_text()
            self.assertIn('DEVELOPMENT', md);self.assertIn('no independent confirmation', md)
            self.assertIn('-0.400000', md);self.assertIn('[-0.530000, -0.170000]', md)
            self.assertIn('[0.130000, 0.790000]', md)
            self.assertIn('Full native protein frame: 40; proteins with residual positive labels: 12', md)
            self.assertIn('original frozen comparison', md);self.assertIn('no interval, threshold, winner or new success gate', md)
            self.assertEqual(document.count('<details>'), 6)
            self.assertIn('not 867 new output classes', md)
            self.assertIn('does not isolate learning as the sole source of any difference', md)
            self.assertEqual(public['source_aggregate_sha256'], hashlib.sha256(source.read_bytes()).hexdigest())
            manifest = json.loads((root/'public/publication_manifest.json').read_text())
            self.assertFalse(manifest['evaluation_scores_intervals_or_model_choices_recomputed'])
            for name, record in manifest['files'].items():
                self.assertEqual(record['sha256'], hashlib.sha256((root/'public'/name).read_bytes()).hexdigest())
            published = ''.join(p.read_text() for p in (root/'public').iterdir())
            self.assertNotIn(PRIVATE, published);self.assertNotIn('/private/', published)
            self.assertEqual({p.name for p in (root/'public').iterdir()},
                             {'report.md', 'report.html', 'summary.json', 'publication_manifest.json'})

    def test_absent_reference_render_does_not_invent_success_or_coverage(self):
        raw = invented()
        for view in module.VIEWS:
            raw['views'][view]['cells']['PK/' + module.NS].update(status='reference_absent', methods={})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);source = root/'source.json';source.write_text(json.dumps(raw))
            module.render(source, root/'public');text = (root/'public/report.md').read_text()
            self.assertIn('No native reference; no score or interval claim.', text)
            self.assertIn('| unavailable | unavailable |', text)


if __name__ == '__main__':unittest.main()
