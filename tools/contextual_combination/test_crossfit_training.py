"""Invented metadata/source guards; native numerical parity is a separate gate."""
from contextlib import contextmanager
import copy
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import crossfit_training as module


SMALL = {'fit_universe': 10, 'full_positive_cells': 20, 'root_positive_rows': 8,
         'validation_proteins': 2, 'final_proteins': 3, 'model_terms': 3}


class InventedSources:
    def __init__(self, root):
        self.root, self.pins = root, {}
        self.ids = {'fit': ['invented_fit_' + str(i) for i in range(10)],
            'validation': ['invented_val_' + str(i) for i in range(2)],
            'final': ['invented_final_' + str(i) for i in range(3)]}
        self.terms = ['GO:1000001', 'GO:1000002', 'GO:1000003']
        self.channels = ['global.raw', 'global.propagated'] + ['invented.' + str(i) for i in range(38)]
        self.contract = {'channels': self.channels}
        contract = self.put('contract.json', self.contract)
        obo = self.blob('model.obo', b'invented ontology; not a numerical fixture')
        target = self.blob('targets.npy', b'invented targets; native reader mocked')
        mask = self.blob('known.npy', b'invented known mask; native reader mocked')
        old = {'proteins': self.ids['fit'], 'terms': self.terms,
            'targets_file': target['file'], 'known_positive_mask_file': mask['file'],
            'file_pins': {target['file']: target['sha256'], mask['file']: mask['sha256']}}
        original = self.put('original_fit.json', old)
        plan = {'format': module.PLAN_FORMAT, 'arm': module.ARM, 'namespace': module.NAMESPACE,
            'parent_axis': module.PARENTS, 'reference_previously_consumed': True,
            'independent_confirmation': False, 'model': {
                'seed': 20261115, 'params': module.native.CONTEXT_PARAMETERS,
                'fitting_universe': 10, 'root_positive_fitting_rows': 8,
                'validation_proteins': 2, 'final_proteins': 3, 'model_terms': 3,
                'original_full_positive_cells': 20, 'new_fits': 1,
                'native_training_loss_optimizer_and_SWA_unchanged': True,
                'normal_consumed_validation_checkpoint_selection': True},
            'folds': {'n_splits': 5, 'group_key': 'exact_full_sequence_SHA256',
                'method': 'sklearn.model_selection.GroupKFold', 'shuffle': False,
                'priors': 'native_complement_before_root_filter'},
            'new_primary_success_gate': False, 'original_primary_comparison_unchanged': True,
            'graph_pruning_or_app_promotion': False, 'test_outcome_based_model_selection': False}
        plan_spec = self.put('plan.json', plan)
        assignment = [i % 5 for i in range(10)]
        fold_rows = []
        for i in range(5):
            heldout = [j for j, fold in enumerate(assignment) if fold == i]
            complement = [j for j, fold in enumerate(assignment) if fold != i]
            fold_rows.append({'fold_index': i, 'heldout_rows': heldout, 'complement_rows': complement,
                'heldout_proteins': [self.ids['fit'][j] for j in heldout],
                'complement_proteins': [self.ids['fit'][j] for j in complement], 'group_overlap': 0})
        folds = {'format': 'biograph-steward.crossfit-full-sequence-folds.v1',
            'status': 'passed', 'plan_sha256': plan_spec['sha256'], 'fit_proteins': self.ids['fit'],
            'fold_index_by_row': assignment, 'folds': fold_rows,
            'sequence_source': self.blob('sequence_source.json', b'invented sequences'),
            'splitter_runtime': {'sklearn_version': 'invented-fixture',
                'source': self.blob('splitter.py', b'# invented splitter source')}}
        fold_spec = self.put('folds.json', folds)
        priors = []
        for i, fold in enumerate([*fold_rows, None]):
            prior = {'fold_index': i if fold is not None else None,
                'complement_proteins': fold['complement_proteins'] if fold is not None else self.ids['fit'],
                'heldout_proteins': fold['heldout_proteins'] if fold is not None else [],
                'target_source': target, 'crossfit_fold_manifest': fold_spec,
                'computed_before_root_positive_filter': True,
                'files': {name: self.blob('prior_%d_%s.npy' % (i, name), ('invented ' + name).encode())
                          for name in ('raw', 'conditional', 'nulls')}}
            priors.append(self.put('prior_%d.json' % i, prior))
        self.priors = {'folds': priors[:5], 'all_fit': priors[5]}
        contexts, manifests = {}, {}
        for role, proteins in self.ids.items():
            context_file = self.blob(role + '_context.npy', b'invented context array')
            contexts[role] = self.put(role + '_context.json', {
                'format': 'biograph-steward.contextual-boolean-features.v1',
                'proteins': proteins, 'terms': self.terms, 'channels': self.channels,
                'context_file': context_file['file'], 'context_sha256': context_file['sha256'],
                'fresh_final_reference_opened': False})
            feature = self.blob(role + '_features.npy', b'invented feature array')
            meta = {'namespace': module.NAMESPACE, 'proteins': proteins, 'terms': self.terms,
                'parent_axis': module.PARENTS, 'feature_file': feature['file'],
                'features_shape': [len(proteins), 9, 3], 'features_dtype': 'float32',
                'file_pins': {feature['file']: feature['sha256']},
                'crossfit_fold_manifest': fold_spec,
                'feature_prior_receipts': priors[:5] if role == 'fit' else [priors[5]]}
            if role == 'fit': meta.update({k: old[k] for k in ('targets_file', 'known_positive_mask_file', 'file_pins')});meta['file_pins'] = {**old['file_pins'], feature['file']: feature['sha256']}
            manifests[role] = self.put(role + '.json', meta)
        producer = self.blob('producer.py', b'# invented metadata producer; never executed')
        admission = self.put('admission.json', {'status': 'passed', 'qualified': True,
            'plan_sha256': plan_spec['sha256'], 'producer_source': producer, 'counts': SMALL,
            'parent_axis': module.PARENTS, 'original_targets_and_known_mask_bytes_retained': True,
            'new_annotation_source_or_target_cells': False, 'original_fit_manifest': original,
            'original_targets': target, 'original_known_positive_mask': mask,
            'native_full_fit_priors_match_original_vectors_exactly': True})
        source_cfg = self.put('producer_config.json', {'plan': plan_spec,
            'parent_axis': module.PARENTS, 'contexts': contexts, 'model_obo': obo,
            'channel_contract': contract, 'original_fit_manifest': original})
        self.ready = {'format': module.READY_FORMAT, 'status': 'complete', 'plan': plan_spec,
            'namespace': module.NAMESPACE, 'parent_axis': module.PARENTS,
            'configuration': source_cfg, 'producer_source': producer,
            'model_obo': obo, 'channel_contract': contract, 'manifests': manifests, 'contexts': contexts,
            'fold_manifest': fold_spec, 'prior_receipts': self.priors,
            'source_admission': admission, 'input_file_pins': self.pins,
            'no_DeepGO_features_or_heads_read': True,
            'final_reference_labels_read_for_feature_construction': False, **module.FLAGS}
        ready_spec = self.put('ready.json', self.ready, pin=False)
        inner = {'format': 'biograph-steward.coded-context-training.v1',
            'namespace': module.NAMESPACE, 'seed': 20261115,
            'params': copy.deepcopy(module.native.CONTEXT_PARAMETERS),
            'channel_contract': contract, 'author_root': '/invented/never/read', 'model_obo': obo,
            'fit_manifest': manifests['fit']['file'], 'validation_manifest': manifests['validation']['file'],
            'fit_context_manifest': contexts['fit']['file'], 'validation_context_manifest': contexts['validation']['file'],
            'input_file_pins': self.pins, 'evaluation': {'role': module.VALIDATION_ROLE}}
        sources = {}
        for key, name in module.SOURCE_MODULES.items():
            filename = importlib.import_module(name).__file__
            sources[key] = {'file': filename, 'sha256': module.sha(filename)}
        sources['crossfit_prepare'] = producer
        self.cfg = {'format': module.CONFIG_FORMAT, 'plan': plan_spec,
            'source_readiness': ready_spec, 'native_training_configuration': inner,
            'qualified_source_pins': sources}
        self.original_spec, self.obo_spec = original, obo

    def blob(self, name, value):
        path = self.root / name; path.write_bytes(value)
        spec = {'file': str(path), 'sha256': module.sha(path)}; self.pins[str(path)] = spec['sha256']; return spec

    def put(self, name, value, *, pin=True):
        path = self.root / name; path.write_text(json.dumps(value, sort_keys=True))
        spec = {'file': str(path), 'sha256': module.sha(path)}
        if pin: self.pins[str(path)] = spec['sha256']
        return spec

    def save_ready(self):
        self.cfg['source_readiness'] = self.put('ready.json', self.ready, pin=False)


