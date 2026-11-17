"""Invented scores/objectives only; no biological labels or source files."""
import inspect
import math
from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
except ImportError:
    np = None

from .core import (
    ALPHA_GRID, LOCALPLUS_UPPER_ROUNDOFF, ScoreMatrix, convex_mix,
    mix_then_propagate, select_development_alpha,
)
from .score_io import load_scores, write_scores


PROTEINS = ('synthetic-P1', 'synthetic-P2')
TERMS = ('GO:0000001', 'GO:0000002', 'GO:0000003')


class SelectionTests(unittest.TestCase):
    def objectives(self, value=0.2):
        return {alpha: value for alpha in ALPHA_GRID}

    def test_fixed_grid_contains_exact_endpoints(self):
        self.assertEqual(ALPHA_GRID, (0., .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.))

    def test_selects_native_development_objective_per_aspect(self):
        for aspect, chosen in (('mf', .2), ('bp', .7), ('cc', 1.)):
            values = self.objectives()
            values[chosen] = .8
            result = select_development_alpha(aspect, values, development_id='synthetic-development')
            self.assertEqual((result.aspect, result.alpha, result.development_micro_fmax),
                             (aspect, chosen, .8))
            self.assertEqual(result.to_dict()['split_role'], 'development')
            self.assertEqual(result.to_dict()['alpha_grid'], list(ALPHA_GRID))

    def test_tie_always_chooses_smallest_alpha_even_in_reversed_mapping(self):
        values = self.objectives(0.)
        result = select_development_alpha('mf', dict(reversed(list(values.items()))), development_id='invented')
        self.assertEqual(result.alpha, 0.)
        values[.2] = values[.8] = .9
        result = select_development_alpha('mf', dict(reversed(list(values.items()))), development_id='invented')
        self.assertEqual(result.alpha, .2)

    def test_incomplete_extra_or_invalid_objectives_fail(self):
        cases = []
        values = self.objectives(); del values[.5]; cases.append(values)
        values = self.objectives(); values[.55] = .3; cases.append(values)
        for value in (math.nan, math.inf, -.1, 1.1, True, '.8'):
            values = self.objectives(); values[.5] = value; cases.append(values)
        for values in cases:
            with self.subTest(values=values), self.assertRaises(ValueError):
                select_development_alpha('mf', values, development_id='synthetic')

    def test_final_test_role_and_labels_are_not_fitter_inputs(self):
        with self.assertRaisesRegex(ValueError, 'final-test'):
            select_development_alpha('mf', self.objectives(),
                                     development_id='synthetic', split_role='final_test')
        with self.assertRaises(TypeError):
            select_development_alpha('mf', self.objectives(),
                                     development_id='synthetic', final_test_labels=[1, 0])
        self.assertFalse(any('label' in name or 'test' in name
                             for name in inspect.signature(select_development_alpha).parameters))
        for aspect, identity in (('MF', 'synthetic'), ('mf', ''), ('mf', ' padded ')):
            with self.subTest(aspect=aspect, identity=identity), self.assertRaises(ValueError):
                select_development_alpha(aspect, self.objectives(), development_id=identity)


