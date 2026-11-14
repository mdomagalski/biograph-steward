"""Source-scope preservation for additive graph publication, no biology labels."""
from copy import deepcopy
import unittest

from tools.pathway_history.extend_inventory import migrate_inventory


class HistoryInventoryExtensionTests(unittest.TestCase):
    def setUp(self):
        self.edge = {'id': 'edge:old', 'record_kind': 'pathway_membership',
                     'evidence_record': {'type': 'WikiPathways', 'sourceID': 'WP1_r12'},
                     'subject': 'UniProtKB:P12345', 'object': 'pathway:1'}
        self.graph = {'edges': [self.edge]}
        self.inventory = {'content_sha256': 'a' * 64, 'versions': [
            {'evidence_edges': [{'edge_id': 'edge:old'}]}]}

    def test_nonwiki_addition_rebinds_only_new_inventory_and_preserves_parent(self):
        original = deepcopy(self.inventory)
        new = {'edges': [deepcopy(self.edge), {'id': 'edge:new', 'record_kind': 'native_go_annotation'}]}
        result = migrate_inventory(self.inventory, self.graph, new, '/private/tmp/new_graph.json', 'b' * 64)
        self.assertEqual(self.inventory, original)
        self.assertEqual(result['versions'], original['versions'])
        self.assertEqual(result['parent_inventory_content_sha256'], original['content_sha256'])
        self.assertEqual(result['source_graph_file_sha256'], 'b' * 64)

    def test_any_changed_added_or_missing_wiki_row_fails(self):
        changed = deepcopy(self.edge); changed['subject'] = 'UniProtKB:Q12345'
        extra = deepcopy(self.edge); extra['id'] = 'edge:extra'
        for rows in ([], [changed], [self.edge, extra]):
            with self.subTest(rows=rows), self.assertRaisesRegex(ValueError, 'remain identical'):
                migrate_inventory(self.inventory, self.graph, {'edges': rows}, '/private/tmp/new_graph.json', 'b'*64)

    def test_partial_or_repeated_inventory_does_not_claim_complete_frame(self):
        for rows in ([], [{'edge_id': 'edge:old'}, {'edge_id': 'edge:old'}]):
            bad = {**self.inventory, 'versions': [{'evidence_edges': rows}]}
            with self.subTest(rows=rows), self.assertRaisesRegex(ValueError, 'complete unchanged'):
                migrate_inventory(bad, self.graph, self.graph, '/private/tmp/new_graph.json', 'b'*64)


if __name__ == '__main__':
    unittest.main()
