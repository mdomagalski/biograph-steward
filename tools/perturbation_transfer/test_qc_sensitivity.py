"""Check the native nonfinite-column operation without experimental outcomes."""
import unittest

from tools.perturbation_transfer.qc_sensitivity import finite_columns


class NativeColumnPolicyTests(unittest.TestCase):
    def test_blocked_reader_matches_published_pandas_operation(self):
        import numpy as np
        import pandas as pd
        x = np.array([[1., 2., 3., 4., 0.], [2., np.inf, 3., 4., 0.],
                      [3., 2., np.nan, 4., 0.], [4., 2., 3., -np.inf, 0.]])
        expected = pd.DataFrame(x).replace({np.inf: np.nan, -np.inf: np.nan}).dropna(axis=1)
        mask = finite_columns(x, block_size=2)
        np.testing.assert_array_equal(np.flatnonzero(mask), expected.columns)
        np.testing.assert_array_equal(x[:, mask], expected.to_numpy())
        self.assertTrue(mask[-1], 'Finite constant features are not fabricated as missing values.')


if __name__ == '__main__':
    unittest.main()
