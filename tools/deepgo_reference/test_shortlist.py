"""Invented ranking/reachability/paired-uncertainty tests, without reference rows."""
import unittest
from .shortlist import select_top3, ancestor_pairs, paired_interval


class FixedBudget(unittest.TestCase):
    def test_strict_three_sorted_canonical_ties_and_source_masks(self):
        import numpy as np
        scores = np.asarray([1., .5, .5, .5, .5, 0.])
        names = ['ROOT', 'GO:4', 'GO:2', 'GO:3', 'GO:1', 'GO:5']
        # Highest root/known score is absent from allowed; four tied candidates
        # yield exactlythree ordered by canonical ID, independent of file order.
        chosen = select_top3(scores, [1,2,3,4,5], names)
        self.assertEqual(chosen.tolist(), [4,2,3])
        self.assertEqual(select_top3(scores, [5], names).tolist(), [])
        with self.assertRaises(ValueError): select_top3([float('nan')], [0], ['GO:1'])

    def test_ancestry_is_descriptive_and_never_changes_selected_budget(self):
        import numpy as np
        from scipy.sparse import csr_matrix
        # Native direction is child→parent. Node2 descendsfrom1;3isunrelated.
        graph = csr_matrix(np.asarray([[0,0,0,0],[1,0,0,0],[0,1,0,0],[1,0,0,0]]))
        chosen = np.asarray([2,1,3]); before=chosen.copy(); cache={}
        self.assertEqual(ancestor_pairs(chosen, graph, cache), 1)
        self.assertTrue(np.array_equal(chosen, before))
        self.assertEqual(ancestor_pairs(np.asarray([1,3]), graph, cache), 0)

    def test_paired_scipy_uses_same_samples_and_retains_zero_or_negative_results(self):
        import numpy as np
        a=np.asarray([0.,1/3,2/3,1.])
        identical, draws = paired_interval(a,a.copy())
        self.assertEqual(identical['point_difference'],0.)
        self.assertEqual(identical['paired_95_percentile_interval'],[0.,0.])
        self.assertTrue(np.array_equal(draws,np.zeros(2000)))
        negative, first = paired_interval(np.zeros(4),np.repeat(1/3,4))
        self.assertAlmostEqual(negative['point_difference'],-1/3)
        self.assertTrue(all(abs(x+1/3)<1e-15 for x in negative['paired_95_percentile_interval']))
        _, replay = paired_interval(np.zeros(4),np.repeat(1/3,4))
        self.assertTrue(np.array_equal(first,replay))


if __name__ == '__main__': unittest.main()
