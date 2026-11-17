"""Invented source-only controls: no biological labels or forecasts are read."""
import copy
from contextlib import ExitStack
import gzip
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from . import current_refit_controls as module


def scope():
    return {'format': 'biograph-steward.current-refit-source-controls.v1',
        'development_after_reference_opening': True, 'reference_previously_consumed': True,
        'fresh_final_reference_claimed': False, 'independent_confirmation': False,
        'namespace': 'biological_process', 'forecast_role': 'final',
        'expected_final_count': 3300, 'expected_fit_count': 4040,
        'arms': list(module.ARMS), 'nonexperimental_LocalPlus_seeds': False,
        'old_validation_or_T1_labels_allowed': False, 'model_or_threshold_selection': False}


class SourceScopeTests(unittest.TestCase):
    def test_fresh_validation_non_BP_or_extra_policy_is_rejected_before_source_access(self):
        module.validate_scope(scope())
        for key, bad in (('fresh_final_reference_claimed', True), ('reference_previously_consumed', False),
                ('independent_confirmation', True), ('forecast_role', 'validation'),
                ('namespace', 'molecular_function'), ('expected_final_count', 3299),
                ('nonexperimental_LocalPlus_seeds', True), ('old_validation_or_T1_labels_allowed', True),
                ('model_or_threshold_selection', True)):
            cfg = scope(); cfg[key] = bad
            with self.subTest(key=key), patch.object(module, '_pin', side_effect=AssertionError('no source read')):
                with self.assertRaises(ValueError): module.admit_sources(cfg)

    def test_complete_3300_and_4040_order_is_retained_and_intersection_rejected(self):
        final = tuple('INVENTED_FINAL_' + str(i) for i in range(3300))
        fit = tuple('INVENTED_FIT_' + str(i) for i in range(4040))
        self.assertEqual(module.validate_identity_frames(final, fit), (final, fit))
        with self.assertRaisesRegex(ValueError, 'overlap'):
            module.validate_identity_frames(final, (final[0],) + fit[1:])
        with self.assertRaisesRegex(ValueError, 'complete unique'):
            module.validate_identity_frames(final[:-1], fit)

    def test_reference_path_is_rejected_before_hash(self):
        with patch.object(module, 'file_sha256', side_effect=AssertionError('must not hash')):
            with self.assertRaisesRegex(ValueError, 'reference or validation'):
                module._pin({'file': '/invented/validation_labels.tsv', 'sha256': '0' * 64})


