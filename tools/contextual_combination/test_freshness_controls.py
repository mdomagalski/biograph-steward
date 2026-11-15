"""Invented union/scope cases and the unchanged published LocalPlus function."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .freshness_controls import union_training,by_head,load_config


class SeedUnionTests(unittest.TestCase):
    def test_add_only_fit_union_retains_all_global_sources_and_new_heads(self):
        original={'FIT':[['BPO','GO:2000001']],
                  'VAL':[['BPO','GO:2000001']],
                  'FINAL':[['CCO','GO:3000001']],
                  'OTHER':[['MFO','GO:1000001']]}
        before=copy.deepcopy(original)
        additions={'FIT':{('BPO','GO:2000002'),('BPO','GO:2000001'),('MFO','GO:1000002')}}
        updated,added=union_training(original,additions,{'FIT'})
        self.assertEqual(added['FIT'],{('BPO','GO:2000002'),('MFO','GO:1000002')})
        for p in ('VAL','FINAL','OTHER'):self.assertEqual(updated[p],sorted(map(tuple,original[p])))
        for p,rows in original.items():self.assertTrue(set(map(tuple,rows))<=set(updated[p]))
        self.assertEqual(original,before)
        self.assertIn(('BPO','GO:2000002'),set(x for rows in updated.values() for x in rows))

    def test_validation_or_final_addition_is_rejected(self):
        original={'FIT':[],'VAL':[],'FINAL':[]}
        for outside in ('VAL','FINAL'):
            with self.assertRaisesRegex(ValueError,'fitting-only'):
                union_training(original,{'FIT':[],outside:[('BPO','GO:2000001')]},{'FIT'})

    def test_empty_additions_preserve_original_semantic_seed_sets(self):
        original={'FIT':[['BPO','GO:2000001']],'OTHER':[['CCO','GO:3000001']]}
        updated,added=union_training(original,{'FIT':[]},{'FIT'})
        self.assertFalse(added['FIT'])
        self.assertEqual({p:set(map(tuple,r)) for p,r in original.items()},
                         {p:set(r) for p,r in updated.items()})

    def test_no_new_reference_file_may_enter_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            p=Path(temporary)/'inputs.json';p.write_text(json.dumps({
                'format':'biograph-steward.training-freshness-controls.v1',
                'fresh_final_reference_opened':False,'input_pins':{
                 '/data/reference_apr_nov_2026_v1/native_reference_v1/sealed_reference/groundtruth_PK.tsv':'not-read'}}))
            with patch('tools.contextual_combination.freshness_controls.file_sha256',side_effect=AssertionError('no fresh-reference hash')) as hashed:
                with self.assertRaisesRegex(ValueError,'held-out'):load_config(p)
                hashed.assert_not_called()


class PublishedLocalPlusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            from tools.cafa_prediction import core
            cls.np,cls.core=np,core
            author=os.environ.get('BIOGRAPH_LOCALPLUS_AUTHOR_ROOT',str(Path(__file__).resolve().parents[2]/'runs/prediction_next_20261113/author_methods'))
            receipt=os.environ.get('BIOGRAPH_LOCALPLUS_AUTHOR_RECEIPT',str(Path(author).with_name('author_methods_receipt.json')))
            cls.modules=core.author_modules(author,receipt)
        except (ImportError,FileNotFoundError,ValueError) as error:
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED')=='1':raise
            raise unittest.SkipTest(str(error))

    def setUp(self):
        self.index={'FIT':0,'VAL':1,'FINAL':2}
        self.P=self.modules['alg_utils'].normalizeGraphEdgeWeights(
            self.core.adjacency(['FIT','VAL','FINAL'],[('FIT','VAL',.5),('VAL','FINAL',1.)]))

    def test_empty_fit_additions_replay_published_scores_bit_for_bit(self):
        original={'FIT':[['BPO','GO:2000001']],'VAL':[],'FINAL':[]}
        updated,_=union_training(original,{'FIT':[]},{'FIT'})
        before=by_head(original,self.index);after=by_head(updated,self.index)
        left,_=self.core.run_term(self.modules,self.P,None,before[('BPO','GO:2000001')],'localplus')
        right,_=self.core.run_term(self.modules,self.P,None,after[('BPO','GO:2000001')],'localplus')
        self.assertEqual(left.dtype,self.np.float64);self.assertEqual(left.tobytes(),right.tobytes())

    def test_published_nonnegative_neighbor_score_is_monotone_for_add_only_seeds(self):
        # Here FIT is the sole allowed new-label protein; VAL/FINAL are never
        # assigned new training labels. Existing source labels remain legal.
        original={'FIT':[],'VAL':[],'FINAL':[['BPO','GO:2000001']]}
        updated,_=union_training(original,{'FIT':[('BPO','GO:2000001'),('BPO','GO:2000002')]},{'FIT'})
        before=by_head(original,self.index);after=by_head(updated,self.index)
        old,_=self.core.run_term(self.modules,self.P,None,before[('BPO','GO:2000001')],'localplus')
        new,_=self.core.run_term(self.modules,self.P,None,after[('BPO','GO:2000001')],'localplus')
        direct=self.modules['fss'].runLocal(self.P,sorted(after[('BPO','GO:2000001')]))[0]
        self.np.testing.assert_array_equal(new,direct)
        self.assertTrue((new>=old).all());self.assertTrue((new>old).any())
        self.assertIn(('BPO','GO:2000002'),after)


if __name__=='__main__':unittest.main()
