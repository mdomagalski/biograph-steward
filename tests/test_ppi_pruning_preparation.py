"""Synthetic offline PPI projection: source identity, weights and export replay."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import PharosClient, digest, write_json
from biograph_steward.gold_packet import load_packet
from biograph_steward.graph import build_graph
from biograph_steward import refresh
from test_pharos_inventory import InventoryAPI, retrieval

SPEC = importlib.util.spec_from_file_location('prepare_ppi_pruning_graph',
    Path(__file__).resolve().parents[1] / 'scripts/prepare_ppi_pruning_graph.py')
preparation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preparation)

P1, P2, P3, MISSING = 'P04637', 'P00533', 'P15056', 'P01116'


class PPIPruningPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.api = InventoryAPI()
        self.api.identities[P3] = {'uniprot': P3, 'sym': 'SYNTHETIC3', 'name': 'Invented protein 3', 'tdl': 'Tbio', 'fam': None}
        self.api.context[P3] = {k: [] for k in retrieval.PPI_LIMITS}
        for uid in (P1, P2, P3):
            self.api.context[uid] = {k: [] for k in retrieval.PPI_LIMITS}
        for i, (a, b, bundle, weight) in enumerate([
                (P1, P2, 'STRINGDB', '0.2'),
                (P2, P3, 'BioPlex,STRINGDB', '0.8'),
                (P1, P3, 'BioPlex', None)], 1):
            props = ([{'name': 'Score', 'value': weight}] if weight is not None else [])
            if 'BioPlex' in bundle:
                props.append({'name': 'p_int', 'value': '0.9999'})
            for subject, obj in ((a, b), (b, a)):
                self.api.context[subject]['ppis'].append({'nid': i, 'type': bundle,
                    'props': deepcopy(props), 'target': {'uniprot': obj, 'sym': 'INVENTED'}})
        # An out-of-cohort row must survive the raw response, but not become an edge.
        self.api.context[P1]['ppis'].append({'nid': 99, 'type': 'STRINGDB',
            'props': [{'name': 'Score', 'value': '0.9'}], 'target': {'uniprot': 'Q99999', 'sym': 'OUTSIDE'}})
        self.inventory = self.root / 'inventory.json'
        write_json(self.inventory, {'format': retrieval.ACCESSION_FORMAT,
            'author_commit': 'a' * 40, 'author_panel_sha256': 'b' * 64,
            'published_uniprot_accessions': sorted((P1, P2, P3, MISSING)), 'outcome_fields_decoded': False})
        self.folder = self.root / 'retrieval'
        retrieval.retrieve_inventory(self.inventory, self.folder, chunk_size=1, profile='ppi', progress=None,
            client_factory=lambda: PharosClient(transport=self.api))
        plan, source, summary = [retrieval.read_json(self.folder / n) for n in ('plan.json', 'source.json', 'summary.json')]
        self.audit = self.root / 'audit.json'
        write_json(self.audit, {'format': 'biograph-steward.lambourne-pharos-lookup-audit.v1',
            'outcome_fields_decoded': False, 'retrieval_plan_sha256': plan['content_sha256'],
            'retrieval_summary_sha256': summary['content_sha256'],
            'retrieval_source_sha256': preparation.sha(self.folder / 'source.json'),
            'inventory_sha256': preparation.sha(self.folder / 'context_targets.json'),
            'db_version': source['db_version'], 'endpoint': plan['endpoint'],
            'counts': {'raw_source_views': 7, 'retained_source_views': 6,
                       'resolved_products': 3, 'requested_products': 4}})

    def project(self):
        return preparation.project_snapshot(self.folder, self.audit)

    def test_offsets_raw_rows_and_unresolved_identity_survive_ordinary_packet(self):
        snapshot, binding = self.project()
        for row in snapshot['scope']['resolutions']:
            envelope = snapshot['requests'][row['request_index']]
            key = row['response_pointer'].split('/')[-1]
            self.assertEqual(envelope['response']['data'][key], row['returned'])
        for row in snapshot['retrieval']['context']['targets']:
            for page in row['pages']:
                envelope = snapshot['requests'][page['request_index']]
                self.assertIn('Scoped_' + row['family'], envelope['request']['query'])
                alias = page['response_pointer'].split('/')[2]
                self.assertEqual(envelope['response']['data'][alias]['uniprot'], row['uniprot'])
        self.assertGreater(binding['chunks'][1]['request_offset'], binding['chunks'][0]['request_offset'])
        self.assertTrue(any('Q99999' in str(r['response']) for r in snapshot['requests']))
        graph = build_graph(snapshot)
        self.assertEqual(len(graph['nodes']), 3)
        self.assertEqual(len(graph['edges']), 3)
        self.assertTrue(all(len(e['retrieval_provenance']['source_responses']) == 2 for e in graph['edges']))
        self.assertNotIn('UniProtKB:' + MISSING, {n['id'] for n in graph['nodes']})
        result = preparation.prepare(self.folder, self.audit, self.root / 'prepared')
        self.assertEqual(result['counts']['requested_accessions'], 4)
        self.assertEqual(result['counts']['unresolved_requested_accessions'], 1)
        self.assertEqual(result['counts']['retained_source_views'], 6)
        loaded = load_packet(self.root / 'prepared/gold_packet')
        self.assertEqual(loaded[1]['edges'], graph['edges'])
        self.assertFalse(result['outcomes_loaded'])
        self.assertEqual(result['new_source_requests'], 0)

    def test_native_component_never_pools_bioplex_and_mixed_sources_are_not_prunable(self):
        snapshot, _ = self.project()
        nodes, pairs, weights = preparation.pair_tables(build_graph(snapshot), snapshot)
        self.assertEqual(len(nodes), 4)
        missing = next(n for n in nodes if n['node_id'] == 'UniProtKB:' + MISSING)
        self.assertEqual(missing['canonical_graph_node_present'], 'false')
        self.assertEqual(missing['resolution_status'], 'not_found')
        self.assertEqual({r['weight'] for r in weights}, {0.2, 0.8})
        by_source = {r['source_bundle']: r for r in pairs}
        self.assertEqual(by_source['STRINGDB']['pruning_eligible'], 'true')
        self.assertEqual(by_source['BioPlex,STRINGDB']['pruning_eligible'], 'false')
        self.assertEqual(by_source['BioPlex']['weight'], '')
        self.assertEqual(by_source['BioPlex']['pruning_eligible'], 'false')

    def test_conflicting_reciprocal_native_weights_fail_without_averaging(self):
        snapshot, _ = self.project()
        target = next(t for t in snapshot['targets'] if t['uniprot'] == P1)
        row = next(r for r in target['pharos_context']['ppis'] if r['target']['uniprot'] == P2)
        row['props'][0]['value'] = '0.3'
        snapshot.pop('content_sha256')
        snapshot['content_sha256'] = digest(snapshot)
        with self.assertRaisesRegex(ValueError, 'reciprocal'):
            preparation.pair_tables(build_graph(snapshot), snapshot)

    def test_changed_raw_response_fails_before_projecting(self):
        path = sorted((self.folder / 'chunks').glob('*.json'))[0]
        value = json.loads(path.read_text())
        value['requests'][0]['response']['data'] = {}
        write_json(path, value)
        with self.assertRaisesRegex(ValueError, 'hash'):
            self.project()

    def test_numeric_zero_is_a_native_weight_and_multiple_bundle_pairs_stop(self):
        snapshot, _ = self.project()
        for target in snapshot['targets']:
            for row in target['pharos_context']['ppis']:
                if row['type'] == 'STRINGDB' and row['target']['uniprot'] != 'Q99999':
                    row['props'][0]['value'] = '0'
        snapshot.pop('content_sha256')
        snapshot['content_sha256'] = digest(snapshot)
        _, _, weighted = preparation.pair_tables(build_graph(snapshot), snapshot)
        self.assertIn(0.0, {r['weight'] for r in weighted})
        target = next(t for t in snapshot['targets'] if t['uniprot'] == P1)
        row = deepcopy(next(r for r in target['pharos_context']['ppis'] if r['target']['uniprot'] == P2))
        row.update({'type': 'BioPlex', 'props': [{'name': 'p_int', 'value': '0.99'}]})
        target['pharos_context']['ppis'].append(row)
        snapshot.pop('content_sha256')
        snapshot['content_sha256'] = digest(snapshot)
        with self.assertRaisesRegex(ValueError, 'Multiple source bundles'):
            preparation.pair_tables(build_graph(snapshot), snapshot)

    def test_projection_is_deterministic_and_output_wont_overwrite_prior_runs(self):
        first, _ = self.project()
        second, _ = self.project()
        self.assertEqual(first, second)
        destination = self.root / 'prepared'
        preparation.prepare(self.folder, self.audit, destination, packet=False)
        before = (destination / 'source_protocol.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'new immutable'):
            preparation.prepare(self.folder, self.audit, destination, packet=False)
        self.assertEqual((destination / 'source_protocol.json').read_bytes(), before)

    def test_resume_old_complete_ordinary_files_keeps_bytes_and_verifies_packet(self):
        destination = self.root / 'prepared'
        preparation.prepare(self.folder, self.audit, destination, packet=False)
        # Simulate the older interrupted publication, before a checkpoint existed.
        (destination / 'source_protocol.json').unlink()
        (destination / preparation.CHECKPOINT).unlink()
        originals = {p.name: p.read_bytes() for p in (destination / 'ordinary_run').glob('*.json')}
        result = preparation.resume_existing(self.folder, self.audit, destination)
        self.assertIsNotNone(result['packet_id'])
        self.assertFalse(result['outcomes_loaded'])
        self.assertEqual(originals, {p.name: p.read_bytes() for p in (destination / 'ordinary_run').glob('*.json')})
        self.assertEqual(load_packet(destination / 'gold_packet')[1]['summary']['evidence_edges'], 3)

    def test_checkpoint_cannot_resume_changed_table(self):
        destination = self.root / 'prepared'
        preparation.prepare(self.folder, self.audit, destination, packet=False)
        (destination / 'source_protocol.json').unlink()
        table = destination / 'weighted_pairs.tsv'
        table.write_bytes(table.read_bytes().replace(b'0.2', b'0.3'))
        with self.assertRaisesRegex(ValueError, 'table changed'):
            preparation.complete_publication(destination)
        self.assertFalse((destination / 'gold_packet').exists())

    def test_bounded_semantics_comparison_matches_original_and_rejects_changes(self):
        snapshot, _ = self.project()
        original = build_graph(snapshot)
        variants = [deepcopy(original) for _ in range(7)]
        variants[0]['nodes'].reverse()
        variants[0]['edges'].reverse()
        variants[0]['assertions'].reverse()
        variants[1]['nodes'][0]['name'] = 'Changed node'
        variants[2]['edges'][0]['evidence_record']['source_views'][0]['record']['props'].append(
            {'name': 'Score', 'value': '0.1'})
        variants[3]['assertions'][0]['lifecycle_state'] = 'accepted'
        variants[4]['assertions'][0]['review_history'] = [{'reason': 'Changed review'}]
        variants[5]['assertions'].pop()
        variants[6]['edges'][0]['snapshot_sha256'] = 'changed transport binding'
        for modified in variants:
            with self.subTest(modified=modified['edges'][0]['id']):
                self.assertEqual(refresh._same_graph_semantics(original, modified),
                                 refresh._graph_semantics(original) == refresh._graph_semantics(modified))


if __name__ == '__main__':
    unittest.main()
