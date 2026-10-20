"""Invented identifiers and measurements; these tests provide no biomedical labels."""
from contextlib import redirect_stdout
from copy import deepcopy
import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.__main__ import main
from biograph_steward.client import digest, write_json
from biograph_steward.cohort_mapping import (Registry, SOURCES, collect_registry, load_registry,
                                            map_cohort, map_matrix, verify_mapping)
from biograph_steward.cptac import prepare_cptac
from biograph_steward.graph import save_run
from test_civic import fixture


def tsv(rows):
    out = StringIO(); writer = csv.DictWriter(out, fieldnames=list(rows[0]), delimiter='\t')
    writer.writeheader(); writer.writerows(rows)
    return out.getvalue().encode()


def gene(gid, symbol, *, previous='', aliases='', products='P00001', status='Approved'):
    return {'hgnc_id': gid, 'symbol': symbol, 'prev_symbol': previous, 'alias_symbol': aliases,
            'uniprot_ids': products, 'status': status, 'entrez_id': gid.split(':')[1],
            'ensembl_gene_id': 'INVENTED-' + gid, 'locus_type': 'gene with protein product'}


def protein(accession, gid, symbol, *, aliases='', taxon='9606', ncbi=None):
    return {'Entry': accession, 'Gene Names (primary)': symbol, 'Gene Names (synonym)': aliases,
            'HGNC': gid + ';', 'GeneID': (ncbi or gid.split(':')[1]) + ';',
            'Organism (ID)': taxon, 'Protein names': 'INVENTED SOFTWARE TEST product'}


def registry(genes=None, proteins=None):
    return Registry(tsv(genes or [gene('HGNC:1', 'TEST_0')]), tsv(proteins or [protein('P00001', 'HGNC:1', 'TEST_0')]))


class IdentifierTests(unittest.TestCase):
    def test_primary_precedes_alias_but_preserves_shadowed_candidate(self):
        r = registry([gene('HGNC:1', 'ALPHA'), gene('HGNC:2', 'BETA', aliases='ALPHA')])
        resolved = r.resolve('ALPHA')
        self.assertEqual(resolved['hgnc_id'], 'HGNC:1')
        self.assertEqual(resolved['shadowed_relation_candidates'], ['HGNC:2'])
        self.assertIsNone(r.resolve('alpha')['hgnc_id'])  # No case guessing.

    def test_alias_conflicts_are_not_ranked_and_withdrawn_entries_are_not_selected(self):
        r = registry([gene('HGNC:1', 'ALPHA', previous='OLD'), gene('HGNC:2', 'BETA', aliases='OLD'),
                      gene('HGNC:3', 'RETIRED', status='Entry Withdrawn'), gene('HGNC:4', 'DELTA', previous='UNIQUE')])
        self.assertEqual(r.resolve('OLD')['candidate_hgnc_ids'], ['HGNC:1', 'HGNC:2'])
        self.assertIsNone(r.resolve('OLD')['hgnc_id'])
        self.assertIsNone(r.resolve('RETIRED')['hgnc_id'])
        self.assertEqual(r.resolve('UNIQUE')['hgnc_id'], 'HGNC:4')

    def test_uniprot_synonym_joins_through_hgnc_not_symbol_similarity(self):
        r = registry([gene('HGNC:1', 'ALPHA'), gene('HGNC:2', 'BETA')],
                     [protein('P00001', 'HGNC:1', 'ALPHA', aliases='LEGACY')])
        self.assertEqual(r.resolve('LEGACY')['hgnc_id'], 'HGNC:1')
        self.assertIsNone(r.resolve('LEGAC')['hgnc_id'])

    def test_nonhuman_duplicate_and_malformed_identifiers_fail(self):
        for proteins in [[protein('P00001', 'HGNC:1', 'ALPHA', taxon='10090')],
                         [protein('P00001', 'HGNC:1', 'ALPHA')] * 2]:
            with self.assertRaises(ValueError): registry(proteins=proteins)
        with self.assertRaises(ValueError): registry([gene('HGNC:1', 'ALPHA')] * 2)
        with self.assertRaises(ValueError): Registry(b'<html>unavailable</html>', b'')

    def test_two_products_do_not_duplicate_one_gene_measurement_and_missing_stays_missing(self):
        r = registry([gene('HGNC:1', 'TEST_0', products='P00001|P00002')],
                     [protein('P00001', 'HGNC:1', 'TEST_0'), protein('P00002', 'HGNC:1', 'TEST_0')])
        graph = {'nodes': [{'id': 'UniProtKB:P00001', 'sym': 'TEST_0'}, {'id': 'UniProtKB:P00002', 'sym': 'TEST_0'}]}
        rows, crosswalk, counts = map_matrix(b'attrib_name\tA\tB\nTEST_0\tNA\t2\n', graph, r)
        self.assertEqual(len(rows), 1); self.assertEqual(counts['identifier_eligible_gene_rows'], 1)
        self.assertEqual(rows[0]['missing_samples'], 1); self.assertEqual(rows[0]['median_reported_log2_ratio'], 2)
        self.assertEqual(len(rows[0]['protein_candidates']), 2)
        self.assertTrue(all(not x['protein_specific_assignment'] for x in rows + crosswalk))
        self.assertEqual(counts['pharos_proteins_linked_to_measured_gene'], 2)
        self.assertEqual(counts['measured_rows_linked_to_pharos'], 1)

    def test_duplicate_gene_rows_shared_products_conflicts_and_absence_do_not_become_labels(self):
        r = registry([gene('HGNC:1', 'ALPHA', previous='OLD', products='P00001|P00003'),
                      gene('HGNC:2', 'BETA', products='P00001'), gene('HGNC:3', 'GAMMA', products='P00003')],
                     [protein('P00001', 'HGNC:1;HGNC:2', 'ALPHA', ncbi='1;2'), protein('P00003', 'HGNC:3', 'GAMMA')])
        graph = {'nodes': [{'id': 'UniProtKB:P00003', 'sym': 'GAMMA'}]}
        rows, crosswalk, counts = map_matrix(b'attrib_name\tA\tB\nALPHA\t1\tNA\nOLD\t2\tNA\nBETA\tNA\tNA\nUNKNOWN\t3\tNA\n', graph, r)
        self.assertEqual(counts['duplicate_resolved_gene_groups'], 1)
        self.assertEqual(counts['identifier_eligible_gene_rows'], 0)
        self.assertTrue(rows[0]['protein_candidates'][0]['shared_across_genes'])
        self.assertEqual(rows[0]['protein_candidates'][1]['status'], 'registry_conflict')
        self.assertEqual(crosswalk[0]['status'], 'no_unambiguous_measured_gene')
        self.assertEqual(counts['labels_created'], 0)
        self.assertEqual(len(rows), 4)
        with self.assertRaises(ValueError): map_matrix(b'attrib_name\tA\tB\nALPHA\tinf\t1\n', graph, r)

    def test_complex_locus_constituents_with_confirmed_products_remain_available(self):
        g = gene('HGNC:1', 'ALPHA'); g['locus_type'] = 'complex locus constituent'
        r = registry([g], [protein('P00001', 'HGNC:1', 'ALPHA')])
        rows, _, stats = map_matrix(b'attrib_name\tA\tB\nALPHA\t1\t2\n', {'nodes': []}, r)
        self.assertTrue(rows[0]['protein_context_eligible'])
        self.assertEqual(stats['protein_context_eligible_gene_rows'], 1)


