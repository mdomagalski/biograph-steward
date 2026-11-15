# SPDX-License-Identifier: GPL-3.0-only
"""Invented-only provenance, complete-history and paired-draw regression tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from . import crossfit_assessment as module
from .assessment import REQUIRED_ARMS


ORIGINAL_NAMES = REQUIRED_ARMS + ('coded_context_gcn',)
OLD_NAMES = ORIGINAL_NAMES + module.PRIOR_ARMS + module.REFIT_ARMS


def forecast():
    return {'format': 'biograph-steward.crossfit-context-forecast.v1', 'status': 'complete',
        'arm': module.ARM, 'namespace': module.NS, 'parent_axis': module.PARENTS, 'plan_sha256': 'plan',
        'development_after_reference_opening': True, 'reference_previously_consumed': True,
        'independent_confirmation': False, 'final_reference_labels_read_for_forecasting': False,
        'final_reference_metrics_computed': False, 'forecast_phase_scientific_metrics_computed': False,
        'consumed_validation_used_for_SWA': True, 'validation_metric_role': module.VALIDATION_ROLE,
        'no_DeepGO_features_or_heads_read': True, 'models_fitted': True,
        'automatic_graph_or_app_promotion': False, 'in_models': 2, 'in_goa': 40, 'n_layers': 8,
        'upper_roundoff_tolerance': 0.}


class BoundaryTests(unittest.TestCase):
    def test_authorization_precedes_any_file_access(self):
        cfg = {'format': 'biograph-steward.crossfit-assessment.v1',
            'parent_authorized_consumed_reference_assessment': False,
            'development_followup_on_consumed_reference': True, 'independent_confirmation': False}
        with patch.object(module, 'pinned_json', side_effect=AssertionError('must not read')) as reader:
            with self.assertRaisesRegex(ValueError, 'authorization'): module.prepare_inputs(cfg)
            reader.assert_not_called()
        cfg['parent_authorized_consumed_reference_assessment'] = True
        cfg['independent_confirmation'] = True
        with self.assertRaisesRegex(ValueError, 'no independent'): module.authorization(cfg)

    def test_consumed_validation_metrics_are_allowed_but_fresh_or_final_claims_rejected(self):
        meta = forecast(); meta['current_validation_metric_computed'] = True
        module.validate_forecast_provenance(meta, 'plan')
        for key, value in [('independent_confirmation', True), ('final_reference_metrics_computed', True),
                           ('final_reference_labels_read_for_forecasting', True), ('models_fitted', False),
                           ('consumed_validation_used_for_SWA', False), ('upper_roundoff_tolerance', .00001),
                           ('in_models', 3), ('parent_axis', ['localplus', 'deepgose']),
                           ('automatic_graph_or_app_promotion', True)]:
            changed = copy.deepcopy(meta); changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.validate_forecast_provenance(changed, 'plan')

    def test_exact_plan_retains_all_six_cells_and_no_new_gate(self):
        plan = json.loads(Path(__file__).with_name('crossfit_protocol.json').read_text())
        module.validate_plan_evaluation(plan)
        for key, value in [('complete_contrast_rows', 132), ('earlier_methods', 21),
                           ('views', ['native']), ('bootstrap_seed', 20261115)]:
            changed = copy.deepcopy(plan); changed['evaluation'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'six-cell'):
                module.validate_plan_evaluation(changed)
        changed = copy.deepcopy(plan); changed['new_primary_success_gate'] = True
        with self.assertRaises(ValueError): module.validate_plan_evaluation(changed)

    def cells(self):
        base = {'status': 'evaluated', 'methods': {name: {'native_micro_fmax': .2} for name in ORIGINAL_NAMES}}
        annotation = copy.deepcopy(base)
        annotation['methods'].update({name: {'native_micro_fmax': .3} for name in module.PRIOR_ARMS})
        previous = copy.deepcopy(annotation)
        previous['methods'].update({name: {'native_micro_fmax': .4} for name in module.REFIT_ARMS})
        return base, annotation, previous

    def test_history_requires_every_earlier_method_and_literal_point(self):
        values = self.cells(); self.assertEqual(len(module.old_cell_chain(*values)), 22)
        for index, name in [(0, ORIGINAL_NAMES[0]), (1, module.PRIOR_ARMS[0]), (2, module.REFIT_ARMS[0])]:
            changed = copy.deepcopy(values); del changed[index]['methods'][name]
            with self.subTest(index=index), self.assertRaises(ValueError): module.old_cell_chain(*changed)
        changed = copy.deepcopy(values); changed[2]['methods'][ORIGINAL_NAMES[0]]['native_micro_fmax'] = .9
        with self.assertRaisesRegex(ValueError, 'readout changed'): module.old_cell_chain(*changed)

    def test_counts_route_all17_plus2_plus3_to_their_immutable_roots(self):
        cfg = {'original_results_directory': 'original', 'annotation_prior_results_directory': 'prior',
               'previous_development_results_directory': 'refit'}
        reports = ({'name': 'original'}, {'name': 'prior'}, {'name': 'refit'})
        routes = [module.earlier_count_source(cfg, *reports, name) for name in OLD_NAMES]
        self.assertEqual([sum(path == root for path, _ in routes) for root in ('original', 'prior', 'refit')], [17, 2, 3])
        for name, (path, report) in zip(OLD_NAMES, routes): self.assertEqual(path, report['name'])


def boot(names):
    return {'draws': 2000, 'seed': 20261113, 'raw_proteins': 3, 'ordinary_only': True,
        'shared_protein_samples_across_all_arms': True,
        'scores': {name: {'bootstrap_Fmax': [.2] * 2000, 'bootstrap_mean': .2,
            'bootstrap_95_percentile_interval': [.2, .2]} for name in names}, 'comparisons': []}


def earlier_boot():
    old = boot(OLD_NAMES)
    for candidate, comparator in module.required_pairs(ORIGINAL_NAMES + module.PRIOR_ARMS):
        old['comparisons'].append({'candidate': candidate, 'comparator': comparator,
            'difference_draws': [0.] * 2000, 'difference_mean': 0.,
            'paired_95_percentile_interval': [0., 0.], 'fraction_draws_above_zero': 0.,
            'interpretation': 'literal earlier interpretation'})
    return old


class PairedDrawTests(unittest.TestCase):
    def test_exact_saved_scores_and32_contrasts_preserved_with22_new_contrasts(self):
        old = earlier_boot(); new = boot([module.ARM, module.ANCHOR]); before = copy.deepcopy(old)
        new['scores'][module.ARM] = {'bootstrap_Fmax': [.1] * 2000, 'bootstrap_mean': .1,
            'bootstrap_95_percentile_interval': [.1, .1]}
        result = module.joined_bootstrap(old, new)
        self.assertEqual(old, before)
        self.assertEqual(result['comparisons'][:32], old['comparisons'])
        self.assertEqual({k: result['scores'][k] for k in old['scores']}, old['scores'])
        self.assertEqual(len(result['comparisons']), 54); self.assertEqual(len(result['scores']), 23)
        self.assertEqual({(r['candidate'], r['comparator']) for r in result['comparisons'][32:]},
                         {(module.ARM, name) for name in OLD_NAMES})
        self.assertTrue(all(r['paired_95_percentile_interval'][1] < 0 for r in result['comparisons'][32:]))
        self.assertFalse(result['new_success_gate_or_model_selection']); self.assertFalse(result['independent_confirmation'])

    def test_missing_old_peak_pair_design_or_comparison_fails_closed(self):
        changes = [lambda o, n: o['scores'].pop(OLD_NAMES[0]),
            lambda o, n: o['comparisons'].pop(), lambda o, n: o['comparisons'].append(o['comparisons'][0]),
            lambda o, n: n.update(seed=1), lambda o, n: n.update(raw_proteins=4),
            lambda o, n: n['scores'][module.ANCHOR]['bootstrap_Fmax'].__setitem__(4, .3),
            lambda o, n: n['scores'][module.ARM]['bootstrap_Fmax'].__setitem__(4, float('nan'))]
        for mutation in changes:
            old = earlier_boot(); new = boot([module.ARM, module.ANCHOR]); mutation(old, new)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): module.joined_bootstrap(old, new)

    def test_native_anchor_replay_uses_the_same_whole_protein_draws(self):
        # Invented sufficient statistics, not real study rows or reference labels.
        ordinary = np.zeros((3, 2, 6), dtype=np.float64)
        ordinary[:, :, 0] = [[1, 0], [2, 1], [1, 1]]
        ordinary[:, :, 1] = [[1, 2], [0, 1], [1, 1]]
        ordinary[:, :, 2] = [[1, 0], [1, 0], [0, 0]]
        ordinary[:, :, 3] = ordinary[:, :, 1]
        row = {'ids': np.array(['fixture_a', 'fixture_b', 'fixture_c']), 'tau': np.array([.1, .2]), 'ordinary': ordinary}
        first = module.bootstrap_contrast({module.ANCHOR: row, 'fixture_comparator': row}, module.ANCHOR)
        replay = module.bootstrap_contrast({module.ARM: row, module.ANCHOR: row}, module.ARM)
        self.assertEqual(first['scores'][module.ANCHOR], replay['scores'][module.ANCHOR])
        self.assertEqual(replay['draws'], 2000); self.assertEqual(replay['seed'], 20261113)

    def test_original_count_helper_rejects_missing_source_changed_bytes_or_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            relative = 'native/PK/bp_fixture_counts.npz'; path = Path(directory) / relative
            path.parent.mkdir(parents=True)
            ids = np.array(['fixture_a', 'fixture_b']); tau = np.array([.1, .2])
            np.savez_compressed(path, ids=ids, tau=tau, ordinary=np.zeros((2, 2, 6)), eligible=np.ones(2, dtype=bool))
            report = {'files': {relative: module.file_sha256(path)}}
            module.load_original_counts(directory, report, 'native', 'PK', 'bp', 'fixture', ids, tau)
            with self.assertRaisesRegex(ValueError, 'pairing frame'):
                module.load_original_counts(directory, report, 'native', 'PK', 'bp', 'fixture', ids[::-1], tau)
            with self.assertRaisesRegex(ValueError, 'missing'):
                module.load_original_counts(directory, {'files': {}}, 'native', 'PK', 'bp', 'fixture', ids, tau)
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'changed'):
                module.load_original_counts(directory, report, 'native', 'PK', 'bp', 'fixture', ids, tau)


class ProducerLinkageTests(unittest.TestCase):
    def fixture(self):
        spec = lambda name: {'file': name, 'sha256': name + '_sha'}
        qualified = {name: spec(name + '.py') for name in module.SOURCE_MODULES}
        cfg = {'qualified_source_pins': qualified, 'plan': spec('plan')}; cfg['plan']['sha256'] = 'plan'
        meta = forecast(); meta.update(model_metadata=spec('model.json'), model_metadata_sha256='model.json_sha',
            source_configuration=spec('train.json'), source_readiness=spec('ready.json'),
            producer_source=qualified['crossfit_training'], producer_code_sha256=qualified['crossfit_training']['sha256'],
            native_model_metadata=spec('native/model.json'), native_forecast_metadata=spec('native/predictions.json'),
            proteins=['fixture_a'], terms=['fixture_term'] * module.COUNTS['model_terms'],
            prediction_file='soft.npy', prediction_sha256='soft.npy_sha', raw_prediction_file='raw.npy', raw_prediction_sha256='raw.npy_sha')
        proof = {'source_admission': spec('admission.json'), 'fold_manifest': spec('folds.json'),
            'parent_axis': module.PARENTS, 'no_DeepGO_features_or_heads_read': True,
            'final_reference_labels_read_for_fitting': False, 'final_reference_labels_read_for_forecasting': False}
        meta['source_admission'] = proof
        model = {key: copy.deepcopy(meta[key]) for key in ('arm', 'namespace', 'parent_axis', 'plan_sha256',
            'source_readiness', 'producer_source', 'producer_code_sha256', 'development_after_reference_opening',
            'reference_previously_consumed', 'independent_confirmation', 'consumed_validation_used_for_SWA',
            'validation_metric_role', 'final_reference_metrics_computed', 'automatic_graph_or_app_promotion',
            'source_admission', 'in_models', 'in_goa', 'n_layers', 'native_model_metadata')}
        model.update(format='biograph-steward.crossfit-context-model.v1', status='complete',
            configuration_sha256='train.json_sha', qualified_source_pins=qualified,
            final_reference_labels_read_for_fitting=False, checkpoint_file='weights.pth', checkpoint_sha256='weights.pth_sha')
        ready = {'format': 'biograph-steward.crossfit-graph-prevalence-features.v1', 'status': 'complete',
            'plan': cfg['plan'], 'producer_source': qualified['crossfit_prepare'], 'parent_axis': module.PARENTS,
            'namespace': module.NS, 'final_reference_labels_read_for_feature_construction': False,
            'input_file_pins': {'feature.npy': 'feature.npy_sha'}, 'source_admission': spec('admission.json'),
            'fold_manifest': spec('folds.json'), 'channel_contract': spec('channels.json'),
            'manifests': {'fit': spec('fit.json'), 'final': spec('final.json')}, 'contexts': {'final': spec('context.json')}}
        native = {'checkpoint_file': 'weights.pth', 'checkpoint_sha256': 'weights.pth_sha', 'configuration_sha256': 'native_cfg_sha'}
        exported = {key: meta[key] for key in ('prediction_file', 'prediction_sha256', 'raw_prediction_file', 'raw_prediction_sha256')}
        exported.update(model_metadata_sha256='native/model.json_sha', feature_manifest_sha256='final.json_sha',
            context_manifest_sha256='context.json_sha')
        docs = {'train.json': {'format': 'biograph-steward.crossfit-context-training.v1', 'plan': cfg['plan'],
            'source_readiness': meta['source_readiness'], 'qualified_source_pins': qualified,
            'native_training_configuration': {'fixture': True}}, 'ready.json': ready, 'model.json': model,
            'admission.json': {'status': 'passed', 'qualified': True, 'plan_sha256': 'plan', 'counts': module.COUNTS,
                'producer_source': qualified['crossfit_prepare'], 'native_full_fit_priors_match_original_vectors_exactly': True,
                'original_targets_and_known_mask_bytes_retained': True, 'new_annotation_source_or_target_cells': False},
            'fit.json': {'terms': meta['terms']}, 'channels.json': {'channels': ['fixture']},
            'native/model.json': native, 'native/configuration.json': {'fixture': True},
            'native/predictions.json': exported, 'final.json': {'proteins': meta['proteins']}}
        return copy.deepcopy((cfg, meta, docs))

    def check(self, cfg, meta, docs):
        with patch.object(module, 'pinned_json', side_effect=lambda spec: docs[spec['file']]), \
             patch.object(module, 'file_sha256', side_effect=lambda path: str(path) + '_sha'), \
             patch('tools.contextual_combination.crossfit_training.check_source_pins'), \
             patch('tools.contextual_combination.crossfit_training.validate_native_model'):
            return module.validate_producer_bindings(cfg, meta)

    def test_completed_producer_model_and_native_export_are_bound(self):
        values = self.fixture()
        self.assertTrue(self.check(*values)['completed_and_qualified_producer_linkage_verified'])

    def test_stale_or_unrelated_completed_files_fail_closed(self):
        mutations = [lambda c, m, d: d['model.json'].update(status='partial'),
            lambda c, m, d: d['admission.json'].update(qualified=False),
            lambda c, m, d: d['ready.json'].update(plan={'file': 'other', 'sha256': 'other'}),
            lambda c, m, d: d['ready.json']['input_file_pins'].update({'feature.npy': 'changed'}),
            lambda c, m, d: d['native/predictions.json'].update(context_manifest_sha256='other'),
            lambda c, m, d: d['native/configuration.json'].update(fixture=False),
            lambda c, m, d: d['native/model.json'].update(checkpoint_sha256='other'),
            lambda c, m, d: d['model.json'].update(final_reference_labels_read_for_fitting=True),
            lambda c, m, d: d['model.json'].update(consumed_validation_used_for_SWA=False),
            lambda c, m, d: m.update(raw_prediction_sha256='changed')]
        for mutation in mutations:
            cfg, meta, docs = self.fixture(); mutation(cfg, meta, docs)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): self.check(cfg, meta, docs)


if __name__ == '__main__': unittest.main()
