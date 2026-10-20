"""Invented outcomes only: numerical correctness, held-out isolation and sealed replay."""
from copy import deepcopy
import csv
from io import StringIO
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest, write_json
from biograph_steward.comparison_protocol import reviewed_features
from biograph_steward.growth_comparison import (Design, aggregate, decision, group_outcomes, metrics,
    paired_bootstrap, permuted_genes, predict, ranks, read_effects, ridge_fit, run_comparison, spearman, split_ids, verify_comparison)
from test_comparison_protocol import invented_inputs, freeze_fixture


def expanded_inputs():
    data = invented_inputs()
    for i in range(11, 61):
        gid = 'HGNC:' + str(i); uid = 'P' + str(i).zfill(5)
        data['members'].append({'hgnc_id': gid, 'ncbi_gene_id': str(i), 'cptac_matrix_row': i + 1,
            'approved_symbol': 'TEST_' + str(i), 'protein_candidates': [{'uniprot_id': 'UniProtKB:' + uid, 'shared_across_genes': False, 'status': 'reviewed_human_hgnc_match'}]})
        data['targets'].append({'uniprot': uid, 'pathways': [], 'pharos_context': {'go': [], 'ppis': [], 'expressions': []}})
        data['cptac_mapping_rows'].append({'hgnc_id': gid, 'ncbi_gene_id': str(i), 'matrix_row': i + 1, 'measurement_sha256': digest('INVENTED-' + str(i))})
    for i, member in enumerate(data['members'], 1):
        member.update(depmap_matrix_column=i, depmap_release_label='TEST_' + str(i) + ' (' + str(i) + ')')
        data['cptac_mapping_rows'][i - 1]['median_reported_log2_ratio'] = ((i * 7) % 61) / 10
        data['targets'][i - 1]['pharos_context']['expressions'] = [{'type': 'HPM Protein', 'tissue': 'Adult Colon', 'value': str(i)}]
    for i, model in enumerate(data['models'], 2): model['matrix_row'] = i
    return data


def comparison_fixture(root):
    data = expanded_inputs()
    with patch('test_comparison_protocol.invented_inputs', return_value=data): freeze_fixture(root)
    source = root / 'source'; source.mkdir(); stream = StringIO(); writer = csv.writer(stream)
    writer.writerow(['', *[g['depmap_release_label'] for g in data['members']]])
    for i, model in enumerate(data['models'], 1):
        writer.writerow([model['model_id'], *[-r['median_reported_log2_ratio'] - i * .001 for r in data['cptac_mapping_rows']]])
    (source / 'CRISPRGeneEffect.csv').write_text(stream.getvalue())
    return data, source


