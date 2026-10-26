"""Qualified assay handoffs use invented sources; these are integrity tests."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.assay_attachment import attach_assay
from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from biograph_steward.gold_packet import (MANIFEST_FILE, _packet_id, export_packet,
                                         load_packet, save_decisions, load_decisions)
from biograph_steward.graph import save_run
from biograph_steward.reviews import review_run
from biograph_steward.standard_export import project_graph, export_standard
from test_assay_attachment import cohort_snapshot, make_publication, _seal
from test_normalization import resign


def read(path):
    return json.loads(Path(path).read_text())


class GoldAssayPacketTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source, self.publication, self.run, self.packet = [self.root / name for name in
            ('cohort', 'publication', 'attached', 'packet')]
        self.snapshot = cohort_snapshot()
        save_run(self.snapshot, self.source)
        make_publication(self.publication)
        self.graph = attach_assay(self.source, self.publication, self.run)

    def rebind(self):
        """Reseal the outer packet to exercise independent inner source checks."""
        manifest = read(self.packet / MANIFEST_FILE)
        manifest['graph_sha256'] = digest(read(self.packet / 'source/graph.json'))
        manifest['input_files'] = {name: sha(self.packet / 'source' / name)
                                   for name in manifest['input_files']}
        manifest['packet_id'] = _packet_id(manifest)
        template = read(self.packet / 'decisions.template.json')
        template['packet_id'] = manifest['packet_id']
        write_json(self.packet / 'decisions.template.json', template)
        manifest['files'] = {name: sha(self.packet / name) for name in manifest['files']}
        write_json(self.packet / MANIFEST_FILE, _seal(manifest))

    def test_complete_source_bytes_qualifications_exclusions_and_default_abstentions(self):
        before = {p.relative_to(self.run).as_posix(): p.read_bytes()
                  for p in self.run.rglob('*') if p.is_file()}
        manifest = export_packet(self.run, self.packet)
        verified, graph = load_packet(self.packet)
        self.assertEqual(verified, manifest)
        self.assertEqual(graph, self.graph)
        self.assertEqual(manifest['counts']['assay_observations'], 4)
        self.assertEqual([json.loads(row) for row in (self.packet / 'assay_observations.jsonl').read_text().splitlines()],
                         self.graph['assay_observations'])
        for name in manifest['input_files']:
            self.assertEqual((self.packet / 'source' / name).read_bytes(), before[name])
        self.assertEqual({name[len('assay_source/'):] for name in manifest['input_files']
                          if name.startswith('assay_source/')},
                         {p.relative_to(self.publication).as_posix() for p in self.publication.rglob('*') if p.is_file()})
        self.assertEqual(read(self.packet / 'source/source_licenses.json'), read(self.run / 'source_licenses.json'))
        self.assertTrue(any(not o['evaluable'] and o['graph_edge_id'] is None for o in graph['assay_observations']))
        self.assertTrue(all(row['decision'] == 'abstain' and row['confidence'] is None
                            for row in read(self.packet / 'decisions.template.json')['decisions']))
        self.assertEqual(before, {p.relative_to(self.run).as_posix(): p.read_bytes()
                                 for p in self.run.rglob('*') if p.is_file()})

    def test_packet_is_offline_without_originals_or_source_graph_rebuild(self):
        export_packet(self.run, self.packet)
        for folder in (self.source, self.publication, self.run):
            shutil.rmtree(folder)
        with patch('biograph_steward.graph.build_graph', side_effect=AssertionError('No graph rebuild')):
            self.assertEqual(load_packet(self.packet)[1], self.graph)

    def test_decision_bundle_preserves_complete_portable_assay_baseline(self):
        export_packet(self.run, self.packet)
        decisions = self.root / 'decisions.json'
        shutil.copyfile(self.packet / 'decisions.template.json', decisions)
        output = self.root / 'dispositions'
        report = save_decisions(self.packet, decisions, output)
        for folder in (self.source, self.publication, self.run, self.packet):
            shutil.rmtree(folder)
        self.assertEqual(load_packet(output / report['baseline_packet'])[1], self.graph)
        self.assertIn('baseline_packet/source/assay_source/publication.json', report['files'])

    def test_explicit_assay_prune_changes_only_retained_edge_and_keeps_original_observation(self):
        export_packet(self.run, self.packet)
        value = read(self.packet / 'decisions.template.json')
        edge_id = next(e['id'] for e in self.graph['edges'] if e['record_kind'] == 'assay_observation')
        value.update(actor='Invented fixture reviewer', method='Invented explicit test exclusion')
        next(row for row in value['decisions'] if row['edge_id'] == edge_id).update(
            decision='prune', reason='Fixture only; not a nondetection rule or biological decision')
        path, output = self.root / 'decision.json', self.root / 'retained'
        write_json(path, value)
        save_decisions(self.packet, path, output)
        report, graph = load_decisions(output)
        self.assertNotIn(edge_id, {e['id'] for e in graph['edges']})
        self.assertEqual(graph['nodes'], self.graph['nodes'])
        self.assertEqual(len(graph['assay_observations']), len(self.graph['assay_observations']))
        retained = next(o for o in graph['assay_observations']
                        if o['retention']['baseline_graph_edge_id'] == edge_id)
        self.assertIsNone(retained['graph_edge_id'])
        self.assertEqual(retained['retention']['decision'], 'prune')
        original = next(o for o in self.graph['assay_observations'] if o['graph_edge_id'] == edge_id)
        self.assertEqual({k: v for k, v in retained.items() if k not in {'retention', 'graph_edge_id'}},
                         {k: v for k, v in original.items() if k != 'graph_edge_id'})
        self.assertEqual(load_packet(output / 'baseline_packet')[1], self.graph)
        self.assertIn('retained_assay_observations.jsonl', report['files'])

    def test_zero_matching_observations_preserves_full_publication(self):
        snapshot = deepcopy(self.snapshot)
        snapshot['targets'] = [row for row in snapshot['targets'] if row['uniprot'] == 'P00533']
        snapshot['scope']['requested_uniprot'] = ['P00533']
        snapshot['scope']['resolutions'] = [{'requested_uniprot': 'P00533', 'returned_uniprot': 'P00533', 'status': 'resolved'}]
        cohort, attached = self.root / 'one_protein', self.root / 'zero_matches'
        save_run(resign(snapshot), cohort)
        graph = attach_assay(cohort, self.publication, attached)
        self.assertEqual(graph['assay_observations'], [])
        receipt = export_packet(attached, self.packet)
        self.assertEqual(receipt['counts']['assay_observations'], 0)
        self.assertEqual(load_packet(self.packet)[1], graph)
        self.assertIn('assay_source/evidence.json', receipt['input_files'])
        self.assertEqual((self.packet / 'assay_observations.jsonl').read_bytes(), b'')

    def test_review_publication_and_selection_bindings_preserved_offline(self):
        assertion = next(a for a in self.graph['assertions'] if a['kind'] == 'assay_observation')
        reviewed = self.root / 'reviewed'
        graph = review_run(self.run, reviewed, assertion['id'], 'provisional', 'Fixture reviewer', 'Inspect assay qualification')
        export_packet(reviewed, self.packet)
        self.assertEqual(load_packet(self.packet)[1], graph)
        self.assertEqual(graph['review_events'][-1]['assay_publication_sha256'], graph['assay_publication_sha256'])
        self.assertEqual(graph['review_events'][-1]['assay_attachment_sha256'], graph['assay_attachment_sha256'])
        path = self.packet / 'source/graph.json'
        changed = read(path)
        changed['review_events'][-1]['assay_attachment_sha256'] = '0' * 64
        write_json(path, changed)
        write_json(self.packet / 'source/review_events.json', changed['review_events'])
        self.rebind()
        with self.assertRaisesRegex(ValueError, 'different assay'):
            load_packet(self.packet)

    def test_inner_source_tamper_rejected_even_if_outer_receipt_resealed(self):
        export_packet(self.run, self.packet)
        path = self.packet / 'source/assay_source/source/freeze/source/panel.tsv'
        path.write_bytes(path.read_bytes() + b'TAMPERED\n')
        self.rebind()
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            load_packet(self.packet)

    def test_resealed_sidecar_changes_cannot_override_publication(self):
        export_packet(self.run, self.packet)
        path = self.packet / 'source/assay_attachment.json'
        value = read(path)
        value['observations'][0]['assay_status'] = 'INVENTED CHANGE'
        write_json(path, _seal(value))
        self.rebind()
        with self.assertRaisesRegex(ValueError, 'differs'):
            load_packet(self.packet)

    def test_resealed_observation_ledger_cannot_discard_failed_assays(self):
        export_packet(self.run, self.packet)
        path = self.packet / 'source/assay_observations.json'
        write_json(path, [o for o in read(path) if o['evaluable']])
        self.rebind()
        with self.assertRaisesRegex(ValueError, 'observation ledger'):
            load_packet(self.packet)

    def test_resealed_graph_cannot_flatten_assay_semantics(self):
        export_packet(self.run, self.packet)
        path = self.packet / 'source/graph.json'
        graph = read(path)
        edge = next(e for e in graph['edges'] if e['record_kind'] == 'assay_observation')
        edge['predicate'] = 'biolink:physically_interacts_with'
        write_json(path, graph)
        self.rebind()
        with self.assertRaisesRegex(ValueError, 'observation projection'):
            load_packet(self.packet)

    def test_missing_sidecar_or_unlisted_source_cannot_silently_drop_assay(self):
        (self.run / 'assay_attachment.json').unlink()
        with self.assertRaisesRegex(ValueError, 'without its attachment'):
            export_packet(self.run, self.packet)
        self.assertFalse(self.packet.exists())

    def test_standard_projection_still_rejects_unsupported_assay_mapping(self):
        export_packet(self.run, self.packet)
        with self.assertRaisesRegex(ValueError, 'outside this KGX profile'):
            project_graph(self.graph)
        output = self.root / 'standard'
        with self.assertRaisesRegex(ValueError, 'outside this KGX profile'):
            export_standard(self.packet, output, self.root / 'unused_standards')
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
