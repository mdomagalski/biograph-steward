"""Invented-only controls; no captured scientific source is opened here."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import LICENSES, VERSION, PharosError
from biograph_steward.intact_final_publication import publish_material
from scripts import run_pharos_reliability as reliability
from scripts.intact_final_common import summarize
from test_intact_fresh_publication import fresh_material
from test_pharos_inventory import InventoryAPI


class Response(BytesIO):
    status = 200


class NativeAPI:
    def __init__(self, *, license_timeout=False):
        self.api = InventoryAPI()
        self.api.context['P00533']['ppis'] = [{'nid': 5, 'type': 'STRINGDB',
            'target': {'uniprot': 'P04637', 'sym': 'INVENTED'}}]
        self.license_timeout = license_timeout
        self.requests = []

    def __call__(self, request, **kwargs):
        payload = json.loads(request.data)
        self.requests.append(payload)
        if self.license_timeout and 'query SourceLicenses' in payload['query']:
            self.license_timeout = False
            raise TimeoutError('Invented license timeout, then recovery')
        return Response(json.dumps(self.api(payload)).encode())


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def client(self, name='batch', total=None):
        folder = self.root / name
        folder.mkdir()
        return reliability.ReliabilityClient(folder, self.root / 'cache',
            total if total is not None else {'logical_requests': 0, 'actual_attempts': 0})

    def test_native_timeout_recovers_and_verified_license_cache_prevents_next_http(self):
        api = NativeAPI(license_timeout=True)
        first = self.client()
        with patch('biograph_steward.client.urlopen', side_effect=api), patch('biograph_steward.client.time.sleep'):
            first.execute(LICENSES)
        self.assertEqual(first.actual_attempts, 2)
        events = reliability._jsonl(first.folder / 'http_attempts.jsonl')
        self.assertEqual([event['phase'] for event in events], ['started', 'finished', 'started', 'finished'])
        self.assertEqual(events[1]['outcome'], 'retry_scheduled')
        second = self.client('second')
        with patch('biograph_steward.client.urlopen', side_effect=AssertionError('Cache hit used HTTP')):
            second.execute(LICENSES)
        self.assertTrue(second.records[0]['loaded_from_cache'])
        self.assertEqual(second.actual_attempts, 0)
        self.assertFalse((second.folder / 'http_attempts.jsonl').exists())

    def test_attempt_and_logical_caps_stop_before_another_http_open(self):
        for counter, cap in (('actual_attempts', 84), ('logical_requests', 28)):
            client = self.client(counter, {'logical_requests': 0, 'actual_attempts': 0, counter: cap})
            with patch('biograph_steward.client.urlopen') as opening:
                with self.assertRaises(reliability.ReliabilityBudgetExceeded):
                    client.execute(VERSION)
            opening.assert_not_called()
        client = self.client('per_pair')
        client.actual_attempts = 21
        with patch('biograph_steward.client.urlopen') as opening, self.assertRaises(reliability.ReliabilityBudgetExceeded):
            client.execute(VERSION)
        opening.assert_not_called()

    def test_exhausted_native_retries_are_retained_as_failure_not_cached_success(self):
        client = self.client()
        with patch('biograph_steward.client.urlopen', side_effect=TimeoutError('invented timeout')) as opening, \
                patch('biograph_steward.client.time.sleep'):
            with self.assertRaises(PharosError):
                client.execute(LICENSES)
        self.assertEqual(opening.call_count, 3)
        self.assertEqual(client.records, [])
        self.assertFalse((self.root / 'cache').exists())
        events = reliability._jsonl(client.folder / 'http_attempts.jsonl')
        self.assertEqual(sum(row['phase'] == 'started' for row in events), 3)
        self.assertEqual(events[-1]['outcome'], 'failed')
        logical = reliability._jsonl(client.folder / 'logical_requests.jsonl')
        self.assertEqual(logical[-1]['outcome'], 'failed')

    def test_complete_ordinary_flow_preserves_source_fields_after_transport_recovery(self):
        files, catalog, bindings, inspection, records, ledger = fresh_material()
        publication = self.root / 'publication'
        publish_material(files, catalog, bindings, inspection, publication)
        references = [{'ledger': item, 'reader_record': record['reader_record']}
                      for item, record in zip(ledger, records)]
        source_before = {path.relative_to(publication).as_posix(): path.read_bytes()
                         for path in publication.rglob('*') if path.is_file()}
        client, api = self.client(), NativeAPI(license_timeout=True)
        with patch('biograph_steward.client.urlopen', side_effect=api), patch('biograph_steward.client.time.sleep'):
            evaluation, checks = reliability.evaluate_pair(references, references, publication,
                source_before, client.folder, client)
        self.assertEqual(len(evaluation['rows']), 4)
        self.assertTrue(all(row['strict_fidelity'] for row in evaluation['rows']))
        self.assertTrue(all(check['passed'] for check in checks + evaluation['global_checks']))
        self.assertTrue((client.folder / 'packet/source/assay_source/publication.json').is_file())
        self.assertEqual(source_before, {path.relative_to(publication).as_posix(): path.read_bytes()
                                       for path in publication.rglob('*') if path.is_file()})
        self.assertGreater(client.actual_attempts, client.logical_requests)

    def test_missing_outputs_keep_all_eight_source_rows_in_denominator_and_empty_strata(self):
        _, _, _, _, records, ledger = fresh_material()
        references = []
        for item, record in zip(ledger, records):
            for offset in (0, 1):
                entry, reader = deepcopy(item), deepcopy(record['reader_record'])
                entry['source_line'] += offset
                reader['line_number'] += offset
                references.append({'ledger': entry, 'reader_record': reader})
        evaluation = reliability.evaluate_rows(references, [], [], [], [], '',
                                              graph_edges=[], columns=reliability.field_groups())
        metrics = summarize(evaluation, references, list(reliability.FRESH))
        self.assertEqual(metrics['coverage']['denominator'], 8)
        self.assertEqual(metrics['coverage']['numerator'], 0)
        self.assertEqual(metrics['strict_fidelity']['denominator'], 8)
        self.assertTrue(any(value['status'] == 'unevaluated_empty_stratum'
                            for strata in metrics['strata'].values() for value in strata.values()))

    def test_existing_output_is_rejected_before_source_reads_or_http(self):
        with patch.object(reliability, 'load_panel', side_effect=AssertionError('Existing output opened sources')), \
                patch('biograph_steward.client.urlopen', side_effect=AssertionError('Existing output used network')):
            with self.assertRaises(ValueError):
                reliability.execute(self.root)

    def test_new_sibling_inside_historical_assessment_is_rejected_before_source_access(self):
        origin = self.root / 'historical_assessment/execution'
        origin.mkdir(parents=True)
        with patch.object(reliability, 'ORIGIN', origin), \
                patch.object(reliability, 'load_panel', side_effect=AssertionError('Historical output opened sources')), \
                patch('biograph_steward.client.urlopen', side_effect=AssertionError('Historical output used network')):
            with self.assertRaises(ValueError):
                reliability.execute(origin.parent / 'new_sibling')


if __name__ == '__main__':
    unittest.main()
