"""Invented panel/source fixtures: selection blindness, exact scope and provenance."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import PharosClient, PharosError, digest, write_json
from biograph_steward.crc_pilot import sha
from biograph_steward.matched_panel import (choose_panel, feature_view, load_panel, prepare_panel,
                                          retrieve_panel, verify_retrieval)
from test_retrieval import ContextAPI


def inputs():
    mapping = []; coverage = []
    for i, uid in enumerate(['P04637', 'P00533']):
        gid = 'HGNC:' + str(i + 1)
        mapping.append({'hgnc_id': gid, 'ncbi_gene_id': str(i + 1), 'approved_symbol': 'TEST_' + str(i),
                        'matrix_row': i + 2, 'identifier_eligible': True, 'protein_context_eligible': True,
                        'protein_candidates': [{'uniprot_id': 'UniProtKB:' + uid,
                            'status': 'reviewed_human_hgnc_match', 'shared_across_genes': False}]})
        coverage.append({'hgnc_id': gid, 'ncbi_gene_id': str(i + 1), 'approved_symbol': 'TEST_' + str(i),
                         'cptac_matrix_row': i + 2, 'matrix_column': i + 1, 'release_label': 'TEST (' + str(i + 1) + ')',
                         'protein_context_eligible': True, 'status': 'unique_stable_id_match',
                         'crc_observed_models': 2, 'crc_missing_models': 0})
    return coverage, mapping


def panel_fixture(root):
    audit = root / 'audit'; mapping = root / 'mapping'; audit.mkdir(); mapping.mkdir()
    coverage, mappings = inputs()
    write_json(audit / 'gene_coverage.json', coverage); write_json(mapping / 'mappings.json', mappings)
    write_json(audit / 'model_inventory.json', [{'selected_crc_model': True, 'screen_provenance_eligible_2d': True,
        'patient_sample_group': 'INVENTED-SAME-SAMPLE', 'model_id': str(i)} for i in range(2)])
    with patch('biograph_steward.matched_panel.verify_audit', return_value={
            'cohort_mapping_result_sha256': 'MAP', 'result_sha256': 'AUDIT', 'source_sha256': 'SOURCE'}), \
         patch('biograph_steward.matched_panel.verify_mapping', return_value={'result_sha256': 'MAP', 'registry_sha256': 'REG'}):
        prepare_panel(audit, mapping, root / 'panel', size=2)
    return root / 'panel'


class PanelAPI(ContextAPI):
    def __init__(self):
        super().__init__(); self.missing = set(); self.wrong = set()
        for records in self.context.values():
            for record in records['go']: record['assigned_by'] = 'UniProtKB'
            for record in records['expressions']: record['type'] = 'HPA Protein'
        self.context['P04637']['ppis'][0]['type'] = 'BioPlex'

    def __call__(self, payload):
        if 'ExplicitPanelTargets' not in payload['query']: return super().__call__(payload)
        self.calls.append(deepcopy(payload)); data = {}
        for key, uid in payload['variables'].items():
            row = next(r for r in self.rows if r['uniprot'] == uid)
            data['t' + key.removeprefix('id')] = None if uid in self.missing else {
                'uniprot': 'P01116' if uid in self.wrong else uid, 'sym': row['sym'], 'name': row['name']}
        return {'data': data}


class SelectionTests(unittest.TestCase):
    def test_membership_ignores_input_order_scores_disease_and_popularity(self):
        coverage, mappings = inputs(); population, members = choose_panel(coverage, mappings, 2, 1)
        changed = deepcopy(mappings)
        for row in changed:
            row.update(depmap_effect=-999, cptac_median=999, disease='ANSWER', publicationCount=1000000)
        self.assertEqual(choose_panel(list(reversed(coverage)), list(reversed(changed)), 2, 1), (population, members))
        self.assertEqual(members, population[:1])
        self.assertFalse(any('effect' in k or 'median' in k or 'disease' in k for row in population for k in row))

    def test_incomplete_and_ambiguous_genes_cannot_replace_fixed_members(self):
        coverage, mappings = inputs(); coverage[0]['crc_missing_models'] = 1
        with self.assertRaises(ValueError): choose_panel(coverage, mappings, 2, 2)
        coverage[0]['crc_missing_models'] = 0; coverage[0]['status'] = 'ambiguous_release_gene_identity'
        with self.assertRaises(ValueError): choose_panel(coverage, mappings, 2, 2)
        for size in [0, 257, True]:
            with self.assertRaises(ValueError): choose_panel(*inputs(), 2, size)

    def test_all_reviewed_products_remain_one_gene_unit_and_identity_disagreement_fails(self):
        coverage, mappings = inputs()
        mappings[0]['protein_candidates'].append({**mappings[0]['protein_candidates'][0], 'uniprot_id': 'UniProtKB:P01116'})
        population, _ = choose_panel(coverage, mappings, 2, 2)
        self.assertEqual(len(population), 2)
        self.assertEqual(len(next(g for g in population if g['hgnc_id'] == 'HGNC:1')['protein_candidates']), 2)
        mappings[0]['ncbi_gene_id'] = '999'
        with self.assertRaises(ValueError): choose_panel(coverage, mappings, 2, 2)

    def test_prepared_panel_is_immutable_and_hash_rule_is_rechecked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = panel_fixture(root); panel, members = load_panel(path)
            self.assertFalse(panel['outcomes_loaded']); self.assertEqual(len(members), 2)
            (path / 'members.json').write_text('[]')
            with self.assertRaises(ValueError): load_panel(path)


class MatchedRetrievalTests(unittest.TestCase):
    def test_explicit_id_pipeline_has_no_disease_or_label_query_and_replays_source_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); panel = panel_fixture(root); api = PanelAPI(); client = PharosClient(transport=api)
            client.search('test')  # Request locators must be local to this snapshot.
            r = retrieve_panel(panel, root / 'result', client=client)
            self.assertEqual(verify_retrieval(root / 'result'), r)
            self.assertEqual(r['target_resolution_counts'], {'resolved': 2})
            self.assertFalse(r['scoring_run']); self.assertFalse(r['outcome_values_loaded'])
            self.assertFalse(r['ready_for_prediction_comparison'])
            snapshot = json.loads((root / 'result/snapshot.json').read_text())
            for request in snapshot['requests']:
                query = request['request']['query']
                self.assertNotIn('disease', query.lower()); self.assertNotIn('geneEffect', query)
                self.assertEqual(digest(request['response']), request['response_sha256'])
            for state in snapshot['retrieval_coverage']['targets']:
                for page in state['pages']:
                    request = snapshot['requests'][page['request_index']]
                    self.assertIn('Scoped_' + state['family'], request['request']['query'])
            genes = json.loads((root / 'result/feature_candidates.json').read_text())
            self.assertEqual(len(genes), 2)
            expressions = [f['record'] for g in genes for f in g['features'] if f['family'] == 'expressions']
            self.assertTrue(any(r['qual'] == 'Not detected' for r in expressions))
            self.assertTrue(any(r['value'] is None for r in expressions))
            for g in genes:
                for f in g['features']:
                    raw = snapshot
                    for part in f['source_locator'].split('#/')[1].split('/'):
                        raw = raw[int(part)] if isinstance(raw, list) else raw[part]
                    self.assertEqual(digest(raw), f['record_sha256'])
                    self.assertNotIn('props', f['record'])
            (root / 'result/feature_candidates.json').write_text('[]')
            with self.assertRaises(ValueError): verify_retrieval(root / 'result')

    def test_missing_and_wrong_ids_stay_visible_without_replacements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); panel = panel_fixture(root); api = PanelAPI()
            api.missing.add('P04637'); api.wrong.add('P00533')
            r = retrieve_panel(panel, root / 'result', client=PharosClient(transport=api))
            self.assertEqual(r['target_resolution_counts'], {'identity_mismatch': 1, 'not_found': 1})
            self.assertEqual(r['genes_with_any_resolved_product'], 0)
            self.assertEqual(len(json.loads((root / 'result/feature_candidates.json').read_text())), 2)
            verify_retrieval(root / 'result')

    def test_wrong_page_identity_and_partial_graphql_errors_fail_closed(self):
        for mode in ['wrong', 'partial']:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); panel = panel_fixture(root); api = PanelAPI()
                api.modify = lambda family, uid, skip, row: {**row, 'uniprot': 'P01116'}
                transport = api if mode == 'wrong' else lambda payload: {'data': {'dbVersion': 'TEST'}, 'errors': [{'message': 'INVENTED'}]}
                with self.assertRaises(PharosError): retrieve_panel(panel, root / 'result', client=PharosClient(transport=transport))
                self.assertFalse((root / 'result/metrics.json').exists())

    def test_feature_policy_withholds_dependency_composites_and_shared_products(self):
        _, members = choose_panel(*inputs(), 2, 2)
        target = {'uniprot': 'P04637', 'pathways': [
            {'type': 'Reactome', 'sourceID': 'R-HSA-1', 'name': 'INVENTED'},
            {'type': 'Reactome', 'sourceID': 'R-HSA-2', 'name': 'INVENTED DepMap label'}],
            'pharos_context': {'go': [{'assigned_by': 'CCLE'}], 'expressions': [], 'ppis': [
                {'type': 'STRINGDB', 'target': {'uniprot': 'P00533'}},
                {'type': 'BioPlex', 'target': {'uniprot': 'P00533', 'sym': 'TEST', 'name': 'DESCRIPTION'}, 'props': [{'value': 99}]}]}}
        genes, excluded = feature_view(members, [target])
        self.assertEqual(sum(len(g['features']) for g in genes), 2)
        self.assertEqual(len(excluded), 3)
        ppi = next(f for g in genes for f in g['features'] if f['family'] == 'ppis')
        self.assertEqual(ppi['record']['target'], {'uniprot': 'P00533', 'sym': 'TEST'})
        next(g for g in members if g['hgnc_id'] == 'HGNC:1')['protein_candidates'][0]['shared_across_genes'] = True
        genes, excluded = feature_view(members, [target])
        self.assertTrue(all(not g['features'] for g in genes)); self.assertEqual(len(excluded), 5)


if __name__ == '__main__': unittest.main()
