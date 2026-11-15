"""Invented OBO/forecasts/truth only, checked against preserved author APIs."""
import gzip
import os
from pathlib import Path
import sys
import tempfile
import unittest

try:
    import numpy as np
    import pandas as pd
except ImportError:
    np = pd = None

from .core import ScoreMatrix
from .native_adapter import (
    _native, align_predictions, evaluate_native, load_native_scores,
    native_ontologies, native_predictions,
)


SOURCE = Path(os.environ.get('BIOGRAPH_CAFA_AUTHOR_SOURCE',
    str(Path(__file__).resolve().parents[2] /
        'runs/accuracy_next_20261113/cafa5_intake/evaluator_author_source/src')))
AVAILABLE = np is not None and (SOURCE / 'cafaeval/graph.py').is_file()
MF = 'molecular_function'
PROTEINS = ('invented-P3', 'invented-P1', 'invented-P2')
OBO = '''format-version: 1.2

[Term]
id: GO:0003674
name: invented MF root
namespace: molecular_function
def: "invented"

[Term]
id: GO:1000001
name: invented MF child A
namespace: molecular_function
def: "invented"
alt_id: GO:9000001
alt_id: GO:9000002
is_a: GO:0003674 ! invented root

[Term]
id: GO:1000002
name: invented MF child B
namespace: molecular_function
def: "invented"
alt_id: GO:9000001
is_a: GO:0003674 ! invented root

[Term]
id: GO:0008150
name: invented BP root
namespace: biological_process
def: "invented"

[Term]
id: GO:2000001
name: invented BP child
namespace: biological_process
def: "invented"
relationship: part_of GO:0008150 ! invented root

[Term]
id: GO:0005575
name: invented CC root
namespace: cellular_component
def: "invented"

[Term]
id: GO:3000001
name: invented CC child
namespace: cellular_component
def: "invented"
is_a: GO:0005575 ! invented root
'''