class PositiveUnionTests(unittest.TestCase):
    def test_three_curated_sources_preserve_candidate_old_axis_ancestor_and_empty_rows(self):
        retained = {'P1': [('BPO', 'GO:1000001')], 'P2': [], 'P3': [('MFO', 'GO:2000001')], 'P4': []}
        current = {'P1': [('P', 'GO:1000002')], 'P2': [('P', 'GO:1000002')], 'P3': [], 'P4': []}
        # GO:1000003 stands for a candidate's original-axis ancestor absent
        # from the already propagated current-source seed table.
        candidate = {'P2': [('BPO', 'GO:1000003')], 'P3': []}
        combined, audit = module.union_bp_sources(retained, current, candidate, ('P2', 'P3'))
        self.assertEqual(set(combined), set(retained))
        self.assertEqual(set(combined['P1']), {('BPO', 'GO:1000001'), ('BPO', 'GO:1000002')})
        self.assertEqual(set(combined['P2']), {('BPO', 'GO:1000002'), ('BPO', 'GO:1000003')})
        self.assertEqual(combined['P3'], []); self.assertEqual(combined['P4'], [])
        self.assertEqual(audit['retained_memberships_removed'], 0)
        self.assertFalse(audit['nonexperimental_annotations_seeded_into_LocalPlus'])
        self.assertFalse(audit['new_alias_mapping_or_ontology_propagation'])

    def test_incomplete_fit_or_graph_frame_and_unknown_aspects_fail_closed(self):
        retained = {'P1': [('BPO', 'GO:1000001')], 'P2': []}
        current = {'P1': [], 'P2': []}
        with self.assertRaisesRegex(ValueError, 'entire explicit fitting'):
            module.union_bp_sources(retained, current, {}, ('P2',))
        with self.assertRaisesRegex(ValueError, 'exact graph frame'):
            module.union_bp_sources(retained, {'P1': []}, {'P2': []}, ('P2',))
        with self.assertRaisesRegex(ValueError, 'aspect tag'):
            module.bp_rows({'P1': [('guessed', 'GO:1000001')]})

    def test_full_positive_matrix_is_not_root_filtered_or_replaced(self):
        terms = ('GO:0008150', 'GO:1000001', 'GO:1000002')
        original = np.array([[1, 1, 0], [0, 0, 0], [1, 0, 0]], dtype=np.float32)
        new = original.copy(); new[1] = [1, 0, 1]
        known = original.astype(bool)
        rows = module.fit_repertoire(('P1', 'P2', 'P3'), terms, new, original, known)
        self.assertEqual(set(rows), {'P1', 'P2', 'P3'})
        self.assertIn(('BPO', 'GO:1000002'), rows['P2'])
        broken = new.copy(); broken[0, 1] = 0
        with self.assertRaisesRegex(ValueError, 'removed an original full'):
            module.fit_repertoire(('P1', 'P2', 'P3'), terms, broken, original, known)

    def test_literal_binary_prior_preserves_both_vocabularies_aliases_and_all_zero_rows(self):
        proteins = ('P2', 'P1', 'P3')
        prior_terms = ('GO:1000002', 'GO:1999999')
        prior = np.array([[1, 0], [0, 1], [0, 0]], dtype=np.float64)
        historical_terms = ('GO:1000001', 'GO:1000002', 'GO:1000003')
        rows = {'P1': [('BPO', 'GO:1000001')], 'P2': [('BPO', 'GO:1000002')], 'P3': []}
        terms, result, audit = module.binary_prior_union(proteins, prior_terms, prior, historical_terms, rows)
        self.assertEqual(terms, ('GO:1000002', 'GO:1999999', 'GO:1000001', 'GO:1000003'))
        np.testing.assert_array_equal(result, [[1, 0, 0, 0], [0, 1, 1, 0], [0, 0, 0, 0]])
        self.assertEqual(result.dtype, prior.dtype)
        self.assertEqual(audit['binary_annotation_score'], 1)
        self.assertFalse(audit['new_alias_mapping_or_ontology_propagation'])
        self.assertEqual(audit['source_positive_memberships_removed'], 0)

    def test_nonbinary_prior_missing_query_and_clipped_vocabulary_are_rejected(self):
        args = (('P1',), ('GO:1000001',))
        with self.assertRaisesRegex(ValueError, 'binary positive'):
            module.binary_prior_union(*args, np.array([[.99]]), ('GO:1000002',), {'P1': []})
        with self.assertRaisesRegex(ValueError, 'every literal final target'):
            module.binary_prior_union(*args, np.ones((1, 1)), ('GO:1000002',), {})
        with self.assertRaisesRegex(ValueError, 'outside its complete source vocabulary'):
            module.binary_prior_union(*args, np.ones((1, 1)), ('GO:1000002',),
                                      {'P1': [('BPO', 'GO:1000003')]})