class NumericalTests(unittest.TestCase):
    def test_ridge_matches_analytic_solution_and_keeps_intercept_unpenalized(self):
        model = ridge_fit([{'x': -1}, {'x': 1}], [5, 9], 1.0)
        self.assertAlmostEqual(model['coefficients']['x'], 1)
        self.assertAlmostEqual(model['intercept'], 7)
        self.assertEqual([round(v, 10) for v in predict(model, [{'x': -1}, {'x': 1}])], [6, 8])
        constant = ridge_fit([{'x': 9}] * 3, [2, 5, 8], .1)
        self.assertEqual([round(v, 10) for v in predict(constant, [{'x': 9}] * 2)], [5, 5])

    def test_average_ties_undefined_correlations_and_ranking_metrics(self):
        self.assertEqual(ranks([1, 1, 2]), [1.5, 1.5, 3])
        self.assertAlmostEqual(spearman([1, 1, 2], [1, 2, 3]), math.sqrt(.75))
        self.assertIsNone(spearman([1, 1], [1, 2])); self.assertIsNone(spearman([1], [2]))
        ids = ['HGNC:' + str(i) for i in range(1, 21)]; values = list(range(20))
        result = metrics(list(reversed(values)), values, ids, {'GROUP': dict(zip(ids, values))})
        self.assertEqual(result['recall_at_10'], 0); self.assertEqual(result['spearman'], -1)

    def test_sample_groups_receive_equal_weight_and_negation_is_not_a_binary_label(self):
        groups = [{'group': 'A', 'model_ids': ['ONE', 'TWO']}, {'group': 'B', 'model_ids': ['THREE']}]
        raw = {'ONE': {'HGNC:1': 0}, 'TWO': {'HGNC:1': 2}, 'THREE': {'HGNC:1': 100}}
        grouped = group_outcomes(raw, groups, ['HGNC:1'])
        self.assertEqual(grouped['A']['HGNC:1'], 1); self.assertEqual(aggregate(grouped, ['HGNC:1']), [50.5])

    def test_bootstrap_is_paired_deterministic_and_signal_requires_both_criteria(self):
        ids = ['HGNC:' + str(i) for i in range(1, 9)]; values = list(range(8))
        groups = {'A': dict(zip(ids, values)), 'B': {gid: value + .1 for gid, value in zip(ids, values)}}
        result = paired_bootstrap(values, list(reversed(values)), groups, ids)
        self.assertEqual(result, paired_bootstrap(values, list(reversed(values)), groups, ids))
        self.assertEqual(result['lower_95'], -2); self.assertEqual(result['upper_95'], -2)
        self.assertFalse(decision(.04, {'lower_95': .01})['within_pilot_signal'])
        self.assertFalse(decision(.1, {'lower_95': -.01})['within_pilot_signal'])
        self.assertFalse(decision(None, {'lower_95': None})['within_pilot_signal'])
        self.assertTrue(decision(.1, {'lower_95': .01})['within_pilot_signal'])