@contextmanager
def invented():
    with tempfile.TemporaryDirectory() as temp:
        fixture = InventedSources(Path(temp))
        proof = {'native_input_checks_performed': False, 'full_positive_cells': 20,
                 'root_positive_rows': 8, 'role_counts': {'fit': 10, 'validation': 2, 'final': 3}}
        with patch.object(module, 'COUNTS', SMALL), \
             patch.object(module, 'MODEL_OBO_SHA256', fixture.obo_spec['sha256']), \
             patch.object(module, 'ORIGINAL_FIT_MANIFEST_SHA256', fixture.original_spec['sha256']), \
             patch.object(module.native, 'validate_context_contract', return_value=fixture.contract), \
             patch.object(module, 'validate_validation_sources') as validation, \
             patch.object(module, 'native_input_admission', return_value=proof) as arrays:
            yield fixture, arrays, validation


class AdmissionTests(unittest.TestCase):
    def test_extra_reference_configuration_fails_before_any_file_is_opened(self):
        cfg = {'format': module.CONFIG_FORMAT, 'plan': {}, 'source_readiness': {},
               'native_training_configuration': {}, 'qualified_source_pins': {},
               'fresh_reference': '/must/not/read'}
        with patch.object(module, 'pinned', side_effect=AssertionError('must not read')) as reader:
            with self.assertRaisesRegex(ValueError, 'allowlisted'): module.prepare_inputs(cfg)
            reader.assert_not_called()

    def test_valid_metadata_uses_complement_priors_and_keeps_consumed_status(self):
        with invented() as (f, arrays, validation):
            data = module.prepare_inputs(f.cfg)
            arrays.assert_called_once(); validation.assert_called_once_with(f.cfg['native_training_configuration']['evaluation'])
            self.assertEqual(data['proof']['fitting_feature_complement_counts'], [8] * 5)
            self.assertEqual(data['proof']['validation_and_final_feature_prior_count'], 10)
            self.assertTrue(data['proof']['reference_previously_consumed'])
            self.assertFalse(data['proof']['independent_confirmation'])
            self.assertIn('not verified biological or PU class priors', data['proof']['prior_semantics'])

    def test_plan_cannot_change_batch_budget_or_add_test_selection(self):
        with invented() as (f, arrays, _):
            plan = module.pinned(f.cfg['plan']); plan['model']['params']['batch_size'] = 16
            f.cfg['plan'] = f.put('plan.json', plan)
            with self.assertRaisesRegex(ValueError, 'training budget'): module.prepare_inputs(f.cfg)
            arrays.assert_not_called()

    def test_renamed_or_reordered_parent_is_rejected_before_native_arrays(self):
        with invented() as (f, arrays, _):
            f.ready['parent_axis'] = ['localplus', 'deepgose']; f.save_ready()
            with self.assertRaisesRegex(ValueError, 'named-parent'): module.prepare_inputs(f.cfg)
            arrays.assert_not_called()

    def test_final_outcome_array_cannot_enter_the_feature_manifest(self):
        with invented() as (f, arrays, _):
            spec = f.ready['manifests']['final']; meta = module.pinned(spec)
            meta['targets_file'] = '/invented/outcome.npy'
            f.ready['manifests']['final'] = f.put('final.json', meta); f.save_ready()
            with self.assertRaisesRegex(ValueError, 'no outcome'): module.prepare_inputs(f.cfg)
            arrays.assert_not_called()

    def test_changed_cache_bytes_are_rejected_before_array_read(self):
        with invented() as (f, arrays, _):
            meta = module.pinned(f.ready['manifests']['fit']); Path(meta['feature_file']).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'input changed'): module.prepare_inputs(f.cfg)
            arrays.assert_not_called()

    def test_source_helper_hash_drift_is_rejected(self):
        with invented() as (f, arrays, _):
            f.cfg['qualified_source_pins']['training_context']['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'executable source'): module.prepare_inputs(f.cfg)
            arrays.assert_not_called()

    def test_unpassed_source_admission_cannot_reach_training_arrays(self):
        with invented() as (f, arrays, _):
            admission = module.pinned(f.ready['source_admission']); admission['qualified'] = False
            f.ready['source_admission'] = f.put('admission.json', admission); f.save_ready()
            with self.assertRaisesRegex(ValueError, 'did not admit'): module.prepare_inputs(f.cfg)
            arrays.assert_not_called()

    def test_heldout_row_cannot_be_added_to_its_complement(self):
        with invented() as (f, _, _):
            folds = module.pinned(f.ready['fold_manifest']); folds['folds'][0]['complement_rows'].append(0)
            f.ready['fold_manifest'] = f.put('folds.json', folds)
            fit = module.pinned(f.ready['manifests']['fit'])
            with self.assertRaisesRegex(ValueError, 'fold rows'):
                module.validate_folds_and_priors(f.ready, fit, f.pins, f.cfg['plan']['sha256'])

    def test_prior_cannot_include_its_own_heldout_protein(self):
        with invented() as (f, _, _):
            prior = module.pinned(f.priors['folds'][0]); prior['complement_proteins'][0] = prior['heldout_proteins'][0]
            f.priors['folds'][0] = f.put('prior_0.json', prior)
            fit = module.pinned(f.ready['manifests']['fit'])
            with self.assertRaisesRegex(ValueError, 'exclude its own'):
                module.validate_folds_and_priors(f.ready, fit, f.pins, f.cfg['plan']['sha256'])


def fake_native_train(cfg, output):
    output.mkdir(); module.write_json(output / 'configuration.json', cfg)
    checkpoint = output / 'weights.pth'; checkpoint.write_bytes(b'invented model bytes')
    selected = {}
    for i in range(3):
        p = output / ('selected_' + str(i) + '.pth'); p.write_bytes(('invented state ' + str(i)).encode()); selected[str(p)] = module.sha(p)
    fit = json.loads(Path(cfg['fit_manifest']).read_text())
    context = json.loads(Path(cfg['fit_context_manifest']).read_text())
    meta = {'n_layers': 8, 'in_goa': 40, 'in_models': 2, 'epoch_scores': [.2] * 20,
        'supervised_fitting_rows': 8, 'prior_universe_count': 10, 'swa_parameter_parity_max_abs': 0.,
        'fresh_final_reference_opened': False, 'checkpoint_file': str(checkpoint),
        'checkpoint_sha256': module.sha(checkpoint), 'selected_swa_sources': selected,
        'model_terms_sha256': module.axis_sha(fit['terms']), 'context_channels': context['channels'],
        'context_channels_sha256': module.axis_sha(context['channels']),
        'postprocessing': module.PARAMETERS['postprocessing'], 'validation_ordinary_micro_fmax': .2,
        'configuration_sha256': module.sha(output / 'configuration.json'),
        'fit_manifest_sha256': module.sha(cfg['fit_manifest']),
        'validation_manifest_sha256': module.sha(cfg['validation_manifest']),
        'fit_context_manifest_sha256': module.sha(cfg['fit_context_manifest']),
        'validation_context_manifest_sha256': module.sha(cfg['validation_context_manifest'])}
    module.write_json(output / 'model.json', meta)
    return {'status': 'complete', 'model_file': str(output / 'model.json'),
            'model_metadata_sha256': module.sha(output / 'model.json')}


class NativeDelegationTests(unittest.TestCase):
    def test_native_training_configuration_stays_unchanged_and_outer_status_is_truthful(self):
        with invented() as (f, _, _), patch.object(module.native, 'train_context_model', side_effect=fake_native_train) as trainer:
            original = copy.deepcopy(f.cfg['native_training_configuration'])
            result = module.train_prepared(f.cfg, f.root / 'training')
            self.assertEqual(trainer.call_args.args[0], original)
            self.assertEqual(json.loads((f.root / 'training/native_training/configuration.json').read_text()), original)
            self.assertTrue(result['consumed_validation_used_for_SWA'])
            self.assertTrue(result['reference_previously_consumed'])
            self.assertFalse(result['independent_confirmation'])
            self.assertNotIn('fresh_final_reference_opened', result)
            self.assertFalse(result['final_reference_metrics_computed'])

    def test_forecast_keeps_inner_hash_bound_receipt_and_separate_honest_outer_metadata(self):
        with invented() as (f, _, _), patch.object(module.native, 'train_context_model', side_effect=fake_native_train):
            module.train_prepared(f.cfg, f.root / 'training')
            model_spec = {'file': str(f.root / 'training/model.json'), 'sha256': module.sha(f.root / 'training/model.json')}
            def export(cfg, *, model_metadata, feature_manifest, context_manifest, output):
                output.mkdir(); raw = output / 'raw.npy'; raw.write_bytes(b'invented raw forecast')
                soft = output / 'soft.npy'; soft.write_bytes(b'invented soft forecast')
                result = {'proteins': f.ids['final'], 'terms': f.terms,
                    'prediction_file': str(soft), 'prediction_sha256': module.sha(soft),
                    'raw_prediction_file': str(raw), 'raw_prediction_sha256': module.sha(raw),
                    'model_metadata_sha256': module.sha(model_metadata),
                    'feature_manifest_sha256': module.sha(feature_manifest),
                    'context_manifest_sha256': module.sha(context_manifest),
                    'fresh_final_reference_opened': False, 'final_reference_labels_read_for_forecasting': False}
                module.write_json(output / 'predictions.json', result); return result
            with patch.object(module.native, 'export_context_predictions', side_effect=export) as exporter:
                result = module.forecast_prepared(f.cfg, model_spec, f.root / 'forecast')
            self.assertEqual(exporter.call_args.args[0], f.cfg['native_training_configuration'])
            self.assertTrue(json.loads((f.root / 'forecast/native_forecast/predictions.json').read_text())['fresh_final_reference_opened'] is False)
            self.assertEqual(module.sha(f.root / 'forecast/native_forecast/predictions.json'), result['native_forecast_metadata']['sha256'])
            self.assertNotIn('fresh_final_reference_opened', result)
            self.assertEqual(result['parent_axis'], module.PARENTS)
            self.assertTrue(result['reference_previously_consumed'])
            self.assertFalse(result['forecast_phase_scientific_metrics_computed'])
            self.assertFalse(result['final_reference_metrics_computed'])


if __name__ == '__main__': unittest.main()