class CompleteInventedContractTests(unittest.TestCase):
    """Exercise real source/config schemas with full3300/4040 invented axes."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name); self.stack = ExitStack(); self.addCleanup(self.stack.close)
        def save(name, value):
            path = self.root / name
            if name.endswith('.gz'):
                with gzip.open(path, 'wt') as stream: json.dump(value, stream)
            else: path.write_text(json.dumps(value))
            return {'file': str(path), 'sha256': module.file_sha256(path)}
        self.save = save
        fit = ['FIT' + str(i) for i in range(4040)]; final = ['FINAL' + str(i) for i in range(3300)]
        ids = self.root / 'fit_ids.txt'; ids.write_text('\n'.join(fit) + '\n')
        ids_spec = {'file': str(ids), 'sha256': module.file_sha256(ids)}
        terms = ['GO:0008150', 'GO:1000001']; graph_ids = fit + final[:2]
        graph = save('graph.json.gz', {'nodes': ['UniProtKB:' + p for p in graph_ids], 'pairs': []})
        old = np.zeros((4040, 2), dtype=np.float32); old[0] = 1
        old_known = np.zeros_like(old, dtype=bool); old_known[0, 0] = True
        new = old.copy(); new[1] = 1
        def array(name, value):
            path = self.root / name; np.save(path, value, allow_pickle=False); return str(path)
        old_file = array('old_targets.npy', old); known_file = array('old_known.npy', old_known)
        new_file = array('union_targets.npy', new); mask_file = array('full_retention.npy', old.astype(bool))
        self.mask_file = Path(mask_file)
        old_meta = {'proteins': fit, 'terms': terms, 'targets_file': old_file,
            'known_positive_mask_file': known_file, 'file_pins': {p: module.file_sha256(p) for p in (old_file, known_file)}}
        old_spec = save('original_fit_manifest.json', old_meta)
        candidate = {**old_meta, 'namespace': 'biological_process', 'targets_file': new_file,
            'known_positive_mask_file': mask_file, 'file_pins': {p: module.file_sha256(p) for p in (new_file, mask_file)},
            'target_semantics': 'known_T0_union_allowed_development_additions_upward_closed',
            'development_after_reference_opening': True, 'reference_previously_consumed': True,
            'fresh_final_reference_claimed': False, 'original_full_positive_retention': True,
            'retention_mask_semantics': 'original_full_fitting_positive_repertoire'}
        candidate_spec = save('candidate_fit_manifest.json', candidate)
        seeds = {p: [] for p in graph_ids}; seeds[fit[0]] = [('BPO', term) for term in terms]
        seeds[final[0]] = [('BPO', terms[1])]
        historical = save('historical_seeds.json.gz', seeds)
        updated = save('matched_seeds.json.gz', seeds)
        retained = save('seed_union.json', {'format': 'biograph-steward.fitting-only-seed-union.v1',
            'role_counts': {'fit': 4040, 'validation': 797, 'final': 3300}, 'original_pairs_removed': 0,
            'only_allowed4040_proteins_gained_labels': True, 'all_original_nonfitting_rows_retained': True,
            'source_input_pins': {graph['file']: graph['sha256'], ids_spec['file']: ids_spec['sha256']},
            'updated_training_file': updated['file'], 'updated_training_sha256': updated['sha256'],
            'original_training_file': historical['file'], 'original_training_sha256': historical['sha256'],
            'fit_manifest_sources': {'biological_process': old_spec}})
        current_rows = {p: [] for p in graph_ids}; current_rows[final[1]] = [('P', terms[1])]
        current_seeds = save('current_seeds.json.gz', current_rows)
        current = save('current_prepared.json', {'format': 'biograph-steward.current-T0-curated-seeds.v1',
            'forecast_role': 'final', 'forecast_count': 3300, 'future_reference_read': False,
            'historical_labels_merged': False, 'native_admission_and_propagation_unchanged': True,
            'source_input_pins': {graph['file']: graph['sha256']},
            'seed_file': current_seeds['file'], 'seed_sha256': current_seeds['sha256']})
        target_file = self.root / 'final_ids.txt'; target_file.write_text('\n'.join(final) + '\n')
        target_spec = {'file': str(target_file), 'sha256': module.file_sha256(target_file)}
        prior_file = array('prior.npy', np.zeros((3300, 2), dtype=np.float64))
        prior_spec = save('prior.json', {'namespace': 'biological_process', 'proteins': final, 'terms': terms,
            'prediction_file': prior_file, 'prediction_sha256': module.file_sha256(prior_file),
            'final_reference_labels_read_for_forecasting': False, 'upper_roundoff_tolerance': 0.})
        original_cfg = save('configuration.json', {'targets': target_spec,
            'arms': {'native_T0_nonexperimental': {'biological_process': prior_spec}},
            'references': {'NEVER_OPEN': '/invented/future_t1/groundtruth.tsv'}})
        from .assessment import validate_source_manifest
        verified = validate_source_manifest(prior_spec, final, arm='native_T0_nonexperimental', namespace='biological_process')
        seal = save('forecast_seal.json', {'format': 'biograph-steward.contextual-forecast-seal.v1',
            'future_GO_labels_opened': False, 'configuration_sha256': original_cfg['sha256'],
            'forecasts': {'native_T0_nonexperimental': {'biological_process': verified}}})
        plan = save('plan.json', {'format': 'biograph-steward.current-T0-union-refit-development-plan.v1',
            'reference_already_consumed': True, 'independent_confirmation': False,
            'arms': {a: ['biological_process'] for a in (*module.ARMS, 'current_T0_positive_union_context_refit')},
            'source_adaptation': {'expected_original_full_BP_positive_cells': 2,
                'expected_augmented_BP_positive_cells': 4, 'expected_added_BP_positive_cells': 2,
                'expected_fitting_proteins_with_additions': 1,
                'expected_original_root_positive_rows': 1, 'expected_augmented_root_positive_rows': 2}})
        author = save('author_receipt.json', {'files': {}})
        self.cfg = {**scope(), 'source_generation_authorized': True, 'source_plan': plan,
            'graph': graph, 'fit_ids': ids_spec, 'retained_seed_union': retained,
            'current_curated_prepared': current, 'candidate_fit_manifest': candidate_spec,
            'original_seal_directory': str(self.root), 'original_seal_sha256': seal['sha256'],
            'localplus_author': str(self.root), 'localplus_author_receipt': author}
        constants = {'PLAN_SHA256': plan['sha256'], 'STRICT_GRAPH_SHA256': graph['sha256'],
            'RETAINED_UNION_RECEIPT_SHA256': retained['sha256'], 'RETAINED_UNION_SEEDS_SHA256': updated['sha256'],
            'CURRENT_PREPARED_SHA256': current['sha256'], 'CURRENT_SEEDS_SHA256': current_seeds['sha256'],
            'ORIGINAL_SEAL_SHA256': seal['sha256'], 'ORIGINAL_NONEXPERIMENTAL_BP_SHA256': prior_spec['sha256']}
        self.stack.enter_context(patch.multiple(module, **constants))

    def test_actual_complete_manifest_contract_admits_without_reference_access(self):
        result = module.admit_sources(self.cfg)
        self.assertEqual(len(result['targets']), 3300)
        self.assertIn(('BPO', 'GO:1000001'), result['seeds']['FIT1'])
        self.assertIn(('BPO', 'GO:1000001'), result['query_memberships']['FINAL0'])
        self.assertEqual(result['query_memberships']['FINAL1'], [])
        self.assertNotIn('/invented/future_t1/groundtruth.tsv', result['source_input_pins'])

    def test_wrong_full_retention_mask_cannot_hide_behind_true_metadata(self):
        manifest_path = Path(self.cfg['candidate_fit_manifest']['file'])
        manifest = json.loads(manifest_path.read_text())
        mask = np.load(self.mask_file); mask[0, 1] = False; np.save(self.mask_file, mask)
        manifest['file_pins'][str(self.mask_file)] = module.file_sha256(self.mask_file)
        manifest_path.write_text(json.dumps(manifest))
        self.cfg['candidate_fit_manifest']['sha256'] = module.file_sha256(manifest_path)
        with self.assertRaisesRegex(ValueError, 'exactly every original full positive'):
            module.admit_sources(self.cfg)

    def test_generation_gate_precedes_arrays_and_all_consumed_flags_are_explicit(self):
        output = self.root / 'generated'
        def invented_native(modules, graph, seeds, targets, path):
            gate = json.loads((output / 'generation_gate.json').read_text())
            self.assertFalse(gate['new_forecast_arrays_generated_at_receipt'])
            self.assertEqual(gate['source_code_sha256'], module.file_sha256(module.__file__))
            values = np.zeros((3300, 2), dtype=np.float64); np.save(path, values)
            return ('GO:0008150', 'GO:1000001'), values, {'invented_native_stub': True}
        with patch('tools.cafa_prediction.core.author_modules', return_value={}), \
             patch.object(module, 'native_localplus_bp', side_effect=invented_native):
            delivered = module.produce(self.cfg, output)
        self.assertEqual(delivered['status'], 'complete')
        self.assertEqual(set(delivered['arms']), set(module.ARMS))
        for arm, specs in delivered['arms'].items():
            meta = json.loads(Path(specs['biological_process']['file']).read_text())
            self.assertEqual(meta['status'], 'complete')
            self.assertEqual(meta['producer_code_sha256'], module.file_sha256(module.__file__))
            self.assertEqual(len(meta['proteins']), 3300)
            self.assertFalse(meta['independent_confirmation']); self.assertTrue(meta['reference_previously_consumed'])
            self.assertFalse(meta['scientific_metrics_computed']); self.assertFalse(meta['current_validation_metric_computed'])
            self.assertEqual(meta['upper_roundoff_tolerance'], 1e-10 if arm == module.LOCALPLUS else 0.)


class NativeLocalPlusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import scipy
            from tools.cafa_prediction import core
            author = os.environ.get('BIOGRAPH_LOCALPLUS_AUTHOR', 'runs/prediction_next_20261113/author_methods')
            receipt = os.environ.get('BIOGRAPH_LOCALPLUS_RECEIPT', 'runs/prediction_next_20261113/author_methods_receipt.json')
            cls.modules = core.author_modules(author, receipt)
            cls.core = core
        except (ImportError, FileNotFoundError, ValueError) as error:
            if os.environ.get('BIOGRAPH_SOURCE_CONTROL_NATIVE_TESTS_REQUIRED') == '1': raise
            raise unittest.SkipTest('Optional source-pinned LocalPlus CPU runtime unavailable: ' + str(error))

    def test_actual_unchanged_LocalPlus_scores_and_missing_query_rows(self):
        graph = {'nodes': ['UniProtKB:P1', 'UniProtKB:P2', 'UniProtKB:P3'],
                 'pairs': [('UniProtKB:P1', 'UniProtKB:P2', .5), ('UniProtKB:P2', 'UniProtKB:P3', 1.)]}
        seeds = {'P1': [('BPO', 'GO:1000001')], 'P2': [], 'P3': [('BPO', 'GO:1000002')]}
        matrix = self.modules['alg_utils'].normalizeGraphEdgeWeights(
            self.core.adjacency(graph['nodes'], graph['pairs']))
        direct = []
        for positives in ({0}, {2}):
            result, _ = self.core.run_term(self.modules, matrix, None, positives, 'localplus')
            direct.append(result)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'invented.npy'
            terms, actual, provenance = module.native_localplus_bp(self.modules, graph, seeds,
                ('P3', 'MISSING', 'P1', 'P2'), path)
            self.assertEqual(terms, ('GO:1000001', 'GO:1000002'))
            expected = np.zeros((4, 2)); expected[[0, 2, 3]] = np.asarray(direct).T[[2, 0, 1]]
            np.testing.assert_array_equal(actual, expected)
            self.assertEqual(provenance['native_LocalPlus_parameters'], {})
            self.assertEqual(provenance['graph_absent_query_rows'], 1)
            self.assertFalse(provenance['graph_topology_or_weights_changed'])


if __name__ == '__main__': unittest.main()
