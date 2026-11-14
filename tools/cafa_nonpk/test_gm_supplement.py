"""Invented matrix controls verify native-score preservation and convergence."""
import importlib.util
from types import SimpleNamespace
import unittest

from tools.cafa_nonpk import gm_supplement as module


@unittest.skipUnless(importlib.util.find_spec('numpy') and importlib.util.find_spec('scipy'),
                     'optional numerical runtime unavailable')
class NativeNumericalCertificateTests(unittest.TestCase):
    def fixture(self, scores):
        import numpy as np
        from scipy.sparse import eye, csr_matrix
        W=eye(2,format='csr');L=csr_matrix((2,2),dtype=float)
        M,certificate=module.numerical_certificate(W,L)
        values=np.asarray(scores,dtype=float);calls=[]
        def native(l,y,**parameters):
            calls.append((l,y.copy(),parameters));return values,.1,.2,1
        return {'gm':SimpleNamespace(runGeneMANIA=native)},L,M,certificate,values,calls

    def test_small_cg_undershoot_within_residual_is_retained_byte_for_byte(self):
        import numpy as np
        modules,L,M,certificate,values,calls=self.fixture([1.,-1e-7]);before=values.tobytes()
        scores,diagnostic=module.author_scores(modules,L,M,certificate,[0])
        self.assertIs(scores,values);self.assertEqual(scores.tobytes(),before)
        self.assertEqual(calls[0][2],{'alpha':1,'tol':1e-5})
        self.assertTrue(np.array_equal(calls[0][1],[1.,0.]))
        self.assertEqual(diagnostic['negative_graph_scores'],1)
        self.assertGreaterEqual(diagnostic['componentwise_error_bound'],1e-7)

    def test_nonconverged_and_nonfinite_outputs_fail_without_clipping(self):
        for scores in ([1.,-.01],[1.,float('nan')],[1.,float('inf')]):
            with self.subTest(scores=scores):
                modules,L,M,c,values,_=self.fixture(scores)
                with self.assertRaises(ValueError):module.author_scores(modules,L,M,c,[0])

    def test_matrix_must_support_the_published_diagonal_dominance_bound(self):
        from scipy.sparse import eye,csr_matrix
        for L in (csr_matrix([[0.,.1],[.1,0.]]),csr_matrix([[-2.,0.],[0.,0.]]),
                  csr_matrix([[0.,-.1],[-.2,0.]])):
            with self.subTest(L=L),self.assertRaises(ValueError):
                module.numerical_certificate(eye(2,format='csr'),L)

    def test_seed_definition_is_not_silently_changed(self):
        modules,L,M,c,_,_=self.fixture([1.,0.])
        for seeds in ([],[0,0],[-1],[2]):
            with self.subTest(seeds=seeds),self.assertRaises(ValueError):
                module.author_scores(modules,L,M,c,seeds)


if __name__=='__main__':unittest.main()