@unittest.skipUnless(AVAILABLE, 'Optional NumPy/Pandas or preserved native evaluator source unavailable.')
class NativeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_path = list(sys.path)
        sys.path.insert(0, str(SOURCE))
        _native()  # Includes pinned-source-byte admission, not only importability.

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.previous_path

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='biograph-invented-native-mixture-')
        self.folder = Path(self.temporary.name)
        self.obo = self.folder / 'invented.obo'
        self.obo.write_text(OBO)
        self.ontologies = native_ontologies(self.obo)
        self.native = _native()

    def tearDown(self):
        self.temporary.cleanup()

    def source(self, name, text):
        path = self.folder / name
        if path.suffix == '.gz':
            with gzip.open(path, 'wt') as stream:
                stream.write(text)
        else:
            path.write_text(text)
        return path

    def truth(self):
        path = self.source('invented-truth.tsv',
            'invented-P2 GO:1000002\ninvented-P1 GO:1000001\ninvented-P3 GO:1000001\n')
        return self.native['parser'].gt_parser(str(path), self.ontologies)

    def test_pure_endpoints_match_native_reader_including_alias_max_and_float_bytes(self):
        left = self.source('invented-left.tsv',
            'invented-P1 GO:9000001 .7\ninvented-P1 GO:1000001 .2\n'
            'invented-P1 GO:9000002 .8\ninvented-P1 GO:1000001 .1\n'
            'invented-P2 GO:1000002 .12345678912345678\n'
            'invented-outside GO:1000001 .9\ninvented-P1 GO:9999999 .6\n')
        right = self.source('invented-right.tsv',
            'invented-P2 GO:1000001 .9\ninvented-P3 GO:1000002 .3\n')
        a, audit = load_native_scores(left, PROTEINS, self.ontologies, localplus=True, chunksize=2)
        b, _ = load_native_scores(right, PROTEINS, self.ontologies, chunksize=1)
        self.assertEqual(audit['native_alias_source_rows'], 2)
        self.assertEqual(audit['duplicate_native_cell_assignments'], 3)
        self.assertEqual(audit['rows_outside_requested_protein_axis'], 1)
        self.assertEqual(audit['rows_outside_native_ontology'], 1)
        self.assertEqual(audit['by_namespace'][MF]['targets_without_source_rows'], 1)
        truth = self.truth()
        for alpha, path in ((1., left), (0., right)):
            result = native_predictions({MF: a[MF]}, {MF: b[MF]}, {MF: alpha}, self.ontologies)
            result = align_predictions(result, truth)
            expected = self.native['parser'].pred_parser(str(path), self.ontologies, truth, 'fill')
            self.assertEqual(result[MF].matrix.tobytes(), expected[MF].matrix.tobytes())
        self.assertEqual(a[MF].values[1, 1], .8)
        self.assertEqual(a[MF].values[1, 2], .7)
        self.assertEqual(a[MF].values[1, 0], 0.)  # Still raw, not propagated.

    def test_native_fill_happens_after_mix_and_once(self):
        from unittest.mock import patch

        terms = tuple(item['id'] for item in self.ontologies[MF].terms_list)
        left = ScoreMatrix(('invented-P1',), terms, [[0., 1., 0.]])
        right = ScoreMatrix(('invented-P1',), terms, [[0., 0., 1.]])
        with patch.object(self.native['graph'], 'propagate', wraps=self.native['graph'].propagate) as call:
            result = native_predictions({MF: left}, {MF: right}, {MF: .5}, self.ontologies)
            self.assertEqual(call.call_count, 1)
            self.assertEqual(call.call_args.kwargs['mode'], 'fill')
        np.testing.assert_array_equal(result[MF].matrix, [[.5, .5, .5]])
        # An explicitly nonzero parent's own score is retained by native fill,
        # unlike MAX closure; this catches accidentally selecting mode='max'.
        left = ScoreMatrix(('invented-P1',), terms, [[.1, 1., 0.]])
        result = native_predictions({MF: left}, {MF: right}, {MF: 1.}, self.ontologies)
        np.testing.assert_array_equal(result[MF].matrix, [[.1, 1., 0.]])

    def test_evaluation_is_exact_author_curve_and_requires_id_alignment(self):
        path = self.source('invented.tsv.gz',
            'invented-P1 GO:1000001 .8\ninvented-P2 GO:1000002 .6\n'
            'invented-P3 GO:1000002 .9\n')
        scores, _ = load_native_scores(path, PROTEINS, self.ontologies)
        predictions = native_predictions({MF: scores[MF]}, {MF: scores[MF]}, {MF: .5}, self.ontologies)
        truth = self.truth()
        self.assertNotEqual(predictions[MF].ids, truth[MF].ids)
        with self.assertRaisesRegex(ValueError, 'row identities differ'):
            evaluate_native(predictions, truth, self.ontologies, tau=np.array([.1, .5, .9]))
        aligned = align_predictions(predictions, truth)
        tau = np.array([.1, .5, .9])
        actual, summary = evaluate_native(aligned, truth, self.ontologies, tau=tau)
        expected = self.native['evaluation'].evaluate_prediction(aligned, truth,
            self.ontologies, tau, gt_exclude=None, normalization='cafa', n_cpu=1)
        pd.testing.assert_frame_equal(actual, expected, check_exact=True)
        self.assertEqual(summary[MF], float(expected['f_micro'].max()))
        aligned[MF]._learned_combination_terms = aligned[MF]._learned_combination_terms[::-1]
        with self.assertRaisesRegex(ValueError, 'term IDs/order differ'):
            evaluate_native(aligned, truth, self.ontologies, tau=tau)

    def test_optional_native_exclusion_is_forwarded_and_identity_checked(self):
        path = self.source('invented.tsv', 'invented-P1 GO:1000001 .8\ninvented-P2 GO:1000002 .6\n')
        scores, _ = load_native_scores(path, PROTEINS, self.ontologies)
        truth = self.truth()
        predictions = align_predictions(
            native_predictions({MF: scores[MF]}, {MF: scores[MF]}, {MF: .5}, self.ontologies), truth)
        exclude_matrix = np.zeros_like(truth[MF].matrix)
        exclude_matrix[truth[MF].ids['invented-P1'], 1] = True
        excluded = {MF: self.native['graph'].GroundTruth(dict(truth[MF].ids), exclude_matrix, MF)}
        tau = np.array([.1, .5, .9])
        actual, _ = evaluate_native(predictions, truth, self.ontologies, tau=tau, gt_exclude=excluded)
        expected = self.native['evaluation'].evaluate_prediction(predictions, truth,
            self.ontologies, tau, gt_exclude=excluded, normalization='cafa', n_cpu=1)
        pd.testing.assert_frame_equal(actual, expected, check_exact=True)
        bad = {MF: self.native['graph'].GroundTruth({'wrong-P': 0}, exclude_matrix[:1], MF)}
        with self.assertRaisesRegex(ValueError, 'exclusion'):
            evaluate_native(predictions, truth, self.ontologies, tau=tau, gt_exclude=bad)

    def test_source_range_guards_apply_even_to_outside_rows_and_roundoff_is_not_clipped(self):
        above_one = 1 + 1e-15
        path = self.source('invented.tsv.gz', f'invented-P1 GO:1000001 {above_one:.17g}\n')
        with self.assertRaisesRegex(ValueError, 'finite qualified'):
            load_native_scores(path, PROTEINS, self.ontologies)
        values, audit = load_native_scores(path, PROTEINS, self.ontologies, localplus=True)
        self.assertEqual(values[MF].values[1, 1], above_one)
        self.assertEqual(audit['scores_in_upper_roundoff_band'], 1)
        for bad in ('nan', 'inf', '-1e-15', '1.00000001'):
            self.source('bad.tsv', f'invented-outside GO:9999999 {bad}\n')
            with self.subTest(bad=bad), self.assertRaises((ValueError, TypeError)):
                load_native_scores(self.folder / 'bad.tsv', PROTEINS, self.ontologies, localplus=True)

    def test_chunked_parser_rejects_extra_missing_fields_and_all_zero_is_explicit(self):
        for text in ('invented-P1 GO:1000001 .3 extra\n',
                     'invented-P1 GO:1000001 .3\ninvented-P2 GO:1000002 .4 extra\n',
                     'invented-P1 GO:1000001\n'):
            path = self.source('bad.tsv', text)
            with self.subTest(text=text), self.assertRaises((ValueError, pd.errors.ParserError)):
                load_native_scores(path, PROTEINS, self.ontologies, chunksize=1)
        empty = self.source('empty.tsv.gz', '')
        values, audit = load_native_scores(empty, PROTEINS, self.ontologies)
        self.assertEqual(audit['source_rows'], 0)
        self.assertEqual(audit['by_namespace'][MF]['targets_without_source_rows'], 3)
        self.assertTrue(audit['by_namespace'][MF]['all_scores_zero'])
        result = native_predictions({MF: values[MF]}, {MF: values[MF]}, {MF: .5}, self.ontologies)
        self.assertEqual(tuple(result[MF].ids), PROTEINS)
        self.assertFalse(np.any(result[MF].matrix))
        curve, summary = evaluate_native(align_predictions(result, self.truth()), self.truth(),
                                         self.ontologies, tau=np.array([.1, .5, .9]))
        self.assertIsNone(summary[MF])
        self.assertTrue((curve['cov'] == 0).all())

    def test_known_only_exclusion_has_no_native_scored_endpoint(self):
        path = self.source('invented.tsv',
            'invented-P1 GO:1000001 .8\ninvented-P2 GO:1000002 .6\n')
        scores, _ = load_native_scores(path, PROTEINS, self.ontologies)
        truth = self.truth()
        predictions = align_predictions(
            native_predictions({MF: scores[MF]}, {MF: scores[MF]}, {MF: .5}, self.ontologies), truth)
        excluded = {MF: self.native['graph'].GroundTruth(dict(truth[MF].ids),
                    np.ones_like(truth[MF].matrix), MF)}
        _, summary = evaluate_native(predictions, truth, self.ontologies,
            gt_exclude=excluded, tau=np.array([.1, .5, .9]))
        self.assertIsNone(summary[MF])


if __name__ == '__main__':
    unittest.main()
