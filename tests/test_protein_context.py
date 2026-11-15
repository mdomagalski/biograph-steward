"""Deterministic offline registration and source-context scope checks."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest
from biograph_steward.file_utils import sha
from biograph_steward.graph import build_graph
from biograph_steward.protein_context import (INDEX, INDEX_FORMAT, _protein,
    inspect_selection, load_publication, registered_contexts, selection_contexts)
from protein_context_fixtures import ContractPacket, dump, native_go
from test_normalization import fixture


class ProteinContext(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(); self.graph = build_graph(fixture())
        self.edge = next(row for row in self.graph['edges'] if row['record_kind'] == 'go_annotation')
        self.protein = self.edge['subject']; self.selection = self.edge['id']

    def test_registration_order_is_explicit_and_context_does_not_select_newest(self):
        first = ContractPacket(self.root, self.protein, name='older')
        second = ContractPacket(self.root, self.protein, name='newer')
        second.manifest['created_at'] = '2027-01-01T00:00:00+00:00'; second.seal()
        dump(self.root / INDEX, {'format': INDEX_FORMAT, 'contexts': [
            {'id': 'older', 'manifest_sha256': first.pin}, {'id': 'newer', 'manifest_sha256': second.pin}]})
        metadata = selection_contexts(self.root, self.graph, self.selection)
        self.assertEqual(metadata['proteins'][0]['context_id'], 'older')
        view = inspect_selection(self.root, self.graph, self.selection, self.protein, 'run')
        self.assertEqual(view['context_manifest_sha256'], first.pin)
        self.assertEqual(view['releases']['context_created_at'], first.manifest['created_at'])
        self.assertTrue(view['precomputed_found'])
        self.assertEqual(view['sequence']['status'], 'sequence_available')

    def test_full_isoform_identity_and_selected_endpoint_scope_are_not_collapsed(self):
        self.assertTrue(_protein(self.protein + '-2'))
        packet = ContractPacket(self.root, self.protein + '-2')
        self.assertFalse(selection_contexts(self.root, self.graph, self.selection)['eligible'])
        with self.assertRaises(ValueError):
            inspect_selection(self.root, self.graph, self.selection, self.protein + '-2', 'run')
        self.assertEqual(set(load_publication(packet.folder, packet.pin)['proteins']), {self.protein + '-2'})

    def test_index_is_explicit_and_rejects_unsafe_registration_and_packet_symlink(self):
        packet = ContractPacket(self.root, self.protein)
        (self.root / INDEX).unlink()
        self.assertEqual(registered_contexts(self.root), [])
        dump(self.root / INDEX, {'format': INDEX_FORMAT,
            'contexts': [{'id': '../context', 'manifest_sha256': packet.pin}]})
        with self.assertRaises(ValueError): registered_contexts(self.root)
        outside = self.root / 'outside'; outside.write_text('do not read')
        (packet.folder / 'unlisted_link').symlink_to(outside)
        with self.assertRaises(ValueError): load_publication(packet.folder, packet.pin)

    def test_native_go_selected_term_binding_and_literal_group_coverage(self):
        packet = ContractPacket(self.root, self.protein)
        native = native_go(self.protein, self.edge['object'], self.graph, self.selection)
        saved = deepcopy(native)
        result = inspect_selection(self.root, self.graph, self.selection, self.protein, 'run', native)
        self.assertEqual(native, saved)
        self.assertEqual([row['native_record'] for row in result['goa_lineage']['records']], native['records'])
        for row in result['goa_lineage']['records']:
            self.assertFalse(row['positive_annotation_inferred'])
            self.assertFalse(row['historical_record_identity_established'])
        invalid = deepcopy(native)
        invalid['query']['go_id'] = 'GO:9999999'
        for row in invalid['records']: row['go_id'] = 'GO:9999999'
        invalid.pop('content_sha256'); invalid['content_sha256'] = digest(invalid)
        with self.assertRaises(ValueError):
            inspect_selection(self.root, self.graph, self.selection, self.protein, 'run', invalid)

    def test_optional_current_and_deleted_entry_metadata_are_native_and_source_bound(self):
        packet = ContractPacket(self.root, self.protein)
        current = {'metadata': {'accession': 'IPR999999', 'is_llm': True,
            'is_reviewed_llm': False, 'is_updated_llm': False, 'go_terms': None}}
        deleted = {'accession': 'ipr888888', 'source_database': 'interpro', 'deletion_date': '2022-08-25T00:00:00.000Z',
            'history': {'signatures': {'panther': {'INVENTED': {'name': 'Former signature'}}}}}
        requests = []
        packet.manifest['entry_files'] = {}
        for identifier, status, body in [('IPR999999', 200, current), ('IPR888888', 410, deleted)]:
            relative = 'interpro/entries/' + identifier + '.json'
            dump(packet.folder / relative, body)
            packet.manifest['entry_files'][identifier] = relative
            requests.append({'provider': 'InterPro', 'response_file': relative, 'http_status': status, 'method': 'GET',
                'url': 'https://www.ebi.ac.uk/interpro/api/entry/interpro/' + identifier + '/?format=json',
                'file_sha256': sha(packet.folder / relative), 'completed_at': packet.manifest['created_at']})
        dump(packet.folder / 'source_requests.json', {'requests': requests}); packet.seal()
        view = inspect_selection(self.root, self.graph, self.selection, self.protein, 'run')
        self.assertEqual([r['native_record'] for r in view['entry_metadata']], [current, deleted])
        self.assertEqual([r['http_status'] for r in view['entry_metadata']], [200, 410])
        self.assertTrue(all(not r['automatic_remapping_performed'] for r in view['entry_metadata']))
        self.assertTrue(all(not r['independent_evidence'] for r in view['entry_metadata']))
        self.assertTrue(view['entry_metadata'][0]['native_record']['metadata']['is_llm'])
        requests[0]['http_status'] = 410
        dump(packet.folder / 'source_requests.json', {'requests': requests}); packet.seal()
        with self.assertRaises(ValueError): load_publication(packet.folder, packet.pin)

    def test_native_no_content_is_separate_unresolved_metadata_without_fabricated_json(self):
        packet = ContractPacket(self.root, self.protein)
        raw = 'interpro/entries/IPR999999.raw';(packet.folder / raw).parent.mkdir(parents=True, exist_ok=True)
        (packet.folder / raw).write_bytes(b'')
        request = {'provider': 'InterPro', 'raw_file': raw, 'body_sha256': sha(packet.folder / raw),
            'http_status': 204, 'method': 'GET', 'request': None,
            'started_at': packet.manifest['created_at'], 'completed_at': packet.manifest['created_at'],
            'url': 'https://www.ebi.ac.uk/interpro/api/entry/interpro/IPR999999/?format=json'}
        dump(packet.folder / 'source_requests.json', {'requests': [request]})
        packet.manifest['entry_unavailable'] = {'IPR999999': raw};packet.seal()
        view = inspect_selection(self.root, self.graph, self.selection, self.protein, 'run')
        self.assertEqual(view['entry_metadata'], [])
        row, = view['entry_unavailable']
        self.assertEqual(row['status'], 'no_content')
        self.assertFalse(row['biological_negative_inferred'])
        self.assertNotIn('native_record', row)
        self.assertEqual(row['source_pointer'], 'source_requests.json#/requests/0')
        self.assertEqual(row['raw_file'], raw)
        self.assertEqual(view['sequence']['match_status'], 'found_with_matches')
        request['http_status'] = 410
        dump(packet.folder / 'source_requests.json', {'requests': [request]});packet.seal()
        with self.assertRaises(ValueError): load_publication(packet.folder, packet.pin)

    def test_no_content_body_and_current_entry_are_not_merged_even_after_resigning(self):
        packet = ContractPacket(self.root, self.protein)
        packet.manifest['entry_unavailable'] = {'IPR999999': 'interpro/info_before.json'};packet.seal()
        with self.assertRaises(ValueError): load_publication(packet.folder, packet.pin)
        packet.manifest['entry_files'] = {'IPR999999': 'interpro/info_before.json'};packet.seal()
        with self.assertRaises(ValueError): load_publication(packet.folder, packet.pin)


if __name__ == '__main__': unittest.main()
