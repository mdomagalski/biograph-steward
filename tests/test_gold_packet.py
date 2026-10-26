"""Invented-source integrity and disposition tests, not a biological gold set."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.assertions import new_review_event
from biograph_steward.client import digest, write_json
from biograph_steward.demo import demo_snapshot
from biograph_steward.file_utils import sha
from biograph_steward.gold_packet import (DECISION_FORMAT, MANIFEST_FILE, export_packet,
                                         load_packet, save_decisions)
from biograph_steward.graph import build_graph, save_run
from test_civic import CivicAPI, fixture


def read(path):
    return json.loads(Path(path).read_text())


def resign(value):
    value.pop('content_sha256', None)
    value['content_sha256'] = digest(value)
    return value


class GoldPacketTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run, self.packet = self.root / 'run', self.root / 'packet'
        self.snapshot = demo_snapshot()
        self.graph = save_run(self.snapshot, self.run)

    def export(self):
        return export_packet(self.run, self.packet)

    def decisions(self):
        path = self.root / 'decisions.json'
        value = read(self.packet / 'decisions.template.json')
        write_json(path, value)
        return path, value

    def repair_receipt(self, *names):
        manifest = read(self.packet / MANIFEST_FILE)
        for name in names:
            manifest['files'][name] = sha(self.packet / name)
        write_json(self.packet / MANIFEST_FILE, resign(manifest))

    def rebind_changed_source(self, packet=None):
        """Reseal byte bindings to test independent metadata consistency checks."""
        from biograph_steward.gold_packet import _packet_id
        packet = self.packet if packet is None else packet
        manifest = read(packet / MANIFEST_FILE)
        manifest['graph_sha256'] = digest(read(packet / 'source/graph.json'))
        manifest['input_files'] = {name: sha(packet / 'source' / name) for name in manifest['input_files']}
        manifest['packet_id'] = _packet_id(manifest)
        template = read(packet / 'decisions.template.json')
        template['packet_id'] = manifest['packet_id']
        write_json(packet / 'decisions.template.json', template)
        manifest['files'] = {name: sha(packet / name) for name in manifest['files']}
        write_json(packet / MANIFEST_FILE, resign(manifest))

    def test_export_retains_exact_source_records_and_stable_identity(self):
        before = {p.name: p.read_bytes() for p in self.run.iterdir() if p.is_file()}
        manifest = self.export()
        second = export_packet(self.run, self.root / 'second')
        self.assertEqual(manifest['packet_id'], second['packet_id'])
        self.assertEqual(manifest['graph_sha256'], digest(self.graph))
        verified, graph = load_packet(self.packet)
        self.assertEqual(verified, manifest)
        self.assertEqual(graph, self.graph)
        self.assertFalse(manifest['official_scoring_performed'])
        for name in manifest['input_files']:
            self.assertEqual((self.packet / 'source' / name).read_bytes(), before[name])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.run.iterdir() if p.is_file()})
        self.assertGreater(len(graph['quarantine']), 0)
        self.assertEqual([json.loads(line) for line in (self.packet / 'quarantine.jsonl').read_text().splitlines()],
                         graph['quarantine'])
        self.assertTrue(all(r['decision'] == 'abstain' and r['confidence'] is None
                            for r in read(self.packet / 'decisions.template.json')['decisions']))

    def test_rejects_changed_graph_even_field_not_checked_by_refresh_semantics(self):
        graph = read(self.run / 'graph.json')
        graph['warnings'] = ['Invented unrecorded warning']
        write_json(self.run / 'graph.json', graph)
        with self.assertRaisesRegex(ValueError, 'exactly replay'):
            self.export()
        self.assertFalse(self.packet.exists())

    def test_rejects_missing_manifest_history_or_metadata_mismatch(self):
        for name in ('run_manifest.json', 'review_events.json'):
            with self.subTest(name=name):
                content = (self.run / name).read_bytes()
                (self.run / name).unlink()
                with self.assertRaises(ValueError):
                    self.export()
                (self.run / name).write_bytes(content)
        manifest = read(self.run / 'run_manifest.json')
        manifest['normalization_policy'] = 'invented-other-policy'
        write_json(self.run / 'run_manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'replay checks'):
            self.export()

    def test_export_rejects_changed_or_missing_source_metadata_labels(self):
        original = read(self.run / 'run_manifest.json')
        for key in ('database_version', 'endpoint', 'data_kind'):
            for missing in (False, True):
                with self.subTest(field=key, missing=missing):
                    manifest = deepcopy(original)
                    if missing:
                        manifest.pop(key)
                    else:
                        manifest[key] = 'invented-conflicting-source'
                    write_json(self.run / 'run_manifest.json', manifest)
                    with self.assertRaisesRegex(ValueError, 'source bindings'):
                        self.export()
        write_json(self.run / 'run_manifest.json', original)

    def test_offline_load_rejects_resealed_source_metadata_conflicts(self):
        for field in ('database_version', 'endpoint', 'data_kind'):
            with self.subTest(field=field):
                packet = self.root / ('metadata-' + field)
                export_packet(self.run, packet)
                path = packet / 'source/run_manifest.json'
                manifest = read(path)
                manifest[field] = 'invented-conflicting-source'
                write_json(path, manifest)
                self.rebind_changed_source(packet)
                with self.assertRaisesRegex(ValueError, 'source bindings'):
                    load_packet(packet)
        packet = self.root / 'missing-null-metadata'
        export_packet(self.run, packet)
        path = packet / 'source/run_manifest.json'
        manifest = read(path)
        manifest.pop('database_version')  # Explicit null is a required, meaningful binding.
        write_json(path, manifest)
        self.rebind_changed_source(packet)
        with self.assertRaisesRegex(ValueError, 'source bindings'):
            load_packet(packet)

    def test_offline_load_rejects_resealed_graph_source_metadata_conflicts(self):
        for field in ('db_version', 'snapshot_created_at'):
            with self.subTest(field=field):
                packet = self.root / ('graph-' + field)
                export_packet(self.run, packet)
                path = packet / 'source/graph.json'
                graph = read(path)
                graph[field] = 'invented-conflicting-source'
                write_json(path, graph)
                self.rebind_changed_source(packet)
                with self.assertRaisesRegex(ValueError, 'source bindings'):
                    load_packet(packet)

    def test_rejects_refresh_and_inherited_review_runs(self):
        manifest = read(self.run / 'run_manifest.json')
        manifest['run_mode'] = 'refresh'
        write_json(self.run / 'run_manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'Refresh'):
            self.export()
        manifest['run_mode'] = 'build'
        write_json(self.run / 'run_manifest.json', manifest)
        write_json(self.run / 'review_events.json', [{'migration': {}}])
        with self.assertRaisesRegex(ValueError, 'Refresh'):
            self.export()

    def test_packet_is_offline_and_load_does_not_rebuild(self):
        self.export()
        with patch('biograph_steward.graph.build_graph', side_effect=AssertionError('No replay on load')):
            self.assertEqual(load_packet(self.packet)[1], self.graph)

    def test_changed_source_after_copy_preparation_fails_without_sealed_packet(self):
        from biograph_steward import gold_packet
        original = gold_packet._source_material
        calls = 0

        def changing(run):
            nonlocal calls
            calls += 1
            result = original(run)
            if calls == 3:
                result['graph.json'] += b' '
            return result

        with patch.object(gold_packet, '_source_material', side_effect=changing):
            with self.assertRaisesRegex(ValueError, 'changed while copying'):
                self.export()
        self.assertFalse((self.packet / MANIFEST_FILE).exists())

    def test_rejects_modified_bytes_and_unlisted_files(self):
        self.export()
        nodes = self.packet / 'nodes.jsonl'
        content = nodes.read_bytes()
        nodes.write_bytes(content + b'\n')
        with self.assertRaisesRegex(ValueError, 'saved bytes'):
            load_packet(self.packet)
        nodes.write_bytes(content)
        (self.packet / 'unlisted.txt').write_text('extra')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            load_packet(self.packet)

    def test_rejects_changed_projection_even_when_file_hash_resealed(self):
        self.export()
        (self.packet / 'quarantine.jsonl').write_text('')
        self.repair_receipt('quarantine.jsonl')
        with self.assertRaisesRegex(ValueError, 'inventory disagrees'):
            load_packet(self.packet)

    def test_rejects_changed_graph_identity_even_when_file_hash_resealed(self):
        self.export()
        graph = read(self.packet / 'source/graph.json')
        graph['data_kind'] = 'invented_other_kind'
        write_json(self.packet / 'source/graph.json', graph)
        self.repair_receipt('source/graph.json')
        with self.assertRaises(ValueError):
            load_packet(self.packet)

    def test_rejects_duplicate_json_keys_nonfinite_fields_and_unsafe_manifest_paths(self):
        self.export()
        path = self.packet / MANIFEST_FILE
        original = path.read_bytes()
        path.write_bytes(b'{"format": "a", "format": "b"}')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'):
            load_packet(self.packet)
        for number in (b'NaN', b'1e999'):
            path.write_bytes(b'{"x": ' + number + b'}')
            with self.assertRaisesRegex(ValueError, 'Nonfinite'):
                load_packet(self.packet)
        path.write_bytes(original)
        manifest = read(path)
        manifest['files']['../outside.json'] = 'a' * 64
        write_json(path, resign(manifest))
        with self.assertRaisesRegex(ValueError, 'manifest'):
            load_packet(self.packet)

    def test_rejects_source_and_packet_symlinks_and_nested_output(self):
        link = self.root / 'linked_run'
        link.symlink_to(self.run, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'ordinary'):
            export_packet(link, self.packet)
        with self.assertRaisesRegex(ValueError, 'outside'):
            export_packet(self.run, self.run / 'nested')
        self.export()
        (self.packet / 'extra-link').symlink_to(self.run / 'graph.json')
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            load_packet(self.packet)

    def test_licenses_preserved_or_explicitly_derived(self):
        self.export()
        self.assertEqual(load_packet(self.packet)[0]['license_material'], 'copied_saved_run')
        (self.run / 'source_licenses.json').unlink()
        derived = self.root / 'derived'
        manifest = export_packet(self.run, derived)
        self.assertEqual(manifest['license_material'], 'derived_from_preserved_snapshots')
        self.assertNotIn('source_licenses.json', manifest['input_files'])
        self.assertEqual(read(derived / 'source/source_licenses.json'), self.snapshot['source_licenses'])

    def test_explicit_dispositions_preserve_nodes_and_every_edge(self):
        self.export()
        path, value = self.decisions()
        value['actor'], value['method'] = 'Invented software reviewer', 'Invented test rule'
        value['decisions'][0].update(decision='keep', reason='Invented keep rationale')
        value['decisions'][1].update(decision='prune', reason='Invented prune rationale')
        write_json(path, value)
        before = (self.packet / 'source/graph.json').read_bytes()
        output = self.root / 'dispositions'
        report = save_decisions(self.packet, path, output)
        self.assertEqual(report['counts'], {'keep': 1, 'prune': 1, 'abstain': len(self.graph['edges']) - 2})
        self.assertEqual(set(report['node_ids']), {n['id'] for n in self.graph['nodes']})
        self.assertEqual(set(sum(report['edge_ids'].values(), [])), {e['id'] for e in self.graph['edges']})
        self.assertEqual((output / 'decisions.json').read_bytes(), path.read_bytes())
        self.assertEqual(before, (self.packet / 'source/graph.json').read_bytes())
        self.assertFalse(report['official_scoring_performed'])
        shutil.rmtree(self.packet)
        shutil.rmtree(self.run)
        copied_manifest, copied_graph = load_packet(output / report['baseline_packet'])
        self.assertEqual(copied_manifest['packet_id'], report['packet_id'])
        self.assertEqual(copied_graph, self.graph)
        self.assertIn('baseline_packet/source/snapshot.json', report['files'])

    def test_missing_duplicate_unknown_stale_or_unsupported_decisions_rejected(self):
        self.export()
        path, initial = self.decisions()
        mutations = [
            lambda v: v['decisions'].pop(),
            lambda v: v['decisions'].append(deepcopy(v['decisions'][0])),
            lambda v: v['decisions'][0].update(edge_id='edge:unknown'),
            lambda v: v.update(packet_id='packet:stale'),
            lambda v: v['decisions'][0].update(confidence=0.9),
            lambda v: v['decisions'][0].update(decision='accepted'),
            lambda v: v['decisions'][0].update(reason=''),
            lambda v: v['decisions'][0].update(extra='ignored'),
            lambda v: v.update(extra='ignored'),
            lambda v: v['decisions'][0].update(decision='keep'),
            lambda v: v['decisions'][0].update(decision=[]),
        ]
        for i, mutation in enumerate(mutations):
            with self.subTest(mutation=i):
                value = deepcopy(initial)
                mutation(value)
                write_json(path, value)
                with self.assertRaises(ValueError):
                    save_decisions(self.packet, path, self.root / ('invalid_' + str(i)))

    def test_review_acceptance_never_becomes_default_keep(self):
        assertion = next(a for a in self.graph['assertions']
                         if a['kind'] != 'disease_filtered_membership' and a['structurally_usable_evidence_ids'])
        event = new_review_event(self.graph, assertion['id'], 'accepted', 'Invented reviewer', 'Fixture only')
        run = self.root / 'reviewed'
        save_run(self.snapshot, run, review_events=[event])
        export_packet(run, self.packet)
        self.assertTrue(all(row['decision'] == 'abstain'
                            for row in read(self.packet / 'decisions.template.json')['decisions']))
        self.assertEqual(load_packet(self.packet)[1]['review_events'], [event])

    def test_isolated_node_survives_when_all_dispositions_prune(self):
        snapshot = demo_snapshot()
        snapshot['targets'] = [{**snapshot['targets'][0], 'pathways': [], 'diseaseAssociationDetails': []}]
        snapshot['query_settings']['pathway_top'] = 0
        # No pathway or disease evidence is available for the synthetic protein.
        snapshot['data_kind'] = 'synthetic_demo'
        snapshot = resign(snapshot)
        run = self.root / 'isolated'
        graph = save_run(snapshot, run)
        export_packet(run, self.packet)
        path, value = self.decisions()
        value['actor'], value['method'] = 'Invented reviewer', 'Invented decision rule'
        for row in value['decisions']:
            row.update(decision='prune', reason='Fixture only')
        write_json(path, value)
        report = save_decisions(self.packet, path, self.root / 'isolated-decisions')
        self.assertEqual(report['node_ids'], [n['id'] for n in graph['nodes']])
        self.assertEqual(report['counts']['keep'], 0)

    def test_qualified_civic_records_remain_complete_and_separately_bound(self):
        api = CivicAPI()
        api.rows = [api.rows[-1]]
        api.rows[0]['evidenceDirection'] = 'DOES_NOT_SUPPORT'
        snapshot, civic = fixture(api)
        run = self.root / 'civic'
        graph = save_run(snapshot, run, civic_snapshot=civic)
        manifest = export_packet(run, self.packet)
        restored = load_packet(self.packet)[1]
        self.assertEqual(restored, graph)
        self.assertEqual(manifest['civic_snapshot_sha256'], civic['content_sha256'])
        self.assertEqual((self.packet / 'source/civic_snapshot.json').read_bytes(),
                         (run / 'civic_snapshot.json').read_bytes())
        edge = next(e for e in restored['edges'] if e['record_kind'] == 'variant_therapy_response')
        self.assertEqual(edge['qualifiers']['evidence_direction'], 'DOES_NOT_SUPPORT')
        self.assertEqual(len(edge['evidence_record']['therapies']), 2)

    def test_civic_manifest_and_graph_metadata_are_bound_to_civic_source(self):
        snapshot, civic = fixture()
        run = self.root / 'civic-bindings'
        save_run(snapshot, run, civic_snapshot=civic)
        original = read(run / 'run_manifest.json')
        for field in ('source_version', 'policy', 'snapshot_sha256', 'coverage', 'mapping'):
            with self.subTest(field=field):
                manifest = deepcopy(original)
                manifest['civic'][field] = 'invented-conflicting-value'
                write_json(run / 'run_manifest.json', manifest)
                with self.assertRaisesRegex(ValueError, 'source bindings'):
                    export_packet(run, self.root / ('civic-export-' + field))
        write_json(run / 'run_manifest.json', original)
        export_packet(run, self.packet)
        path = self.packet / 'source/run_manifest.json'
        manifest = read(path)
        manifest['civic'].pop('source_version')
        write_json(path, manifest)
        self.rebind_changed_source()
        with self.assertRaisesRegex(ValueError, 'source bindings'):
            load_packet(self.packet)
        write_json(path, original)
        graph_path = self.packet / 'source/graph.json'
        graph = read(graph_path)
        graph['civic']['source_version'] = 'invented-conflicting-source'
        write_json(graph_path, graph)
        self.rebind_changed_source()
        with self.assertRaisesRegex(ValueError, 'source bindings'):
            load_packet(self.packet)


if __name__ == '__main__':
    unittest.main()
