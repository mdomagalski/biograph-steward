import unittest

from .query_context import extract_context


class CompleteOneHopTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        import torch
        from scipy.sparse import csr_matrix
        self.nodes=['UniProtKB:'+p for p in ('Q','A','B','C','I')]
        # Outside-cohort A has a strong unrelated edge to C. Its normalization
        # can differ locally, but complete query Q's row must remain exact.
        self.W=csr_matrix((np.asarray([.9,.1,.9,8.,.1,8.]),([0,0,1,1,2,3],[1,2,0,3,0,1])),shape=(5,5))
        coo=self.W.tocoo();self.edge_index=torch.tensor(np.vstack((coo.row,coo.col)),dtype=torch.long)

    def test_complete_query_keeps_full_weighted_denominator(self):
        import numpy as np
        subset,mapping,local=extract_context(self.nodes,self.W,self.edge_index,[self.nodes[0]])
        self.assertEqual(subset.tolist(),[0,1,2]);self.assertEqual(mapping.tolist(),[0])
        fullscore=float(self.W[0,1]/self.W.getrow(0).sum())
        self.assertEqual(float(local[0,1]/local.getrow(0).sum()),fullscore)
        self.assertEqual(fullscore,.9)
        cohort=self.W[[0,2],:][:,[0,2]]
        self.assertEqual(float(cohort[0,1]/cohort.getrow(0).sum()),1.)

    def test_highest_index_isolate_and_requested_order_preserved(self):
        subset,mapping,local=extract_context(self.nodes,self.W,self.edge_index,[self.nodes[4],self.nodes[0]])
        self.assertEqual(subset[mapping].tolist(),[4,0])
        self.assertEqual(local.getrow(mapping[0]).nnz,0)

    def test_unknown_duplicate_and_unbounded_queries_fail(self):
        for queries in ([],[self.nodes[0],self.nodes[0]],['UniProtKB:unknown'],['x'+str(i) for i in range(26)]):
            with self.subTest(queries=queries),self.assertRaises(ValueError):
                extract_context(self.nodes,self.W,self.edge_index,queries)


if __name__=='__main__':unittest.main()
