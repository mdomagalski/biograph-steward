"""Invented-only aggregate completeness, scalar copying and privacy checks."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from . import crossfit_report as module


PRIVATE = 'PRIVATE_ACCESSION_REFERENCE_PATH_AND_DRAW'


def invented():
    plan = json.loads(Path(module.__file__).with_name('crossfit_protocol.json').read_text())
    raw = {'format': 'biograph-steward.crossfit-development-assessment.v1', **module.FLAGS,
        'plan_sha256': module.PLAN_SHA, 'target_count': 3300,
        'original_report_sha256': module.ORIGINAL_SHA,
        'annotation_prior_report_sha256': module.ANNOTATION_SHA,
        'previous_development_report_sha256': module.PREVIOUS_SHA,
        'original_public_summary_sha256': plan['original_public_summary_sha256'],
        'original_forecast_seal_sha256': plan['original_forecast_seal_sha256'],
        'new_arm_scopes': {module.ARM: [module.NS]}, 'method_rows': 138, 'contrast_rows': 324,
        'views': {}, 'ids': [PRIVATE], 'files': {'/private/' + PRIVATE: PRIVATE},
        'source_admission': {'private': PRIVATE, 'targets_file': '/data/private/' + PRIVATE}}
    for view in module.VIEWS:
        dest = {'reference_pins': {role: {'file': '/private/' + PRIVATE, 'sha256': 'c' * 64}
                for role in module.REFERENCE_ROLES}, 'cells': {}}
        raw['views'][view] = dest
        for setting in module.SETTINGS:
            methods = {}
            for arm in module.LABELS:
                point = .4 if arm == module.ARM else .8 if arm in module.FOCUS else .6
                methods[arm] = {'native_micro_fmax': point, 'status': 'evaluated',
                    'pre_exclusion_GT_proteins': 40, 'eligible_proteins': 12, 'raw_native_reference_proteins': 40,
                    'native_curve_agreement': {'author_point_agreement_passed': True, 'ids': [PRIVATE]},
                    'forecast_projection': {'protein_ids': [PRIVATE], 'term_ids': ['GO:9999999']},
                    'prediction_file': '/private/' + PRIVATE}
            # The private vectors are deliberate nonnumeric sentinels: the
            # publisher must ignore them rather than recompute or expose them.
            scores = {arm: {'bootstrap_mean': .51, 'bootstrap_95_percentile_interval': [.13, .79],
                           'bootstrap_Fmax': [PRIVATE]} for arm in module.LABELS}
            old = list(reversed(module.previous_pairs()))
            new = [(module.ARM, name) for name in reversed(module.PREVIOUS_LABELS)]
            boot = {'draws': 2000, 'seed': 20261113, 'raw_proteins': 40,
                'original_native_gated_draws_reused_without_recomputation': True,
                'earlier_contrasts_reused_without_recomputation': True,
                'regenerated_anchor_peaks_equal_preserved_exactly': True,
                'development_followup_on_consumed_reference': True, 'independent_confirmation': False,
                'new_success_gate_or_model_selection': False, 'scores': scores,
                'comparisons': [{'candidate': a, 'comparator': b, 'difference_mean': -.77,
                    'paired_95_percentile_interval': [-.53, -.17], 'fraction_draws_above_zero': .01,
                    'difference_draws': [PRIVATE], 'case_ids': [PRIVATE], 'paths': ['/Users/private/' + PRIVATE]}
                    for a, b in old + new], 'ids': [PRIVATE]}
            dest['cells'][setting + '/' + module.NS] = {'setting': setting, 'namespace': module.NS,
                'status': 'evaluated', 'methods': methods, 'bootstrap': boot,
                'reference': {'ids': [PRIVATE]}, 'positive_reference_score_ledger': {'file': '/private/' + PRIVATE}}
    return raw


class PublicationTests(unittest.TestCase):
    def test_all138_points_and324_saved_contrasts_survive_without_cases(self):
        raw = invented(); before = copy.deepcopy(raw); public = module.aggregate(raw)
        self.assertEqual(raw, before)
        self.assertEqual(public['reporting_focus'], list(module.FOCUS))
        self.assertEqual(public['previous_method_count'], 22); self.assertEqual(public['new_fixed_method_count'], 1)
        self.assertEqual(public['total_declared_method_count'], 23)
        points = contrasts = 0
        for view in module.VIEWS:
            self.assertEqual(len(public['views'][view]['cells']), 3)
            for key, cell in public['views'][view]['cells'].items():
                old = raw['views'][view]['cells'][key]
                self.assertEqual(set(cell['methods']), set(module.LABELS)); points += len(cell['methods'])
                self.assertEqual(len(cell['bootstrap']['comparisons']), 54); contrasts += 54
                self.assertEqual([(r['candidate'], r['comparator']) for r in cell['bootstrap']['comparisons']],
                    [(r['candidate'], r['comparator']) for r in old['bootstrap']['comparisons']])
                for arm, row in cell['methods'].items(): self.assertEqual(row['native_micro_fmax'], old['methods'][arm]['native_micro_fmax'])
                self.assertEqual(cell['bootstrap']['comparisons'][0]['difference_mean'], -.77)
                self.assertEqual(cell['bootstrap']['comparisons'][0]['paired_95_percentile_interval'], [-.53, -.17])
                self.assertEqual(cell['bootstrap']['scores'][module.ARM]['bootstrap_mean'], .51)
        self.assertEqual((points, contrasts), (138, 324))
        text = json.dumps(public)
        for private in (PRIVATE, '/private/', '/Users/', 'GO:9999999', 'bootstrap_Fmax', 'difference_draws',
                        'prediction_file', 'forecast_projection', 'positive_reference_score_ledger'):
            self.assertNotIn(private, text)

    def test_contrast_contract_matches_all_earlier_pairs_and_new22(self):
        from .current_refit_assessment import required_pairs
        from .annotation_prior_report import LABELS as nineteen
        self.assertEqual(module.previous_pairs(), required_pairs(tuple(nineteen)))
        self.assertEqual(len(module.expected_pairs()), 54)
        self.assertEqual(len(set(module.expected_pairs())), 54)

    def test_missing_cell_control_contrast_duplicate_or_prefix_reorder_fails(self):
        for kind in ('cell', 'control', 'contrast', 'duplicate', 'unknown', 'prefix', 'count'):
            raw = invented(); cell = raw['views']['native']['cells']['PK/' + module.NS]
            if kind == 'cell': del raw['views']['native']['cells']['NK/' + module.NS]
            if kind == 'control': del cell['methods']['localplus']
            if kind == 'contrast': cell['bootstrap']['comparisons'].pop()
            if kind == 'duplicate': cell['bootstrap']['comparisons'][-1] = cell['bootstrap']['comparisons'][0]
            if kind == 'unknown': cell['methods'][PRIVATE] = dict(cell['methods']['localplus'])
            if kind == 'prefix': cell['bootstrap']['comparisons'].reverse()
            if kind == 'count': raw['contrast_rows'] = 323
            with self.subTest(kind=kind), self.assertRaises(ValueError): module.aggregate(raw)

    def test_plan_source_pins_consumed_status_and_promotion_flags_are_fixed(self):
        changes = [('plan_sha256', 'a' * 64), ('original_report_sha256', 'b' * 64),
            ('annotation_prior_report_sha256', 'c' * 64), ('previous_development_report_sha256', 'd' * 64),
            ('original_public_summary_sha256', 'e' * 64), ('original_forecast_seal_sha256', 'f' * 64),
            ('independent_confirmation', True), ('new_success_gate_or_model_selection', True),
            ('graph_pruning_or_app_promotion', True), ('original_primary_comparison_unchanged', False)]
        for field, value in changes:
            raw = invented(); raw[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): module.aggregate(raw)

    def test_native_gate_saved_draw_design_and_full_frames_cannot_be_dropped(self):
        for kind in ('gate', 'frame', 'anchor', 'draws', 'earlier', 'residual', 'reference_pin'):
            raw = invented(); cell = raw['views']['native']['cells']['PK/' + module.NS]
            if kind == 'gate': cell['methods'][module.ARM]['native_curve_agreement']['author_point_agreement_passed'] = False
            if kind == 'frame': cell['methods']['localplus']['raw_native_reference_proteins'] = 39
            if kind == 'anchor': cell['bootstrap']['regenerated_anchor_peaks_equal_preserved_exactly'] = False
            if kind == 'draws': cell['bootstrap']['draws'] = 1000
            if kind == 'earlier': cell['bootstrap']['earlier_contrasts_reused_without_recomputation'] = False
            if kind == 'residual': cell['methods'][module.ARM]['eligible_proteins'] = 41
            if kind == 'reference_pin': del raw['views']['native']['reference_pins']['obo']
            with self.subTest(kind=kind), self.assertRaises(ValueError): module.aggregate(raw)

    def test_nonfinite_bool_out_of_range_or_reversed_scalar_readouts_rejected(self):
        changes = [('point', float('nan')), ('point', True), ('point', 1.1), ('fraction', 1.1),
            ('mean', float('inf')), ('mean', -1.1), ('interval', [.8, .1]), ('interval', [-1.1, -.1]),
            ('score_interval', [-.1, .8])]
        for kind, value in changes:
            raw = invented(); cell = raw['views']['native']['cells']['PK/' + module.NS]
            if kind == 'point': cell['methods'][module.ARM]['native_micro_fmax'] = value
            if kind == 'fraction': cell['bootstrap']['comparisons'][0]['fraction_draws_above_zero'] = value
            if kind == 'mean': cell['bootstrap']['comparisons'][0]['difference_mean'] = value
            if kind == 'interval': cell['bootstrap']['comparisons'][0]['paired_95_percentile_interval'] = value
            if kind == 'score_interval': cell['bootstrap']['scores'][module.ARM]['bootstrap_95_percentile_interval'] = value
            with self.subTest(kind=kind, value=value), self.assertRaises(ValueError): module.aggregate(raw)

    def test_partial_or_unavailable_private_assessment_is_not_published_as_complete(self):
        for kind in ('cell_absent', 'bootstrap_unavailable', 'missing_count'):
            raw = invented(); cell = raw['views']['native']['cells']['PK/' + module.NS]
            if kind == 'cell_absent': cell.update(status='reference_absent', methods={})
            if kind == 'bootstrap_unavailable': cell['bootstrap'] = {'status': 'unavailable', 'reason': PRIVATE}
            if kind == 'missing_count': del raw['method_rows']
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); source = root/'private.json'; source.write_text(json.dumps(raw))
                with self.subTest(kind=kind), self.assertRaises(ValueError): module.render(source, root/'public')
                self.assertFalse((root/'public').exists())

    def test_earlier_no_coverage_method_is_preserved_without_fake_point(self):
        raw = invented(); old = raw['views']['native']['cells']['PK/' + module.NS]['methods']['localplus']
        old.update(status='no_native_coverage', native_micro_fmax=None, eligible_proteins=0)
        old['native_curve_agreement'] = {'status': 'unscorable_no_residual_reference_proteins'}
        public = module.aggregate(raw)
        self.assertIsNone(public['views']['native']['cells']['PK/' + module.NS]['methods']['localplus']['native_micro_fmax'])

    def test_render_retains_losses_all_cells_copied_intervals_and_no_case_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root/'private.json'; source.write_text(json.dumps(invented()))
            public = module.render(source, root/'public'); md = (root/'public/report.md').read_text()
            document = (root/'public/report.html').read_text()
            self.assertIn('DEVELOPMENT', md); self.assertIn('no independent confirmation', md)
            self.assertIn('-0.400000', md); self.assertIn('[-0.530000, -0.170000]', md)
            self.assertIn('[0.130000, 0.790000]', md)
            self.assertIn('Full native/bootstrap protein frame: 40; proteins with residual positive labels: 12', md)
            self.assertEqual(document.count('<details>'), 6)
            for text in ('DeepGO-SE is absent', 'No positive-unlabeled loss', 'same 4,040 fitting proteins',
                         'not a full ProtBoost reproduction', 'original frozen comparison',
                         'No interval, threshold, winner or new success gate'):
                self.assertIn(text, md)
            self.assertEqual(public['source_aggregate_sha256'], hashlib.sha256(source.read_bytes()).hexdigest())
            manifest = json.loads((root/'public/publication_manifest.json').read_text())
            self.assertFalse(manifest['evaluation_scores_intervals_or_model_choices_recomputed'])
            self.assertFalse(manifest['raw_cases_draws_or_paths_published'])
            for name, record in manifest['files'].items(): self.assertEqual(record['sha256'], hashlib.sha256((root/'public'/name).read_bytes()).hexdigest())
            published = ''.join(p.read_text() for p in (root/'public').iterdir())
            for private in (PRIVATE, '/private/', '/data/private/', '/Users/private/', 'GO:9999999'): self.assertNotIn(private, published)
            self.assertEqual({p.name for p in (root/'public').iterdir()}, {'report.md', 'report.html', 'summary.json', 'publication_manifest.json'})

    def test_existing_publication_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root/'private.json'; source.write_text(json.dumps(invented()))
            module.render(source, root/'public'); before = (root/'public/summary.json').read_bytes()
            with self.assertRaises(FileExistsError): module.render(source, root/'public')
            self.assertEqual(before, (root/'public/summary.json').read_bytes())


if __name__ == '__main__': unittest.main()
