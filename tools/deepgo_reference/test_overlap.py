"""Invented overlap/rank aggregation checks, without biological reference rows."""
from types import SimpleNamespace
import unittest
from .overlap import rrf3, bucket, diagnose, pk_reproduction


class Complementarity(unittest.TestCase):
    def test_fixed_rrf_exact_ties_deduplicate_and_keep_three(self):
        names = ['GO:4','GO:3','GO:1','GO:2']
        self.assertEqual(rrf3([2,0,1], [1,3,2], names), [2,1,3])
        self.assertEqual(rrf3([0], [0], names), [0])
        self.assertEqual(rrf3([], [], names), [])
        self.assertEqual(rrf3([0,1], [], names), [0,1])
        with self.assertRaises(ValueError): rrf3([0,0], [], names)
        with self.assertRaises(ValueError): rrf3([0,1,2,3], [], names)

    def test_baseline_partition_is_not_an_independence_or_truth_verdict(self):
        result = bucket({1,2,3,4}, {1,3}, {1}, {1,2}, [1]*5)
        self.assertEqual(result['selected_pairs'], 4)
        self.assertEqual(result['curator_supported_pairs'], 2)
        self.assertEqual(result['reference_unmatched_pairs'], 2)
        self.assertEqual(result['literal_released_baseline'], {'selected_pairs':1,'curator_supported_pairs':1})
        self.assertEqual(result['baseline_closure_only'], {'selected_pairs':1,'curator_supported_pairs':0})
        self.assertEqual(result['baseline_absent'], {'selected_pairs':2,'curator_supported_pairs':1})
        with self.assertRaises(ValueError): bucket({1}, {1}, {1}, set(), [1,1])

    def test_oracle_is_capped_and_unique_support_not_recoverable_from_marginals(self):
        import numpy as np
        ontology = SimpleNamespace(terms_dict={f'GO:{i}':{'index':i} for i in range(6)},
            toi=np.arange(1,6), ia=np.ones(6), dag=np.zeros((6,6)))
        ontology.dag[3,4] = 1
        gt = SimpleNamespace(matrix=np.asarray([[0,1,1,0,1,0],[0,0,0,0,0,1]], dtype=bool))
        raw = np.zeros((2,6)); raw[0,2] = 1; closed = raw.copy(); closed[0,0] = 1
        result, novelty = diagnose([[1,2,3],[1]], [[2,4,5],[]], gt, None, ontology,
                                    raw, closed, np.ones(2,dtype=bool))
        self.assertEqual(result['exact_overlap']['intersection_pairs'], 1)
        self.assertEqual(result['exact_overlap']['union_pairs'], 6)
        self.assertEqual(result['exact_overlap']['buckets']['deepgose_only']['curator_supported_pairs'], 1)
        self.assertEqual(result['exact_overlap']['buckets']['strict_alias_localplus_only']['curator_supported_pairs'], 1)
        self.assertEqual(result['oracle']['union_supported_cap3'], 3)
        self.assertEqual(result['oracle']['extra_supported_slots_over_best_parent_per_protein'], 1)
        self.assertEqual(result['oracle']['extra_baseline_absent_supported_slots_over_best_parent_per_protein'], 1)
        self.assertEqual(novelty['rrf3'].tolist(), [2/3,0])
        self.assertEqual(result['ancestor_overlap']['nonidentical_cross_method_related_pairs'],1)
        ontology.dag[2,1] = 1
        same,_ = diagnose([[1,2]],[[1,2]],SimpleNamespace(matrix=np.ones((1,6),dtype=bool)),
            None,ontology,np.zeros((1,6)),np.zeros((1,6)),np.ones(1,dtype=bool))
        self.assertEqual(same['ancestor_overlap']['nonidentical_cross_method_related_pairs'],1)
        self.assertTrue(result['oracle']['ground_truth_aware_ceiling_not_a_deployable_result'])

    def test_reproduction_gate_preserves_failure_instead_of_relaxing_it(self):
        point = {'ordinary':{'TP':3.,'shortlist_is_ancestor_closed':False},
                 'IA_weighted':{'TP':1.2}}
        pk_reproduction(point, point)
        with self.assertRaises(ValueError): pk_reproduction(
            {'ordinary':{'TP':2.,'shortlist_is_ancestor_closed':False},'IA_weighted':{'TP':1.2}}, point)


if __name__ == '__main__': unittest.main()
