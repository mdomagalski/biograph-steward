"""Invented records only; no biomedical source/reference files."""
import io
import gzip
import json
from pathlib import Path
import tempfile
import tarfile
from types import SimpleNamespace as Object
import unittest

from .archived_reference_presence import inventory_records, release_proof, support_references, file_sha, run


def invented_dat():
    return ('ID   INVENTED_HUMAN Reviewed; 4 AA.\nAC   P00001;\n'
        'DE   RecName: Full=Invented;\nOS   Homo sapiens (Human).\n'
        'OC   Eukaryota; Metazoa.\nOX   NCBI_TaxID=9606;\n'
        'RN   [1]\nRP   INVENTED REFERENCE.\nRX   PubMed=123; DOI=10.0/invented;\n'
        'RA   Invented A.;\nRT   "Invented fixture";\nRL   NOT A DATE CLAIM.\n'
        'SQ   SEQUENCE   4 AA; 0 MW; 0000000000000000 CRC64;\n     MAAA\n//\n')


class ArchivedReferencePresenceTests(unittest.TestCase):
    def test_release_date_requires_explicit_official_announcement_before_cutoff(self):
        self.assertEqual(release_proof('UniProt2026_01 (28-Jan-2026).', release='2026_01',
            expected_date='2026-01-28', cutoff='2026-04-10'), '2026-01-28')
        with self.assertRaisesRegex(ValueError, 'announcement'):
            release_proof('UniProt2026_01', release='2026_01',
                expected_date='2026-01-28', cutoff='2026-04-10')
        with self.assertRaisesRegex(ValueError, 'pre-cutoff'):
            release_proof('2026_01 (28-Jan-2026).', release='2026_01',
                expected_date='2026-01-28', cutoff='2026-01-01')

    def test_all_human_records_deduplicate_PMIDs_without_citation_year_inference(self):
        def record(taxon, references, host=None):
            return Object(data_class='Reviewed', taxonomy_id=[taxon], host_taxonomy_id=host or [],
                references=[Object(references=refs, location='DO NOT PARSE2027') for refs in references])
        rows = [record('9606', [[('PubMed', '123'), ('DOI', 'ignored')], [('PubMed', '123')]]),
                record('9606', [[('PubMed', '456')]]),
                record('10090', [[('PubMed', '789')]], ['9606']), record('9606', [])]
        pmids, counts = inventory_records(rows, expected_records=4)
        self.assertEqual(pmids, {'123', '456'})
        self.assertEqual(counts['reviewed_human_records'], 3)
        self.assertEqual(counts['human_PubMed_occurrences'], 3)
        self.assertEqual(counts['reviewed_human_records_with_PubMed'], 2)
        with self.assertRaisesRegex(ValueError, 'entry count'):
            inventory_records(rows, expected_records=5)

    def test_complete_support_scope_deduplicates_ancestor_links_and_rejects_subset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'invented.jsonl'
            match = {'native_record_id': 'one-row', 'references': ['PMID:123', 'GO_REF:0000001']}
            path.write_text('\n'.join(json.dumps({'positive_support': [match]}) for _ in range(3)) + '\n')
            spec = {'file': str(path), 'sha256': file_sha(path),
                    'expected_distinct_PMIDs': 1, 'expected_support_rows': 1}
            result = support_references({'native': spec})['native']
            self.assertEqual(result['pmids'], {'123'})
            self.assertEqual(result['distinct_support_rows'], 1)
            self.assertEqual(result['residual_reference_pairs'], 3)
            with self.assertRaisesRegex(ValueError, 'scope differs'):
                support_references({'native': {**spec, 'expected_support_rows': 2}})

    def test_official_reader_extracts_reference_tuple_and_own_taxonomy(self):
        try:
            from Bio import SwissProt
        except ImportError:
            self.skipTest('Optional official Biopython runtime unavailable')
        pmids, counts = inventory_records(SwissProt.parse(io.StringIO(invented_dat())), expected_records=1)
        self.assertEqual(pmids, {'123'})
        self.assertEqual(counts['reviewed_human_records'], 1)

    def test_dated_invented_tar_DAT_stream_and_aggregate_contains_no_identifiers(self):
        try:
            import Bio
            from Bio import SwissProt
        except ImportError:
            self.skipTest('Optional official Biopython runtime unavailable')
        if Bio.__version__ != '1.85':
            self.skipTest('Execution is pinned to official Biopython1.85')
        from tools.deepgo_reference.archive import index, fingerprints
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); archive = root / 'invented.tar.gz'; data = gzip.compress(invented_dat().encode())
            with tarfile.open(archive, 'w:gz') as tar:
                member = tarfile.TarInfo('uniprot_sprot.dat.gz'); member.size = len(data)
                tar.addfile(member, io.BytesIO(data))
            fp = fingerprints(archive); idx = root / 'index.json'
            index(archive, fp['bytes'], fp['md5'], idx)
            notes = root / 'notes.txt'; notes.write_text('UniProt2026_01 (28-Jan-2026).')
            support = root / 'support.jsonl'; support.write_text(json.dumps({'positive_support': [
                {'native_record_id': 'invented-row', 'references': ['PMID:123', 'PMID:999']} ]}) + '\n')
            cfg = {'release_notes': {'file': str(notes), 'sha256': file_sha(notes)},
                'release': '2026_01', 'release_date': '2026-01-28', 'cutoff_date': '2026-04-10',
                'SwissProt_reader_sha256': file_sha(SwissProt.__file__),
                'archive_index': {'file': str(idx), 'sha256': file_sha(idx)},
                'archive': {'file': str(archive), **fp}, 'dat_member': 'uniprot_sprot.dat.gz',
                'expected_records': 1, 'support_files': {'native': {'file': str(support),
                    'sha256': file_sha(support), 'expected_distinct_PMIDs': 2, 'expected_support_rows': 1}}}
            result = run(cfg, root / 'out')
            self.assertEqual(result['views']['native']['present_in_dated_reviewed_human_references'], 1)
            self.assertEqual(result['views']['native']['absent_from_dated_reviewed_human_references'], 1)
            self.assertFalse(result['publication_years_or_experiment_dates_inferred'])
            self.assertNotIn('PMID:123', json.dumps(result))
            self.assertNotIn('PMID:999', json.dumps(result))
            self.assertEqual(result['dat_member']['bytes'], len(data))
            self.assertFalse((root / 'out/uniprot_sprot.dat.gz').exists())


if __name__ == '__main__':
    unittest.main()
