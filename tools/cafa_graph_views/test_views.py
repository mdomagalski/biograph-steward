from copy import deepcopy
import unittest

from .run import MEMBERSHIP_HEADER, VIEWS, subset_graphs


class MaskReplayTests(unittest.TestCase):
    def fixture(self):
        graph = {'nodes': ['A', 'B', 'C', 'D'], 'pairs': [['A','B',.9],['B','C',.3],['A','C',.2]]}
        weights = [dict(pair_id=str(i), subject=a, object=b, weight=str(w))
                   for i, (a,b,w) in enumerate(graph['pairs'])]
        membership = [dict.fromkeys(MEMBERSHIP_HEADER, 'true') for _ in weights]
        for i, row in enumerate(membership): row['pair_id'] = str(i)
        for view, i in zip(VIEWS, range(3)): membership[i][view] = 'false'
        return graph, weights, membership

    def test_same_nodes_and_exact_weights_survive_different_fixed_masks(self):
        graph, weights, membership = self.fixture(); before = deepcopy((graph, weights, membership))
        result = subset_graphs(graph, weights, membership, expected_source_rows=3)
        for value in result.values():
            self.assertEqual(value['nodes'], ['A','B','C','D'])
            self.assertEqual(len(value['pairs']), 2)
            self.assertTrue(all(row in graph['pairs'] for row in value['pairs']))
        self.assertEqual(result['native_top80']['pairs'], [['B','C',.3],['A','C',.2]])
        self.assertEqual((graph, weights, membership), before)

    def test_partial_duplicate_or_invalid_memberships_fail(self):
        graph, weights, membership = self.fixture()
        for changed in (membership[:-1], [membership[0], membership[0], membership[2]]):
            with self.assertRaises(ValueError): subset_graphs(graph, weights, changed, expected_source_rows=3)
        membership[0]['native_top80'] = 'TRUE'
        with self.assertRaises(ValueError): subset_graphs(graph, weights, membership, expected_source_rows=3)

    def test_source_weight_changes_and_unequal_budgets_fail(self):
        graph, weights, membership = self.fixture(); weights[0]['weight'] = '.95'
        with self.assertRaises(ValueError): subset_graphs(graph, weights, membership, expected_source_rows=3)
        graph, weights, membership = self.fixture(); membership[1]['native_top80'] = 'false'
        with self.assertRaises(ValueError): subset_graphs(graph, weights, membership, expected_source_rows=3)


if __name__ == '__main__': unittest.main()