@unittest.skipIf(np is None, 'Optional NumPy research runtime is not installed.')
class ArrayTests(unittest.TestCase):
    def setUp(self):
        self.left = ScoreMatrix(PROTEINS, TERMS, np.array([[.9, 0, .2], [.1, .5, 1]], dtype=np.float64))
        self.right = ScoreMatrix(PROTEINS, TERMS, np.array([[.2, .6, .1], [.7, 0, .4]], dtype=np.float32))

    def test_exact_endpoint_parity_and_no_parent_mutation(self):
        before_left, before_right = self.left.values.copy(), self.right.values.copy()
        for alpha, source in ((0., self.right), (1., self.left)):
            with self.subTest(alpha=alpha):
                result = convex_mix(self.left, self.right, alpha)
                self.assertTrue(np.array_equal(result.values, source.values))
                self.assertEqual(result.values.tobytes(), source.values.tobytes())
                self.assertFalse(np.shares_memory(result.values, source.values))
        convex_mix(self.left, self.right, .3)
        np.testing.assert_array_equal(self.left.values, before_left)
        np.testing.assert_array_equal(self.right.values, before_right)

    def test_literal_convex_formula_and_arithmetic_zero(self):
        result = convex_mix(self.left, self.right, .3)
        np.testing.assert_array_equal(result.values, .3 * self.left.values + .7 * self.right.values)
        self.assertEqual(result.values[0, 1], .7 * self.right.values[0, 1])
        self.assertEqual(result.values[1, 1], .3 * self.left.values[1, 1])

    def test_exact_axes_no_implicit_reordering_or_alias_collapse(self):
        for proteins, terms, values in (
            (PROTEINS[::-1], TERMS, self.right.values[::-1]),
            (PROTEINS, TERMS[::-1], self.right.values[:, ::-1]),
            (('UniProtKB:synthetic-P1', PROTEINS[1]), TERMS, self.right.values),
        ):
            with self.subTest(proteins=proteins, terms=terms), self.assertRaisesRegex(ValueError, 'axes differ'):
                convex_mix(self.left, ScoreMatrix(proteins, terms, values), .5)

    def test_finite_bounds_and_explicit_unchanged_upper_roundoff(self):
        above_one = 1 + 1e-15
        values = self.left.values.copy(); values[0, 0] = above_one
        with self.assertRaises(ValueError): ScoreMatrix(PROTEINS, TERMS, values)
        qualified = ScoreMatrix(PROTEINS, TERMS, values, LOCALPLUS_UPPER_ROUNDOFF)
        self.assertEqual(qualified.values[0, 0], above_one)
        self.assertEqual(convex_mix(qualified, self.right, 1).values[0, 0], above_one)
        for bad in (math.nan, math.inf, -1e-15, 1 + 2e-10):
            invalid = self.left.values.copy(); invalid[0, 0] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ScoreMatrix(PROTEINS, TERMS, invalid, LOCALPLUS_UPPER_ROUNDOFF)
        for tolerance in (-1., 1., True, math.nan):
            with self.subTest(tolerance=tolerance), self.assertRaises(ValueError):
                ScoreMatrix(PROTEINS, TERMS, values, tolerance)

    def test_invalid_axes_shapes_types_or_alpha_fail(self):
        for proteins, terms, values in (
            ((PROTEINS[0],) * 2, TERMS, self.left.values),
            (PROTEINS, (TERMS[0],) * 3, self.left.values),
            (('invalid protein', PROTEINS[1]), TERMS, self.left.values),
            (PROTEINS, ('GO:1',) + TERMS[1:], self.left.values),
            (PROTEINS, TERMS, [1., 2.]),
            (PROTEINS, TERMS, self.left.values.astype(str)),
            (PROTEINS, TERMS, np.ones((2, 3), dtype=bool)),
        ):
            with self.subTest(proteins=proteins, terms=terms), self.assertRaises(ValueError):
                ScoreMatrix(proteins, terms, values)
        for alpha in (-.1, 1.1, math.nan, math.inf, True, '.5'):
            with self.subTest(alpha=alpha), self.assertRaises(ValueError):
                convex_mix(self.left, self.right, alpha)

    def test_mixture_must_precede_native_ancestor_max_closure(self):
        # Invented three-term DAG: term[0] is ancestor of terms[1:3].
        # Opposite component winners establish noncommutativity, without
        # loading an ontology or implementing a replacement GO propagator.
        left = ScoreMatrix(('synthetic',), TERMS, [[0., 1., 0.]])
        right = ScoreMatrix(('synthetic',), TERMS, [[0., 0., 1.]])
        calls = []

        def synthetic_native_max_closure(values):
            calls.append(values.copy())
            values[:, 0] = values.max(axis=1)
            return values

        correct = mix_then_propagate(left, right, .5, synthetic_native_max_closure)
        self.assertEqual(len(calls), 1)
        np.testing.assert_array_equal(calls[0], [[0., .5, .5]])
        np.testing.assert_array_equal(correct.values, [[.5, .5, .5]])
        left_filled = ScoreMatrix(left.proteins, TERMS, synthetic_native_max_closure(left.values.copy()))
        right_filled = ScoreMatrix(right.proteins, TERMS, synthetic_native_max_closure(right.values.copy()))
        incorrect = convex_mix(left_filled, right_filled, .5)
        self.assertEqual(incorrect.values[0, 0], 1.)
        self.assertNotEqual(correct.values[0, 0], incorrect.values[0, 0])
        np.testing.assert_array_equal(left.values, [[0., 1., 0.]])
        with self.assertRaisesRegex(ValueError, 'shape'):
            mix_then_propagate(left, right, .5, lambda values: values[:, :1])


