"""Synthetic overlap inventories with deliberately undecodable assay fields."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from biograph_steward.client import PharosClient, digest, write_json
from test_pharos_inventory import GENES, InventoryAPI, inventory_fixture, retrieval

SPEC = importlib.util.spec_from_file_location(
    "audit_pharos_inventory", Path(__file__).resolve().parents[1] / "scripts/audit_pharos_inventory.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
from audit_inmc_inputs import PANEL_HEADER


class InventoryAuditTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.archive = self.root / 'synthetic.zip'
        pairs = [(GENES[0], GENES[1]), (GENES[1], GENES[0]), (GENES[2], GENES[2]),
                 (GENES[0], GENES[2]), (GENES[3], GENES[4]), (GENES[5], GENES[0])]
        self.panel = PANEL_HEADER + b'\n' + b''.join(
            f'{a}\t{b}\t'.encode('ascii') + b'\xff\t\xff\t\xff\t\xff\n' for a, b in pairs)
        with zipfile.ZipFile(self.archive, 'w') as bundle:
            bundle.writestr(audit.PANEL_MEMBER, self.panel)
            bundle.writestr('author-positive-pairs.xlsx', b'NEVER OPEN')
        self.archive_sha = audit.sha256(self.archive.read_bytes())
        self.pin = patch.object(audit, 'ARCHIVE_SHA256', self.archive_sha)
        self.pin.start()
        self.addCleanup(self.pin.stop)
        inventory = inventory_fixture()
        inventory['archive_sha256'] = self.archive_sha
        self.inventory = self.root / 'inventory.json'
        write_json(self.inventory, inventory)
        self.folder = self.root / 'retrieval'
        self.api = InventoryAPI()
        self.api.context['P00533']['ppis'] = [
            {'nid': 10, 'type': 'BioPlex,STRINGDB', 'props': [],
             'target': {'uniprot': 'P04637', 'sym': 'TEST_0'}}]
        self.api.context['P04637']['ppis'].append(
            {'nid': 11, 'type': 'Reactome', 'props': [{'name': 'reference', 'value': 'PMID:36949045'}],
             'target': {'uniprot': 'P04637', 'sym': 'TEST_0'}})
        retrieval.retrieve_inventory(self.inventory, self.folder, chunk_size=1, progress=None,
                                     client_factory=lambda: PharosClient(transport=self.api))

    def run_audit(self):
        return audit.audit(self.folder, self.archive)

    def replace_chunk(self, transform):
        path = self.folder / 'chunks/00000.json'
        chunk = retrieval.read_json(path)
        chunk.pop('content_sha256')
        transform(chunk)
        write_json(path, retrieval.seal(chunk))
        summary = retrieval.read_json(self.folder / 'summary.json')
        summary.pop('content_sha256')
        summary['files']['chunks/00000.json'] = retrieval.file_sha(path)
        write_json(self.folder / 'summary.json', retrieval.seal(summary))

    def test_shared_products_reverse_views_and_cross_chunk_matches_are_preserved(self):
        report, overlaps = self.run_audit()
        self.assertEqual(report['counts']['original_candidate_rows'], 6)
        self.assertEqual(report['counts']['original_unordered_candidate_pairs'], 5)
        self.assertEqual(report['counts']['original_self_pairs'], 1)
        self.assertEqual(report['counts']['equivalent_unordered_product_pairs'], 4)
        self.assertEqual(report['counts']['self_equivalent_product_pairs'], 2)
        for view in ['raw', 'retained']:
            self.assertEqual(report['ppi_overlap'][view]['source_views_scanned'], 4)
            self.assertEqual(report['ppi_overlap'][view]['matching_source_views'], 3)
            self.assertEqual(report['ppi_overlap'][view]['matching_unordered_product_pairs'], 2)
            self.assertEqual(report['ppi_overlap'][view]['matching_views_by_provider'],
                             {'BioPlex': 1, 'STRINGDB': 2, 'Reactome': 1})
        forward = next(row for row in overlaps['candidate_pairs'] if row['original_genes'] == [GENES[0], GENES[1]])
        self.assertEqual([(r['source'], r['target']) for r in forward['source_rows']],
                         [(GENES[0], GENES[1]), (GENES[1], GENES[0])])
        shared = next(row for row in overlaps['candidate_pairs'] if row['original_genes'] == [GENES[0], GENES[2]])
        self.assertIn(['P04637', 'P04637'], shared['equivalent_product_pairs'])
        self.assertFalse(shared['self_pair'])
        chunks = {row['locator'].split('#')[0] for row in overlaps['matches']['raw']}
        self.assertEqual(chunks, {'chunks/00000.json', 'chunks/00002.json'})

    def test_unmapped_and_unresolved_pairs_stay_in_full_candidate_inventory(self):
        report, overlaps = self.run_audit()
        self.assertEqual(report['counts']['original_pairs_without_mapped_context'], 1)
        self.assertEqual(report['counts']['original_pairs_without_resolved_pharos_context'], 2)
        unmapped = next(row for row in overlaps['candidate_pairs'] if GENES[5] in row['original_genes'])
        self.assertEqual(unmapped['equivalent_product_pairs'], [])
        self.assertEqual(unmapped['missing_mapped_context_genes'], [GENES[5]])
        unresolved = next(row for row in overlaps['candidate_pairs'] if GENES[4] in row['original_genes'])
        self.assertEqual(unresolved['equivalent_product_pairs'], [['P01116', 'P15056']])
        self.assertFalse(report['exposure']['candidate_pairs_excluded'])

    def test_only_named_identity_member_is_opened_and_outcomes_are_never_decoded(self):
        opened = []
        original = zipfile.ZipFile.read

        def guarded_read(bundle, name, *args, **kwargs):
            opened.append(name)
            if name != audit.PANEL_MEMBER:
                raise AssertionError('An unrelated experimental member was opened')
            return original(bundle, name, *args, **kwargs)

        with patch.object(zipfile.ZipFile, 'read', guarded_read):
            report, _ = self.run_audit()
        self.assertEqual(opened, [audit.PANEL_MEMBER])
        self.assertTrue(report['exposure']['only_pair_identity_fields_decoded'])
        self.assertFalse(report['exposure']['outcome_values_decoded'])
        self.assertFalse(report['exposure']['author_positive_pairs_opened'])
        self.assertFalse(report['exposure']['labels_or_features_generated'])

    def test_wrong_archive_hash_fails_before_opening_any_member(self):
        self.archive.write_bytes(b'changed archive')
        with patch.object(zipfile.ZipFile, 'read', side_effect=AssertionError('Wrong archive was opened')):
            with self.assertRaisesRegex(ValueError, 'checked Zenodo release'):
                self.run_audit()

    def test_raw_source_mutation_rejected_even_with_resealed_outer_artifacts(self):
        self.replace_chunk(lambda chunk: chunk['requests'][0]['response']['data'].update(dbVersion='CHANGED'))
        with self.assertRaisesRegex(ValueError, 'Pharos response changed'):
            self.run_audit()

    def test_manifest_file_mutation_and_missing_chunks_are_rejected(self):
        path = self.folder / 'chunks/00000.json'
        original = path.read_bytes()
        path.write_bytes(original + b' ')
        with self.assertRaisesRegex(ValueError, 'file hash'):
            self.run_audit()
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'manifest'):
            self.run_audit()

    def test_retained_ppi_without_raw_source_view_is_rejected(self):
        self.replace_chunk(lambda chunk: chunk['targets'][0]['pharos_context']['ppis'][0].update(type='Altered'))
        with self.assertRaisesRegex(ValueError, 'identical raw response'):
            self.run_audit()

    def test_inventory_mutation_is_rejected(self):
        path = self.folder / 'context_targets.json'
        changed = retrieval.read_json(path)
        changed['targets'][0]['panel_gene_ids'].append(GENES[1])
        write_json(path, changed)
        with self.assertRaisesRegex(ValueError, 'inventory hash'):
            self.run_audit()

    def test_changed_coverage_claim_is_rejected_even_when_summary_is_resealed(self):
        path = self.folder / 'summary.json'
        changed = retrieval.read_json(path)
        changed.pop('content_sha256')
        changed['genes_with_resolved_context'] += 1
        write_json(path, retrieval.seal(changed))
        with self.assertRaisesRegex(ValueError, 'coverage summary'):
            self.run_audit()

    def test_go_observations_and_publication_mentions_do_not_assert_independence(self):
        report, overlaps = self.run_audit()
        self.assertEqual(report['go_field_observations']['raw']['assigned_by'], {'TEST': 1})
        self.assertEqual(report['go_field_observations']['raw']['rows_with_reference_field'], 0)
        self.assertEqual(report['go_field_observations']['raw']['rows_with_polarity_or_relation_field'], 0)
        self.assertEqual(report['blocked_publication_diagnostic']['string_matches'], 1)
        self.assertEqual(len(overlaps['blocked_publication_mentions']), 1)
        self.assertTrue(any('does not establish source independence' in note for note in report['limitations']))
        for row in overlaps['matches']['raw']:
            name, pointer = row['locator'].split('#')
            value = retrieval.read_json(self.folder / name)
            for part in pointer.strip('/').split('/'):
                value = value[int(part)] if isinstance(value, list) else value[part]
            self.assertEqual(digest(value), row['record_sha256'])
        self.assertEqual(report['overlaps_sha256'], digest(overlaps))


if __name__ == '__main__':
    unittest.main()
