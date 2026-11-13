"""Invented frame controls for the separate consumed-reference RA extension."""
import importlib.util
import importlib.metadata
import unittest

from tools.coessentiality_feasibility.resource_allocation import native_scores, weighted_point
from tools.coessentiality_feasibility.compare import fractional_top


class WeightedQueryTests(unittest.TestCase):
    def test_query_specific_weighted_expectation_and_fractional_ties(self):
        genes = ['a', 'b', 'c']
        partners = {'a': [('b', .1), ('c', .1)], 'b': [('a', .1), ('c', .1)], 'c': [('a', .1), ('b', .1)]}
        selections = {g: fractional_top(p, 1) for g, p in partners.items()}
        weights = {('a', 'b'): 1., ('a', 'c'): 0., ('b', 'c'): 2.}
        point = weighted_point(genes, partners, selections, weights, 1)
        self.assertEqual(point['observed_weighted_sum'], 3.)
        self.assertEqual(point['expected_weighted_sum'], 3.)
        self.assertEqual(point['enrichment'], 1.)
        self.assertEqual([r['expected_weighted_sum'] for r in point['queries']], [.5, 1.5, 1.])

    def test_zero_context_query_remains_in_slots_not_dropped(self):
        genes = ['a', 'b', 'c']
        partners = {'a': [('b', .01), ('c', .2)], 'b': [('a', .01), ('c', .3)], 'c': [('a', .2), ('b', .3)]}
        selections = {g: fractional_top(p, 1) for g, p in partners.items()}
        point = weighted_point(genes, partners, selections, {('a', 'b'): 1., ('a', 'c'): 0., ('b', 'c'): 0.}, 1)
        self.assertEqual(point['selected_slots'], 3)
        self.assertEqual(point['observed_weighted_sum'], 2.)
        self.assertEqual(point['expected_weighted_sum'], 1.)
        self.assertEqual(point['queries'][-1]['observed_weighted_sum'], 0.)
        self.assertAlmostEqual(point['observed_mean_RA_per_slot'], 2 / 3)

    def test_zero_expected_is_undefined_and_incomplete_frame_is_UNKNOWN(self):
        partners = {'a': [('b', .1)], 'b': [('a', .1)]}
        selections = {g: fractional_top(p, 1) for g, p in partners.items()}
        point = weighted_point(['a', 'b'], partners, selections, {('a', 'b'): 0.}, 1)
        self.assertIsNone(point['enrichment']); self.assertTrue(point['zero_expected_enrichment_undefined'])
        selections['b'] = None
        point = weighted_point(['a', 'b'], partners, selections, {('a', 'b'): 1.}, 1)
        self.assertIsNone(point['observed_weighted_sum'])
        self.assertIsNone(point['selected_slots'])
        self.assertEqual(point['available_queries'], 1)


def native_runtime_available():
    try:
        return bool(importlib.util.find_spec('networkx')) and importlib.metadata.version('networkx') == '3.7'
    except importlib.metadata.PackageNotFoundError:
        return False


@unittest.skipUnless(native_runtime_available(), 'optional reviewed NetworkX3.7 runtime not installed')
class NativeResourceAllocationTests(unittest.TestCase):
    def test_native_parity_broad_and_narrow_models_full_frame_degree(self):
        import networkx as nx
        memberships = [('a', 'broad'), ('b', 'broad'), ('c', 'broad'), ('a', 'narrow'), ('b', 'narrow'), ('c', 'singleton')]
        # Only a/b is queried, but c still contributes to the fixed broad-model degree.
        weights, info = native_scores(['a', 'b', 'c', 'isolated'], memberships, [('a', 'b'), ('a', 'isolated')], nx)
        self.assertAlmostEqual(weights[('a', 'b')], 1 / 3 + 1 / 2)
        self.assertEqual(weights[('a', 'isolated')], 0)
        self.assertEqual(info['full_frame_model_degrees'], {'broad': 3, 'narrow': 2, 'singleton': 1})
        self.assertEqual(info['query_nodes_including_isolates'], 4)
        self.assertFalse(info['degree_rebuilt_per_query_or_chromosome'])

    def test_affinity_can_exceed_one_and_is_not_a_probability(self):
        import networkx as nx
        rows = [(g, model) for g in ['a', 'b'] for model in ['v1', 'v2', 'v3']]
        weights, info = native_scores(['a', 'b'], rows, [('a', 'b')], nx)
        self.assertEqual(weights[('a', 'b')], 1.5)

    def test_gene_model_namespaces_and_exact_versions_are_not_collapsed(self):
        import networkx as nx
        weights, info = native_scores(['same', 'other', 'isolated'], [('same', 'same'), ('other', 'same'),
            ('same', 'WP1_r1'), ('other', 'WP1_r2')], [('same', 'other'), ('other', 'isolated')], nx)
        self.assertEqual(weights[('same', 'other')], .5)
        self.assertEqual(weights[('other', 'isolated')], 0.)
        self.assertEqual(info['model_nodes'], 3)
        self.assertEqual(info['membership_edges'], 4)

    def test_duplicate_self_and_out_of_frame_inputs_fail(self):
        import networkx as nx
        for rows, pairs in [([('a', 'w'), ('a', 'w')], [('a', 'b')]),
                            ([('a', 'w')], [('a', 'a')]), ([('outside', 'w')], [('a', 'b')]),
                            ([('a', 'w')], [('a', 'b'), ('a', 'b')])]:
            with self.subTest(rows=rows, pairs=pairs), self.assertRaises(ValueError):
                native_scores(['a', 'b'], rows, pairs, nx)


if __name__ == '__main__':
    unittest.main()
