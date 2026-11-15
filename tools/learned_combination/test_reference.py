"""Invented source rows and opaque future bytes; no biological reference data."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .reference import (
    BASELINE_SELECTION, NATIVE_FILES, audit_t0_gaf, development_split,
    file_sha256, gaf_header, lafa_future_identities, prepare_t0_nonexperimental,
    read_target_ids,
)


def gaf_row(target='P04637', *, db='UniProtKB', evidence='IEA', qualifier='',
            form='', taxon='taxon:9606', extension='', term='GO:0000001'):
    return '\t'.join((db, target, 'invented', qualifier, term, 'PMID:0', evidence,
                      '', 'F', 'invented', '', 'protein', taxon, '20250904',
                      'invented', extension, form)) + '\n'


HEADER = '!gaf-version: 2.2\n!date-generated: 2025-09-04 14:19\n!generated-by: invented\n'


class ReferenceTests(unittest.TestCase):
    def test_opaque_future_term_bytes_and_author_aspect_translation(self):
        result, rows = lafa_future_identities(iter((b'EntryID\tterm\taspect\n',
            b'P04637\t\xff\xfe\tF\n', b'P04637\tstill opaque\tP\n',
            b'Q13315\tNEVER DECODE\tC\n')))
        self.assertEqual(rows, 3)
        self.assertEqual(result, {'MFO': {'P04637'}, 'BPO': {'P04637'}, 'CCO': {'Q13315'}})

    def test_future_header_aspect_aliases_and_isoforms_are_rejected(self):
        for body in (b'protein\tterm\taspect\n',
                     b'EntryID\tterm\taspect\nP04637\t\xff\tMFO\n',
                     b'EntryID\tterm\taspect\nP04637-2\t\xff\tF\n',
                     b'EntryID\tterm\taspect\nTP53\t\xff\tF\n'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                lafa_future_identities(iter(body.splitlines(keepends=True)))

    def test_target_file_is_headerless_exact_unique_accessions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'targets.tsv'
            path.write_bytes(b'P04637\nQ13315\n')
            self.assertEqual(read_target_ids(path), ('P04637', 'Q13315'))
            for bad in (b'EntryID\nP04637\n', b'P04637\nP04637\n',
                        b'P04637\tGO:0000001\n', b'P04637-2\n', b'\xff\n', b''):
                path.write_bytes(bad)
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    read_target_ids(path)

    def test_all_final_accessions_and_exact_sequence_duplicates_are_excluded(self):
        candidates = ('P04637', 'Q13315', 'P38398')
        final = ('P04637', 'P00533')
        # The final target P00533 need not have any convenient captured forecast.
        sequences = {'P04637': '1' * 64, 'P00533': '2' * 64,
                     'Q13315': '2' * 64, 'P38398': '3' * 64}
        kept, audit = development_split(candidates, final, sequence_sha256=sequences)
        self.assertEqual(kept, ('P38398',))
        self.assertEqual(audit['exact_accessions_excluded'], 1)
        self.assertEqual(audit['additional_exact_sequence_duplicates_excluded'], 1)
        self.assertTrue(audit['exact_sequence_disjointness_checked'])
        del sequences['P00533']
        with self.assertRaisesRegex(ValueError, 'every development and final'):
            development_split(candidates, final, sequence_sha256=sequences)
        kept, audit = development_split(candidates, final)
        self.assertEqual(kept, ('P38398', 'Q13315'))
        self.assertFalse(audit['exact_sequence_disjointness_checked'])

    def test_native_t0_admission_is_audited_without_quiet_form_or_taxon_restriction(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'invented.gaf'
            rows = [gaf_row(form='UniProtKB:P04637-2', taxon='taxon:10090',
                            qualifier='contributes_to', extension='part_of(X:1)'),
                    gaf_row(evidence='NAS'), gaf_row(evidence='ND'),
                    gaf_row(evidence='IDA'), gaf_row(qualifier='NOT|enables'),
                    gaf_row(db='OTHER'), gaf_row(target='Q13315')]
            path.write_text(HEADER + ''.join(rows))
            audit = audit_t0_gaf(path, ('P04637',), expected_generated_date='2025-09-04')
            self.assertEqual(audit['counts']['source_rows'], 7)
            self.assertEqual(audit['counts']['native_admitted_rows_before_ontology_projection'], 3)
            self.assertEqual(audit['counts']['admitted_rows_with_gene_product_form_id'], 1)
            self.assertEqual(audit['native_admitted_taxa']['taxon:10090'], 1)
            self.assertIn('contributes_to', audit['native_admitted_qualifiers'])

    def test_wrong_source_date_fails_before_annotation_bytes_are_decoded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'wrong.gaf'
            path.write_bytes(b'!gaf-version: 2.2\n!date-generated: 2026-09-04\n\xff\xfe\n')
            self.assertEqual(len(gaf_header(path)), 2)
            with self.assertRaisesRegex(ValueError, 'generated date'):
                audit_t0_gaf(path, ('P04637',), expected_generated_date='2025-09-04')

    def test_native_cli_owns_projection_and_output_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); native = root / 'native'; native.mkdir()
            for name in NATIVE_FILES:
                (native / name).write_text('invented ' + name)
            pins = {name: file_sha256(native / name) for name in NATIVE_FILES}
            gaf = root / 'source.gaf'; gaf.write_text(HEADER + gaf_row())
            graph = root / 'go.obo'; graph.write_text('invented ontology')
            output = root / 'out'
            def fake_run(command, **kwargs):
                self.assertEqual(kwargs, {'cwd': native.resolve(), 'check': True})
                self.assertEqual(command[command.index('--selected_go') + 1], BASELINE_SELECTION)
                self.assertEqual(Path(command[command.index('--query_file') + 1]).read_text(), 'P04637\n')
                Path(command[command.index('--output_baseline') + 1]).write_text('P04637\tGO:0000002\t1\n')
            arguments = dict(gaf=gaf, graph=graph, targets=('P04637',), native_directory=native,
                             python='/qualified/python', output=output,
                             gaf_sha256=file_sha256(gaf), graph_sha256=file_sha256(graph),
                             native_sha256=pins)
            with patch('tools.learned_combination.reference.subprocess.run', side_effect=fake_run) as runner:
                receipt = prepare_t0_nonexperimental(**arguments)
                self.assertEqual(runner.call_count, 1)
                self.assertEqual(receipt['native_unique_prediction_cells'], 1)
                self.assertFalse(receipt['final_GO_labels_read'])
                with self.assertRaises(FileExistsError):
                    prepare_t0_nonexperimental(**arguments)
            arguments['gaf_sha256'] = hashlib.sha256(b'wrong').hexdigest()
            with self.assertRaisesRegex(ValueError, 'source file differs'):
                prepare_t0_nonexperimental(**arguments)


if __name__ == '__main__':
    unittest.main()
