"""A discovered floating-grid mismatch must never pass paired resampling."""
import unittest
try:
    import numpy as np
except ImportError:
    np=None
from tools.cafa_reference.paired_bootstrap import resample


@unittest.skipIf(np is None,'optional numpy unavailable')
class ThresholdByteTests(unittest.TestCase):
    def test_even_one_ULP_threshold_difference_is_rejected(self):
        values=np.zeros((2,2,6));values[:,:,1]=1
        first={'ids':np.array(['P04637','Q13315']),'tau':np.array([.03,.5]),
               'ordinary':values,'IA_weighted':values.copy()}
        other={k:v.copy() for k,v in first.items()}
        other['tau'][0]=np.nextafter(other['tau'][0],np.inf)
        self.assertNotEqual(first['tau'][0].hex(),other['tau'][0].hex())
        with self.assertRaises(ValueError):resample({'a':first,'b':other},draws=2,seed=7)


if __name__=='__main__':unittest.main()
