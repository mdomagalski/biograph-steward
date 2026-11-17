"""Synthetic parity checks against actual pinned native count/evaluator APIs."""
from contextlib import redirect_stdout
import io
import os
import unittest


class OrdinaryCountsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            from .native_adapter import _native
            cls.np, cls.native = np, _native()
        except (ImportError, ModuleNotFoundError) as error:
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED') == '1':
                raise
            raise unittest.SkipTest('Optional native numeric runtime unavailable: ' + str(error))

    def fixture(self):
        np = self.np
        native = self.native['graph']
        namespace = 'molecular_function'
        terms = {}
        for index in range(5):
            term = 'GO:100000' + str(index)
            terms[term] = {'name': term, 'namespace': namespace, 'def': '', 'alt_id': [],
                           'rel': [] if index == 0 else ['GO:1000000']}
        ontology = native.Graph(namespace, terms)
        # The native update_toi API can also restrict to an explicit subset.
        ontology.toi = np.asarray([1, 2, 3], dtype=int)
        truth = np.zeros((4, 5), dtype=bool)
        truth[0, 1] = truth[1, 2] = truth[2, 4] = truth[3, 3] = True
        scores = np.asarray([
            [1, .5, .5, np.nextafter(.5, 0), 1],
            [1, .5, np.nextafter(.5, 1), .001, 1],
            [1, 1, 1, 1, 1],
            [1, 1, 0, 0, 1],
        ], dtype=np.float64)
        known = np.zeros_like(truth)
        known[0, 1] = True  # All this row's GT known: FP on term2 must remain.
        known[3, 1:4] = True  # Empty allowed set after exclusion.
        ids = {name: i for i, name in enumerate(('P00001', 'P00002', 'P00003', 'P00004'))}
        prediction = native.Prediction(dict(ids), scores, namespace)
        gt = native.GroundTruth(dict(ids), truth, namespace)
        exclude = native.GroundTruth(dict(ids), known, namespace)
        tau = np.asarray([.001, .5, np.nextafter(.5, 1), .999])
        return prediction, gt, ontology, tau, exclude

    def check_parity(self, *, known):
        from .ordinary_counts import contributions, verify_curve
        np = self.np
        prediction, gt, ontology, tau, exclude = self.fixture()
        exclude = exclude if known else None
        before = prediction.matrix.copy()
        counts, eligible = contributions(prediction, gt, ontology, tau, exclude)
        self.assertEqual(counts.shape, (4, 4, 6))
        np.testing.assert_array_equal(eligible, [True, True, False, True])
        np.testing.assert_array_equal(counts[2], np.zeros((4, 6)))
        np.testing.assert_array_equal(prediction.matrix, before)
        evaluation = self.native['evaluation']
        # Compare every row and threshold to actual native low-level routines,
        # with the same pre-exclusion inclusion rule as compute_metrics.
        for row in range(4):
            if not eligible[row]:
                continue
            toi = ontology.toi if exclude is None else np.setdiff1d(
                ontology.toi, exclude.matrix[row].nonzero()[0], assume_unique=True)
            g = gt.matrix[row, toi]
            n_gt = np.asarray([g.sum()])
            with redirect_stdout(io.StringIO()):
                if exclude is None:
                    expected = evaluation.compute_confusion_matrix(
                        tau, g[None, :], prediction.matrix[row:row + 1, toi], toi, n_gt, None)
                else:
                    expected = evaluation.compute_confusion_matrix_exclude(
                        tau, [g], prediction.matrix[row:row + 1], [toi], n_gt, None)
            np.testing.assert_allclose(counts[row], expected, rtol=0, atol=1e-12)
        ns = ontology.namespace
        with redirect_stdout(io.StringIO()):
            curve = evaluation.evaluate_prediction({ns: prediction}, {ns: gt}, {ns: ontology},
                tau, gt_exclude=None if exclude is None else {ns: exclude},
                normalization='cafa', n_cpu=1)
        receipt = verify_curve(counts, curve, namespace=ns)
        self.assertTrue(receipt['author_point_agreement_passed'])
        self.assertLessEqual(receipt['max_absolute_curve_difference'], 1e-12)
        if known:
            self.assertTrue(eligible[0])
            self.assertEqual(counts[0, 1, 1], 0)
            self.assertEqual(counts[0, 1, 2], 1)
            self.assertEqual(counts[0, 1, 3], 0)
            self.assertEqual(receipt['post_exclusion_GT_proteins'], 1)
        else:
            # score == tau is included, immediately lower is not.
            self.assertEqual(counts[0, 1, 1], 1)
            self.assertEqual(counts[0, 1, 2], 1)
            self.assertEqual(counts[0, 2, 1], 0)
            self.assertEqual(counts[1, 2, 1], 1)
        changed = counts.copy()
        changed[1, :, 2] += 1
        with self.assertRaisesRegex(ValueError, 'full-curve mismatch'):
            verify_curve(changed, curve, namespace=ns)
        return counts, tau

    def test_native_unexcluded_ties_and_no_gt_in_toi(self):
        self.check_parity(known=False)

    def test_native_known_only_rows_still_contribute_fp(self):
        self.check_parity(known=True)

    def test_exact_boundary_nearby_float_and_empty_allowed_set(self):
        from .ordinary_counts import contributions
        np = self.np
        pred, gt, ont, tau, exclude = self.fixture()
        counts, _ = contributions(pred, gt, ont, tau, exclude)
        np.testing.assert_array_equal(counts[3], np.zeros((len(tau), 6)))
        self.assertEqual(counts[1, 0, 2], 2)
        self.assertEqual(counts[1, 1, 2], 1)
        self.assertEqual(counts[1, 2, 2], 0)

    def test_rejects_unaligned_ids_and_weighted_ontology(self):
        from .ordinary_counts import contributions
        pred, gt, ont, tau, exclude = self.fixture()
        pred.ids = {k: 3 - v for k, v in pred.ids.items()}
        with self.assertRaisesRegex(ValueError, 'identity axes'):
            contributions(pred, gt, ont, tau)
        pred.ids = dict(gt.ids)
        ont.ia = self.np.ones(5)
        with self.assertRaisesRegex(ValueError, 'IA None'):
            contributions(pred, gt, ont, tau)

    def test_ordinary_bootstrap_matches_established_micro_fmax_and_rng(self):
        from .ordinary_counts import paired_bootstrap
        from tools.cafa_reference.paired_bootstrap import DRAWS, SEED, micro_fmax
        np = self.np
        counts, tau = self.check_parity(known=True)
        ids = np.asarray(['P00001', 'P00002', 'P00003', 'P00004'])
        # Reconstruct the unchanged established whole-protein RNG weights;
        # call its ordinary micro_fmax directly, without an IA channel.
        arrays = {name: {'ids': ids, 'tau': tau, 'ordinary': counts.copy()}
                  for name in ('learned_mix', 'deepgose', 'localplus', 'equal_mix',
                               'native_t0_nonexperimental')}
        weights = np.random.default_rng(SEED).multinomial(
            len(ids), np.repeat(1 / len(ids), len(ids)), size=DRAWS).astype(np.float64)
        expected = {name: micro_fmax(row['ordinary'], weights) for name, row in arrays.items()}
        actual = paired_bootstrap(arrays)
        self.assertEqual(actual['draws'], 2000)
        self.assertEqual(actual['seed'], 20261113)
        self.assertEqual(len(actual['comparisons']), 4)
        self.assertFalse(actual['IA_supplied'])
        for name in arrays:
            np.testing.assert_array_equal(actual['scores'][name]['bootstrap_Fmax'],
                                          expected[name])
        for comparison in actual['comparisons']:
            self.assertEqual(comparison['paired_95_percentile_interval'], [0, 0])
            self.assertTrue(all(value == 0 for value in comparison['difference_draws']))
        arrays['localplus']['ids'] = ids[::-1]
        with self.assertRaisesRegex(ValueError, 'axes differ'):
            paired_bootstrap(arrays)


if __name__ == '__main__':
    unittest.main()
