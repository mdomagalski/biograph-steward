import unittest
from .reserved_context import target_frame


class ReservedFrameTests(unittest.TestCase):
    def test_disjoint_exact_source_subset(self):
        self.assertEqual(target_frame(['B','C'],['A'],['A','B','C']),['B','C'])

    def test_overlap_and_alias_rescue_rejected(self):
        with self.assertRaisesRegex(ValueError,'overlap'):
            target_frame(['A'],['A'],['A','B'])
        with self.assertRaisesRegex(ValueError,'outside'):
            target_frame(['alias'],['A'],['A','B'])

    def test_order_or_duplicate_changes_rejected(self):
        for values in (['C','B'],['B','B'],[]):
            with self.assertRaises(ValueError): target_frame(values,['A'],['A','B','C'])


if __name__=='__main__': unittest.main()
