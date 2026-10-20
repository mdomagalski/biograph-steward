"""Invented development outcomes; source masking, scope and untouched membership."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest, write_json
from biograph_steward.crc_pilot import sha
from biograph_steward.growth_comparison import run_comparison, split_ids
from biograph_steward.growth_diagnostics import (ABLATIONS, CANDIDATES, FUSION, block_of,
    fit_ablation, fusion, mask_row, proposed_candidate, reserve_fresh, run_diagnostics,
    select_reserve, verify_diagnostics, verify_reserve)
from biograph_steward.matched_panel import prepare_panel
from test_growth_comparison import comparison_fixture
from test_matched_panel import inputs as panel_inputs


def invented_panel(root):
    audit = root / 'audit'; mapping = root / 'mapping'; audit.mkdir(); mapping.mkdir()
    coverage, mappings = panel_inputs()
    for i in range(3, 321):
        gene = deepcopy(mappings[0]); row = deepcopy(coverage[0]); gid = 'HGNC:' + str(i)
        gene.update(hgnc_id=gid, ncbi_gene_id=str(i), approved_symbol='INVENTED_' + str(i), matrix_row=i + 1)
        gene['protein_candidates'][0]['uniprot_id'] = 'UniProtKB:P' + str(i + 50000)
        row.update(hgnc_id=gid, ncbi_gene_id=str(i), approved_symbol=gene['approved_symbol'], cptac_matrix_row=i + 1,
            matrix_column=i, release_label='INVENTED_' + str(i) + ' (' + str(i) + ')')
        coverage.append(row); mappings.append(gene)
    write_json(audit / 'gene_coverage.json', coverage); write_json(mapping / 'mappings.json', mappings)
    write_json(audit / 'model_inventory.json', [{'selected_crc_model': True, 'screen_provenance_eligible_2d': True,
        'patient_sample_group': 'INVENTED-SAMPLE', 'model_id': str(i)} for i in range(2)])
    with patch('biograph_steward.matched_panel.verify_audit', return_value={
            'cohort_mapping_result_sha256': 'MAP', 'result_sha256': 'AUDIT', 'source_sha256': 'SOURCE'}), \
         patch('biograph_steward.matched_panel.verify_mapping', return_value={'result_sha256': 'MAP', 'registry_sha256': 'REG'}):
        panel = prepare_panel(audit, mapping, root / 'panel', size=2)
    old = json.loads((root / 'panel/members.json').read_text()); previous = root / 'previous'; previous.mkdir()
    write_json(previous / 'protocol_metrics.json', {'panel_sha256': panel['panel_sha256'], 'depmap_source_sha256': 'SOURCE'})
    write_json(previous / 'fitted_models.json', {'pharos_restricted': {'final_design': {'fit_gene_ids': [old[0]['hgnc_id']]}}})
    write_json(previous / 'test_outcomes.json', {'gene_ids': [old[1]['hgnc_id']]})
    write_json(previous / 'fit_outcomes.json', {'INVENTED': {old[0]['hgnc_id']: 1}})
    write_json(previous / 'protocol_partitions.json', {'models': [{'group': 'INVENTED-SAMPLE', 'model_ids': ['0', '1'], 'split': 'train'}]})
    verified_parent = {'result_sha256': 'INVENTED-PARENT', 'files': {n: sha(previous / n) for n in ['fit_outcomes.json', 'test_outcomes.json', 'fitted_models.json']}}
    return panel, verified_parent


class AblationTests(unittest.TestCase):
    def test_block_mask_keeps_only_requested_source_without_changing_values(self):
        row = {'pathway|Reactome|A': .3, 'expression|HPM|colon': -.4, 'expression_missing|HPM|colon': 1,
            'category|HPA|colon|High': .5, 'bioplex|HGNC:1': 1, 'cptac|median_ratio': 2}
        self.assertEqual(mask_row(row, ['expression']), {k: v for k, v in row.items() if block_of(k) == 'expression'})
        self.assertEqual(mask_row(row, ['bioplex']), {'bioplex|HGNC:1': 1})
        with self.assertRaises(ValueError): mask_row(row, ['unknown'])

    def test_fixed_fusion_uses_shared_effect_units_no_test_fitting_and_checks_identities(self):
        a = {'test_gene_ids': ['HGNC:1', 'HGNC:2'], 'predictions': [2, 4], 'validation_gene_ids': ['HGNC:3', 'HGNC:4'],
            'validation_target': [1, 2], 'selected_alpha': 1., 'selection': [{'alpha': 1., 'predictions': [0, 2]}]}
        b = deepcopy(a); b['predictions'] = [6, 8]; b['selection'][0]['predictions'] = [2, 4]
        r = fusion(a, b); self.assertEqual(r['predictions'], [4, 6]); self.assertEqual(r['validation_predictions'], [1, 3])
        self.assertEqual(r['weights'], [.5, .5]); self.assertEqual(r['additional_fits'], 0)
        b['test_gene_ids'].reverse()
        with self.assertRaises(ValueError): fusion(a, b)

    def test_proposal_uses_validation_only_and_deterministic_ties(self):
        rows = {n: {'selected_alpha': 1., 'selection': [{'alpha': 1., 'spearman': .1}], 'predictions': [0, 1]} for n in CANDIDATES}
        rows[FUSION] = {'kind': 'fixed_average_of_saved_predictions', 'validation_spearman': .1}
        self.assertEqual(proposed_candidate(rows)['candidate'], 'pharos_restricted')
        rows['expression_only']['selection'][0]['spearman'] = .2
        rows['pathways_only']['exposed_test_spearman'] = 1; rows['expression_only']['exposed_test_spearman'] = -1
        self.assertEqual(proposed_candidate(rows)['candidate'], 'expression_only')

    def test_full_invented_diagnostics_replays_without_original_matrix_or_new_test_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, source = comparison_fixture(root)
            with patch('biograph_steward.growth_comparison.load_depmap', return_value={'source_sha256': 'DEPMAP'}):
                parent = run_comparison(root / 'frozen', source, root / 'comparison')
            (source / 'CRISPRGeneEffect.csv').unlink()
            with patch('biograph_steward.growth_comparison.read_effects', side_effect=AssertionError('New matrix access forbidden')):
                result = run_diagnostics(root / 'comparison', root / 'diagnostics')
                self.assertEqual(result, verify_diagnostics(root / 'diagnostics'))
            self.assertEqual(result['parent_result_sha256'], parent['result_sha256']); self.assertEqual(result['additional_ridge_fits'], 24)
            self.assertFalse(result['fresh_test_executed']); self.assertFalse(result['scientific_improvement_established'])
            models = json.loads((root / 'diagnostics/models.json').read_text())
            self.assertTrue(all(block_of(k) == 'expression' for k in models['expression_only']['model']['coefficients']))
            # Altered pathways cannot affect an expression-only model.
            genes = {g['hgnc_id']: g for g in json.loads((root / 'comparison/protocol_features.json').read_text())['genes']}
            for g in genes.values(): g['pathways'] = []; g['bioplex_neighbors'] = []
            changed = fit_ablation(genes, json.loads((root / 'comparison/protocol_partitions.json').read_text()),
                json.loads((root / 'comparison/fit_outcomes.json').read_text()), 'expression_only')
            self.assertEqual(changed['predictions'], models['expression_only']['predictions'])
            (root / 'diagnostics/scores.json').write_text('{}')
            with self.assertRaises(ValueError): verify_diagnostics(root / 'diagnostics')

    def test_invalid_parent_stops_before_any_new_fit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('biograph_steward.growth_diagnostics.verify_comparison', side_effect=ValueError('tampered')), \
                 patch('biograph_steward.growth_diagnostics.fit_ablation') as fit:
                with self.assertRaises(ValueError): run_diagnostics(Path(tmp) / 'missing', Path(tmp) / 'out')
                fit.assert_not_called(); self.assertFalse((Path(tmp) / 'out').exists())


class ReserveTests(unittest.TestCase):
    def population(self):
        return [{'hgnc_id': 'HGNC:' + str(i), 'selection_hash': str(i).zfill(3),
            'protein_candidates': [{'uniprot_id': 'UniProtKB:INVENTED-' + str(i)}]} for i in range(1, 9)]

    def test_excludes_transitive_shared_product_components_and_keeps_selected_components_whole(self):
        p = self.population()
        p[1]['protein_candidates'].append(p[0]['protein_candidates'][0]); p[2]['protein_candidates'].append(p[1]['protein_candidates'][0])
        p[4]['protein_candidates'].append(p[3]['protein_candidates'][0])
        selected, excluded, remaining = select_reserve(p, {'HGNC:1'}, size=1)
        self.assertEqual({g['hgnc_id'] for g in selected}, {'HGNC:4', 'HGNC:5'})
        self.assertEqual(excluded[0]['genes'], ['HGNC:1', 'HGNC:2', 'HGNC:3']); self.assertEqual(remaining, 3)

    def test_selection_is_order_independent_and_does_not_read_outcome_like_fields(self):
        p = self.population(); before = select_reserve(p, {'HGNC:1'}, size=3)
        p.reverse()
        for i, g in enumerate(p): g['dependency_value'] = i * 1e9
        after = select_reserve(p, {'HGNC:1'}, size=3)
        self.assertEqual([g['hgnc_id'] for g in before[0]], [g['hgnc_id'] for g in after[0]])
        with self.assertRaises(ValueError): select_reserve(p, {'HGNC:1'}, size=256)
        with self.assertRaises(ValueError): select_reserve(p, {'HGNC:999'}, size=1)
        with self.assertRaises(ValueError): select_reserve(p + [p[0]], {'HGNC:1'}, size=1)

    def test_bound_reservation_reproduces_and_never_opens_experimental_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, previous = invented_panel(root)
            with patch('biograph_steward.growth_diagnostics.verify_comparison', return_value=previous), \
                 patch('biograph_steward.growth_comparison.read_effects', side_effect=AssertionError('Forbidden')):
                r = reserve_fresh(root / 'panel', root / 'previous', root / 'reserved')
            self.assertEqual(r, verify_reserve(root / 'reserved')); self.assertEqual(r['reserved_genes'], 256)
            self.assertEqual(r['gene_overlap_with_previous'], 0); self.assertEqual(r['protein_overlap_with_previous'], 0)
            self.assertFalse(r['fresh_dependency_values_loaded']); self.assertFalse(r['new_pharos_features_retrieved'])
            (root / 'reserved/reserved_members.json').write_text('[]')
            with self.assertRaises(ValueError): verify_reserve(root / 'reserved')

    def test_mismatched_population_identity_rejects_before_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, previous = invented_panel(root)
            write_json(root / 'previous/protocol_metrics.json', {'panel_sha256': 'WRONG', 'depmap_source_sha256': 'SOURCE'})
            with patch('biograph_steward.growth_diagnostics.verify_comparison', return_value=previous):
                with self.assertRaises(ValueError): reserve_fresh(root / 'panel', root / 'previous', root / 'out')
            self.assertFalse((root / 'out').exists())


if __name__ == '__main__': unittest.main()
