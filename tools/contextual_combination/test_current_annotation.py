"""Invented source admission/current-only graph joins; no held-out real rows."""
import csv
import gzip
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .current_annotation import graph_seeds, load_config, native_pipeline


class CurrentScopeTests(unittest.TestCase):
    def test_no_historical_merge_and_exact_graph_accessions_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'native.tsv'
            path.write_text('EntryID\tterm\taspect\n'
                'P00001\tGO:1000001\tP\nP00001\tGO:1000001\tP\n'
                'P00002-2\tGO:1000002\tP\nP00003\tGO:1000003\tF\n')
            seeds, counts = graph_seeds(path, ('P00001', 'P00002', 'P00004'))
            self.assertEqual(seeds, {'P00001': [('P', 'GO:1000001')],
                                     'P00002': [], 'P00004': []})
            self.assertEqual(counts['unique_graph_label_pairs'], 1)
            self.assertEqual(counts['outside_exact_graph_rows'], 2)
            # A formerly known historical term is deliberately absent from
            # this current-only table; no old training table is an input.
            self.assertNotIn(('P', 'GO:1999999'), seeds['P00001'])

    def test_fresh_reference_rejected_before_any_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            cfg = {'format': 'biograph-steward.current-T0-curated-control.v1',
                   'fresh_final_reference_opened': False, 'forecast_role': 'final',
                   'expected_final_count': 3300, 'gaf_generated_date': '2026-04-10',
                   'native_evidence_selection': 'Experimental,IC,TAS',
                   'historical_seed_union': False, 'graph': 'graph', 'gaf': 'gaf',
                   'reviewed_human_fasta': 'fasta', 'ontology': 'obo',
                   'final_ids': 'ids', 'localplus_author_receipt': 'author',
                   'native_source_files': [], 'input_pins': {x: 'never-read' for x in
                       ('graph', 'gaf', 'fasta', 'obo', 'ids', 'author',
                        '/data/reference_apr_nov_2026_v1/native_reference_v1/sealed_reference/groundtruth_PK.tsv')}}
            path.write_text(json.dumps(cfg))
            with patch('tools.contextual_combination.current_annotation.file_sha256',
                       side_effect=AssertionError('future hash must stay closed')) as hashed:
                with self.assertRaisesRegex(ValueError, 'held-out'):
                    load_config(path)
                hashed.assert_not_called()

    def test_earlier_validation_forecasts_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            path.write_text(json.dumps({'format': 'biograph-steward.current-T0-curated-control.v1',
                'fresh_final_reference_opened': False, 'forecast_role': 'validation',
                'expected_final_count': 3300}))
            with self.assertRaisesRegex(ValueError, 'final3300-only'):
                load_config(path)


class UnchangedNativePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            if importlib.util.find_spec('democafa.datacollection.retrieve_terms') is None:
                raise ImportError('qualified external democafa package unavailable')
        except (ImportError, ModuleNotFoundError) as error:
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED') == '1':
                raise
            raise unittest.SkipTest(str(error))
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        root = Path(cls.temporary.name)
        obo = root / 'invented.obo'
        text = 'format-version: 1.2\n\n'
        for term, ns, parent, alias in (
                ('GO:0008150', 'biological_process', None, None),
                ('GO:1000001', 'biological_process', 'GO:0008150', 'GO:1999999'),
                ('GO:1000002', 'biological_process', 'GO:1000001', None),
                ('GO:0003674', 'molecular_function', None, None),
                ('GO:2000001', 'molecular_function', 'GO:0003674', None),
                ('GO:0005575', 'cellular_component', None, None),
                ('GO:3000001', 'cellular_component', 'GO:0005575', None)):
            text += f'[Term]\nid: {term}\nname: invented\nnamespace: {ns}\ndef: "invented"\n'
            if parent:
                text += f'is_a: {parent} ! invented\n'
            if alias:
                text += f'alt_id: {alias}\n'
            text += '\n'
        obo.write_text(text)
        fasta = root / 'reviewed.fasta'
        fasta.write_text(''.join(f'>sp|P0000{i}|INVENTED OX=9606\nMAAAA\n' for i in range(1, 7)))
        source = root / 'source.gaf.gz'
        rows = [('P00001', 'GO:1000002', 'P', 'IMP', 'involved_in'),
                ('P00002', 'GO:1999999', 'P', 'IC', 'involved_in'),
                ('P00003', 'GO:2000001', 'F', 'TAS', 'enables'),
                ('P00004', 'GO:3000001', 'C', 'IDA', 'NOT|located_in'),
                ('P00005', 'GO:3000001', 'C', 'IEA', 'located_in'),
                ('P00006', 'GO:3000001', 'C', 'IDA', 'located_in'),
                ('P99999', 'GO:1000002', 'P', 'IMP', 'involved_in')]
        with gzip.open(source, 'wt') as stream:
            stream.write('!gaf-version: 2.2\n!date-generated: 2026-04-10 09:40\n')
            for protein, term, aspect, evidence, qualifier in rows:
                fields = ['UniProtKB', protein, protein, qualifier, term, 'PMID:1', evidence, '',
                          aspect, 'invented', '', 'protein', 'taxon:9606', '20260408', 'UniProt', '', '']
                stream.write('\t'.join(fields) + '\n')
        propagated, cls.commands = native_pipeline(source, fasta, obo, root / 'native')
        with propagated.open() as stream:
            cls.rows = {(r['EntryID'], r['term'], r['aspect'])
                        for r in csv.DictReader(stream, delimiter='\t')}

    def test_native_experimental_ic_tas_not_and_electronic_policy(self):
        self.assertEqual({p for p, _, _ in self.rows}, {'P00001', 'P00002', 'P00003', 'P00006'})
        self.assertEqual(len(self.commands), 3)
        self.assertTrue(all(r['exit_code'] == 0 for r in self.commands))

    def test_native_alias_and_ancestor_propagation(self):
        self.assertIn(('P00002', 'GO:1000001', 'P'), self.rows)
        self.assertNotIn(('P00002', 'GO:1999999', 'P'), self.rows)
        self.assertIn(('P00001', 'GO:1000001', 'P'), self.rows)
        self.assertIn(('P00001', 'GO:0008150', 'P'), self.rows)

    def test_exact_reviewed_fasta_filter(self):
        self.assertNotIn('P99999', {p for p, _, _ in self.rows})


if __name__ == '__main__':
    unittest.main()
