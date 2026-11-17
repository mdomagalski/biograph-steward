"""Synthetic checks for the complete native curve/threshold gate."""
import unittest
try:
    import numpy as np
    import pandas as pd
except ImportError:
    np=pd=None
from tools.cafa_nonpk.counts import compare_curves


@unittest.skipIf(pd is None,'optional pinned NumPy/Pandas research runtime required')
class CompleteCurveTests(unittest.TestCase):
    def frames(self):
        a=pd.DataFrame({'ns':['biological_process']*2,'tau':np.asarray([.001,.002]),
            'f_micro':[.1,.2],'f_micro_w':[.2,.3],'cov':[1.,1.],'fp':[4.,3.]})
        b=a.copy();b['filename']='invented.tsv';return a,b

    def test_identical_numeric_native_curves_pass_all_columns(self):
        a,b=self.frames();v=compare_curves(a,b)
        self.assertEqual(v['max_absolute_curve_difference'],0.)
        self.assertEqual(v['numeric_columns'],5)

    def test_grid_ulp_column_count_duplicates_and_nonfinite_fail(self):
        for kind in ('value','ulp','column','rows','duplicate','nonfinite'):
            a,b=self.frames()
            if kind=='value':b.loc[0,'f_micro']+=1e-4
            if kind=='ulp':b.loc[0,'tau']=np.nextafter(b.loc[0,'tau'],1.)
            if kind=='column':b=b.drop(columns='fp')
            if kind=='rows':b=b.iloc[:1]
            if kind=='duplicate':b.loc[1,'tau']=b.loc[0,'tau']
            if kind=='nonfinite':b.loc[0,'f_micro']=float('nan')
            with self.subTest(kind=kind),self.assertRaises(ValueError):compare_curves(a,b)

    def test_raw_column_difference_is_explicit_but_does_not_redefine_micro_endpoint(self):
        a,b=self.frames();b.loc[0,'fp']+=1e-4
        v=compare_curves(a,b)
        self.assertEqual(v['max_absolute_curve_difference'],0.)
        self.assertGreater(v['complete_raw_numeric_max_absolute_difference'],1e-12)
        self.assertFalse(v['complete_raw_numeric_columns_within_1e_12'])
        self.assertEqual(v['column_max_absolute_difference']['f_micro_w'],0.)


if __name__=='__main__':unittest.main()
