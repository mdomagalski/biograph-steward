"""Invented native-core/feature fixtures, no scientific labels or model calls."""
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from .native_stacker import (
    AUTHOR_PINS, collate_rows, load_author, make_dataset, make_model,
    transform_batch, validate_model_axis,
)


class NativeStackerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            import torch
            import pandas as pd
            root = Path(os.environ.get('BIOGRAPH_PROTBOOST_AUTHOR_ROOT',
                'runs/contextual_gain_20261115/operator/combination_methods_v1/author'))
            cls.author = load_author(root)
            cls.np, cls.torch, cls.root = np, torch, root
        except (ImportError, FileNotFoundError) as error:
            if os.environ.get('BIOGRAPH_CONTEXT_NATIVE_TESTS_REQUIRED') == '1':
                raise
            raise unittest.SkipTest('Optional source-pinned research runtime unavailable: ' + str(error))

    def fixture(self):
        np = self.np
        terms = ('GO:1000000', 'GO:1000001', 'GO:1000002', 'GO:1000003', 'GO:1000004')
        graph = SimpleNamespace(idxs=5, namespace='biological_process', terms_list=[
            {'id': terms[0], 'adj': [], 'children': [1, 2]},
            {'id': terms[1], 'adj': [0], 'children': [3]},
            {'id': terms[2], 'adj': [0], 'children': [3]},
            {'id': terms[3], 'adj': [1, 2], 'children': [4]},
            {'id': terms[4], 'adj': [3], 'children': []},
        ])
        args = dict(proteins=('inventedP1', 'inventedP2'), terms=terms, graph=graph,
            predictions=[(np.array([[1, .8, .3], [.7, .4, 0.]]), [0, 1, 3]),
                         (np.array([[1, .6, .2], [.8, 0., .5]]), [0, 2, 4])],
            prior_raw=np.array([1, .3, .2, .05, .02]),
            prior_cond=np.array([1, .3, .2, .2, .4]),
            goa_indices=[[3], [1, 4]],
            targets=np.array([[1, 1, 0, 1, 0], [1, 0, 1, 0, 1]], dtype=bool))
        return args

    def test_set_backed_evaluator_graph_matches_source_sequence_features(self):
        from .native_stacker import sequence_edge_graph
        args = self.fixture()
        expected = make_dataset(self.author, **args)
        original = args['graph']
        for node in original.terms_list:
            node['adj'], node['children'] = set(node['adj']), set(node['children'])
        view = sequence_edge_graph(original)
        self.assertTrue(all(isinstance(n['adj'], set) for n in original.terms_list))
        self.assertTrue(all(isinstance(n['adj'], list) for n in view.terms_list))
        actual = make_dataset(self.author, **args)
        for row in range(len(actual)):
            self.np.testing.assert_array_equal(actual[row]['x'], expected[row]['x'])

    @contextmanager
    def native_cpu_placement(self):
        # Scope-only interception of native .cuda() placement, with unchanged
        # Tensor operations, layer/feature bodies and weights. No CUDA access.
        with patch.object(self.torch.Tensor, 'cuda', lambda value, *args, **kwargs: value):
            yield

    def test_source_bytes_and_license_are_admitted_before_execution(self):
        self.assertEqual(self.author.source_receipt['source_sha256'], AUTHOR_PINS)
        self.assertFalse(self.author.source_receipt['model_body_changed'])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in AUTHOR_PINS:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.root / name, p)
            with (root / 'protnn/stacker.py').open('a') as stream:
                stream.write('\n# altered source\n')
            with self.assertRaisesRegex(ValueError, 'differs'):
                load_author(root)

    def test_native_marginal_heads_keep_copies_and_missing_priors_propagate(self):
        np = self.np
        args = self.fixture()
        dataset = make_dataset(self.author, **args)
        batch = dataset[0]
        x = batch['x'].numpy()
        # Original class: [missing flag, raw, AND prior view, OR prior view].
        self.assertEqual(x.dtype, np.float32)
        np.testing.assert_array_equal(x[0], [0, 0, 1, 0, 1])
        np.testing.assert_array_equal(x[4], [0, 1, 0, 1, 0])
        np.testing.assert_array_equal(x[1:4, [0, 1, 3]], np.tile([1, .8, .3], (3, 1)).astype(np.float32))
        self.assertAlmostEqual(float(x[5, 3]), .05, places=7)
        self.assertAlmostEqual(float(x[6, 3]), .036, places=7)
        self.assertAlmostEqual(float(x[7, 3]), .144, places=7)
        np.testing.assert_array_equal(x[8], [0, 0, 0, 1, 0])
        self.assertTrue(all(cond is False for _, _, cond in dataset.preds))
        # The training target keeps already-known positive functions; y is not
        # just a new-annotation delta or an exclusion mask.
        np.testing.assert_array_equal(batch['y'].numpy(), args['targets'][0].astype(np.float32))

    def test_device_portable_transform_matches_unchanged_native_loader(self):
        torch = self.torch
        args = self.fixture()
        dataset = make_dataset(self.author, **args)
        actual = collate_rows(self.author, dataset, [0, 1])
        with self.native_cpu_placement():
            loader = self.author.data_module.StackDataLoader(dataset, batch_size=2,
                                                              shuffle=False, num_workers=0)
            expected = next(iter(loader))
        self.assertEqual(set(expected), set(actual))
        for name in ('x', 'goa', 'y'):
            self.assertTrue(torch.equal(actual[name], expected[name]), name)
        for direction in ('all', 'fwd', 'bwd'):
            for index in ('dst', 'src'):
                self.assertTrue(torch.equal(actual[direction][index], expected[direction][index]))
        self.assertEqual(actual['x'].shape, (2, 5, 8))
        self.assertEqual(actual['goa'].shape, (2, 5, 1))
        self.assertTrue(torch.isfinite(actual['x']).all())
        # Missing flags and binary GOA do not receive the logit transform.
        self.assertTrue(set(actual['x'][..., [0, 4]].flatten().tolist()) <= {0., 1.})
        self.assertTrue(set(actual['goa'].flatten().tolist()) <= {0., 1.})

    def test_native_graph_core_exact_forward_and_fixed_term_embedding_axis(self):
        torch = self.torch
        args = self.fixture()
        dataset = make_dataset(self.author, **args)
        batch = collate_rows(self.author, dataset, [0, 1])
        model = make_model(self.author, n_terms=5, terms=args['terms'], seed=99)
        expected = self.author.stacker_module.GCNStacker(2, 1, 5, hidden_size=16,
                                                        n_layers=8, embed_size=8)
        expected.load_state_dict(model.state_dict())
        model.eval(); expected.eval()
        validate_model_axis(model, args['terms'])
        with self.native_cpu_placement(), torch.no_grad():
            observed = model(batch)
            reference = expected(batch)
        self.assertTrue(torch.equal(observed, reference))
        self.assertEqual(observed.shape, (2, 5))
        with self.assertRaisesRegex(ValueError, 'order changed'):
            validate_model_axis(model, tuple(reversed(args['terms'])))
        with self.assertRaisesRegex(ValueError, 'ordered literal'):
            make_model(self.author, n_terms=5)

    def test_zero_layer_is_supported_same_data_no_message_control(self):
        torch = self.torch
        args = self.fixture()
        dataset = make_dataset(self.author, **args)
        batch = collate_rows(self.author, dataset, [0, 1])
        model = make_model(self.author, n_terms=5, terms=args['terms'], n_layers=0, seed=99)
        model.eval()
        empty = dict(batch)
        for direction in ('all', 'fwd', 'bwd'):
            empty[direction] = {'dst': torch.empty(0, dtype=torch.int64),
                                'src': torch.empty(0, dtype=torch.int64)}
        with self.native_cpu_placement(), torch.no_grad():
            self.assertTrue(torch.equal(model(batch), model(empty)))
        self.assertEqual(model.n_layers, 0)
        self.assertEqual(model.embed_size, 8)
        self.assertTrue(hasattr(model, 'act'))  # This control remains a native MLP.

    def test_actual_native_forward_backward_is_finite_on_invented_batch(self):
        torch = self.torch
        args = self.fixture()
        dataset = make_dataset(self.author, **args)
        batch = collate_rows(self.author, dataset, [0, 1])
        model = make_model(self.author, n_terms=5, terms=args['terms'], seed=99)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=0.)
        before = model.input.weight.detach().clone()
        with self.native_cpu_placement():
            optimizer.zero_grad()
            loss = torch.nn.BCEWithLogitsLoss()(model(batch), batch['y'])
            loss.backward()
            torch.nn.utils.clip_grad_value_(model.parameters(), clip_value=1e-1)
            self.assertTrue(torch.isfinite(loss))
            self.assertTrue(all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None))
            optimizer.step()
        self.assertFalse(torch.equal(before, model.input.weight.detach()))

    def test_no_jit_backend_is_explicit_and_missing_numba_does_not_silently_fallback(self):
        self.assertEqual(self.author.source_receipt['jit_backend'], 'none')
        if importlib.util.find_spec('numba') is None:
            with self.assertRaises(ImportError):
                load_author(self.root, jit_backend='numba')
        else:
            compiled = load_author(self.root, jit_backend='numba')
            args = self.fixture()
            a = make_dataset(self.author, **args)[0]['x']
            b = make_dataset(compiled, **args)[0]['x']
            self.np.testing.assert_allclose(a.numpy(), b.numpy(), rtol=0, atol=1e-7)

    def test_invalid_or_ambiguous_source_axes_are_rejected(self):
        args = self.fixture()
        with self.assertRaisesRegex(ValueError, 'term axis'):
            make_dataset(self.author, **{**args, 'terms': tuple(reversed(args['terms']))})
        bad = dict(args)
        bad['predictions'] = list(args['predictions'])
        bad['predictions'][0] = (args['predictions'][0][0], [0, 1, 1])
        with self.assertRaisesRegex(ValueError, 'unique native model-head'):
            make_dataset(self.author, **bad)
        with self.assertRaisesRegex(ValueError, 'GOA row'):
            make_dataset(self.author, **{**args, 'goa_indices': [[1]]})
        with self.assertRaisesRegex(ValueError, 'priors'):
            make_dataset(self.author, **{**args, 'prior_raw': [.2]})
        with self.assertRaisesRegex(ValueError, 'binary training'):
            make_dataset(self.author, **{**args, 'targets': self.np.ones((2, 5)) * .5})


if __name__ == '__main__':
    unittest.main()
