"""Invented full-axis prior unions and immutable-source admission gates."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import annotation_prior as module
from .annotation_prior import merge_full_union, read_original_pair, run
from .assessment import validate_source_manifest
from .postprocessing import POSTPROCESS_SOURCE_PINS, SOFT_RATE, MAX_MIN_RATE
from tools.learned_combination.reference import file_sha256
from tools.learned_combination.runner import NS_ASPECT, write_json


class _PriorFixture:
    def setUp(self):
        try:
            import numpy as np
            import pandas as pd
        except ImportError:
            if os.environ.get('BIOGRAPH_ANNOTATION_PRIOR_TESTS_REQUIRED') == '1':
                raise
            self.skipTest('Optional NumPy/Pandas research runtime unavailable')
        self.np, self.pd = np, pd
        self.proteins = ('P00001', 'P00002', 'P00003')
        self.model_terms = ('GO:1000001', 'GO:1999999', 'GO:1000003')
        self.prior_terms = ('GO:1000003', 'GO:1000002', 'GO:1000008')
        self.prior = np.asarray([[1, 1, 0], [0, 1, 0], [0, 0, 0]], dtype=np.float64)

    def parent(self, dtype):
        return self.np.asarray([[.12345678901234567, .4, .999987654321],
            [.8765432109876543, .2, .3], [0., -0., .43210987654321]], dtype=dtype)


class PriorTests(_PriorFixture, unittest.TestCase):
    def pandas_literal(self, values):
        np, pd = self.np, self.pd
        models = pd.DataFrame({'EntryID': np.repeat(self.proteins, len(self.model_terms)),
            'term': np.tile(self.model_terms, len(self.proteins)), 'p': values.ravel()})
        row, col = np.nonzero(self.prior)
        annotations = pd.DataFrame({'EntryID': np.asarray(self.proteins)[row],
            'term': np.asarray(self.prior_terms)[col], 'p': np.full(len(row), .99, dtype=np.float32)})
        union = self.model_terms + tuple(t for t in self.prior_terms if t not in self.model_terms)
        pooled = pd.concat([models, annotations], ignore_index=True)
        expected = pooled.groupby(['EntryID', 'term'])['p'].max().reindex(
            pd.MultiIndex.from_product([self.proteins, union]), fill_value=0).to_numpy(dtype=values.dtype)
        return union, expected.reshape((len(self.proteins), len(union)))

    def test_exact_typed_concat_groupby_MAX_parity_and_float32_literal(self):
        np = self.np
        for dtype in (np.float32, np.float64):
            original = self.parent(dtype); before = original.tobytes()
            terms, values, audit = merge_full_union(self.proteins, self.model_terms, original,
                self.proteins, self.prior_terms, self.prior)
            expected_terms, expected_values = self.pandas_literal(original)
            self.assertEqual(terms, expected_terms)
            np.testing.assert_array_equal(values, expected_values)
            self.assertEqual(original.tobytes(), before)
            self.assertEqual(values.dtype, original.dtype)
            self.assertEqual(float(values[1, terms.index('GO:1000002')]), float(np.float32(.99)))
            self.assertNotEqual(audit['author_annotation_score_exact'], .99)
            self.assertEqual(audit['author_annotation_score_exact'], .9900000095367432)

    def test_full_heads_zero_rows_alias_distinction_and_parent_precision_retained(self):
        np = self.np; original = self.parent(np.float64)
        terms, values, audit = merge_full_union(self.proteins, self.model_terms, original,
            self.proteins, self.prior_terms, self.prior)
        self.assertEqual(terms, (*self.model_terms, 'GO:1000002', 'GO:1000008'))
        self.assertIn('GO:1999999', terms)  # Not replaced by any hypothesized canonical term.
        self.assertEqual(values[0, 0], original[0, 0])
        self.assertEqual(values[0, 2], original[0, 2])  # Parent above .99 wins.
        self.assertEqual(values[2, :3].tobytes(), original[2].tobytes())
        self.assertFalse(values[:, terms.index('GO:1000008')].any())
        self.assertEqual(audit['prior_positive_cells'], 3)
        self.assertEqual(audit['prior_positive_proteins'], 2)
        self.assertEqual(audit['target_rows'], 3)
        self.assertFalse(audit['new_soft_MIN_or_ontology_operation'])

    def test_target_reordering_nonbinary_curated_scores_and_invalid_parent_rejected(self):
        np = self.np; values = self.parent(np.float32)
        with self.assertRaisesRegex(ValueError, 'target order'):
            merge_full_union(self.proteins, self.model_terms, values,
                self.proteins[::-1], self.prior_terms, self.prior)
        prior = self.prior.copy(); prior[0, 0] = .99
        with self.assertRaisesRegex(ValueError, 'binary positive'):
            merge_full_union(self.proteins, self.model_terms, values,
                self.proteins, self.prior_terms, prior)
        for bad in (float('nan'), 1.0001, -.001):
            parent = values.copy(); parent[0, 0] = bad
            with self.assertRaisesRegex(ValueError, 'finite'):
                merge_full_union(self.proteins, self.model_terms, parent,
                    self.proteins, self.prior_terms, self.prior)

    def test_no_namespace_or_case_identity_is_silently_deduplicated(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            merge_full_union(self.proteins, ('GO:1000001',) * 3, self.parent(self.np.float32),
                self.proteins, self.prior_terms, self.prior)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            merge_full_union(('P00001',) * 3, self.model_terms, self.parent(self.np.float32),
                ('P00001',) * 3, self.prior_terms, self.prior)

    def test_actual_polars_Float32_annotation_and_groupby_MAX_when_available(self):
        try:
            import polars as pl
        except ImportError:
            if os.environ.get('BIOGRAPH_ANNOTATION_PRIOR_POLARS_REQUIRED') == '1':
                raise
            self.skipTest('Optional author-compatible Polars runtime unavailable')
        np = self.np; values = self.parent(np.float32)
        parent = pl.DataFrame({'EntryID': np.repeat(self.proteins, len(self.model_terms)),
            'term': np.tile(self.model_terms, len(self.proteins)), 'p': values.ravel()})
        rows, columns = np.nonzero(self.prior)
        prior = pl.DataFrame({'EntryID': np.asarray(self.proteins)[rows],
            'term': np.asarray(self.prior_terms)[columns]}).with_columns(p=pl.lit(.99, dtype=pl.Float32))
        self.assertEqual(prior['p'].dtype, pl.Float32)
        pooled = pl.concat([parent, prior]).group_by(['EntryID', 'term']).agg(pl.col('p').max())
        terms, merged, _ = merge_full_union(self.proteins, self.model_terms, values,
            self.proteins, self.prior_terms, self.prior)
        lookup = {(row['EntryID'], row['term']): row['p'] for row in pooled.to_dicts()}
        for i, protein in enumerate(self.proteins):
            for j, term in enumerate(terms):
                self.assertEqual(float(merged[i, j]), lookup.get((protein, term), 0.))


class SourceAdmissionTests(_PriorFixture, unittest.TestCase):
    def fixture(self, root):
        np = self.np
        targets = root / 'targets.txt'; targets.write_text('\n'.join(self.proteins) + '\n')
        cfg = {'targets': {'file': str(targets), 'sha256': file_sha256(targets)}, 'arms': {}}
        forecasts = {}
        for arm in ('validation_selected_context', 'native_T0_nonexperimental'):
            cfg['arms'][arm] = {}; forecasts[arm] = {}
            for namespace in NS_ASPECT:
                path = root / (arm + namespace + '.npy')
                values, terms = ((self.parent(np.float32), self.model_terms)
                    if arm == 'validation_selected_context' else (self.prior, self.prior_terms))
                np.save(path, values, allow_pickle=False)
                meta = {'namespace': namespace, 'proteins': list(self.proteins), 'terms': list(terms),
                    'prediction_file': str(path), 'prediction_sha256': file_sha256(path),
                    'model_metadata_sha256': '1' * 64, 'final_reference_labels_read_for_forecasting': False,
                    'postprocessing': {'source_sha256': POSTPROCESS_SOURCE_PINS, 'soft_rate': SOFT_RATE,
                        'max_min_rate': MAX_MIN_RATE, 'annotation_or_reference_files_read': False}}
                manifest = root / (arm + namespace + '.json'); write_json(manifest, meta)
                spec = {'file': str(manifest), 'sha256': file_sha256(manifest)}
                cfg['arms'][arm][namespace] = spec
                forecasts[arm][namespace] = validate_source_manifest(spec, self.proteins,
                    arm=arm, namespace=namespace)
        config_path = root / 'configuration.json'; write_json(config_path, cfg)
        seal = {'format': 'biograph-steward.contextual-forecast-seal.v1', 'future_GO_labels_opened': False,
            'target_count': len(self.proteins), 'configuration_sha256': file_sha256(config_path),
            'forecasts': forecasts}
        seal_path = root / 'forecast_seal.json'; write_json(seal_path, seal)
        author = root / 'invented_author_operation.py'; author.write_text('# Invented source fixture\n')
        return {'format': 'biograph-steward.annotation-prior-development.v1',
            'original_seal_directory': str(root), 'original_seal_sha256': file_sha256(seal_path),
            'author_script': {'file': str(author), 'sha256': file_sha256(author)}}

    def test_original_seal_gate_rejects_unregistered_sources_before_reading_them(self):
        with self.assertRaisesRegex(ValueError, 'original presealed'):
            read_original_pair('/MUST_NOT_READ_CURATED_OR_FUTURE', '0' * 64, 'biological_process')
        with self.assertRaisesRegex(ValueError, 'extra source'):
            run({'format': 'biograph-steward.annotation-prior-development.v1',
                 'curated_T1_file': '/MUST_NOT_READ'}, '/MUST_NOT_WRITE')

    def test_invented_original_seal_three_aspect_export_and_precision_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); cfg = self.fixture(root)
            with patch.object(module, 'ORIGINAL_SEAL_SHA256', cfg['original_seal_sha256']), \
                 patch.object(module, 'TARGET_COUNT', len(self.proteins)), \
                 patch.object(module, 'AUTHOR_SCRIPT_SHA256', cfg['author_script']['sha256']):
                result = run(cfg, root / 'out')
            self.assertEqual(set(result['forecasts']), set(NS_ASPECT))
            self.assertEqual(set(result['matched_prior_forecasts']), set(NS_ASPECT))
            self.assertTrue(result['development_only'])
            self.assertTrue(result['reference_previously_consumed'])
            self.assertFalse(result['models_fitted_or_scores_computed'])
            self.assertFalse(result['reference_labels_read'])
            for spec in result['forecasts'].values():
                meta = json.loads(Path(spec['file']).read_text())
                self.assertEqual(meta['proteins'], list(self.proteins))
                self.assertEqual(meta['operation']['output_dtype'], 'float32')
                self.assertEqual(meta['operation']['appended_prior_heads'], 2)
                self.assertFalse(meta['fresh_final_reference_claimed'])
                self.assertFalse(meta['automatic_graph_or_app_promotion'])
                self.assertFalse(meta['final_reference_labels_read_for_forecasting'])
                control_spec = result['matched_prior_forecasts'][meta['namespace']]
                control = json.loads(Path(control_spec['file']).read_text())
                self.assertEqual(control['terms'], meta['terms'])
                self.assertEqual(control['proteins'], meta['proteins'])
                self.assertTrue(control['matched_prior_only'])
                self.assertTrue(control['model_forecast_is_exactly_zero'])
                values = self.np.load(control['prediction_file'], allow_pickle=False)
                self.assertEqual(values.dtype, self.np.float32)
                self.assertEqual(set(values.ravel()), {self.np.float32(0), self.np.float32(.99)})

    def test_changed_sealed_configuration_cannot_swap_annotation_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); cfg = self.fixture(root)
            old = json.loads((root / 'configuration.json').read_text())
            old['arms']['native_T0_nonexperimental']['biological_process']['file'] = '/CURATED_T1_MUST_NOT_READ'
            (root / 'configuration.json').write_text(json.dumps(old))
            with patch.object(module, 'ORIGINAL_SEAL_SHA256', cfg['original_seal_sha256']), \
                 patch.object(module, 'TARGET_COUNT', len(self.proteins)):
                with self.assertRaisesRegex(ValueError, 'changed original sealed metadata'):
                    read_original_pair(root, cfg['original_seal_sha256'], 'biological_process')


if __name__ == '__main__':
    unittest.main()
