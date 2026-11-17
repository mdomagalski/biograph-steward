import io
import math
import unittest

from .intake import naive_predictions, selected_rows


class BaselineFilteringTests(unittest.TestCase):
    def test_exact_first_column_and_native_score_bytes_preserved(self):
        rows = [b'A1\tGO:0000001\t0.123400\n', b'A10\tGO:0000001\t0.8\n',
                b'A1\tGO:0000002\t0\n', b'B2\tGO:0000003\t1\n']
        out = io.BytesIO(); result = selected_rows(rows, {'A1','B2','C3'}, out)
        self.assertEqual(out.getvalue(), rows[0] + rows[2] + rows[3])
        self.assertEqual(result['selected_rows'], 3)
        self.assertEqual(result['targets_unrepresented'], ['C3'])

    def test_incompatible_scale_nan_or_invalid_GO_never_rescaled(self):
        for raw in (b'A1\tGO:0000001\t99\n', b'A1\tGO:0000001\tnan\n', b'A1\tbad\t.5\n'):
            with self.assertRaises(ValueError): selected_rows([raw], {'A1'}, io.BytesIO())

    def test_official_naive_cartesian_product_with_zero_preserved(self):
        out = io.BytesIO()
        result = naive_predictions(b'GO:0000001\t0.123400\nGO:0000002\t0\n', {'B2','A1'}, out)
        self.assertEqual(out.getvalue(), b'A1\tGO:0000001\t0.123400\nA1\tGO:0000002\t0\nB2\tGO:0000001\t0.123400\nB2\tGO:0000002\t0\n')
        self.assertEqual(result['selected_rows'], 4)
        with self.assertRaises(ValueError): naive_predictions(b'GO:0000001\t.2\nGO:0000001\t.2\n', {'A1'}, io.BytesIO())


if __name__ == '__main__': unittest.main()