class MappingArtifactsTests(unittest.TestCase):
    def test_cli_export_reproduces_every_row_and_detects_tampering_without_changing_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'pharos'; p, _ = fixture(); save_run(p, source)
            original = (source / 'snapshot.json').read_bytes()
            matrix = root / 'matrix.cct'; matrix.write_bytes(b'attrib_name\tA\tB\nTEST_0\t1\tNA\nUNKNOWN\t2\t3\n')
            prepare_cptac(source, root / 'cptac', matrix=matrix)
            h = tsv([gene('HGNC:1', 'TEST_0', products='P04637')]); u = tsv([protein('P04637', 'HGNC:1', 'TEST_0')])
            reg = root / 'registry'
            collect_registry(reg, transport=lambda url: (h if 'googleapis' in url else u, {'release': 'INVENTED'}))
            with redirect_stdout(StringIO()):
                self.assertEqual(main(['cptac-map', '--cptac', str(root / 'cptac'), '--pharos-run', str(source), '--registry', str(reg), '--out', str(root / 'mapped')]), 0)
            result = verify_mapping(root / 'mapped')
            self.assertEqual(result['summary']['measured_gene_rows'], 2)
            self.assertEqual(result['summary']['identifier_eligible_gene_rows'], 1)
            self.assertEqual((source / 'snapshot.json').read_bytes(), original)
            self.assertEqual((root / 'mapped/measurements.cct').read_bytes(), matrix.read_bytes())
            with self.assertRaises(ValueError): map_cohort(root / 'cptac', source, reg, root / 'mapped')
            (root / 'mapped/mappings.json').write_text('[]')
            with self.assertRaises(ValueError): verify_mapping(root / 'mapped')
            (reg / 'hgnc_complete_set.txt').write_text('changed')
            with self.assertRaises(ValueError): load_registry(reg)

    def test_download_receipts_require_fixed_source_url_and_exact_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); downloads = root / 'downloads'; downloads.mkdir()
            receipts = []
            for name, url in SOURCES.items():
                raw = tsv([gene('HGNC:1', 'ALPHA')]) if name.startswith('hgnc') else tsv([protein('P00001', 'HGNC:1', 'ALPHA')])
                (downloads / name).write_bytes(raw)
                import hashlib
                receipts.append({'file': name, 'url': url, 'sha256': hashlib.sha256(raw).hexdigest()})
            write_json(downloads / 'retrieval.json', receipts)
            collect_registry(root / 'good', downloads=downloads)
            receipts[0]['url'] = 'https://example.invalid/registry'
            write_json(downloads / 'retrieval.json', receipts)
            with self.assertRaises(ValueError): collect_registry(root / 'bad', downloads=downloads)


if __name__ == '__main__':
    unittest.main()