@unittest.skipIf(np is None, 'Optional NumPy research runtime is not installed.')
class ScoreIOTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='biograph-invented-mixture-')
        self.folder = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_duplicate_max_omissions_and_literal_axis_order(self):
        path = self.folder / 'invented.tsv'
        path.write_text('synthetic-P1\tGO:0000003\t.6\n'
                        'synthetic-P1 GO:0000003 .8\n'
                        'synthetic-P1 GO:0000003 .1\n'
                        'synthetic-P1 GO:0000001 0\n\n')
        scores, diagnostic = load_scores(path, PROTEINS[::-1], TERMS[::-1])
        np.testing.assert_array_equal(scores.values, [[0., 0., 0.], [.8, 0., 0.]])
        self.assertEqual(scores.proteins, PROTEINS[::-1])
        self.assertEqual(scores.terms, TERMS[::-1])
        self.assertEqual(diagnostic['source_rows'], 4)
        self.assertEqual(diagnostic['literal_duplicate_rows'], 2)
        self.assertEqual(diagnostic['observed_cells'], 2)
        self.assertEqual(diagnostic['omitted_cells_filled_with_arithmetic_zero'], 4)
        self.assertEqual(diagnostic['targets_without_source_rows'], 1)

    def test_plain_and_reproducible_gzip_round_trip_keep_exact_values(self):
        matrix = ScoreMatrix(PROTEINS, TERMS,
                             [[0., .0009999999999, .12345678912345678], [1., .7, .3]])
        for name in ('invented.tsv', 'invented.tsv.gz', 'other-name.tsv.gz'):
            path = self.folder / name
            self.assertEqual(write_scores(path, matrix), 5)
            actual, _ = load_scores(path, PROTEINS, TERMS)
            self.assertEqual(actual.values.tobytes(), matrix.values.tobytes())
            with self.assertRaises(FileExistsError): write_scores(path, matrix)
        self.assertEqual((self.folder / 'invented.tsv.gz').read_bytes(),
                         (self.folder / 'other-name.tsv.gz').read_bytes())
        self.assertEqual(write_scores(self.folder / 'all.tsv.gz', matrix, include_zero=True), 6)

    def test_roundoff_retained_and_unknown_or_invalid_rows_rejected(self):
        path = self.folder / 'invented.tsv'
        above_one = 1 + 1e-15
        path.write_text(f'synthetic-P1 GO:0000001 {above_one:.17g}\n')
        with self.assertRaises(ValueError): load_scores(path, PROTEINS, TERMS)
        scores, diagnostic = load_scores(path, PROTEINS, TERMS,
                                         upper_roundoff_tolerance=LOCALPLUS_UPPER_ROUNDOFF)
        self.assertEqual(scores.values[0, 0], above_one)
        self.assertEqual(diagnostic['scores_in_upper_roundoff_band'], 1)
        for line in ('unknown GO:0000001 .5', 'synthetic-P1 GO:9999999 .5',
                     'synthetic-P1 GO:0000001 nan', 'synthetic-P1 GO:0000001 -1e-15',
                     'synthetic-P1 GO:0000001 .5 extra', 'synthetic-P1 GO:0000001 bad'):
            path.write_text(line + '\n')
            with self.subTest(line=line), self.assertRaises(ValueError):
                load_scores(path, PROTEINS, TERMS)


if __name__ == '__main__':
    unittest.main()
