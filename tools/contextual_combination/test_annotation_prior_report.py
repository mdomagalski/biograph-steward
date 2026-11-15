"""Invented-only completeness, privacy and negative-result presentation tests."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from .annotation_prior_report import (aggregate, render, CANDIDATE, MATCHED_PRIOR,
                                      ORIGINAL_PRIOR, LABELS, NAMESPACES, SETTINGS, VIEWS)


PRIVATE = 'PRIVATE_ACCESSION_CASE_AND_PATH'


def invented():
    plan_file = Path(__file__).with_name('annotation_prior_protocol.json')
    plan = json.loads(plan_file.read_text())
    scopes = {arm: (['biological_process'] if arm == 'coded_context_gcn' else list(NAMESPACES))
              for arm in LABELS}
    result = {'format': 'biograph-steward.annotation-prior-development-assessment.v1',
        'development_followup_on_consumed_reference': True, 'independent_confirmation': False,
        'original_primary_comparison_unchanged': True, 'new_success_gate_or_model_selection': False,
        'graph_pruning_or_app_promotion': False, 'target_count': 3300,
        'original_report': {'file': '/private/' + PRIVATE, 'sha256': plan['original_raw_report_sha256']},
        'plan': {'file': '/private/' + PRIVATE, 'sha256': hashlib.sha256(plan_file.read_bytes()).hexdigest()},
        'original_forecast_seal_sha256': plan['original_forecast_seal_sha256'],
        'arm_aspect_scopes': scopes, 'views': {}, 'files': {PRIVATE: PRIVATE}, 'ids': [PRIVATE]}
    for view in VIEWS:
        cells = {};result['views'][view] = {'reference_pins': {
            'PK': {'file': '/private/' + PRIVATE, 'sha256': 'c' * 64}}, 'cells': cells}
        for setting in SETTINGS:
            for ns in NAMESPACES:
                methods = {}
                for arm, aspects in scopes.items():
                    if ns not in aspects:continue
                    value = .4 if arm == CANDIDATE else .8 if arm in (ORIGINAL_PRIOR, MATCHED_PRIOR) else .6
                    methods[arm] = {'status': 'evaluated', 'native_micro_fmax': value,
                        'pre_exclusion_GT_proteins': 40, 'eligible_proteins': 12,
                        'raw_native_reference_proteins': 40,
                        'native_curve_agreement': {'author_point_agreement_passed': True,
                                                   'private_cases': [PRIVATE]},
                        'prediction_file': '/private/' + PRIVATE, 'ids': [PRIVATE]}
                boot = {'draws': 2000, 'seed': 20261113, 'raw_proteins': 40,
                    'original_native_gated_draws_reused_without_recomputation': True,
                    'development_followup_on_consumed_reference': True, 'independent_confirmation': False,
                    'scores': {arm: {'bootstrap_mean': row['native_micro_fmax'],
                        'bootstrap_95_percentile_interval': [.1, .9], 'bootstrap_Fmax': [PRIVATE]}
                        for arm, row in methods.items()},
                    'comparisons': [{'candidate': CANDIDATE, 'comparator': arm, 'difference_mean': -.7,
                        'paired_95_percentile_interval': [-.5, -.1], 'fraction_draws_above_zero': .02,
                        'difference_draws': [PRIVATE], 'ids': [PRIVATE]}
                        for arm in reversed(methods) if arm != CANDIDATE], 'ids': [PRIVATE]}
                cells[setting + '/' + ns] = {'setting': setting, 'namespace': ns, 'status': 'evaluated',
                    'methods': methods, 'bootstrap': boot,
                    'matched_prior_integration_gate': {'status': 'passed',
                        'native_point_exactly_equal': True, 'all_2000_paired_draw_peaks_exactly_equal': True,
                        'ids': [PRIVATE]}, 'reference': {'ids': [PRIVATE]},
                    'positive_reference_score_ledger': {'file': '/private/' + PRIVATE}}
    return result


class PublicationTests(unittest.TestCase):
    def test_all_cells_controls_copied_intervals_and_losses_survive_without_cases(self):
        raw = invented();before = copy.deepcopy(raw);public = aggregate(raw)
        self.assertEqual(raw, before)
        self.assertEqual(public['original_declared_method_count'], 17)
        self.assertEqual(public['new_fixed_method_count'], 2)
        for view in VIEWS:
            self.assertEqual(len(public['views'][view]['cells']), 9)
            for key, cell in public['views'][view]['cells'].items():
                expected = raw['views'][view]['cells'][key]
                self.assertEqual(set(cell['methods']), set(expected['methods']))
                self.assertEqual(len(cell['bootstrap']['comparisons']), len(cell['methods']) - 1)
                self.assertEqual(cell['matched_prior_integration_gate']['draw_count'], 2000)
                self.assertEqual(cell['bootstrap']['comparisons'][0]['paired_95_percentile_interval'], [-.5, -.1])
                self.assertEqual(cell['bootstrap']['comparisons'][0]['difference_mean'], -.7)
        text = json.dumps(public)
        self.assertNotIn(PRIVATE, text)
        for field in ('bootstrap_Fmax', 'difference_draws', 'prediction_file', 'reference_pins', 'positive_reference_score_ledger'):
            self.assertNotIn('"' + field + '"', text)

    def test_absent_and_unscorable_cells_are_not_silently_removed(self):
        raw = invented()
        cell = raw['views']['native']['cells']['LK/cellular_component']
        cell.update(status='reference_absent', methods={})
        other = raw['views']['fixed_T0']['cells']['NK/molecular_function']
        other['matched_prior_integration_gate'] = {'status': 'unavailable_no_native_prior_coverage',
                                                  'equivalence_claimed': False}
        other['bootstrap'] = {'status': 'unavailable', 'reason': PRIVATE}
        public = aggregate(raw)
        self.assertEqual(len(public['views']['native']['cells']), 9)
        self.assertEqual(public['views']['native']['cells']['LK/cellular_component']['status'], 'reference_absent')
        self.assertEqual(public['views']['fixed_T0']['cells']['NK/molecular_function']['bootstrap'], {'status': 'unavailable'})
        self.assertNotIn(PRIVATE, json.dumps(public))

    def test_json_sorted_aspect_scope_order_does_not_change_coverage(self):
        raw = invented()
        for arm in (CANDIDATE, MATCHED_PRIOR):
            raw['arm_aspect_scopes'][arm] = sorted(NAMESPACES)
        public = aggregate(raw)
        for arm in (CANDIDATE, MATCHED_PRIOR):
            self.assertEqual(set(public['arm_aspect_scopes'][arm]), set(NAMESPACES))

    def test_missing_controls_cells_or_saved_contrasts_fail_instead_of_being_hidden(self):
        for change in ('cell', 'method', 'contrast', 'scope'):
            raw = invented()
            cell = raw['views']['native']['cells']['PK/biological_process']
            if change == 'cell':del raw['views']['native']['cells']['NK/cellular_component']
            if change == 'method':del cell['methods']['localplus']
            if change == 'contrast':cell['bootstrap']['comparisons'].pop()
            if change == 'scope':raw['arm_aspect_scopes'][PRIVATE] = list(NAMESPACES)
            with self.subTest(change=change), self.assertRaises(ValueError):aggregate(raw)

    def test_independent_claim_or_failed_prior_gate_is_rejected(self):
        for change in ('independent', 'gate', 'prior_point', 'plan'):
            raw = invented()
            if change == 'independent':raw['independent_confirmation'] = True
            if change == 'gate':
                raw['views']['native']['cells']['PK/biological_process']['matched_prior_integration_gate']['all_2000_paired_draw_peaks_exactly_equal'] = False
            if change == 'prior_point':
                raw['views']['native']['cells']['PK/biological_process']['methods'][MATCHED_PRIOR]['native_micro_fmax'] = .7
            if change == 'plan':raw['plan']['sha256'] = 'a' * 64
            with self.subTest(change=change), self.assertRaises(ValueError):aggregate(raw)

    def test_render_retains_negative_outcomes_and_only_writes_aggregate_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);source = root/'raw.json';source.write_text(json.dumps(invented()))
            public = render(source, root/'public')
            text = (root/'public/report.md').read_text()
            document = (root/'public/report.html').read_text()
            self.assertIn('DEVELOPMENT', text)
            self.assertIn('reference already consumed', text)
            self.assertIn('no independent confirmation', text)
            self.assertIn('original frozen study', text)
            self.assertNotIn('original independent study', text)
            self.assertIn('-0.400000', text)  # Display-only point subtraction.
            self.assertIn('[-0.500000, -0.100000]', text)  # Literal saved interval.
            self.assertIn('Full native/bootstrap protein frame: 40; proteins with residual positive labels: 12', text)
            self.assertEqual(document.count('<details>'), 18)
            self.assertIn('not calibrated confidence', document)
            self.assertIn('no additional pairwise intervals were invented', document)
            self.assertEqual(public['source_aggregate_sha256'], hashlib.sha256(source.read_bytes()).hexdigest())
            manifest = json.loads((root/'public/publication_manifest.json').read_text())
            self.assertFalse(manifest['evaluation_scores_intervals_or_model_choices_recomputed'])
            for name, row in manifest['files'].items():
                self.assertEqual(row['sha256'], hashlib.sha256((root/'public'/name).read_bytes()).hexdigest())
            published = ''.join(path.read_text() for path in (root/'public').iterdir())
            self.assertNotIn(PRIVATE, published)
            self.assertNotIn('/private/', published)
            self.assertFalse(any(path.suffix in ('.npz', '.npy', '.tsv') for path in (root/'public').iterdir()))


if __name__ == '__main__':unittest.main()
