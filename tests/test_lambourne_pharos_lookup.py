"""Synthetic focused-lookup audit contracts; no assay table or real source read."""
from copy import deepcopy
import importlib.util
from itertools import combinations
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from biograph_steward.client import PharosClient, digest, write_json
from test_pharos_inventory import InventoryAPI, retrieval

SPEC = importlib.util.spec_from_file_location('audit_lambourne_pharos_lookup',
    Path(__file__).resolve().parents[1] / 'scripts/audit_lambourne_pharos_lookup.py')
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

P1, P2, P3, P4 = 'P04637', 'P00533', 'P01116', 'P15056'


class FocusedLookupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prior = self.root / 'prior'
        self.prior.mkdir()
        rows, exposure = [], []
        for number, products in enumerate(combinations(sorted((P1, P2, P3, P4)), 2), 2):
            rows.append({'source_row': number, 'uniprot_a': products[0], 'uniprot_b': products[1],
                'ad_orf_id': str(number), 'db_orf_id': str(number + 20),
                'source_dataset_column_5': 'Zhang_et_al', 'source_dataset_column_6': 'Zhang_et_al',
                'in_biorxiv_version': 'True', 'in_published_version': 'True'})
            exposure.append({'products': list(products), 'pharos_status': 'unassessed_neither_endpoint_queried',
                'pharos_retained_match': False, 'huri_registry_projected_match': number == 2,
                'huri_author_crosswalk_match': number == 2, 'inmc_registry_projected_match': number == 3,
                'inmc_author_crosswalk_match': False})
        # Previously observed only, no longer returned by the invented API.
        exposure[-1]['pharos_status'] = 'present_in_saved_raw_ppi'
        exposure[-1]['pharos_retained_match'] = True
        write_json(self.prior / 'identity_rows.json', rows)
        write_json(self.prior / 'pair_exposure.json', exposure)
        self.prior_report = {'format': 'biograph-steward.lambourne-identity-audit.v1',
            'author_commit': audit.COMMIT, 'author_files_sha256': {audit.PANEL: 'a' * 64},
            'outcome_fields_decoded': False,
            'output_sha256': {name: audit.sha(self.prior / name) for name in ('identity_rows.json', 'pair_exposure.json')},
            'groups': {audit.GROUP: {'source_rows': 6, 'distinct_unordered_product_pairs': 6,
                'pharos_status_pairs': {'unassessed_neither_endpoint_queried': 5, 'present_in_saved_raw_ppi': 1},
                'pharos_retained_match_pairs': 1, 'huri_either_mapping_match_pairs': 1,
                'inmc_either_mapping_match_pairs': 1}}}
        write_json(self.prior / 'report.json', self.prior_report)
        self.inventory = self.root / 'inventory.json'
        write_json(self.inventory, {'format': retrieval.ACCESSION_FORMAT, 'author_commit': audit.COMMIT,
            'author_panel_sha256': 'a' * 64, 'published_uniprot_accessions': sorted((P1, P2, P3, P4)),
            'outcome_fields_decoded': False})
        self.api = InventoryAPI()
        self.api.context[P1]['ppis'] = [
            {'nid': 1, 'type': 'STRING', 'props': [{'name': 'Score', 'value': '900'},
                                                 {'name': 'tdl', 'value': 'Tbio'}], 'target': {'uniprot': P2}},
            {'nid': 2, 'type': 'BioPlex', 'props': [{'name': 'p_int', 'value': '0.97'},
                {'name': 'p_ni', 'value': '0.02'}, {'name': 'p_wrong', 'value': '0.01'}],
                'target': {'uniprot': P2}},
            {'nid': 3, 'type': 'STRING', 'props': [{'name': 'Score', 'value': '450'}],
                'target': {'uniprot': P3}},
            {'nid': 4, 'type': 'STRING', 'props': [{'name': 'Score', 'value': '999'}],
                'target': {'uniprot': 'Q99999'}},
        ]
        self.out = self.root / 'lookup'
        self.retrieve()
        self.args = SimpleNamespace(identity_audit=self.prior,
            identity_report_sha256=audit.sha(self.prior / 'report.json'), pharos=self.out)

    def retrieve(self, **kwargs):
        retrieval.retrieve_inventory(self.inventory, self.out, chunk_size=2, profile='ppi', progress=None,
            client_factory=lambda: PharosClient(transport=self.api), **kwargs)

    def mutate_sealed(self, name, mutate):
        path = self.out / name
        value = retrieval.read_json(path)
        value.pop('content_sha256')
        mutate(value)
        write_json(path, retrieval.seal(value))

    def mutate_chunk(self, mutate, name='chunks/00002.json'):
        self.mutate_sealed(name, mutate)
        self.mutate_sealed('summary.json', lambda value: value['files'].update({name: audit.sha(self.out / name)}))

    def test_complete_retrieval_preserves_all_pairs_unresolved_alias_and_asymmetric_views(self):
        report, details = audit.audit(self.args)
        self.assertEqual(report['counts']['published_pairs'], 6)
        self.assertEqual(report['counts']['resolution_statuses'],
                         {'resolved': 2, 'not_found': 1, 'identity_mismatch': 1})
        self.assertEqual(report['counts']['raw_source_views'], 4)
        self.assertEqual(report['counts']['retained_source_views'], 3)
        self.assertEqual(report['counts']['raw_matching_pairs'], 2)
        self.assertEqual(report['counts']['retained_matching_pairs'], 2)
        self.assertEqual(report['counts']['raw_matching_source_views'], 3)
        self.assertEqual(report['counts']['asymmetric_matching_pairs_both_resolved'], 1)
        self.assertEqual(report['counts']['previous_pharos_pairs_not_returned_now'], 1)
        self.assertEqual(report['counts']['huri_either_mapping_pairs'], 1)
        self.assertEqual(report['counts']['inmc_either_mapping_pairs'], 1)
        self.assertEqual(report['counts']['pair_lookup_statuses'], {
            'present_in_raw_ppi': 2, 'no_match_one_endpoint_resolved': 3,
            'unassessed_both_requested_endpoints_unresolved': 1})
        alias = next(r for r in report['unresolved_accessions'] if r['requested_uniprot'] == P4)
        self.assertEqual(alias['returned']['uniprot'], 'P42336')
        self.assertFalse(report['outcome_fields_decoded'])
        self.assertFalse(report['independence_established'])
        self.assertEqual(len(details), 6)

    def test_properties_and_scores_never_pool_sources_or_fill_missing_with_zero(self):
        report, details = audit.audit(self.args)
        stats = {(r['source_bundle'], r['property_name']): r
                 for r in report['properties_by_provider_bundle']['candidate_raw']}
        self.assertEqual(stats[('STRING', 'Score')]['numeric_min'], 450)
        self.assertEqual(stats[('STRING', 'Score')]['numeric_max'], 900)
        self.assertEqual(stats[('STRING', 'Score')]['numeric_observations'], 2)
        self.assertEqual(stats[('BioPlex', 'p_int')]['numeric_min'], .97)
        self.assertEqual(stats[('STRING', 'tdl')]['numeric_observations'], 0)
        pair_details = next(r for r in details if tuple(r['products']) == audit.pair(P1, P2))
        self.assertEqual(pair_details['pharos_matches']['raw'][1]['record']['props'][2],
                         {'name': 'p_wrong', 'value': '0.01'})
        self.assertEqual(report['reference_named_property_counts'], {})

    def test_prior_report_hash_mismatch_rejected_before_retrieval_read(self):
        self.args.identity_report_sha256 = '0' * 64
        self.args.pharos = Path('/must/not/be/opened')
        with self.assertRaisesRegex(ValueError, 'declared hash'):
            audit.audit(self.args)

    def test_prior_output_tampering_and_unexpected_outcome_column_rejected(self):
        path = self.prior / 'identity_rows.json'
        rows = retrieval.read_json(path)
        rows[0]['result'] = 'MUST_NOT_BE_ACCEPTED'
        write_json(path, rows)
        with self.assertRaisesRegex(ValueError, 'output differs'):
            audit.audit(self.args)
        self.prior_report['output_sha256']['identity_rows.json'] = audit.sha(path)
        write_json(self.prior / 'report.json', self.prior_report)
        self.args.identity_report_sha256 = audit.sha(self.prior / 'report.json')
        with self.assertRaisesRegex(ValueError, 'no assay fields'):
            audit.audit(self.args)

    def test_prior_aggregate_flags_must_reproduce(self):
        self.prior_report['groups'][audit.GROUP]['huri_either_mapping_match_pairs'] = 5
        write_json(self.prior / 'report.json', self.prior_report)
        self.args.identity_report_sha256 = audit.sha(self.prior / 'report.json')
        with self.assertRaisesRegex(ValueError, 'aggregate report'):
            audit.audit(self.args)

    def test_incomplete_manifest_and_chunk_hash_tampering_rejected(self):
        self.mutate_sealed('summary.json', lambda d: d.update(retrieval_finished=False))
        with self.assertRaisesRegex(ValueError, 'completed retrieval'):
            audit.audit(self.args)
        self.mutate_sealed('summary.json', lambda d: d.update(retrieval_finished=True))
        with (self.out / 'chunks/00000.json').open('a') as handle:
            handle.write(' ')
        with self.assertRaisesRegex(ValueError, 'Chunk file hash'):
            audit.audit(self.args)

    def test_source_version_or_catalog_must_match_raw_receipts(self):
        self.mutate_sealed('source.json', lambda d: d.update(source_catalog=[{'name': 'invented replacement'}]))
        with self.assertRaisesRegex(ValueError, 'catalog does not reproduce'):
            audit.audit(self.args)

    def test_identity_status_must_match_actual_returned_response(self):
        def mutate(chunk):
            chunk['target_resolution'][1]['returned'] = {'uniprot': 'Q99999'}
        self.mutate_chunk(mutate)
        with self.assertRaisesRegex(ValueError, 'resolution does not reproduce'):
            audit.audit(self.args)

    def test_per_product_counts_must_reconcile_even_when_manifest_total_unchanged(self):
        def mutate(chunk):
            row = next(r for r in chunk['retrieval_coverage']['targets'] if r['family'] == 'ppis')
            row['retrieved'] = row['available'] = 3
        self.mutate_chunk(mutate)
        with self.assertRaisesRegex(ValueError, 'Per-product PPI'):
            audit.audit(self.args)

    def test_resealed_raw_page_count_mismatch_cannot_claim_complete_coverage(self):
        def mutate(chunk):
            for receipt in chunk['requests']:
                if 'Scoped_ppis' in receipt['request']['query']:
                    for response in receipt['response']['data'].values():
                        response['reported'] = [{'name': 'Total', 'value': 999}]
                    receipt['response_sha256'] = digest(receipt['response'])
        self.mutate_chunk(mutate)
        with self.assertRaisesRegex(ValueError, 'PPI page reported count'):
            audit.audit(self.args)

    def test_zero_neighbor_claim_requires_matching_raw_metadata_count(self):
        def mutate(chunk):
            for receipt in chunk['requests']:
                if 'ScopedMetadata' in receipt['request']['query']:
                    for response in receipt['response']['data'].values():
                        response['ppiCounts'] = [{'name': 'Total', 'value': 5}]
                    receipt['response_sha256'] = digest(receipt['response'])
            for target in chunk['targets']:
                target['pharos_context']['metadata']['ppiCounts'] = [{'name': 'Total', 'value': 5}]
        self.mutate_chunk(mutate, name='chunks/00000.json')
        with self.assertRaisesRegex(ValueError, 'Per-product PPI counts'):
            audit.audit(self.args)

    def test_page_locator_must_match_the_actual_raw_request_and_alias(self):
        def mutate(chunk):
            coverage = next(r for r in chunk['retrieval_coverage']['targets'] if r['family'] == 'ppis')
            coverage['pages'][0]['response_pointer'] = '/data/t9/rows'
        self.mutate_chunk(mutate)
        with self.assertRaisesRegex(ValueError, 'PPI page locators'):
            audit.audit(self.args)

    def test_raw_ppi_query_filter_cannot_differ_from_declared_profile(self):
        def mutate(chunk):
            for receipt in chunk['requests']:
                if 'Scoped_ppis' in receipt['request']['query']:
                    receipt['request']['query'] = receipt['request']['query'].replace(
                        'ppiConfidence: 400', 'ppiConfidence: 900')
        self.mutate_chunk(mutate)
        with self.assertRaisesRegex(ValueError, 'declared adapter query and filter'):
            audit.audit(self.args)

    def test_retained_records_must_be_identical_raw_views(self):
        def mutate(chunk):
            chunk['targets'][0]['pharos_context']['ppis'][0]['props'][0]['value'] = 'invented'
        self.mutate_chunk(mutate)
        with self.assertRaisesRegex(ValueError, 'no identical raw'):
            audit.audit(self.args)

    def test_cohort_filter_cannot_silently_omit_a_published_partner(self):
        def mutate(chunk):
            chunk['targets'][0]['pharos_context']['ppis'].pop()
        self.mutate_chunk(mutate)
        with self.assertRaisesRegex(ValueError, 'exactly reproduce'):
            audit.audit(self.args)

    def test_properties_keep_duplicate_values_and_mixed_provider_bundle(self):
        groups = {('STRING,BioPlex', 'Score'): {'"900"': 2, 'null': 1},
                  ('BioPlex', 'p_int'): {'"0.9"': 1, '"NaN"': 1}}
        stats = audit.summarize_properties(groups)
        self.assertEqual(len(stats), 2)
        mixed = next(r for r in stats if r['source_bundle'] == 'STRING,BioPlex')
        self.assertEqual(mixed['numeric_observations'], 2)
        self.assertEqual(mixed['nonnumeric_observations'], 1)
        self.assertEqual(mixed['numeric_median'], 900)


if __name__ == '__main__':
    unittest.main()
