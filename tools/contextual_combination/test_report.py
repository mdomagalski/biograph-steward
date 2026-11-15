"""Invented-only aggregate publication and gate-interpretation checks."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from .protocol import PROTOCOL
from .report import aggregate, render, GATES, SOURCE_GATES, CANDIDATE, PRIMARY


PRIVATE = 'PRIVATE_CASE_ACCESSION_P00001'


def invented():
    methods = {
        CANDIDATE: {'native_micro_fmax': .7, 'eligible_proteins': 12, 'status': 'evaluated'},
        'localplus': {'native_micro_fmax': .4, 'eligible_proteins': 12, 'status': 'evaluated'},
        'localplus_T0_curated': {'native_micro_fmax': .6, 'eligible_proteins': 12, 'status': 'evaluated'},
        'localplus_updated_seeds': {'native_micro_fmax': .5, 'eligible_proteins': 12, 'status': 'evaluated'},
    }
    boot = {'draws': 2000, 'seed': 20261113, 'raw_proteins': 12,
        'scores': {CANDIDATE: {'bootstrap_Fmax': [PRIVATE], 'bootstrap_mean': .68,
            'bootstrap_95_percentile_interval': [.6, .8], 'ids': [PRIVATE]}},
        'comparisons': [{'candidate': CANDIDATE, 'comparator': 'localplus',
            'difference_draws': [PRIVATE], 'difference_mean': .28,
            'paired_95_percentile_interval': [.1, .4], 'ids': [PRIVATE]}],
        'ids': [PRIVATE], 'ordinary': [PRIVATE]}
    cell = {'setting': 'PK', 'namespace': 'biological_process', 'status': 'evaluated',
        'methods': methods, 'bootstrap': boot,
        'positive_reference_score_ledger': {'file': '/private/' + PRIVATE,
            'sha256': 'a' * 64, 'reference_positive_pairs': 20},
        'reference': {'ids': [PRIVATE]}, 'known': {'ids': [PRIVATE]},
        'source_slice_points': {'fresh-inference': {'definition': 'Invented source-only slice',
            'ids': [PRIVATE], 'full_source_slice_proteins': 8, 'raw_native_reference_proteins': 4,
            'methods': {CANDIDATE: {'eligible_proteins': 4, 'derived_micro_fmax': .55,
                                   'ids': [PRIVATE], 'ordinary': [PRIVATE]}}},
            PRIVATE: {'ids': [PRIVATE]}}}
    for method in methods.values():
        method.update(ids=[PRIVATE], ordinary=[PRIVATE], prediction_file='/private/' + PRIVATE,
            forecast_projection={'source_heads': 10, 'mapped_heads': 9, 'dropped_heads': 1,
                                 'protein_ids': [PRIVATE]},
            native_curve_agreement={'author_point_agreement_passed': True,
                                    'per_protein_counts': [PRIVATE], 'columns': {'tp': 0., PRIVATE: 1.}})
    result = {'created_at': '2026-01-01', 'forecast_seal_sha256': 'b' * 64, 'target_count': 3300,
        'protocol': copy.deepcopy(PROTOCOL), 'arm_aspect_scopes': {a: ['biological_process'] for a in methods},
        'model_choices': {'selections': {'biological_process': {
            # Deliberately inconsistent invented scores demonstrate that the
            # presentation preserves a stored choice instead of selecting one.
            'selected_arm': 'context_mlp', 'validation_scores': {'context_mlp': .2, 'context_gcn': .9},
            'model_metadata': {'private_file': PRIVATE}, 'ids': [PRIVATE]}}},
        'views': {v: {'reference_pins': {'PK': {'file': '/private/' + PRIVATE, 'sha256': 'c' * 64}},
            'cells': {PRIMARY: copy.deepcopy(cell), 'NK/molecular_function': {
                'setting': 'NK', 'namespace': 'molecular_function', 'status': 'reference_absent', 'methods': {}}}}
            for v in ('native', 'fixed_T0')},
        'files': {'private_cases.jsonl': PRIVATE}, 'ids': [PRIVATE],
        'primary_success_private_case_rows': [PRIVATE], 'automatic_graph_or_app_promotion': False}
    result['protocol']['cohort']['ids'] = [PRIVATE]
    result['protocol']['private_cases'] = [PRIVATE]
    result['arm_aspect_scopes'][PRIVATE] = ['biological_process']
    for name, _ in GATES:
        result[name] = False
    for name, _ in SOURCE_GATES:
        result[name] = True
    return result


class AggregatePublicationTests(unittest.TestCase):
    def test_nested_case_fields_and_all_bootstrap_draws_are_excluded(self):
        result = aggregate(invented())
        text = json.dumps(result, sort_keys=True)
        self.assertNotIn(PRIVATE, text)
        for key in ('bootstrap_Fmax', 'difference_draws', 'prediction_file', 'per_protein_counts'):
            self.assertNotIn(key, text)
        cell = result['views']['native']['cells'][PRIMARY]
        self.assertEqual(cell['reference_positive_pair_count'], 20)
        self.assertEqual(cell['private_score_ledger_sha256'], 'a' * 64)
        self.assertEqual(cell['bootstrap']['comparisons'][0]['paired_95_percentile_interval'], [.1, .4])
        self.assertEqual(cell['source_slice_points']['fresh-inference']['methods'][CANDIDATE]['derived_micro_fmax'], .55)

    def test_projection_preserves_readouts_and_does_not_mutate_or_reselect(self):
        original = invented()
        before = copy.deepcopy(original)
        public = aggregate(original)
        self.assertEqual(original, before)
        self.assertEqual(public['model_choices']['biological_process']['selected_arm'], 'context_mlp')
        self.assertEqual(public['model_choices']['biological_process']['validation_scores'],
                         {'context_mlp': .2, 'context_gcn': .9})
        self.assertEqual(public['views']['native']['cells'][PRIMARY]['methods'][CANDIDATE]['native_micro_fmax'], .7)
        self.assertFalse(public['primary_success_over_literal_LocalPlus_both_views'])
        self.assertTrue(public['current_T0_LocalPlus_gain_both_views'])

    def test_reference_absent_and_missing_cells_remain_explicit(self):
        public = aggregate(invented())
        for view in public['views'].values():
            self.assertEqual(len(view['cells']), 9)
            self.assertEqual(view['cells']['NK/molecular_function']['status'], 'reference_absent')
            self.assertEqual(view['cells']['LK/cellular_component']['status'], 'missing_result')
            self.assertEqual(view['cells']['LK/cellular_component']['methods'], {})

    def test_source_update_pass_does_not_replace_failed_primary_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'invented.json'
            source.write_text(json.dumps(invented()))
            render(source, root / 'public')
            md = (root / 'public/report.md').read_text()
            document = (root / 'public/report.html').read_text()
            self.assertIn('does not establish a gain over retained LocalPlus', md)
            self.assertIn('| Selected stacker beyond retained LocalPlus | Not established |', md)
            self.assertIn('| Complete current-T0 annotation update beyond retained LocalPlus | Passed |', md)
            self.assertIn('does not establish a learned-stacker gain', md)
            self.assertIn('No native reference', md)
            self.assertIn('Result unavailable', md)
            self.assertIn('unavailable', md)
            self.assertIn('+0.300000', md)  # Display-only observed point subtraction.
            self.assertIn('[+0.100000, +0.400000]', md)  # Literal stored interval.
            self.assertIn('<ul><li>', document)
            self.assertNotIn(PRIVATE, md + document + (root / 'public/summary.json').read_text())

    def test_missing_primary_and_view_render_without_invented_scores(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'invented.json'
            result = invented()
            result['views'] = {'native': {'reference_pins': {}, 'cells': {}}}
            result.pop('primary_success_over_literal_LocalPlus_both_views')
            result.pop('primary_success_beyond_current_T0_curated_LocalPlus_both_views')
            source.write_text(json.dumps(result))
            public = render(source, root / 'public')
            md = (root / 'public/report.md').read_text()
            self.assertIn('primary retained-LocalPlus gain gate is unavailable', md)
            self.assertEqual(public['views']['fixed_T0']['cells'][PRIMARY]['status'], 'missing_result')
            self.assertNotIn('0.000000', md)


if __name__ == '__main__':
    unittest.main()
