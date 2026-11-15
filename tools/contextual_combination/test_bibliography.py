"""Invented metadata only; tests never contact Europe PMC or score models."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from .bibliography import (batch_url, parse_batch, year_bin, reference_inventory,
                           public_year_inventory, retrieve, run, sha, write)


class BibliographicMetadataTests(unittest.TestCase):
    def test_live_selected_PMID_export_requires_specific_user_authorization_first(self):
        with patch('tools.contextual_combination.bibliography.reference_inventory',
                   side_effect=AssertionError('no source read or network before approval')) as inventory:
            with self.assertRaisesRegex(ValueError, 'explicit user approval'):
                run({'format': 'biograph-steward.postseal-bibliographic-inventory.v1',
                     'parent_authorized_descriptive_metadata_only': True}, '/unused')
            inventory.assert_not_called()

    def test_query_is_exact_MED_ID_metadata_only(self):
        query = parse_qs(urlsplit(batch_url(['1', '2'])).query)
        self.assertEqual(query['query'], ['(EXT_ID:1 OR EXT_ID:2) AND SRC:MED'])
        self.assertEqual(query['resultType'], ['lite'])
        self.assertEqual(query['synonym'], ['false'])
        self.assertEqual(query['pageSize'], ['1000'])
        for values in (['1', '1'], ['1 OR TITLE:x'], ['0001']):
            with self.assertRaises(ValueError):
                batch_url(values)

    def test_missing_duplicate_wrong_source_and_unrequested_IDs_are_not_inferred(self):
        payload = {'hitCount': 6, 'resultList': {'result': [
            {'id': '1', 'source': 'MED', 'pubYear': '2025'},
            {'id': '2', 'source': 'MED', 'pubYear': '2020'},
            {'id': '2', 'source': 'MED', 'pubYear': '2026'},
            {'id': '3', 'source': 'AGR', 'pubYear': '2020'},
            {'id': '999', 'source': 'MED', 'pubYear': '2020'}]}}
        rows, audit = parse_batch(payload, ['1', '2', '3', '4'])
        self.assertEqual(rows['1']['status'], 'matched_exact_MED_ID')
        self.assertEqual(rows['2']['status'], 'duplicate_provider_records')
        self.assertEqual(rows['3']['status'], 'not_returned')
        self.assertEqual(rows['4']['status'], 'not_returned')
        self.assertNotIn('provider_pubYear_literal', rows['2'])
        self.assertEqual(len(audit['wrong_source_rows']), 1)
        self.assertEqual(audit['unexpected_MED_IDs'], ['999'])

    def test_provider_date_or_indexing_never_fills_missing_year_or_splits_2026(self):
        def record(year, date='2026-01-01'):
            return {'status': 'matched_exact_MED_ID', 'provider_pubYear_literal': year,
                    'provider_normalized_firstPublicationDate_literal': date,
                    'provider_firstIndexDate_literal_not_publication': '2020-01-01'}
        self.assertEqual(year_bin(record('2025')), 'pubYear_through_2025')
        self.assertEqual(year_bin(record('2026', '2026-01-01')), 'pubYear_cutoff_year_2026')
        self.assertEqual(year_bin(record('2026', '2026-12-31')), 'pubYear_cutoff_year_2026')
        self.assertEqual(year_bin(record('2027')), 'pubYear_after_2026')
        self.assertEqual(year_bin(record(None, '2020-01-01')), 'pubYear_missing_or_invalid')
        self.assertEqual(year_bin(record('2025 Jan')), 'pubYear_missing_or_invalid')

    def test_unexpected_abstracts_are_rejected_without_text_extraction(self):
        with self.assertRaisesRegex(ValueError, 'lite metadata only'):
            parse_batch({'resultList': {'result': [{'id': '1', 'source': 'MED',
                        'abstractText': 'Invented text must not be requested.'}]}}, ['1'])

    def fixture(self, root):
        views = {}
        for view in ('native', 'fixed_T0'):
            path = root / (view + '_all_label_support.jsonl')
            rows = [{'accession': 'PRIVATE_CASE_A', 'GO_ID': 'GO:1000001',
                     'frozen_model_scores': {'candidate': .0001, 'control': .99},
                     'positive_support': [{'references': ['PMID:1', 'PMID:2', 'DOI:invented']}]},
                    {'accession': 'PRIVATE_CASE_B', 'GO_ID': 'GO:1000002',
                     'frozen_model_scores': {'candidate': .99, 'control': .0001},
                     'positive_support': [{'references': ['PMID:2', 'PMID:3', 'PMID:4']}]}]
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            views[view] = {'complete_label_support_file': str(path), 'sha256': sha(path),
                           'aggregate': {'labels': 2, 'distinct_literal_PMID_identifiers': 4}}
        report = root / 'provenance_report.json'
        write(report, {'forecast_seal_sha256': 'a' * 64,
                      'scores_labels_models_choices_or_thresholds_changed': False, 'views': views})
        return report

    def test_every_support_PMID_included_before_request_and_publication_is_aggregate_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            provenance = self.fixture(root)
            output = root / 'output'
            def transport(url):
                inventory = json.loads((output / 'private_reference_inventory.json').read_text())
                self.assertEqual(inventory['union_pmids'], ['1', '2', '3', '4'])
                return json.dumps({'request': {'resultType': 'lite'}, 'hitCount': 3,
                    'resultList': {'result': [{'id': '1', 'source': 'MED', 'pubYear': '2025',
                         'firstPublicationDate': '2025-01-01'},
                        {'id': '2', 'source': 'MED', 'pubYear': '2026'},
                        {'id': '3', 'source': 'MED', 'firstPublicationDate': '2020-01-01'}]}}).encode()
            report = run({'format': 'biograph-steward.postseal-bibliographic-inventory.v1',
                'parent_authorized_descriptive_metadata_only': True,
                'provenance_report': str(provenance), 'provenance_report_sha256': sha(provenance),
                'forecast_seal_sha256': 'a' * 64}, output, transport=transport)
            self.assertEqual(report['API_status_counts'], {'matched_exact_MED_ID': 3, 'not_returned': 1})
            for view in report['views'].values():
                self.assertEqual(view['distinct_requested_PMID_identifiers'], 4)
                self.assertTrue(all(b['count'] == 1 for b in view['year_bins'].values() if b['count']))
                self.assertEqual(view['year_bins']['pubYear_through_2025']['fraction_of_all_requested_PMIDs'], .25)
            text = (output / 'aggregate_report.json').read_text()
            for private in ('PRIVATE_CASE_A', 'PRIVATE_CASE_B', 'GO:1000001', 'PMID:1', 'frozen_model_scores'):
                self.assertNotIn(private, text)
            self.assertFalse(report['new_accuracy_endpoint_threshold_choice_or_model_fit'])

    def test_network_failures_remain_explicit_missing_coverage_after_bounded_attempts(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch('tools.contextual_combination.bibliography.time.sleep'):
                with patch('builtins.print'):
                    def failing(_):
                        raise TimeoutError('invented unavailable provider')
                    records, batches = retrieve(['1', '2'], Path(temporary) / 'cache', transport=failing)
            self.assertEqual(records, {'1': {'status': 'request_error'}, '2': {'status': 'request_error'}})
            batch = json.loads(Path(batches[0]['file']).read_text())
            self.assertEqual(len(batch['attempts']), 3)
            self.assertFalse(list((Path(temporary) / 'cache').glob('*_lite_response.json')))


if __name__ == '__main__':
    unittest.main()
