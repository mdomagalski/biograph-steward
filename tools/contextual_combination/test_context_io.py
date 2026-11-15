"""Invented-data qualification of native variable-GOA and bool-row I/O."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from .context_io import BooleanContextDataset, CONTEXT_FORMAT, read_boolean_context
from .native_stacker import (
    DEFAULT_CONTEXT_CHANNELS, collate_rows, make_dataset, make_model,
    validate_model_context,
)
from .training import sha, write_json


class ContextIOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            import torch
            from .test_native_stacker import NativeStackerTests
            NativeStackerTests.setUpClass()
            cls.owner, cls.author = NativeStackerTests, NativeStackerTests.author
            cls.np, cls.torch = np, torch
        except (ImportError, FileNotFoundError) as error:
            if os.environ.get('BIOGRAPH_CONTEXT_NATIVE_TESTS_REQUIRED') == '1':
                raise
            raise unittest.SkipTest('Optional native context runtime/source unavailable: ' + str(error))

    def fixture(self):
        args = self.owner().fixture()
        dataset = make_dataset(self.author, **args)
        features = self.np.stack([dataset[i]['x'].numpy() for i in range(len(dataset))])
        targets = self.np.stack([dataset[i]['y'].numpy() for i in range(len(dataset))])
        manifest = {'proteins': list(args['proteins']), 'terms': list(args['terms'])}
        return args, dataset, manifest, features, targets

    def test_default_one_context_keeps_exact_native_initial_weights(self):
        torch = self.torch
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(20261115)
            expected = self.author.stacker_module.GCNStacker(2, 1, 5, hidden_size=16, n_layers=8, embed_size=8)
        actual = make_model(self.author, n_terms=5, terms=self.owner().fixture()['terms'])
        for key, state in expected.state_dict().items():
            self.assertTrue(torch.equal(actual.state_dict()[key], state))
        validate_model_context(actual, DEFAULT_CONTEXT_CHANNELS)

    def test_native_multiple_goa_inputs_match_original_loader_and_preserve_binary_values(self):
        args = self.owner().fixture()
        first = args.pop('goa_indices')
        channels = [('invented.raw', first), ('invented.propagated', [[0, 1, 3], [0, 1, 3, 4]])]
        dataset = make_dataset(self.author, **args, goa_channels=channels)
        with self.owner().native_cpu_placement():
            loader = self.author.data_module.StackDataLoader(dataset, batch_size=2, shuffle=False, num_workers=0)
            expected = next(iter(loader))
        actual = collate_rows(self.author, dataset, [0, 1])
        for name in ('x', 'goa', 'y'):
            self.assertTrue(self.torch.equal(actual[name], expected[name]))
        self.assertEqual(actual['goa'].shape, (2, 5, 2))
        self.assertTrue(set(actual['goa'].flatten().tolist()) <= {0., 1.})

    def test_boolean_single_channel_adapter_is_bitwise_equal_to_existing_dataset(self):
        args, native, manifest, features, targets = self.fixture()
        context = features[:, 8:9].astype(bool)
        meta = {**manifest, 'channels': list(DEFAULT_CONTEXT_CHANNELS)}
        adapted = BooleanContextDataset(manifest, features, args['graph'], meta, context, targets)
        for i in range(len(native)):
            for name in ('x', 'y'):
                self.assertTrue(self.torch.equal(adapted[i][name], native[i][name]))

    def test_forty_boolean_channels_feed_unchanged_native_model_without_dense_float_cache(self):
        np, torch = self.np, self.torch
        args, native, manifest, features, targets = self.fixture()
        names = tuple('invented.' + str(i) for i in range(40))
        context = np.zeros((2, 40, 5), dtype=bool)
        context[:, ::2, 1] = True; context[:, 1::2, 3] = True
        original_features, original_context = features.copy(), context.copy()
        adapted = BooleanContextDataset(manifest, features, args['graph'],
            {**manifest, 'channels': list(names)}, context, targets, row_indices=np.asarray([1]))
        self.assertIs(adapted.features, features)
        self.assertEqual(adapted.context.dtype, np.bool_)
        self.assertEqual(adapted[0]['x'].shape, (48, 5))
        self.assertEqual(adapted.preds[0][0].shape[0], 1)
        batch = collate_rows(self.author, adapted, [0])
        original_batch = collate_rows(self.author, native, [1])
        self.assertTrue(torch.equal(batch['x'], original_batch['x']))
        self.assertEqual(batch['x'].shape, (1, 5, 8))
        self.assertEqual(batch['goa'].shape, (1, 5, 40))
        self.assertTrue(set(batch['goa'].flatten().tolist()) <= {0., 1.})
        model = make_model(self.author, n_terms=5, terms=args['terms'], context_channels=names)
        validate_model_context(model, names)
        with self.owner().native_cpu_placement():
            output = model(batch)
            torch.nn.BCEWithLogitsLoss()(output, batch['y']).backward()
        self.assertTrue(bool(torch.isfinite(output).all()))
        np.testing.assert_array_equal(features, original_features)
        np.testing.assert_array_equal(context, original_context)

    def test_same_count_channel_reorder_or_duplicate_is_rejected(self):
        args = self.owner().fixture()
        names = ('evidence.other.raw', 'relation.other.raw')
        model = make_model(self.author, n_terms=5, terms=args['terms'], context_channels=names)
        with self.assertRaisesRegex(ValueError, 'channel identities/order changed'):
            validate_model_context(model, tuple(reversed(names)))
        with self.assertRaisesRegex(ValueError, 'unique literal ordered'):
            make_model(self.author, n_terms=5, terms=args['terms'], context_channels=[names[0]] * 2)
        with self.assertRaisesRegex(ValueError, 'unique GOA indexes'):
            make_dataset(self.author, **{**args, 'goa_indices': [[1.5], []]})

    def test_boolean_manifest_pins_axes_dtype_and_boundary(self):
        np = self.np
        args, native, manifest, features, targets = self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); array = root / 'context.npy'
            np.save(array, features[:, 8:9].astype(bool), allow_pickle=False)
            meta = {**manifest, 'format': CONTEXT_FORMAT, 'channels': list(DEFAULT_CONTEXT_CHANNELS),
                    'context_file': str(array), 'context_sha256': sha(array),
                    'fresh_final_reference_opened': False}
            file = root / 'context.json'; write_json(file, meta)
            pins = {str(file): sha(file), str(array): sha(array)}
            decoded, values = read_boolean_context(file, pins, manifest)
            self.assertIsInstance(values, np.memmap)
            self.assertEqual(values.dtype, np.bool_)
            with self.assertRaisesRegex(ValueError, 'axes differ'):
                read_boolean_context(file, pins, {**manifest, 'proteins': list(reversed(manifest['proteins']))})
            np.save(array, values.astype(np.float32), allow_pickle=False)
            meta['context_sha256'] = sha(array); file.write_text(json.dumps(meta))
            pins = {str(file): sha(file), str(array): sha(array)}
            with self.assertRaisesRegex(ValueError, 'must be bool'):
                read_boolean_context(file, pins, manifest)
            meta['fresh_final_reference_opened'] = True; file.write_text(json.dumps(meta));pins[str(file)] = sha(file)
            with self.assertRaisesRegex(ValueError, 'final-reference boundary'):
                read_boolean_context(file, pins, manifest)


if __name__ == '__main__':
    unittest.main()
