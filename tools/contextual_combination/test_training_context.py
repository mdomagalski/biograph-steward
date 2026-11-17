"""No-label contract and tiny native-training gates for one context profile."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from .training import PARAMETERS, training_author
from .training_context import (
    CONTRACT_NAME, CONTRACT_SHA256, CONTEXT_PARAMETERS, ContextValidationCallback,
    validate_context_contract,
)


class ContextContractTests(unittest.TestCase):
    def fixture(self):
        return {'format': 'biograph-steward.coded-context-training.v1',
                'namespace': 'biological_process', 'seed': 20261115,
                'params': CONTEXT_PARAMETERS,
                'channel_contract': {'file': '/invented/source-only-contract.json', 'sha256': CONTRACT_SHA256}}

    def test_only_predeclared_bpo_architecture_seed_and_native_hypers(self):
        self.assertEqual({k: v for k, v in CONTEXT_PARAMETERS.items() if k not in ('architectures', 'context_profile')},
                         {k: v for k, v in PARAMETERS.items() if k != 'architectures'})
        self.assertEqual(CONTEXT_PARAMETERS['architectures'], [8])
        for key, value in (('namespace', 'molecular_function'), ('seed', 8), ('params', PARAMETERS)):
            cfg = {**self.fixture(), key: value}
            with patch('tools.contextual_combination.training_context.sha') as reader:
                with self.assertRaises(ValueError):
                    validate_context_contract(cfg)
                reader.assert_not_called()

    def test_source_only_contract_pin_is_fixed_before_any_artifact_decoding(self):
        cfg = self.fixture(); cfg['channel_contract']['sha256'] = '0' * 64
        with patch.object(Path, 'read_text') as decode:
            with self.assertRaisesRegex(ValueError, 'qualification contract changed'):
                validate_context_contract(cfg)
            decode.assert_not_called()

    def test_literal40_profile_with_explicit_io_corrections_is_required(self):
        contract = {'name': CONTRACT_NAME, 'channels': ['invented.' + str(i) for i in range(40)],
                    'literal_published38_reproduction': False}
        with patch('tools.contextual_combination.training_context.sha', return_value=CONTRACT_SHA256), \
             patch.object(Path, 'read_text', return_value=json.dumps(contract)):
            self.assertEqual(validate_context_contract(self.fixture()), contract)
        for broken in ({**contract, 'channels': contract['channels'][:-1]},
                       {**contract, 'channels': ['same'] * 40},
                       {**contract, 'literal_published38_reproduction': True}):
            with patch('tools.contextual_combination.training_context.sha', return_value=CONTRACT_SHA256), \
                 patch.object(Path, 'read_text', return_value=json.dumps(broken)):
                with self.assertRaisesRegex(ValueError, 'source-derived forty-channel'):
                    validate_context_contract(self.fixture())

    def test_reordered_context_rejected_before_native_callback_or_scoring(self):
        names = tuple('invented.' + str(i) for i in range(40))
        model = SimpleNamespace(in_goa=40, _biograph_context_channels=names)
        loader = SimpleNamespace(dataset=SimpleNamespace(_biograph_context_channels=tuple(reversed(names))))
        callback = ContextValidationCallback({}, '/unused', {}, None, None)
        with patch('tools.contextual_combination.training.ConsumedValidationCallback.evaluate') as score:
            with self.assertRaisesRegex(ValueError, 'channel identities/order changed'):
                callback.evaluate(model, loader, 'invented')
            score.assert_not_called()


class NativeFortyTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from .test_context_io import ContextIOTests
        ContextIOTests.setUpClass()
        cls.owner = ContextIOTests

    def test_exact_native_train_predict_swa_with_boolean_context_and_original_loader(self):
        from .context_io import BooleanContextDataset
        from .native_stacker import make_model
        fixture = self.owner()
        np, torch = fixture.np, fixture.torch
        args, original, manifest, features, targets = fixture.fixture()
        names = tuple('invented.' + str(i) for i in range(40))
        context = np.zeros((2, 40, 5), dtype=bool); context[:, ::2, 1] = True
        ds = BooleanContextDataset(manifest, features, args['graph'],
            {**manifest, 'channels': list(names)}, context, targets)
        train, swa_class, predict = training_author(fixture.author)
        scores_seen = []
        def invented_callback(model, loader):
            values = predict(model, loader); self.assertEqual(values.shape, (2, 5))
            scores_seen.append(.1 * (len(scores_seen) + 1)); return scores_seen[-1]
        with tempfile.TemporaryDirectory() as temp, fixture.owner().native_cpu_placement(), redirect_stdout(io.StringIO()):
            loader = fixture.author.data_module.StackDataLoader(ds, batch_size=2, shuffle=False, num_workers=0)
            model = make_model(fixture.author, n_terms=5, terms=args['terms'], context_channels=names)
            swa = swa_class(10, path=str(Path(temp) / 'swa'), rewrite=False)
            model, swa, scores = train(model, swa, loader, loader, invented_callback,
                n_ep=2, lr=.001, clip_grad=.1, weight_decay=0.)
            model = swa.set_weights(model, 2, weighted=False)
        self.assertEqual(scores, [.1, .2])
        self.assertTrue(all(bool(torch.isfinite(p).all()) for p in model.parameters()))


if __name__ == '__main__':
    unittest.main()
