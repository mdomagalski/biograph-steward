"""Invented aggregates only; figure faithfully copies points/intervals."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from .plot_results import (CANDIDATE, CONTEXT_ARMS, UPDATES, VIEWS,
                           controls, prepare_rows, prepare_update_rows, render)
from .protocol import PROTOCOL
from .report import aggregate


def raw_fixture():
    report = {'protocol': copy.deepcopy(PROTOCOL), 'synthetic_fixture': True,
        'model_choices': {'fresh_final_reference_opened': False,
            'selections': {'biological_process': {'selected_arm': 'coded_context_gcn',
                'validation_scores': {'context_mlp': .2, 'context_gcn': .3,
                                      'coded_context_gcn': .4}}}}, 'views': {}}
    names = controls(PROTOCOL)
    for view, _ in VIEWS:
        methods = {}
        for i, name in enumerate((*names, *CONTEXT_ARMS, CANDIDATE)):
            point = .44 if i == 0 else .2 + i * .008
            if name in ('coded_context_gcn', CANDIDATE):
                point = .42
            if view == 'fixed_T0':
                point += .005
            methods[name] = {'native_micro_fmax': point, 'status': 'evaluated',
                'native_curve_agreement': {'author_point_agreement_passed': True,
                                          'max_absolute_curve_difference': 0.},
                'raw_native_reference_proteins': 100, 'eligible_proteins': 97}
        def bootstrap(candidate, comparators):
            rows = []
            for name in comparators:
                difference = methods[candidate]['native_micro_fmax'] - methods[name]['native_micro_fmax']
                rows.append({'candidate': candidate, 'comparator': name,
                    'difference_mean': .987654321,  # Deliberately NOT observed point.
                    'paired_95_percentile_interval': [difference - .03, difference + .04]})
            return {'draws': 2000, 'seed': 20261113, 'ordinary_only': True, 'IA_supplied': False,
                'shared_protein_samples_across_all_arms': True, 'raw_proteins': 100, 'comparisons': rows}
        cell = {'status': 'evaluated', 'methods': methods,
                'bootstrap': bootstrap(CANDIDATE, [name for name in methods if name != CANDIDATE])}
        for key, candidate, comparator, _ in UPDATES:
            cell[key] = bootstrap(candidate, [comparator])
        report['views'][view] = {'cells': {'PK/biological_process': cell}}
    report['arm_aspect_scopes'] = {name: ['biological_process'] for name in methods}
    return report


def fixture():
    # Exercise the real publication boundary before every downstream check.
    public = aggregate(raw_fixture())
    public['synthetic_fixture'] = True
    return public


class PlotTests(unittest.TestCase):
    def test_consumes_real_publication_projection_and_rejects_raw_input(self):
        raw = raw_fixture(); public = aggregate(raw)
        self.assertFalse(public['fresh_final_reference_opened_at_model_choice'])
        self.assertNotIn('selections', public['model_choices'])
        self.assertEqual(len(prepare_rows(public)), 26)
        with self.assertRaisesRegex(ValueError, 'must precede final-reference'):
            prepare_rows(raw)
        public['fresh_final_reference_opened_at_model_choice'] = True
        with self.assertRaisesRegex(ValueError, 'must precede final-reference'):
            prepare_rows(public)

    def test_all_declared_controls_retained_in_protocol_order_and_source_unchanged(self):
        report = fixture(); original = copy.deepcopy(report); rows = prepare_rows(report)
        self.assertEqual(len(rows), len(controls(PROTOCOL)) * 2)
        for view, _ in VIEWS:
            self.assertEqual([r['comparator'] for r in rows if r['view'] == view], list(controls(PROTOCOL)))
        self.assertEqual(report, original)
        first = rows[0]
        self.assertAlmostEqual(first['point_difference'], -.02)
        self.assertNotEqual(first['point_difference'], .987654321)
        self.assertEqual(first['paired_95_percentile_interval'],
                         original['views']['native']['cells']['PK/biological_process']['bootstrap']['comparisons'][0]['paired_95_percentile_interval'])

    def test_missing_or_unregistered_control_fails_instead_of_favorable_subset(self):
        report = fixture(); cell = report['views']['native']['cells']['PK/biological_process']
        del cell['methods']['localplus_T0_curated']
        with self.assertRaisesRegex(ValueError, 'every declared non-context control'):
            prepare_rows(report)
        report = fixture(); report['views']['native']['cells']['PK/biological_process']['methods']['unplanned'] = {}
        with self.assertRaisesRegex(ValueError, 'every declared non-context control'):
            prepare_rows(report)

    def test_saved_interval_may_be_asymmetric_or_exclude_observed_point(self):
        report = fixture(); pair = report['views']['native']['cells']['PK/biological_process']['bootstrap']['comparisons'][0]
        pair['paired_95_percentile_interval'] = [.1, .2]
        row = prepare_rows(report)[0]
        self.assertAlmostEqual(row['point_difference'], -.02)
        self.assertEqual(row['paired_95_percentile_interval'], [.1, .2])

    def test_duplicate_pair_wrong_candidate_or_bad_curve_gate_rejected(self):
        report = fixture(); pairs = report['views']['native']['cells']['PK/biological_process']['bootstrap']['comparisons']
        pairs.append(copy.deepcopy(pairs[0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            prepare_rows(report)
        report = fixture(); report['views']['native']['cells']['PK/biological_process']['bootstrap']['comparisons'][0]['candidate'] = 'unplanned'
        with self.assertRaisesRegex(ValueError, 'candidate identity'):
            prepare_rows(report)
        report = fixture(); report['views']['native']['cells']['PK/biological_process']['methods']['localplus']['native_curve_agreement']['author_point_agreement_passed'] = False
        with self.assertRaisesRegex(ValueError, 'curve agreement'):
            prepare_rows(report)

    def test_source_update_rows_use_the_three_saved_contrasts_in_both_views(self):
        report = fixture(); rows = prepare_update_rows(report)
        self.assertEqual(len(rows), 6)
        self.assertEqual([r['label'] for r in rows[:3]], [item[3] for item in UPDATES])
        for row in rows:
            methods = report['views'][row['view']]['cells']['PK/biological_process']['methods']
            self.assertEqual(row['point_difference'], methods[row['candidate']]['native_micro_fmax']
                             - methods[row['comparator']]['native_micro_fmax'])

    def test_saved_selected_model_alias_cannot_be_relabeled(self):
        report = fixture()
        report['views']['native']['cells']['PK/biological_process']['methods']['coded_context_gcn']['native_micro_fmax'] = .9
        with self.assertRaisesRegex(ValueError, 'selected-model alias differs'):
            prepare_rows(report)

    def test_render_exports_source_pinned_invented_artifacts_and_rejects_overwrite(self):
        try:
            import matplotlib
        except ImportError:
            self.skipTest('Optional scientific figure runtime unavailable')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'INVENTED_aggregate.json'
            source.write_text(json.dumps(fixture()))
            result = render(source, root / 'figures')
            self.assertFalse(result['new_statistics_or_model_selection'])
            self.assertEqual(result['displayed_noncontext_controls_per_view'], 13)
            self.assertEqual(len(result['files']), 7)
            for name in result['files']:
                self.assertTrue((root / 'figures' / name).is_file())
            with self.assertRaises(FileExistsError):
                render(source, root / 'figures')


if __name__ == '__main__':
    unittest.main()
