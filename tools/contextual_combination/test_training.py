"""Invented-data gates for native training, cache identity and parameter SWA."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from .native_stacker import load_author, make_dataset, make_model
from .training import (
    CachedNativeDataset, PARAMETERS, TARGET_SEMANTICS, VALIDATION_REFERENCE_PINS,
    VALIDATION_ROLE, read_feature_manifest, project_native_forecasts, sha,
    training_author, validate_validation_sources, write_json, save_soft_forecast, root_positive_rows,
)


class CacheGuardTests(unittest.TestCase):
    def setUp(self):
        try:
            import numpy as np
            self.np = np
        except ImportError:
            self.skipTest('Optional NumPy runtime unavailable')
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        if hasattr(self, 'temp'):
            self.temp.cleanup()

    def fixture(self, *, lose_known=False, semantics=TARGET_SEMANTICS):
        np = self.np
        x = np.ones((2, 9, 3), dtype=np.float32) * .3
        x[:, [0, 4, 8], :] = 0
        known = np.asarray([[True, False, False], [True, True, False]])
        y = np.asarray([[1, 0, 1], [1, 1, 0]], dtype=np.float32)
        if lose_known:
            y[1, 1] = 0
        for name, values in [('features', x), ('targets', y), ('known', known)]:
            np.save(self.root / (name + '.npy'), values, allow_pickle=False)
        manifest = {'proteins': ['invented1', 'invented2'],
                    'terms': ['GO:1000000', 'GO:1000001', 'GO:1000002'],
                    'feature_file': str(self.root / 'features.npy'),
                    'targets_file': str(self.root / 'targets.npy'),
                    'known_positive_mask_file': str(self.root / 'known.npy'),
                    'target_semantics': semantics}
        path = self.root / 'manifest.json'
        write_json(path, manifest)
        pins = {str(p): sha(p) for p in self.root.iterdir() if p.is_file()}
        return path, pins

    def test_known_positives_are_physically_retained_not_only_declared(self):
        path, pins = self.fixture()
        manifest, x, y = read_feature_manifest(path, pins, fitting=True)
        self.assertEqual(x.shape, (2, 9, 3))
        self.assertEqual(float(y[1, 1]), 1.)
        self.assertEqual(manifest['target_semantics'], TARGET_SEMANTICS)

    def test_pk_delta_that_zeroes_known_positive_fails_even_with_matching_hashes(self):
        path, pins = self.fixture(lose_known=True)
        with self.assertRaisesRegex(ValueError, 'known positive function was relabeled'):
            read_feature_manifest(path, pins, fitting=True)

    def test_target_semantics_missing_pins_and_changed_cache_fail(self):
        path, pins = self.fixture(semantics='new_PK_delta_only')
        with self.assertRaisesRegex(ValueError, 'full known-T0 union'):
            read_feature_manifest(path, pins, fitting=True)
        with self.assertRaisesRegex(ValueError, 'input pin'):
            read_feature_manifest(path, {}, fitting=False)
        (self.root / 'features.npy').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'input pin'):
            read_feature_manifest(path, pins, fitting=False)

    def test_validation_targets_are_not_read_as_forecast_features(self):
        path, pins = self.fixture()
        # Even an unavailable validation target file is not read by the I/O
        # adapter's forecast-only path. Scoring labels use a separate fixed role.
        (self.root / 'targets.npy').unlink()
        _, x, y = read_feature_manifest(path, pins, fitting=False)
        self.assertIsNone(y)
        self.assertEqual(x.shape, (2, 9, 3))

    def test_fresh_reference_role_or_pin_is_rejected_before_label_decoding(self):
        fake = {'role': 'fresh_final_reference', 'references': {}}
        with patch('tools.contextual_combination.training.sha') as reader:
            with self.assertRaisesRegex(ValueError, 'already-consumed'):
                validate_validation_sources(fake)
            reader.assert_not_called()
        refs = {role: {'file': '/invented/' + role, 'sha256': pin}
                for role, pin in VALIDATION_REFERENCE_PINS.items()}
        refs['truth']['sha256'] = '0' * 64
        with patch('tools.contextual_combination.training.sha',
                   side_effect=lambda p: refs[Path(p).name]['sha256']) as reader:
            with self.assertRaisesRegex(ValueError, 'consumed immutable release: truth'):
                validate_validation_sources({'role': VALIDATION_ROLE, 'references': refs})
            self.assertNotIn('/invented/truth', [call.args[0] for call in reader.call_args_list])

    def test_fixed_recipe_has_no_final_test_selection_parameter(self):
        self.assertEqual(PARAMETERS['epochs'], 20)
        self.assertEqual(PARAMETERS['architectures'], [0, 8])
        self.assertEqual(PARAMETERS['average_best'], 3)
        self.assertEqual(PARAMETERS['weight_decay'], 0)
        self.assertFalse(any('final' in key for key in PARAMETERS))

    def test_deployed_bundle_preserves_raw_and_soft_separately(self):
        values = self.np.asarray([[.1, .9]], dtype=self.np.float32)
        deployed = self.np.asarray([[.38, .62]], dtype=self.np.float32)
        with patch('tools.contextual_combination.training.published_soft_closure',
                   return_value=(deployed, {'source': 'invented-source-receipt'})) as process:
            result = save_soft_forecast('/invented/author', object(), ['invented'],
                                       ['GO:1000000', 'GO:1000001'], values, self.root)
        self.np.testing.assert_array_equal(self.np.load(result['raw_prediction_file']), values)
        self.np.testing.assert_array_equal(self.np.load(result['prediction_file']), deployed)
        self.assertEqual(result['raw_prediction_sha256'], sha(result['raw_prediction_file']))
        self.assertEqual(result['postprocessing']['source'], 'invented-source-receipt')
        process.assert_called_once()


class NativeTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            import torch
            from .test_native_stacker import NativeStackerTests
            NativeStackerTests.setUpClass()
            cls.fixture_owner = NativeStackerTests
            cls.author = NativeStackerTests.author
            cls.np, cls.torch = np, torch
            train, cls.native_swa, predict = training_author(cls.author)
            cls.native_train, cls.native_predict = staticmethod(train), staticmethod(predict)
        except (ImportError, FileNotFoundError) as error:
            if os.environ.get('BIOGRAPH_CONTEXT_NATIVE_TESTS_REQUIRED') == '1':
                raise
            raise unittest.SkipTest('Optional pinned native training runtime unavailable: ' + str(error))

    def test_native_parameter_swa_is_not_mean_of_probabilities(self):
        torch = self.torch
        with tempfile.TemporaryDirectory() as temp:
            model = torch.nn.Linear(1, 1)
            swa = self.native_swa(10, path=str(Path(temp) / 'native'), rewrite=False)
            probs = []
            states = []
            for weight, bias, score in [(1., 0., .1), (3., 2., .3), (-2., -1., .2)]:
                with torch.no_grad():
                    model.weight.fill_(weight); model.bias.fill_(bias)
                    probs.append(model(torch.ones(1, 1)).sigmoid().item())
                    states.append({k: v.detach().clone() for k, v in model.state_dict().items()})
                swa.add_checkpoint(model, score=score)
            model = swa.set_weights(model, 3, weighted=False)
            for name, value in model.state_dict().items():
                self.assertTrue(torch.allclose(value, sum(s[name] / 3 for s in states), rtol=0, atol=1e-7))
            probability_of_average = model(torch.ones(1, 1)).sigmoid().item()
            self.assertGreater(abs(probability_of_average - sum(probs) / 3), .01)
            with self.assertRaises(FileExistsError):
                self.native_swa(10, path=str(Path(temp) / 'native'), rewrite=False)

    def test_cached_native_loader_matches_original_dataset(self):
        from .native_stacker import collate_rows
        args = self.fixture_owner().fixture()
        original = make_dataset(self.author, **args)
        features = self.np.stack([original[i]['x'].numpy() for i in range(len(original))])
        targets = self.np.stack([original[i]['y'].numpy() for i in range(len(original))])
        cache = CachedNativeDataset({'proteins': list(args['proteins']), 'terms': list(args['terms'])},
                                    features, args['graph'], targets)
        with self.fixture_owner().native_cpu_placement():
            loader = self.author.data_module.StackDataLoader(cache, batch_size=2, shuffle=False, num_workers=0)
            actual = next(iter(loader))
        expected = collate_rows(self.author, original, [0, 1])
        for name in ('x', 'goa', 'y'):
            self.assertTrue(self.torch.equal(actual[name], expected[name]))

    def test_native_root_positive_filter_uses_literal_nonzero_column_and_only_indexes_rows(self):
        from types import SimpleNamespace
        from .native_stacker import _symbols
        np, torch = self.np, self.torch
        # The root deliberately occurs at column1. The unqualified assumption
        # that root==column0 would choose a different protein and fail.
        graph = SimpleNamespace(idxs=3, terms_list=[
            {'id': 'GO:1000001', 'adj': [1], 'children': []},
            {'id': 'GO:1000000', 'adj': [], 'children': [0, 2]},
            {'id': 'GO:1000002', 'adj': [1], 'children': []}])
        y = np.asarray([[1, 1, 0], [0, 0, 0], [0, 1, 1]], dtype=np.float32)
        rows, audit = root_positive_rows(graph, y)
        import pandas as pd
        source_target = pd.DataFrame(y, columns=[n['id'] for n in graph.terms_list])
        root_id = [n['id'] for n in graph.terms_list if len(n['adj']) == 0][0]
        native_rows = np.nonzero(source_target[root_id].values == 1)[0]
        np.testing.assert_array_equal(rows, native_rows)
        x = np.arange(3 * 9 * 3, dtype=np.float32).reshape((3, 9, 3))
        original_x, original_y = x.copy(), y.copy()
        data = CachedNativeDataset({'proteins': ['p0', 'p1', 'p2'],
            'terms': list(source_target.columns)}, x, graph, y, row_indices=rows)
        self.assertEqual(len(data), 2)
        self.assertEqual(data.preds[0][0].shape[0], 2)
        np.testing.assert_array_equal(data[1]['x'].numpy(), x[2])
        np.testing.assert_array_equal(data[1]['y'].numpy(), y[2])
        np.testing.assert_array_equal(x, original_x); np.testing.assert_array_equal(y, original_y)
        self.assertEqual(audit['root_column'], 1)
        self.assertEqual(audit['allowed_prior_universe_rows'], 3)
        self.assertEqual(audit['supervised_fitting_rows'], 2)

    def test_unchanged_native_training_loop_uses_only_supplied_invented_callback(self):
        torch = self.torch
        class Toy(torch.nn.Module):
            def __init__(self):
                super().__init__(); self.layer = torch.nn.Linear(2, 2)
            def forward(self, batch):
                return self.layer(batch['x'])
        seen = []
        def invented_callback(model, loader):
            seen.append('consumed-invented-validation-only')
            return float(len(seen)) / 10
        model = Toy()
        loader = [{'x': torch.tensor([[.1, .2], [.3, .4]]), 'y': torch.tensor([[1., 0.], [0., 1.]])}]
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            swa = self.native_swa(10, path=str(Path(temp) / 'native'), rewrite=False)
            model, swa, scores = self.native_train(model, swa, loader, loader, invented_callback,
                n_ep=2, lr=.001, clip_grad=.1, weight_decay=0.)
        self.assertEqual(scores, [.1, .2])
        self.assertEqual(len(seen), 2)
        self.assertTrue(all(self.torch.isfinite(p).all() for p in model.parameters()))


class NativeProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            source = Path(os.environ.get('BIOGRAPH_CAFA_AUTHOR_SOURCE',
                'runs/accuracy_next_20261113/cafa5_intake/evaluator_author_source/src'))
            sys.path.insert(0, str(source))
            from tools.learned_combination.native_adapter import _native
            cls.native, cls.np = _native(), np
        except (ImportError, ModuleNotFoundError) as error:
            if os.environ.get('BIOGRAPH_CONTEXT_NATIVE_TESTS_REQUIRED') == '1':
                raise
            raise unittest.SkipTest('Optional pinned evaluator source unavailable: ' + str(error))

    def test_array_intake_matches_native_tsv_alternative_max_then_fill(self):
        from tools.learned_combination.test_native_adapter import OBO
        ns = 'molecular_function'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            obo = root / 'invented.obo'; obo.write_text(OBO)
            ont = self.native['parser'].obo_parser(str(obo), ia_file=None, orphans=False)
            namespace = ont[ns]
            alias = next(iter(namespace.terms_dict_alt))
            canonical = next(iter(namespace.terms_dict_alt[alias]))
            proteins = ('invented1', 'invented2')
            terms = (alias, canonical, 'GO:9999999')
            values = self.np.asarray([[.3, .7, .9], [.8, .2, .1]], dtype=self.np.float32)
            truth = self.native['graph'].GroundTruth({p: i for i, p in enumerate(proteins)},
                self.np.ones((2, namespace.idxs), dtype=bool), ns)
            path = root / 'native.tsv'
            with path.open('w') as stream:
                for p, row in zip(proteins, values):
                    for term, score in zip(terms, row):
                        stream.write(f'{p}\t{term}\t{float(score):.17g}\n')
            expected = self.native['parser'].pred_parser(str(path), ont, {ns: truth}, 'fill', None)[ns]
            observed, audit = project_native_forecasts(proteins, terms, values, namespace)
            self.np.testing.assert_array_equal(observed.matrix, expected.matrix)
            self.assertEqual(audit['dropped_heads'], 1)
            self.assertEqual(audit['mapped_heads'], 2)

    def test_explicit_native_alternative_mapping_wins_a_primary_id_collision(self):
        from tools.learned_combination.test_native_adapter import OBO
        ns = 'molecular_function'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            obo = root / 'collision.obo'
            obo.write_text(OBO.replace('id: GO:1000002\n', 'id: GO:1000002\nalt_id: GO:1000001\n'))
            ont = self.native['parser'].obo_parser(str(obo), ia_file=None, orphans=False)
            graph = ont[ns]
            self.assertIn('GO:1000001', graph.terms_dict)
            self.assertIn('GO:1000001', graph.terms_dict_alt)
            values = self.np.asarray([[.7]], dtype=self.np.float32)
            truth = self.native['graph'].GroundTruth({'invented': 0},
                self.np.ones((1, graph.idxs), dtype=bool), ns)
            path = root / 'collision.tsv'; path.write_text('invented\tGO:1000001\t' + str(float(values[0, 0])) + '\n')
            native = self.native['parser'].pred_parser(str(path), ont, {ns: truth}, 'fill', None)[ns]
            actual, _ = project_native_forecasts(('invented',), ('GO:1000001',), values, graph)
            self.np.testing.assert_array_equal(actual.matrix, native.matrix)

    def test_qualified_localplus_roundoff_is_retained_without_clipping(self):
        from tools.learned_combination.test_native_adapter import OBO
        from tools.learned_combination.core import LOCALPLUS_UPPER_ROUNDOFF
        ns = 'molecular_function'
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'invented.obo'; file.write_text(OBO)
            graph = self.native['parser'].obo_parser(str(file), ia_file=None, orphans=False)[ns]
            term = graph.terms_list[0]['id']
            values = self.np.asarray([[1 + 5e-11]])
            with self.assertRaisesRegex(ValueError, 'invalid source model probabilities'):
                project_native_forecasts(['invented'], [term], values, graph)
            observed, audit = project_native_forecasts(['invented'], [term], values, graph,
                upper_roundoff_tolerance=LOCALPLUS_UPPER_ROUNDOFF)
            self.assertEqual(observed.matrix.max(), values.max())
            self.assertFalse(audit['probability_clipping'])
            for tolerance in (True, 1e-9, -1e-10):
                with self.assertRaisesRegex(ValueError, 'qualified LocalPlus'):
                    project_native_forecasts(['invented'], [term], values, graph,
                        upper_roundoff_tolerance=tolerance)


if __name__ == '__main__':
    unittest.main()
