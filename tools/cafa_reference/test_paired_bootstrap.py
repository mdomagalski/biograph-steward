"""Mathematical paired-resampling controls; no real annotation labels."""
import unittest
try:
    import numpy as np
except ImportError:
    np=None
from tools.cafa_reference.paired_bootstrap import resample


@unittest.skipIf(np is None,'optional numpy unavailable')
class PairedTests(unittest.TestCase):
    def array(self, perfect=True):
        values=np.zeros((3,2,6))
        if perfect:values[:,:,1]=1
        else:values[:,:,3]=1
        return {'ids':np.array(['P04637','Q13315','P00533']),'tau':np.array([.001,.002]),
                'ordinary':values,'IA_weighted':values.copy()}

    def test_identical_methods_have_exact_zero_paired_difference(self):
        w,r=resample({'a':self.array(),'b':self.array()},draws=25,seed=7)
        self.assertTrue(np.all(w.sum(axis=1)==3))
        self.assertTrue(np.array_equal(r['a']['ordinary'],r['b']['ordinary']))

    def test_known_perfect_vs_abstaining_prediction_is_one_for_every_draw(self):
        _,r=resample({'a':self.array(),'b':self.array(False)},draws=25,seed=7)
        self.assertTrue(np.all(r['a']['ordinary']-r['b']['ordinary']==1))

    def test_same_seed_reproduces_draws_and_different_order_is_rejected(self):
        w,_=resample({'a':self.array()},draws=25,seed=7)
        w2,_=resample({'a':self.array()},draws=25,seed=7)
        self.assertTrue(np.array_equal(w,w2))
        different=self.array();different['ids']=different['ids'][::-1]
        with self.assertRaises(ValueError):resample({'a':self.array(),'b':different},draws=25,seed=7)


if __name__=='__main__':unittest.main()
