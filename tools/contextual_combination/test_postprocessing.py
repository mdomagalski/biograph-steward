"""Source-native pure GO closure on invented graphs, never benchmark labels."""
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

from .postprocessing import SOFT_RATE, MAX_MIN_RATE, load_postprocessor, published_soft_closure


class PostprocessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            import pandas as pd
            cls.np = np
            cls.root = Path(os.environ.get('BIOGRAPH_PROTBOOST_AUTHOR_ROOT',
                'runs/contextual_gain_20261115/operator/combination_methods_v1/author'))
            cls.native, cls.receipt = load_postprocessor(cls.root)
        except (ImportError, FileNotFoundError) as error:
            if os.environ.get('BIOGRAPH_CONTEXT_NATIVE_TESTS_REQUIRED') == '1':
                raise
            raise unittest.SkipTest('Optional native postprocessor runtime/source unavailable: ' + str(error))

    def graph(self):
        terms = ('GO:1000000', 'GO:1000001', 'GO:1000002', 'GO:1000003')
        graph = SimpleNamespace(idxs=4, order=[3, 2, 1, 0], terms_list=[
            {'id': terms[0], 'adj': [], 'children': [1, 2]},
            {'id': terms[1], 'adj': [0], 'children': [3]},
            {'id': terms[2], 'adj': [0], 'children': [3]},
            {'id': terms[3], 'adj': [1, 2], 'children': []},
        ])
        return terms, graph

    def test_executed_notebook_recipe_not_cli_default_is_fixed(self):
        self.assertEqual(SOFT_RATE, .7)
        self.assertEqual(MAX_MIN_RATE, .5)
        self.assertFalse(self.receipt['annotation_or_reference_files_read'])
        self.assertFalse(self.receipt['guarantees_strict_parent_ge_child'])
        self.assertEqual(set(self.receipt['kernel_body_sha256']), {'propagate_min_kernel', 'propagate_max_kernel'})

    def test_exact_source_traversals_match_invented_hand_calculation(self):
        np = self.np
        terms, graph = self.graph()
        raw = np.asarray([[.1, .4, .7, .9], [.8, .6, .3, .2]], dtype=np.float32)
        original = raw.copy()
        high, low = raw.copy(), raw.copy()
        self.native['propagate_max'](high, graph)
        self.native['propagate_min'](low, graph)
        np.testing.assert_allclose(high, [[.9, .9, .9, .9], [.8, .6, .3, .2]], rtol=0, atol=1e-7)
        np.testing.assert_allclose(low, [[.1, .1, .1, .1], [.8, .6, .3, .2]], rtol=0, atol=1e-7)
        observed, _ = published_soft_closure(self.root, graph, terms, raw)
        expected = (.7 * high + .3 * original) * .5 + (.7 * low + .3 * original) * .5
        np.testing.assert_array_equal(observed, expected)
        np.testing.assert_array_equal(raw, original)

    def test_soft_combination_is_not_strict_hierarchy_enforcement_or_sequential_closure(self):
        np = self.np
        terms, graph = self.graph()
        raw = np.asarray([[.1, .1, .1, .9]], dtype=np.float32)
        result, _ = published_soft_closure(self.root, graph, terms, raw)
        self.assertAlmostEqual(float(result[0, 0]), .38, places=6)
        self.assertAlmostEqual(float(result[0, 3]), .62, places=6)
        self.assertLess(result[0, 0], result[0, 3])
        high_then_low = raw.copy()
        self.native['propagate_max'](high_then_low, graph)
        self.native['propagate_min'](high_then_low, graph)
        self.assertFalse(np.array_equal(result, high_then_low))

    def test_zeros_ones_and_already_coherent_scores_are_retained(self):
        np = self.np
        terms, graph = self.graph()
        for raw in (np.zeros((2, 4), dtype=np.float32), np.ones((2, 4), dtype=np.float32),
                    np.asarray([[1, .8, .6, .3]], dtype=np.float32)):
            result, _ = published_soft_closure(self.root, graph, terms, raw)
            np.testing.assert_allclose(result, raw, rtol=0, atol=1e-7)

    def test_no_silent_score_dtype_or_axis_repair(self):
        np = self.np
        terms, graph = self.graph()
        raw = np.ones((2, 4), dtype=np.float32) * .3
        with self.assertRaisesRegex(ValueError, 'literal model GO axis'):
            published_soft_closure(self.root, graph, tuple(reversed(terms)), raw)
        with self.assertRaisesRegex(ValueError, 'float32'):
            published_soft_closure(self.root, graph, terms, raw.astype(np.float64))
        with self.assertRaisesRegex(ValueError, 'float32'):
            published_soft_closure(self.root, graph, terms, raw * np.inf)

    def test_set_backed_native_graph_containers_preserve_identical_edges_and_output(self):
        np = self.np
        terms, graph = self.graph()
        sets = SimpleNamespace(idxs=graph.idxs, order=graph.order, terms_list=[
            {**node, 'adj': set(node['adj']), 'children': set(node['children'])}
            for node in graph.terms_list])
        raw = np.asarray([[.1, .4, .7, .9]], dtype=np.float32)
        a, _ = published_soft_closure(self.root, graph, terms, raw)
        b, _ = published_soft_closure(self.root, sets, terms, raw)
        np.testing.assert_array_equal(a, b)
        self.assertTrue(all(isinstance(node['children'], set) for node in sets.terms_list))


if __name__ == '__main__':
    unittest.main()
