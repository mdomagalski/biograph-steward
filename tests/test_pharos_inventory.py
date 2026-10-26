"""Synthetic explicit-accession retrieval contracts; no assay outcomes are read."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import PharosClient, PharosError, VERSION, digest, write_json
from test_retrieval import ContextAPI


SPEC = importlib.util.spec_from_file_location(
    "retrieve_pharos_inventory", Path(__file__).resolve().parents[1] / "scripts/retrieve_pharos_inventory.py")
retrieval = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retrieval)

GENES = [f"ENSG{i:011d}" for i in range(1, 7)]


def inventory_fixture():
    return {
        "format": "biograph-steward.inmc-context-targets.v1",
        "panel_gene_ids": GENES,
        "panel_genes_without_confirmed_context": [GENES[5]],
        "targets": [
            {"uniprot_id": "UniProtKB:P04637", "panel_gene_ids": [GENES[0], GENES[2]], "hgnc_ids": ["HGNC:1"]},
            {"uniprot_id": "UniProtKB:P00533", "panel_gene_ids": [GENES[1], GENES[2]], "hgnc_ids": ["HGNC:2"]},
            {"uniprot_id": "UniProtKB:P01116", "panel_gene_ids": [GENES[3]], "hgnc_ids": ["HGNC:3"]},
            {"uniprot_id": "UniProtKB:P15056", "panel_gene_ids": [GENES[4]], "hgnc_ids": ["HGNC:4"]},
        ],
    }


def accession_only_fixture():
    return {
        "format": "biograph-steward.lambourne-ppi-lookup-candidate-inventory.v1",
        "author_commit": "a" * 40,
        "author_panel_sha256": "b" * 64,
        "published_uniprot_accessions": ["P04637", "P00533", "P01116", "P15056"],
        "outcome_fields_decoded": False,
    }


class InventoryAPI(ContextAPI):
    def __init__(self):
        super().__init__()
        self.identities = {
            row['uniprot']: {key: row[key] for key in ['uniprot', 'sym', 'name', 'tdl', 'fam']}
            for row in self.rows
        }
        self.identities.update({'P01116': None, 'P15056': {'uniprot': 'P42336', 'name': 'Different target'}})

    def __call__(self, payload):
        if 'ExplicitInventoryTargets' in payload['query']:
            self.calls.append(deepcopy(payload))
            return {'data': {f't{i}': deepcopy(self.identities[uid])
                             for i, uid in enumerate(payload['variables'].values())}}
        return super().__call__(payload)


class InventoryRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.inventory_path = self.root / 'inventory.json'
        write_json(self.inventory_path, inventory_fixture())
        self.out = self.root / 'retrieved'
        self.api = InventoryAPI()

    def run_inventory(self, **kwargs):
        options = dict(chunk_size=1, progress=None,
                       client_factory=lambda: PharosClient(transport=self.api))
        options.update(kwargs)
        return retrieval.retrieve_inventory(self.inventory_path, self.out, **options)

    def assert_locators(self, chunk):
        for row in chunk['target_resolution']:
            envelope = chunk['requests'][row['request_index']]
            key = row['response_pointer'].split('/')[-1]
            self.assertEqual(envelope['response']['data'][key], row['returned'])
            self.assertIn('ExplicitInventoryTargets', envelope['request']['query'])
        for row in (chunk['retrieval_coverage'] or {}).get('targets', []):
            for page in row['pages']:
                envelope = chunk['requests'][page['request_index']]
                alias = page['response_pointer'].split('/')[2]
                response = envelope['response']['data'][alias]
                self.assertEqual(response['uniprot'], row['uniprot'])
                self.assertEqual(len(response['rows']), page['returned'])
                self.assertIn('Scoped_' + row['family'], envelope['request']['query'])
        for envelope in chunk['requests']:
            self.assertEqual(envelope['response_sha256'], digest(envelope['response']))

    def test_complete_retrieval_preserves_identity_exceptions_genes_and_cross_chunk_links(self):
        summary = self.run_inventory()
        self.assertTrue(summary['retrieval_finished'])
        self.assertEqual(summary['resolution_statuses'], {'resolved': 2, 'not_found': 1, 'identity_mismatch': 1})
        self.assertEqual(summary['original_gene_count'], 6)
        self.assertEqual(summary['genes_with_resolved_context'], 3)
        coverage = {row['original_gene_id']: row for row in retrieval.read_json(self.out / 'gene_coverage.json')}
        self.assertEqual(set(coverage), set(GENES))
        self.assertEqual(coverage[GENES[2]]['resolved_products'], ['P00533', 'P04637'])
        self.assertEqual(coverage[GENES[3]]['requested_products'], ['P01116'])
        self.assertEqual(coverage[GENES[3]]['resolved_products'], [])
        self.assertEqual(coverage[GENES[4]]['resolved_products'], [])
        self.assertEqual(coverage[GENES[5]]['requested_products'], [])
        chunks = [retrieval.verify_sealed(retrieval.read_json(p)) for p in sorted((self.out / 'chunks').glob('*.json'))]
        self.assertEqual(len(chunks), 4)
        for chunk in chunks:
            self.assert_locators(chunk)
            self.assertFalse(chunk['disease_filter_used'])
            self.assertFalse(chunk['outcome_values_loaded'])
            self.assertFalse(chunk['feature_use_approved'])
        target = next(t for c in chunks for t in c['targets'] if t['uniprot'] == 'P04637')
        self.assertEqual({r['target']['uniprot'] for r in target['pharos_context']['ppis']}, {'P00533', 'P01116'})
        self.assertEqual(target['pharos_context']['expressions'], self.api.context['P04637']['expressions'])
        self.assertFalse(any('associatedDisease' in c['query'] or 'DiseaseTargets' in c['query'] for c in self.api.calls))

    def test_completed_resume_reads_saved_chunks_without_constructing_a_client(self):
        self.run_inventory()
        before = {p.name: p.read_bytes() for p in (self.out / 'chunks').glob('*.json')}
        summary = self.run_inventory(resume=True, client_factory=lambda: self.fail('Completed resume performed a request'))
        self.assertTrue(summary['retrieval_finished'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.out / 'chunks').glob('*.json')})

    def test_partial_resume_retrieves_only_uncompleted_chunks(self):
        first = self.run_inventory(stop_after_chunks=1)
        self.assertFalse(first['retrieval_finished'])
        saved = (self.out / 'chunks/00000.json').read_bytes()
        self.api.calls.clear()
        summary = self.run_inventory(resume=True)
        queried = [uid for call in self.api.calls if 'ExplicitInventoryTargets' in call['query']
                   for uid in call['variables'].values()]
        self.assertEqual(queried, ['P01116', 'P04637', 'P15056'])
        self.assertEqual(saved, (self.out / 'chunks/00000.json').read_bytes())
        self.assertTrue(summary['retrieval_finished'])

    def test_changed_inventory_binding_rejects_resume_before_requests(self):
        self.run_inventory(stop_after_chunks=1)
        inventory = inventory_fixture()
        inventory['targets'][0]['hgnc_ids'] = ['HGNC:99']
        write_json(self.inventory_path, inventory)
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.run_inventory(resume=True, client_factory=lambda: self.fail('Changed binding performed a request'))

    def test_corrupt_chunk_or_response_rejected_before_requests(self):
        self.run_inventory(stop_after_chunks=1)
        path = self.out / 'chunks/00000.json'
        original = retrieval.read_json(path)
        for reseal in [False, True]:
            with self.subTest(reseal=reseal):
                changed = deepcopy(original)
                changed['requests'][0]['response']['data']['dbVersion'] = 'CORRUPTED'
                if reseal:
                    changed.pop('content_sha256')
                    changed = retrieval.seal(changed)
                write_json(path, changed)
                with self.assertRaisesRegex(ValueError, 'changed'):
                    self.run_inventory(resume=True, client_factory=lambda: self.fail('Corrupt chunk performed a request'))

    def test_wrong_chunk_plan_binding_rejected_before_requests(self):
        self.run_inventory(stop_after_chunks=1)
        path = self.out / 'chunks/00000.json'
        changed = retrieval.read_json(path)
        changed.pop('content_sha256')
        changed['plan_sha256'] = 'different_plan'
        write_json(path, retrieval.seal(changed))
        with self.assertRaisesRegex(ValueError, 'plan'):
            self.run_inventory(resume=True, client_factory=lambda: self.fail('Wrong chunk binding performed a request'))

    def test_missing_source_on_resume_with_existing_chunks_fails_before_requests(self):
        self.run_inventory(stop_after_chunks=1)
        (self.out / 'source.json').unlink()
        with self.assertRaises((ValueError, PharosError)):
            self.run_inventory(resume=True, client_factory=lambda: self.fail('Missing source triggered metadata requests'))

    def test_source_plan_and_endpoint_bindings_reject_copied_metadata(self):
        self.run_inventory(stop_after_chunks=1)
        path = self.out / 'source.json'
        original = retrieval.read_json(path)
        for key, value in [('plan_sha256', 'other_plan'), ('endpoint', 'https://different.example/graphql')]:
            with self.subTest(key=key):
                changed = deepcopy(original)
                changed.pop('content_sha256')
                changed[key] = value
                write_json(path, retrieval.seal(changed))
                with self.assertRaisesRegex(ValueError, 'plan/endpoint'):
                    self.run_inventory(resume=True, client_factory=lambda: self.fail('Copied source metadata performed a request'))

    def test_changed_saved_inventory_rejects_resume_before_requests(self):
        self.run_inventory(stop_after_chunks=1)
        path = self.out / 'context_targets.json'
        changed = retrieval.read_json(path)
        changed['targets'][0]['hgnc_ids'] = ['HGNC:99']
        write_json(path, changed)
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            self.run_inventory(resume=True, client_factory=lambda: self.fail('Changed saved inventory performed a request'))

    def test_saved_chunk_version_must_match_source_before_requests(self):
        self.run_inventory(stop_after_chunks=1)
        path = self.out / 'chunks/00000.json'
        changed = retrieval.read_json(path)
        changed.pop('content_sha256')
        changed['db_version_before'] = changed['db_version_after'] = 'DIFFERENT-VERSION'
        write_json(path, retrieval.seal(changed))
        with self.assertRaisesRegex(ValueError, 'different Pharos versions'):
            self.run_inventory(resume=True, client_factory=lambda: self.fail('Changed chunk version performed a request'))

    def test_version_change_during_chunk_prevents_publication(self):
        calls = 0

        def changed_version(payload):
            nonlocal calls
            if 'DatabaseVersion' in payload['query']:
                calls += 1
                return {'data': {'dbVersion': 'TEST-ONLY' if calls == 1 else 'NEW-VERSION'}}
            return self.api(payload)

        with self.assertRaisesRegex(PharosError, 'changed during this chunk'):
            retrieval.build_chunk(PharosClient(transport=changed_version), ['P04637'], ['P04637'], 'TEST-ONLY')
        self.assertFalse(self.out.exists())

    def test_no_resolved_target_cannot_claim_reconciled_context(self):
        self.api.identities = {uid: None for uid in self.api.identities}
        summary = self.run_inventory()
        self.assertTrue(summary['retrieval_finished'])
        self.assertEqual(summary['resolution_statuses'], {'not_found': 4})
        self.assertEqual(summary['genes_with_resolved_context'], 0)
        self.assertFalse(summary['all_requested_families_count_reconciled'])

    def test_chunk_locator_indices_ignore_earlier_client_requests(self):
        client = PharosClient(transport=self.api)
        client.execute(VERSION)
        chunk = retrieval.build_chunk(client, ['P04637'], ['P00533', 'P04637'], 'TEST-ONLY')
        self.assert_locators(chunk)
        self.assertEqual(chunk['target_resolution'][0]['request_index'], 1)

    def test_retrieval_never_opens_neighboring_outcome_files(self):
        forbidden = self.root / 'reserved-outcomes.tsv'
        forbidden.write_bytes(b'\xff\xff\xff')
        original_open = Path.open
        read_paths = []

        def guarded_open(path, *args, **kwargs):
            mode = args[0] if args else kwargs.get('mode', 'r')
            if 'r' in mode:
                if path == forbidden:
                    raise AssertionError('Experimental outcomes were opened')
                read_paths.append(path)
            return original_open(path, *args, **kwargs)

        with patch.object(Path, 'open', guarded_open):
            summary = self.run_inventory()
        allowed = {self.inventory_path, Path(retrieval.__file__),
                   retrieval.ROOT / 'biograph_steward/client.py', retrieval.ROOT / 'biograph_steward/retrieval.py'}
        self.assertTrue(all(p in allowed or p.is_relative_to(self.out) for p in read_paths))
        self.assertFalse(summary['outcome_values_loaded'])
        self.assertFalse(summary['feature_use_approved'])
        self.assertEqual(summary['model_requests'], 0)

    def test_ppi_profile_fetches_only_ppi_rows_but_preserves_other_family_metadata(self):
        write_json(self.inventory_path, accession_only_fixture())
        # This response is deliberately outside the declared cohort. It must
        # remain in the source envelope without becoming a retained cohort edge.
        outside = {'nid': 3, 'type': 'TEST', 'target': {'uniprot': 'P42336'}}
        self.api.context['P04637']['ppis'].append(outside)
        summary = self.run_inventory(profile='ppi')
        self.assertTrue(summary['retrieval_finished'])
        self.assertTrue(summary['all_requested_families_count_reconciled'])
        self.assertEqual(summary['resolution_statuses'],
                         {'resolved': 2, 'not_found': 1, 'identity_mismatch': 1})
        pages = [c for c in self.api.calls if 'Scoped_' in c['query']]
        self.assertTrue(pages)
        self.assertTrue(all('Scoped_ppis' in c['query'] for c in pages))
        self.assertTrue(any('ScopedMetadata' in c['query'] for c in self.api.calls))
        plan = retrieval.read_json(self.out / 'plan.json')
        self.assertEqual(plan['profile'], 'ppi')
        self.assertEqual(plan['ppi_cohort'], sorted(accession_only_fixture()['published_uniprot_accessions']))
        self.assertEqual(plan['limits']['ppis'], 5000)
        for family in set(plan['limits']) - {'ppis'}:
            self.assertEqual(plan['limits'][family], 0)
            row = summary['families'][family]
            self.assertEqual(row['retrieved'], 0)
            self.assertEqual(row['retained'], 0)
            self.assertEqual(row['target_statuses'], {'not_requested': 2})
        self.assertGreater(summary['families']['go']['available'], 0)
        self.assertGreater(summary['families']['expressions']['available'], 0)
        self.assertEqual(summary['families']['ppis']['retrieved'], 3)
        self.assertEqual(summary['families']['ppis']['retained'], 2)
        self.assertEqual(summary['families']['ppis']['excluded_by_scope'], 1)
        # P00533 has a count-confirmed zero-neighbor result; it is complete,
        # distinct from the two identities that could not be resolved exactly.
        self.assertEqual(summary['families']['ppis']['target_statuses'], {'complete': 2})
        chunks = [retrieval.read_json(p) for p in (self.out / 'chunks').glob('*.json')]
        for chunk in chunks:
            self.assert_locators(chunk)
        target = next(t for c in chunks for t in c['targets'] if t['uniprot'] == 'P04637')
        self.assertEqual({r['target']['uniprot'] for r in target['pharos_context']['ppis']},
                         {'P00533', 'P01116'})
        source_rows = [r for c in chunks for e in c['requests']
                       if 'Scoped_ppis' in e['request']['query']
                       for response in e['response']['data'].values() for r in response['rows']]
        self.assertIn(outside, source_rows)
        queried = {uid for c in self.api.calls for key, uid in c['variables'].items()
                   if key.startswith('id')}
        self.assertNotIn('P42336', queried)

    def test_accession_inventory_keeps_original_product_identity_without_inventing_genes(self):
        fixture = accession_only_fixture()
        write_json(self.inventory_path, fixture)
        original = self.inventory_path.read_bytes()
        summary = self.run_inventory(profile='ppi')
        self.assertEqual(summary['identity_level'], 'author_protein_accession')
        self.assertIsNone(summary['original_gene_count'])
        self.assertIsNone(summary['genes_with_resolved_context'])
        self.assertEqual(retrieval.read_json(self.out / 'gene_coverage.json'), [])
        self.assertEqual((self.out / 'context_targets.json').read_bytes(), original)
        self.assertEqual(retrieval.read_json(self.out / 'accession_coverage.json'), [
            {'requested_uniprot': 'P00533', 'resolved': True},
            {'requested_uniprot': 'P01116', 'resolved': False},
            {'requested_uniprot': 'P04637', 'resolved': True},
            {'requested_uniprot': 'P15056', 'resolved': False},
        ])
        self.assertFalse(summary['outcome_values_loaded'])
        self.assertFalse(summary['feature_use_approved'])
        self.assertEqual(summary['model_requests'], 0)

    def test_accession_inventory_rejects_bad_identifiers_before_requests(self):
        for ids in [None, [], 'P04637', ['P04637', 'P04637'], ['bad-accession'],
                    ['P04637', None], ['P04637', {}], ['UniProtKB:P04637']]:
            with self.subTest(ids=ids):
                fixture = accession_only_fixture()
                fixture['published_uniprot_accessions'] = ids
                write_json(self.inventory_path, fixture)
                with self.assertRaisesRegex(ValueError, 'unique valid accessions'):
                    self.run_inventory(profile='ppi', client_factory=lambda: self.fail('Invalid IDs made requests'))
                self.assertFalse(self.out.exists())

    def test_accession_inventory_requires_reviewed_identity_only_source_bindings(self):
        for key, value in [('author_commit', 'bad'), ('author_panel_sha256', 'bad'),
                           ('outcome_fields_decoded', True), ('outcome_fields_decoded', None)]:
            with self.subTest(key=key, value=value):
                fixture = accession_only_fixture()
                fixture[key] = value
                write_json(self.inventory_path, fixture)
                with self.assertRaisesRegex(ValueError, 'author source bindings'):
                    self.run_inventory(profile='ppi', client_factory=lambda: self.fail('Invalid binding made requests'))
                self.assertFalse(self.out.exists())

    def test_accession_only_inventory_cannot_implicitly_expand_to_full_context(self):
        write_json(self.inventory_path, accession_only_fixture())
        with self.assertRaisesRegex(ValueError, 'ppi profile only'):
            self.run_inventory(client_factory=lambda: self.fail('Expanded profile made requests'))
        self.assertFalse(self.out.exists())

    def test_profile_change_on_resume_is_rejected_before_requests(self):
        self.run_inventory(profile='ppi', stop_after_chunks=1)
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.run_inventory(profile='context', resume=True,
                               client_factory=lambda: self.fail('Changed profile made requests'))

    def test_completed_ppi_resume_requires_no_network(self):
        write_json(self.inventory_path, accession_only_fixture())
        self.run_inventory(profile='ppi')
        before = {p.name: p.read_bytes() for p in (self.out / 'chunks').glob('*.json')}
        summary = self.run_inventory(profile='ppi', resume=True,
                                     client_factory=lambda: self.fail('Completed PPI resume made requests'))
        self.assertTrue(summary['retrieval_finished'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.out / 'chunks').glob('*.json')})

    def test_ppi_profile_batches_neighbors_and_preserves_alias_locators(self):
        write_json(self.inventory_path, accession_only_fixture())
        self.api.context['P00533']['ppis'] = [
            {'nid': 8, 'type': 'TEST', 'target': {'uniprot': 'P04637'}}]
        summary = self.run_inventory(profile='ppi', chunk_size=4)
        pages = [c for c in self.api.calls if 'Scoped_ppis' in c['query']]
        self.assertEqual(len(pages), 1)
        self.assertEqual({v for k, v in pages[0]['variables'].items() if k.startswith('id')},
                         {'P00533', 'P04637'})
        chunk = retrieval.read_json(self.out / 'chunks/00000.json')
        self.assert_locators(chunk)
        self.assertEqual(summary['families']['ppis']['retrieved'], 3)
        self.assertTrue(summary['all_requested_families_count_reconciled'])

    def test_finished_ppi_lookup_with_changed_counts_is_not_complete_evidence_coverage(self):
        write_json(self.inventory_path, accession_only_fixture())
        self.api.modify = lambda family, uid, skip, row: (
            {**row, 'reported': [{'name': 'Total', 'value': 99}]}
            if family == 'ppis' and uid == 'P04637' else row)
        summary = self.run_inventory(profile='ppi')
        self.assertTrue(summary['retrieval_finished'])
        self.assertFalse(summary['all_requested_families_count_reconciled'])
        self.assertEqual(summary['families']['ppis']['target_statuses'],
                         {'complete': 1, 'inconsistent': 1})

    def test_ppi_unknown_counts_do_not_turn_empty_page_into_confirmed_absence(self):
        write_json(self.inventory_path, accession_only_fixture())
        original_count = self.api.count_for
        self.api.count_for = lambda family, uid: None if family == 'ppis' else original_count(family, uid)
        summary = self.run_inventory(profile='ppi')
        self.assertTrue(summary['retrieval_finished'])
        self.assertFalse(summary['all_requested_families_count_reconciled'])
        self.assertIsNone(summary['families']['ppis']['available'])
        self.assertEqual(summary['families']['ppis']['target_statuses'], {'exhausted': 2})


if __name__ == '__main__':
    unittest.main()
