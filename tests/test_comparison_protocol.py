"""Invented feature/protocol controls. No live calls or biological gold labels."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest, write_json
from biograph_steward.comparison_protocol import (freeze_protocol, partitions, reference_binding,
                                                reviewed_features, specification, verify_protocol)


def invented_inputs():
    members = []; models = []; targets = []; rows = []
    for i in range(1, 11):
        uid = 'P' + str(i).zfill(5); gid = 'HGNC:' + str(i)
        members.append({'hgnc_id': gid, 'ncbi_gene_id': str(i), 'cptac_matrix_row': i + 1,
            'approved_symbol': 'TEST_' + str(i), 'protein_candidates': [{'uniprot_id': 'UniProtKB:' + uid,
                'shared_across_genes': False, 'status': 'reviewed_human_hgnc_match'}]})
        models.append({'model_id': 'MODEL-' + str(i), 'patient_sample_group': 'SAMPLE-' + str(i),
            'selected_crc_model': True, 'screen_provenance_eligible_2d': True})
        targets.append({'uniprot': uid, 'pathways': [], 'pharos_context': {'go': [], 'ppis': [], 'expressions': []}})
        rows.append({'hgnc_id': gid, 'ncbi_gene_id': str(i), 'matrix_row': i + 1,
            'measurement_sha256': digest('INVENTED-' + str(i)), 'median_reported_log2_ratio': i / 10})
    targets[0]['pathways'] = [{'sourceID': 'WP1_r12', 'type': 'WikiPathways', 'name': 'INVENTED'},
        {'sourceID': 'WP1_r13', 'type': 'WikiPathways', 'name': 'INVENTED revision'},
        {'sourceID': 'R-HSA-1.2', 'type': 'Reactome', 'name': 'INVENTED'},
        {'sourceID': 'K1', 'type': 'KEGG', 'name': 'INVENTED'}]
    targets[0]['pharos_context']['go'] = [{'goid': 'GO:0000001', 'assigned_by': 'UniProtKB', 'evidence': 'IDA'}]
    targets[0]['pharos_context']['expressions'] = [
        {'type': 'HPM Protein', 'tissue': 'Adult Colon', 'value': '0'},
        {'type': 'HPM Protein', 'tissue': 'Adult Colon', 'value': '0'},
        {'type': 'HPM Protein', 'tissue': 'Adult Rectum', 'value': None},
        {'type': 'HPA Protein', 'tissue': 'colon - glandular cells', 'qual': 'Not detected'},
        {'type': 'HPA Protein', 'tissue': 'colon - glandular cells', 'qual': 'High'},
        {'type': 'JensenLab TISSUES', 'tissue': 'colon', 'value': '99'}]
    ppi = {'type': 'BioPlex,Reactome,STRINGDB', 'props': [{'name': 'p_int', 'value': '.9'},
        {'name': 'Score', 'value': '.999'}], 'target': {'uniprot': 'P00002'}}
    targets[0]['pharos_context']['ppis'] = [ppi, deepcopy(ppi)]
    targets[1]['pharos_context']['ppis'] = [{**deepcopy(ppi), 'target': {'uniprot': 'P00001'}}]
    return {'members': members, 'models': models, 'targets': targets, 'cptac_mapping_rows': rows}


def freeze_fixture(root, *, incomplete=False):
    inputs = invented_inputs()
    for name in ['panel', 'retrieval', 'mapping']: (root / name).mkdir()
    write_json(root / 'panel/crc_models.json', inputs['models']); write_json(root / 'retrieval/snapshot.json', {'targets': inputs['targets']})
    write_json(root / 'mapping/mappings.json', inputs['cptac_mapping_rows'])
    raw = b'// INVENTED repository source fixture; never executed.\n'
    (root / 'TCRD.js').write_bytes(raw)
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    write_json(root / 'tree.json', {'sha': 'INVENTED-TREE', 'tree': [{'path': 'src/TCRD.js', 'sha': blob}]})
    panel = {'panel_sha256': 'PANEL', 'cohort_mapping_result_sha256': 'MAP', 'depmap_source_sha256': 'DEPMAP', 'depmap_audit_sha256': 'AUDIT'}
    retrieval = {'panel_sha256': 'PANEL', 'version_consistent': True, 'outcome_values_loaded': False, 'disease_filter_used': False,
        'result_sha256': 'RETRIEVAL', 'source_snapshot_sha256': 'SOURCE', 'retrieval': {f: {'target_statuses': {'complete': 10}} for f in ['pathways', 'go', 'ppis', 'expressions']}}
    if incomplete: retrieval['retrieval']['pathways']['target_statuses'] = {'capped': 1, 'complete': 9}
    mapping = {'result_sha256': 'MAP', 'matrix_sha256': 'MATRIX'}
    with patch('biograph_steward.comparison_protocol.load_panel', return_value=(panel, inputs['members'])), \
         patch('biograph_steward.comparison_protocol.verify_retrieval', return_value=retrieval), \
         patch('biograph_steward.comparison_protocol.verify_mapping', return_value=mapping):
        return freeze_protocol(root / 'panel', root / 'retrieval', root / 'mapping', root / 'frozen',
            pharos_code=root / 'TCRD.js', repository_tree=root / 'tree.json')


class ProtocolTests(unittest.TestCase):
    def test_group_splits_ignore_order_and_score_fields_keep_related_units_together(self):
        data = invented_inputs(); data['models'][1]['patient_sample_group'] = data['models'][0]['patient_sample_group']
        data['members'][1]['protein_candidates'].append(deepcopy(data['members'][0]['protein_candidates'][0]))
        expected = partitions(data['members'], data['models'])
        for g in data['members']: g['dependency_value'] = 123456
        for m in data['models']: m['effect'] = -999
        self.assertEqual(partitions(list(reversed(data['members'])), list(reversed(data['models']))), expected)
        self.assertTrue(any(set(g['hgnc_ids']) == {'HGNC:1', 'HGNC:2'} for g in expected['genes']))
        self.assertTrue(any(set(g['model_ids']) == {'MODEL-1', 'MODEL-2'} for g in expected['models']))
        self.assertEqual(set(g['split'] for g in expected['genes']), {'train', 'validation', 'test'})

    def test_duplicate_or_unresolved_models_are_rejected(self):
        data = invented_inputs(); data['models'][0]['patient_sample_group'] = None
        with self.assertRaises(ValueError): partitions(data['members'], data['models'])
        data = invented_inputs(); data['models'].append(data['models'][0])
        with self.assertRaises(ValueError): partitions(data['members'], data['models'])

    def test_stable_memberships_and_component_interactions_deduplicate_without_score_features(self):
        features, excluded, audit = reviewed_features(invented_inputs())
        self.assertEqual(len(features['genes'][0]['pathways']), 2)
        self.assertEqual(audit['collapsed_repeated_or_revision_pathway_memberships'], 1)
        self.assertEqual(len(features['bioplex_edges']), 1)
        self.assertEqual(len(features['bioplex_edges'][0]['support']), 3)
        self.assertEqual(features['genes'][0]['bioplex_neighbors'], ['HGNC:2'])
        self.assertEqual(features['genes'][1]['bioplex_neighbors'], ['HGNC:1'])
        self.assertNotIn('Score', json.dumps(features)); self.assertNotIn('goid', json.dumps(features))
        self.assertIn('go_study_reference_and_qualifier_unavailable', {x['reason'] for x in excluded})
        self.assertFalse(audit['underlying_study_independence_established'])

    def test_expression_zero_missing_and_conflicting_categories_remain_distinct(self):
        features, _, _ = reviewed_features(invented_inputs()); first = features['genes'][0]
        self.assertEqual([x['value'] for x in first['numeric_expression']], [0, None])
        self.assertEqual(first['categorical_expression'][0]['categories'], ['High', 'Not detected'])
        self.assertEqual(len(first['numeric_expression'][0]['support']), 2)
        self.assertEqual(first['cptac_median_reported_log2_ratio'], .1)

    def test_bioplex_missing_duplicate_invalid_and_low_probabilities_cannot_promote_string(self):
        for props in [[], [{'name': 'p_int', 'value': '.74'}], [{'name': 'p_int', 'value': 'nan'}],
                      [{'name': 'p_int', 'value': '1.1'}], [{'name': 'p_int', 'value': '.9'}] * 2]:
            data = invented_inputs()
            for t in data['targets']: t['pharos_context']['ppis'] = []
            data['targets'][0]['pharos_context']['ppis'] = [{'type': 'BioPlex,STRINGDB', 'props': props, 'target': {'uniprot': 'P00002'}}]
            f, _, _ = reviewed_features(data); self.assertEqual(f['bioplex_edges'], [])
        data['targets'][0]['pharos_context']['ppis'][0].update(type='STRINGDB', props=[{'name': 'p_int', 'value': '.99'}])
        f, _, _ = reviewed_features(data); self.assertEqual(f['bioplex_edges'], [])

    def test_shared_products_and_dependency_tagged_records_are_withheld(self):
        data = invented_inputs(); data['members'][0]['protein_candidates'][0]['shared_across_genes'] = True
        f, _, _ = reviewed_features(data); self.assertFalse(f['genes'][0]['pathways']); self.assertFalse(f['bioplex_edges'])
        data = invented_inputs(); data['targets'][0]['pathways'][0]['name'] = 'INVENTED DepMap annotation'
        _, excluded, _ = reviewed_features(data)
        self.assertIn('dependency_or_unresolved_cell_model_source', {x['reason'] for x in excluded})

    def test_freeze_and_offline_reconstruction_without_any_dependency_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); result = freeze_fixture(root)
            self.assertEqual(verify_protocol(root / 'frozen'), result)
            self.assertTrue(result['protocol_frozen']); self.assertFalse(result['dependency_values_loaded'])
            self.assertFalse(result['predictor_fit_run']); self.assertFalse(specification()['scientific_improvement_established'])
            self.assertFalse(any('CRISPRGeneEffect' in p.name for p in root.rglob('*')))
            (root / 'frozen/features.json').write_text('{}')
            with self.assertRaises(ValueError): verify_protocol(root / 'frozen')

    def test_incomplete_coverage_and_changed_repository_bytes_block_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError): freeze_fixture(root, incomplete=True)
            self.assertFalse((root / 'frozen').exists())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); freeze_fixture(root); (root / 'TCRD.js').write_text('altered')
            with self.assertRaises(ValueError): reference_binding(root / 'TCRD.js', root / 'tree.json')


if __name__ == '__main__': unittest.main()
