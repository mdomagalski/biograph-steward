"""Invented scores only; no model, ontology or reference cases loaded."""
import math
import struct
import unittest
from .scores import ENSEMBLES, raw_rows, native_rows, average_author_models


class ScoreTests(unittest.TestCase):
    def test_machine_export_keeps_values_hidden_by_native_presentation(self):
        # Binary32 round trip must retain values below the native cutoff and
        # near the CAFA grid, rather than receiving rounded CLI values.
        values = [struct.unpack('f', struct.pack('f', x))[0] for x in (0.0, .0009999, .1001234, 1.0)]
        rows = list(raw_rows(['P1'], ['GO:0000001', 'GO:0000002', 'GO:0000003', 'GO:0000004'], [values]))
        self.assertEqual([float(x.split('\t')[2]) for x in rows], values)
        shown = list(native_rows(['P1'], ['GO:0000001', 'GO:0000002', 'GO:0000003', 'GO:0000004'], [values]))
        self.assertEqual(shown, ['P1\tGO:0000003\t0.100\n', 'P1\tGO:0000004\t1.000\n'])

    def test_invalid_ids_dimensions_or_values_are_not_repaired(self):
        for args in [(['P1', 'P1'], ['GO:0000001'], [[.1], [.1]]),
                     (['P1'], ['GO:0000001'], []),
                     (['P1'], ['GO:0000001'], [[.1, .2]]),
                     (['P1'], ['invented:foreign'], [[.1]]),
                     (['P1 extra'], ['GO:0000001'], [[.1]])]:
            with self.subTest(args=args), self.assertRaises(ValueError): list(raw_rows(*args))
        for value in (math.nan, math.inf, -.0001, 1.00001):
            with self.subTest(value=value), self.assertRaises(ValueError):
                list(raw_rows(['P1'], ['GO:0000001'], [[value]]))

    def test_fixed_ensemble_matches_literal_author_float32_operation(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest('Optional numerical runtime not installed.')
        matrices = {i: np.array([[.01 * i, .03], [.97, .11]], dtype=np.float32) for i in ENSEMBLES['bp']}
        expected = np.zeros((2, 2), dtype=np.float32)
        for matrix in matrices.values(): expected += matrix
        expected = expected / 6
        actual = average_author_models('bp', matrices)
        self.assertEqual(actual.dtype, np.float32)
        self.assertTrue(np.array_equal(actual, expected))
        with self.assertRaisesRegex(ValueError, 'order'):
            average_author_models('bp', dict(reversed(list(matrices.items()))))
        matrices[ENSEMBLES['bp'][0]] = matrices[ENSEMBLES['bp'][0]].astype(np.float64)
        with self.assertRaisesRegex(ValueError, 'float32'):
            average_author_models('bp', matrices)


if __name__ == '__main__': unittest.main()