class IsolationTests(unittest.TestCase):
    def features(self):
        features, _, _ = reviewed_features(expanded_inputs())
        return {g['hgnc_id']: g for g in features['genes']}

    def test_validation_and_test_features_cannot_change_fitted_preprocessing(self):
        genes = self.features(); fit = ['HGNC:1', 'HGNC:2', 'HGNC:3']; before = Design(genes, fit, 'pharos_restricted_plus_cptac')
        changed = deepcopy(genes)
        for gid in set(changed) - set(fit):
            changed[gid]['pathways'].append({'source': 'Reactome', 'stable_id': 'R-HSA-999999'})
            changed[gid]['cptac_median_reported_log2_ratio'] = 1e12
            changed[gid]['numeric_expression'][0]['value'] = 1e30
        after = Design(changed, fit, 'pharos_restricted_plus_cptac')
        self.assertEqual(before.receipt(), after.receipt()); self.assertEqual([before.row(g) for g in fit], [after.row(g) for g in fit])
        self.assertNotIn('pathway|Reactome|R-HSA-999999', after.row('HGNC:60'))

    def test_pharos_and_coverage_designs_are_invariant_to_cptac_values(self):
        genes = self.features(); changed = deepcopy(genes)
        for row in changed.values(): row['cptac_median_reported_log2_ratio'] = None
        for arm in ['pharos_restricted', 'coverage_only']:
            a = Design(genes, list(genes)[:20], arm); b = Design(changed, list(changed)[:20], arm)
            self.assertEqual(a.receipt(), b.receipt()); self.assertEqual(a.row('HGNC:60'), b.row('HGNC:60'))

    def test_not_detected_is_a_category_and_missing_is_separate(self):
        genes = self.features(); key = {'source': 'HPA Protein', 'tissue': 'colon - glandular cells'}
        genes['HGNC:1']['categorical_expression'] = [{**key, 'categories': ['Not detected']}]
        genes['HGNC:2']['categorical_expression'] = [{**key, 'categories': ['High']}]
        design = Design(genes, ['HGNC:1', 'HGNC:2'], 'pharos_restricted')
        self.assertIn('category|HPA Protein|colon - glandular cells|Not detected', design.row('HGNC:1'))
        self.assertNotIn('category|HPA Protein|colon - glandular cells|__unobserved__', design.row('HGNC:1'))
        self.assertIn('category|HPA Protein|colon - glandular cells|__unobserved__', design.row('HGNC:3'))

    def test_reader_parses_only_requested_cells_and_checks_frozen_identities(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'matrix.csv'; data = expanded_inputs()
            path.write_text(',TEST_1 (1),TEST_2 (2)\nMODEL-1,-2,FORBIDDEN\nMODEL-2,FORBIDDEN,FORBIDDEN\n')
            rows = read_effects(path, data, ['HGNC:1'], ['MODEL-1'])
            self.assertEqual(rows, {'MODEL-1': {'HGNC:1': 2}})
            for raw in ['NA', 'inf']:
                path.write_text(',TEST_1 (1)\nMODEL-1,' + raw + '\n')
                with self.assertRaises(ValueError): read_effects(path, data, ['HGNC:1'], ['MODEL-1'])
            path.write_text(',TEST_1 (999)\nMODEL-1,-2\n')
            with self.assertRaises(ValueError): read_effects(path, data, ['HGNC:1'], ['MODEL-1'])

    def test_cptac_permutations_stay_in_original_gene_partitions_and_preserve_values(self):
        genes = self.features(); parts = {'genes': [{'split': split, 'hgnc_ids': ['HGNC:' + str(i) for i in numbers]} for split, numbers in
            [('train', range(1, 31)), ('validation', range(31, 46)), ('test', range(46, 61))]]}
        result, mapping = permuted_genes(genes, parts, 4)
        for split in ['train', 'validation', 'test']:
            ids = split_ids(parts, 'genes', {split})
            self.assertEqual({mapping[g] for g in ids}, set(ids))
            self.assertEqual(sorted(result[g]['cptac_median_reported_log2_ratio'] for g in ids), sorted(genes[g]['cptac_median_reported_log2_ratio'] for g in ids))
        self.assertEqual(permuted_genes(genes, parts, 4)[1], mapping)


class ExecutionTests(unittest.TestCase):
    def test_full_invented_run_seals_before_test_read_detects_known_signal_and_replays(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); data, source = comparison_fixture(root); calls = []; reader = read_effects
            def observed(matrix, inputs, ids, models):
                calls.append(set(ids))
                if len(calls) == 2:
                    seal = json.loads((root / 'result/sealed_predictions.json').read_text())
                    self.assertFalse(seal['test_values_accessed']); self.assertEqual(len(seal['predictions']), 24)
                    self.assertTrue((root / 'result/test_access_receipt.json').is_file())
                    self.assertTrue(set(ids).isdisjoint(calls[0]))
                return reader(matrix, inputs, ids, models)
            with patch('biograph_steward.growth_comparison.load_depmap', return_value={'source_sha256': 'DEPMAP'}), \
                 patch('biograph_steward.growth_comparison.read_effects', side_effect=observed):
                result = run_comparison(root / 'frozen', source, root / 'result')
            self.assertEqual(len(calls), 2); self.assertEqual(result['ridge_fit_count'], 96)
            self.assertGreater(result['arms']['pharos_restricted_plus_cptac']['spearman'], .95)
            self.assertGreater(result['primary_spearman_delta'], .1)
            self.assertEqual(verify_comparison(root / 'result'), result)
            self.assertFalse(result['scientific_improvement_established'])
            with patch('biograph_steward.growth_comparison.load_depmap') as loader:
                with self.assertRaisesRegex(ValueError, 'already opened test'): run_comparison(root / 'frozen', source, root / 'another_result')
                loader.assert_not_called()
            (root / 'result/scores.json').write_text('{}')
            with self.assertRaises(ValueError): verify_comparison(root / 'result')

    def test_source_mismatch_fails_before_numeric_read_or_output_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, source = comparison_fixture(root)
            with patch('biograph_steward.growth_comparison.load_depmap', return_value={'source_sha256': 'OTHER'}), \
                 patch('biograph_steward.growth_comparison.read_effects') as reader:
                with self.assertRaises(ValueError): run_comparison(root / 'frozen', source, root / 'result')
                reader.assert_not_called(); self.assertFalse((root / 'result').exists())


if __name__ == '__main__': unittest.main()
