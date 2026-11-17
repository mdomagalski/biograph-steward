"""Invented label-free ranking and containment/cost checks; no reference rows."""
from types import SimpleNamespace
import unittest

from .baseline_aware import (after_top3, before_top3, matrix_sha, opportunity,
                             selection_guards, utility)
from .overlap import selections


def ontology():
    import numpy as np
    # Native indices deliberately differ from canonical-ID order for ties.
    names = ['GO:0000000','GO:1000005','GO:1000002','GO:1000001','GO:1000004','GO:1000003']
    return SimpleNamespace(terms_dict={name:{'index':i} for i,name in enumerate(names)},
        toi=np.arange(1,6), ia=np.arange(1,7,dtype=float))


def counts(supported, unmatched, returned, eligible=None):
    import numpy as np
    n = len(supported); values = np.zeros((n,6))
    values[:,1] = supported; values[:,2] = unmatched
    mask = np.ones(n,dtype=bool) if eligible is None else np.asarray(eligible,dtype=bool)
    return {'ordinary':values, 'IA_weighted':values.copy(), 'eligible':mask,
        'eligible_IA_weighted':mask.copy(), 'returned':np.asarray(returned,dtype=int)}


class BaselineAware(unittest.TestCase):
    def test_ranking_uses_only_fixed_scores_baseline_and_original_known(self):
        import numpy as np
        ont = ontology()
        forecast = SimpleNamespace(matrix=np.asarray([[0,.8,.8,.8,.7,0],[0,.9,.8,.7,.6,.5]]))
        truth_a = SimpleNamespace(matrix=np.asarray([[0,1,0,0,0,0],[0,0,1,0,0,0]],dtype=bool))
        truth_b = SimpleNamespace(matrix=np.logical_not(truth_a.matrix))
        known = SimpleNamespace(matrix=np.zeros((2,6),dtype=bool)); known.matrix[0,2] = True
        baseline = SimpleNamespace(matrix=np.zeros((2,6))); baseline.matrix[:,3] = 1
        hashes = [matrix_sha(x.matrix) for x in (forecast,truth_a,truth_b,known,baseline)]
        left = before_top3(forecast,truth_a,known,ont,baseline)
        right = before_top3(forecast,truth_b,known,ont,baseline)
        self.assertEqual(left,right)
        self.assertEqual(left,[[1,4],[1,2,4]])
        self.assertEqual(hashes,[matrix_sha(x.matrix) for x in (forecast,truth_a,truth_b,known,baseline)])
        # Original helper still gives the exact same positive/canonical tie rule.
        self.assertEqual(selections(forecast,truth_a,None,ont)[0],[3,2,1])

    def test_old_baseline_absent_predictions_survive_and_holes_replenish(self):
        import numpy as np
        ont = ontology(); gt=SimpleNamespace(matrix=np.zeros((2,6),dtype=bool))
        forecast=SimpleNamespace(matrix=np.asarray([[0,.9,.8,.7,.6,.5]]*2))
        baseline=SimpleNamespace(matrix=np.asarray([[0,1,0,1,0,0],[0,1,1,1,1,0]]))
        original=selections(forecast,gt,None,ont)
        post=after_top3(original,baseline); aware=before_top3(forecast,gt,None,ont,baseline)
        self.assertEqual(post,[[2],[]]);self.assertEqual(aware,[[2,4,5],[5]])
        guards=selection_guards(original,post,aware,baseline)
        self.assertTrue(guards['all_previous_baseline_absent_predictions_retained'])
        self.assertFalse(guards['ranking_uses_future_reference_values'])
        with self.assertRaises(ValueError): selection_guards(original,post,[[4,5],[5]],baseline)
        with self.assertRaises(ValueError): selection_guards(original,post,[[1,2,4],[5]],baseline)
        with self.assertRaises(ValueError): selection_guards(original,[[4],[]],aware,baseline)
        with self.assertRaises(ValueError): selection_guards(original,post,[[2,2],[5]],baseline)

    def test_support_non_decrease_can_add_mostly_unmatched_cost(self):
        old=counts([1,0],[0,0],[1,0]);new=counts([1,1],[2,2],[3,3])
        value=utility([[1],[]],[[1,2,3],[2,3,4]],old,new)
        self.assertEqual(value['replenished_slots'],5)
        self.assertEqual(value['added_curator_supported_pairs'],1)
        self.assertEqual(value['added_reference_unmatched_pairs'],4)
        self.assertEqual(value['marginal_added_curator_support_fraction'],.2)
        self.assertEqual(value['old_supported_slots_per_original_fixed3_budget'],1/6)
        self.assertEqual(value['new_supported_slots_per_original_fixed3_budget'],2/6)
        self.assertFalse(value['own_variant_uncertainty_or_model_superiority_claimed'])
        # PPV falls from 1.0 to 2/6 despite higher fixed-budget supported yield.
        unchanged=utility([[1],[]],[[1],[]],old,old)
        self.assertIsNone(unchanged['marginal_added_curator_support_fraction'])
        with self.assertRaises(ValueError): utility([[1],[]],[[1],[]],old,counts([0,0],[1,0],[1,0]))

    def test_zero_residual_cases_remain_in_original_denominator_and_oracle(self):
        import numpy as np
        ont=ontology(); gt=SimpleNamespace(matrix=np.asarray(
            [[0,1,1,1,1,0],[0,1,0,0,0,0],[0,0,0,0,0,1]],dtype=bool))
        baseline=SimpleNamespace(matrix=np.asarray(
            [[0,0,0,0,0,0],[0,1,0,0,0,0],[0,0,0,0,0,0]],dtype=float))
        known=SimpleNamespace(matrix=np.zeros((3,6),dtype=bool)); known.matrix[0,1]=True
        value=opportunity(gt,known,ont,baseline,np.ones(3,dtype=bool))
        self.assertEqual(value['original_eligible_proteins'],3)
        self.assertEqual(value['future_reference_pairs_absent_from_baseline'],4)
        self.assertEqual(value['original_proteins_with_residual_reference_support'],2)
        self.assertEqual(value['zero_residual_reference_proteins_retained'],1)
        self.assertEqual(value['oracle_supported_cap3'],4)
        self.assertEqual(value['oracle_supported_slots_per_original_fixed3_budget'],4/9)
        self.assertTrue(value['oracle_is_reference_aware_not_deployable'])
        # The known mask is the ORIGINAL one, not the expanded ranking mask.
        self.assertTrue(gt.matrix[1,1]);self.assertEqual(value['residual_reference_IA'],18.)

    def test_native_membership_shapes_cannot_silently_change(self):
        import numpy as np
        with self.assertRaises(ValueError): before_top3(
            SimpleNamespace(matrix=np.ones((2,6))),SimpleNamespace(matrix=np.ones((2,6))),
            None,ontology(),SimpleNamespace(matrix=np.zeros((1,6))))
        with self.assertRaises(ValueError): before_top3(
            SimpleNamespace(matrix=np.ones((2,6))),SimpleNamespace(matrix=np.ones((2,6))),
            SimpleNamespace(matrix=np.ones((1,6))),ontology(),SimpleNamespace(matrix=np.zeros((2,6))))


if __name__ == '__main__': unittest.main()
