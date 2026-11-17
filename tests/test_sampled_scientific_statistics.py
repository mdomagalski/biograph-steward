"""Exact small-population completions and strict scientific-label admission."""
from copy import deepcopy
from itertools import product
import unittest

from tools.sampled_audit.scientific_statistics import assess


def population(n=4):
    return [{'assertion_id': f'a{i}', 'assertion_content_sha256': str(i) * 64,
             'stored_predicate': 'stored:qualified_claim', 'claim_semantics': 'exact stored claim',
             'stratum': 'large' if i < 3 else 'small'} for i in range(n)]


def judgment(row, label='unknown', **changes):
    return {**{k: row[k] for k in ('assertion_id', 'assertion_content_sha256', 'stored_predicate', 'claim_semantics')},
        'scientific_label': label, 'reference_kind': 'none' if label == 'unknown' else 'expert_curation',
        'exact_claim_match': label != 'unknown', 'context_complete': label != 'unknown',
        'qualifier_scope_complete': label != 'unknown', 'reference_independence': 'unresolved',
        'reference_files': [] if label == 'unknown' else [{'file': 'invented_reference.json', 'sha256': 'f' * 64}],
        'reason': 'Invented explicit admission fixture.', **changes}


class ScientificFinitePopulationTests(unittest.TestCase):
    def test_zero_admitted_labels_does_not_become_zero_or_certain_accuracy(self):
        p = population()
        out = assess(p, {'baseline': ['a0', 'a1', 'a2', 'a3'], 'retained': ['a0', 'a1']}, [],
            comparisons=[{'baseline': 'baseline', 'candidate': 'retained'}])
        self.assertEqual(out['graphs']['baseline']['logical_accuracy_bounds'], {'lower': 0., 'upper': 1.})
        self.assertIsNone(out['graphs']['baseline']['accuracy_point_estimate'])
        self.assertEqual(out['comparisons'][0]['logical_accuracy_difference_bounds'], {'lower': -.5, 'upper': .5})
        self.assertFalse(out['biological_improvement_claimed'])
        self.assertIsNone(out['confidence_interval'])

    def test_all_unsampled_units_remain_unknown_not_extrapolated_census_labels(self):
        p = population()
        out = assess(p, {'all': [r['assertion_id'] for r in p]}, [judgment(p[0], 'true')], comparisons=[])
        self.assertEqual(out['graphs']['all']['logical_accuracy_bounds'], {'lower': .25, 'upper': 1.})
        self.assertEqual(out['graphs']['all']['labels'], {'true': 1, 'false': 0, 'unknown': 3})
        self.assertEqual(out['unreviewed_census_assertions'], 3)

    def test_exhaustive_completions_match_sharp_bounds_for_all_small_memberships(self):
        p = population()
        # Covers retained subsets and nonnested source/enrichment populations.
        graphs = ({'old': ['a0', 'a1', 'a2'], 'new': ['a1', 'a2', 'a3']},
                  {'old': ['a0', 'a1', 'a2', 'a3'], 'new': ['a0', 'a3']})
        for members, statuses in product(graphs, product(('true', 'false', 'unknown'), repeat=4)):
            labels = [judgment(row, label) for row, label in zip(p, statuses)]
            out = assess(p, members, labels, comparisons=[{'baseline': 'old', 'candidate': 'new'}])
            unknown = [i for i, v in enumerate(statuses) if v == 'unknown']
            differences, means = [], {k: [] for k in members}
            for completion in product((0, 1), repeat=len(unknown)):
                truth = {f'a{i}': int(v == 'true') for i, v in enumerate(statuses)}
                truth.update({f'a{i}': v for i, v in zip(unknown, completion)})
                rates = {k: sum(truth[uid] for uid in ids) / len(ids) for k, ids in members.items()}
                differences.append(rates['new'] - rates['old'])
                for k in members: means[k].append(rates[k])
            bound = out['comparisons'][0]['logical_accuracy_difference_bounds']
            self.assertAlmostEqual(bound['lower'], min(differences))
            self.assertAlmostEqual(bound['upper'], max(differences))
            for k in members:
                b = out['graphs'][k]['logical_accuracy_bounds']
                self.assertAlmostEqual(b['lower'], min(means[k]))
                self.assertAlmostEqual(b['upper'], max(means[k]))

    def test_same_assertion_correlation_makes_identical_graph_difference_zero(self):
        p = population()
        out = assess(p, {'a': ['a0', 'a2'], 'b': ['a0', 'a2']}, [],
            comparisons=[{'baseline': 'a', 'candidate': 'b'}])
        row = out['comparisons'][0]
        self.assertEqual(row['logical_accuracy_difference_bounds'], {'lower': 0., 'upper': 0.})
        self.assertEqual(row['accuracy_difference_point_estimate'], 0.)
        self.assertIsNone(out['graphs']['a']['accuracy_point_estimate'])

    def test_fully_labelled_adverse_change_remains_negative(self):
        p = population()
        rows = [judgment(r, 'true' if i < 2 else 'false') for i, r in enumerate(p)]
        out = assess(p, {'old': [r['assertion_id'] for r in p], 'new': ['a2', 'a3']}, rows,
            comparisons=[{'baseline': 'old', 'candidate': 'new'}])
        self.assertEqual(out['graphs']['old']['accuracy_point_estimate'], .5)
        self.assertEqual(out['comparisons'][0]['logical_accuracy_difference_bounds'], {'lower': -.5, 'upper': -.5})
        self.assertFalse(out['comparisons'][0]['biological_improvement_claimed'])

    def test_empty_graph_is_undefined_not_perfect_accuracy(self):
        out = assess(population(), {'old': ['a0'], 'empty': []}, [],
            comparisons=[{'baseline': 'old', 'candidate': 'empty'}])
        self.assertIsNone(out['graphs']['empty']['logical_accuracy_bounds'])
        self.assertEqual(out['comparisons'][0]['status'], 'undefined_empty_graph')

    def test_source_evidence_or_qualifier_gap_cannot_become_scientific_truth(self):
        p = population()
        changes = ({'reference_kind': 'native_source_only'}, {'reference_kind': 'none'},
                   {'reference_files': []}, {'exact_claim_match': False}, {'context_complete': False},
                   {'qualifier_scope_complete': False}, {'reference_independence': 'assumed'},
                   {'scientific_label': 'supported'}, {'reference_files': [{'file': 'x', 'sha256': 'bad'}]})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                assess(p, {'all': ['a0']}, [judgment(p[0], 'true', **change)], comparisons=[])

    def test_hash_predicate_and_semantics_must_match_exact_stored_assertion(self):
        p = population()
        for key, value in (('assertion_content_sha256', 'f' * 64), ('stored_predicate', 'direct_binding'),
                           ('claim_semantics', 'stronger causal biology'), ('assertion_id', 'foreign')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                assess(p, {'all': ['a0']}, [judgment(p[0], **{key: value})], comparisons=[])

    def test_duplicate_census_judgment_or_membership_and_foreign_ids_fail(self):
        p = population()
        for pop, graphs, rows in ((p + [p[0]], {'all': ['a0']}, []),
            (p, {'all': ['a0', 'a0']}, []), (p, {'all': ['foreign']}, []),
            (p, {'all': ['a0']}, [judgment(p[0]), judgment(p[0])])):
            with self.assertRaises(ValueError): assess(pop, graphs, rows, comparisons=[])

    def test_unknown_can_record_native_support_without_promotion_and_inputs_are_unchanged(self):
        p = population(); row = judgment(p[0], reference_kind='native_source_only',
            reference_files=[{'file': 'native.json', 'sha256': 'e' * 64}])
        graphs = {'old': ['a0', 'a1'], 'new': ['a1']}; rows = [row]
        before = deepcopy((p, graphs, rows))
        out = assess(p, graphs, rows, comparisons=[])
        self.assertEqual(out['reference_kind_counts'], {'native_source_only': 1})
        self.assertEqual(out['graphs']['old']['labels']['unknown'], 2)
        self.assertEqual((p, graphs, rows), before)

    def test_main_and_removed_probability_domains_remain_separate(self):
        p = population()
        domains = {'main': {'purpose': 'original_union_probability_sample',
            'population_ids': ['a0', 'a1', 'a2', 'a3'],
            'strata': {'large': {'population_size': 3, 'sample_size': 1}, 'small': {'population_size': 1, 'sample_size': 1}},
            'sample_rows': [{'case_id': 'c1', 'assertion_id': 'a0', 'stratum': 'large'},
                            {'case_id': 'c2', 'assertion_id': 'a3', 'stratum': 'small'}]},
            'removed': {'purpose': 'separate_removed_domain', 'population_ids': ['a1', 'a2'],
                'strata': {'large': {'population_size': 2, 'sample_size': 1}},
                'sample_rows': [{'case_id': 'r1', 'assertion_id': 'a1', 'stratum': 'large'}]}}
        out = assess(p, {'all': ['a0', 'a1', 'a2', 'a3']}, [judgment(p[0], 'true'), judgment(p[1], 'false')],
            comparisons=[], sampling_domains=domains)
        main, removed = (out['sampling_domains'][k] for k in ('main', 'removed'))
        self.assertEqual(main['design_weighted_supplied_label_statuses']['true']['weighted_fraction'], .75)
        self.assertEqual(removed['design_weighted_supplied_label_statuses']['false']['weighted_fraction'], 1.)
        self.assertIsNone(main['design_weighted_supplied_label_statuses']['true']['estimated_design_variance'])
        self.assertFalse(main['pool_with_other_sampling_domains'])
        self.assertIsNone(main['population_scientific_accuracy_estimate'])
        # Sample weighting cannot turn two known assertions into census truth.
        self.assertEqual(out['graphs']['all']['logical_accuracy_bounds'], {'lower': .25, 'upper': .75})
        bad = deepcopy(domains); bad['main']['strata']['large']['population_size'] = 30
        with self.assertRaises(ValueError): assess(p, {'all': ['a0']}, [], comparisons=[], sampling_domains=bad)
        bad = deepcopy(domains)
        bad['main']['sample_rows'][0]['inclusion_probability'] = {'numerator': True, 'denominator': 3}
        with self.assertRaises(ValueError): assess(p, {'all': ['a0']}, [], comparisons=[], sampling_domains=bad)

    def test_malformed_containers_and_conflicting_reference_pins_fail_closed(self):
        p = population()
        with self.assertRaises(ValueError):
            assess(p, {'all': ['a0']}, [], comparisons=[], sampling_domains=[])
        with self.assertRaises(ValueError):
            assess(p, {'all': ['a0']}, [judgment(p[0], assertion_id=[])], comparisons=[])
        with self.assertRaises(ValueError):
            assess(p, {'all': ['a0']}, [], comparisons=[{'baseline': [], 'candidate': 'all'}])
        refs = [{'file': 'same.json', 'sha256': h * 64} for h in ('a', 'b')]
        with self.assertRaises(ValueError):
            assess(p, {'all': ['a0']}, [judgment(p[0], 'true', reference_files=refs)], comparisons=[])


if __name__ == '__main__':
    unittest.main()
