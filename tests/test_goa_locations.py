"""Invented sources test the versioned all-code location application path."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward import evidence_extension, goa_locations, goa_source, go_qualification
from biograph_steward import gold_packet, go_ontology_qualification as ontology
from biograph_steward.client import digest
from biograph_steward.file_utils import sha
from biograph_steward.goa_questions import answer_native_go_question
from biograph_steward.graph import save_run
from biograph_steward.inspection import inspect_selection
from biograph_steward.reviews import read_run
from test_normalization import fixture, resign
from test_goa_source import parsed_record


class NativeLocationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.run, self.context, self.publication = (self.root / n for n in ('baseline', 'context', 'publication'))
        snapshot = fixture()
        for target in snapshot['targets']:
            target['pharos_context']['go'] = [{'goid': 'GO:0000001', 'term': 'Invented old location',
                'type': 'C', 'evidence': 'IDA', 'assigned_by': 'INVENTED'}]
        for row in snapshot['retrieval']['context']['targets']:
            if row['family'] == 'go':
                row.update(status='complete', issues=[], retrieved=1, available=1, retained=1, excluded_by_scope=0)
        self.snapshot = resign(snapshot)
        self.snapshot_file = self.root / 'snapshot.json'
        self.snapshot_file.write_text(json.dumps(self.snapshot))
        self.baseline = save_run(self.snapshot, self.run)
        self.before = {p.relative_to(self.run).as_posix(): sha(p) for p in self.run.rglob('*') if p.is_file()}
        packet = self.root / 'packet'
        gold_packet.export_packet(self.run, packet)
        self.headers = ['!gaf-version: 2.2', '!generated-by: INVENTED', '!date-generated: 2026-01-01']
        fields = []
        for i, target in enumerate(snapshot['targets']):
            fields.append(['UniProtKB', target['uniprot'], 'INVENTED', 'located_in',
                'GO:0000002' if i == 0 else 'GO:0000001', 'PMID:12345', 'TAS' if i == 0 else 'IDA',
                '', 'C', 'Invented protein', '', 'protein', 'taxon:9606', '20260101', 'INVENTED', '', ''])
        self.gaf = self.root / 'annotations.gaf.gz'
        self.gaf.write_bytes(gzip.compress(('\n'.join(self.headers + ['\t'.join(f) for f in fields]) + '\n').encode(), mtime=0))
        self.native = [parsed_record(f, 4 + i, sha(self.gaf)) for i, f in enumerate(fields)]
        source = {'headers': self.headers, 'total_source_rows': len(fields), 'gaf_sha256': sha(self.gaf),
            'parser': {'package': 'biopython', 'version': '1.88', 'function': 'Bio.UniProt.GOA.gafiterator'}}
        with patch.object(go_qualification, 'read_native_gaf', return_value=(self.native, source)):
            go_qualification.qualify_go_context(packet, self.gaf, self.context,
                expected_gaf_sha256=sha(self.gaf), source_url='https://example.invalid/invented.gaf.gz')
        nodes = [{'id': ontology.GO_IRI + term, 'lbl': label, 'type': 'CLASS', 'meta': meta} for term, label, meta in (
            ('0000001', 'Invented old location', {}), ('0000002', 'Invented new location', {}),
            ('0000003', 'Invented obsolete location', {'deprecated': True}),
            ('0003674', 'Invented root', {}), ('0005575', 'Invented root', {}), ('0008150', 'Invented root', {}))]
        self.ontology = self.root / 'ontology.json.gz'
        self.ontology.write_bytes(gzip.compress(json.dumps({'graphs': [{'id': 'http://purl.obolibrary.org/obo/go.owl',
            'meta': {'version': 'http://purl.obolibrary.org/obo/go/releases/2026-01-01/go.owl',
                     'basicPropertyValues': [{'pred': ontology.LICENSE, 'val': 'TEST FIXTURE ONLY'}]},
            'nodes': nodes, 'edges': []}]}).encode(), mtime=0))

    def publish(self):
        goa_locations.publish_locations(self.snapshot_file, self.context, self.ontology, self.publication,
            snapshot_sha256=sha(self.snapshot_file), context_sha256=sha(self.context / 'go_context_qualification.json'),
            ontology_sha256=sha(self.ontology))
        return goa_source.load_publication(self.publication)

    def change(self, **changes):
        fields = list(self.native[0]['raw_fields'])
        indexes = {name: i for i, name in enumerate(go_qualification.GAF_FIELDS)}
        for key, value in changes.items():
            fields[indexes[key]] = value
        return parsed_record(fields, 4, sha(self.gaf))

    def test_legacy_recovery_rejects_TAS_but_explicit_location_profile_preserves_it(self):
        with self.assertRaises(ValueError):
            goa_source.validate_native_record(self.native[0])
        self.assertEqual(goa_source.validate_native_record(self.native[0], policy=goa_source.LOCATION_POLICY), self.native[0])
        manifest, projected, _ = self.publish()
        self.assertEqual(projected['summary']['evidence_code_counts'], {'IDA': 1, 'TAS': 1})
        self.assertEqual(projected['summary']['concepts_absent_from_historical_Pharos'], 1)
        self.assertEqual(manifest['policy'], goa_source.LOCATION_POLICY)

    def test_all_context_boundaries_remain_literal(self):
        changes = [{'Qualifier': 'NOT|located_in'}, {'Qualifier': 'colocalizes_with'},
            {'Qualifier': 'is_active_in'}, {'Aspect': 'P'}, {'Taxon_ID': 'taxon:10090'},
            {'Evidence': 'ND'}, {'GO_ID': 'GO:0005575'},
            {'Taxon_ID': 'taxon:9606|taxon:10090'}, {'With': 'UniProtKB:Q12345'},
            {'Annotation_Extension': 'part_of(CL:0000000)'}, {'Gene_Product_Form_ID': 'UniProtKB:P04637-2'}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                goa_source.validate_native_record(self.change(**change), policy=goa_source.LOCATION_POLICY)
        canonical = self.change(Gene_Product_Form_ID=self.native[0]['subject'])
        self.assertEqual(goa_source.validate_native_record(canonical, policy=goa_source.LOCATION_POLICY), canonical)

    def test_active_scope_and_missing_are_not_repaired(self):
        nodes = {r['go_id']: {'id': r['go_id'], 'lbl': 'Invented', 'meta': {}} for r in self.native}
        nodes['GO:0000003'] = {'id': 'GO:0000003', 'meta': {'deprecated': True}}
        rows = [self.native[0], self.change(GO_ID='GO:0000003'), self.change(GO_ID='GO:9999999')]
        self.assertEqual(goa_locations.selected_records(rows, nodes), [self.native[0]])

    def test_incomplete_pharos_go_retrieval_and_wrong_source_pins_fail(self):
        partial = deepcopy(self.snapshot)
        next(r for r in partial['retrieval']['context']['targets'] if r['family'] == 'go')['status'] = 'truncated'
        with self.assertRaisesRegex(ValueError, 'complete original-cohort'):
            goa_locations.complete_scope(resign(partial))
        with self.assertRaisesRegex(ValueError, 'pins differ'):
            goa_locations.publish_locations(self.snapshot_file, self.context, self.ontology, self.publication,
                snapshot_sha256='0' * 64, context_sha256=sha(self.context / 'go_context_qualification.json'),
                ontology_sha256=sha(self.ontology))

    def test_separate_saved_source_answer_inspection_and_export_preserve_candidates(self):
        self.publish()
        output = self.root / 'native_locations'
        graph = evidence_extension.publish_extension(self.run, {'goa': self.publication}, output)
        self.assertEqual(read_run(output)[2], graph)
        protein = self.native[0]['subject']
        answer = answer_native_go_question(graph, protein, source_run='native_locations')
        self.assertEqual(answer['records'][0]['evidence_code'], 'TAS')
        self.assertEqual(answer['records'][0]['go_id'], 'GO:0000002')
        self.assertEqual(answer_native_go_question(graph, protein, view='accepted')['records'], [])
        inspection = inspect_selection(graph, answer['records'][0]['assertion_id'], run_id='native_locations')
        native_sections = [r for r in inspection['sections'] if r['title'] == 'Recorded native GO annotation']
        self.assertEqual(native_sections[0]['fields']['evidence_code'], 'TAS')
        packet = self.root / 'export'
        gold_packet.export_packet(output, packet)
        exported = json.loads((packet / 'source/graph.json').read_text())
        self.assertEqual(exported, graph)
        self.assertTrue(all(a['lifecycle_state'] == 'candidate' for a in graph['assertions'] if a['kind'] == 'native_go_annotation'))
        self.assertEqual(self.before, {p.relative_to(self.run).as_posix(): sha(p) for p in self.run.rglob('*') if p.is_file()})

    def test_reproducible_workspace_producer_uses_only_pinned_sources_and_fresh_output(self):
        from tools.go_qualification.publish_locations import publish
        output = self.root / 'published_locations'
        options = {'snapshot_sha256': sha(self.snapshot_file),
            'context_sha256': sha(self.context / 'go_context_qualification.json'), 'ontology_sha256': sha(self.ontology)}
        receipt = publish(self.snapshot_file, self.context, self.ontology, output, **options)
        self.assertFalse(receipt['benchmark_inputs_used'])
        self.assertEqual(receipt['native_location_assertions'], 2)
        self.assertTrue(receipt['original_Pharos_payloads_preserved'])
        self.assertEqual((output / 'snapshot.json').read_bytes(), self.snapshot_file.read_bytes())
        with self.assertRaises(ValueError):
            publish(self.snapshot_file, self.context, self.ontology, output, **options)


if __name__ == '__main__':
    unittest.main()
