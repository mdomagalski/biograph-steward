"""Saved native summaries keep mixed endpoints and missing coverage explicit."""
import unittest
from .collect import saved_point


class SavedPointTests(unittest.TestCase):
    def test_each_native_endpoint_and_fixed_coverage_are_preserved(self):
        first={'tau':'.1','f_micro':'.3','f_micro_w':'.2','f':'.5','f_w':'.4','s':'3','s_w':'2','cov':'.8'}
        second={'tau':'.2','f_micro':'.4','f_micro_w':'.1','f':'.2','f_w':'.1','s':'4','s_w':'1','cov':'.9'}
        fixed={'namespace':'biological_process','status':'no_native_coverage'}
        value=saved_point([first,second],[fixed],'biological_process')
        self.assertEqual((value['micro_Fmax'],value['micro_Fmax_tau']),(.4,.2))
        self.assertEqual((value['IA_micro_Fmax'],value['IA_micro_Fmax_tau']),(.2,.1))
        self.assertEqual((value['macro_Fmax'],value['IA_weighted_Smin']),(.5,1))
        self.assertEqual(value['fixed_0_5'],fixed)
        self.assertNotIn('precision',value['fixed_0_5'])

    def test_no_curve_is_not_an_invented_zero_endpoint(self):
        value=saved_point([],[],'cellular_component')
        self.assertEqual(value['status'],'no_native_curve')
        self.assertNotIn('micro_Fmax',value)
        self.assertNotIn('fixed_0_5',value)


if __name__=='__main__':unittest.main()
