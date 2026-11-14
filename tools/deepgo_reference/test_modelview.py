"""Invented extraction receipts test source boundaries without any model data."""
from pathlib import Path
import tempfile
import unittest
from .archive import fingerprints, sealed
from .modelview import extraction, selected_paths, MAIN_MD5
from biograph_steward.client import write_json


class ModelviewTests(unittest.TestCase):
    def test_wrong_source_receipt_and_mutated_member_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder); member = folder/'go.obo'; member.write_bytes(b'invented ontology')
            receipt = folder/'extraction.json'
            write_json(receipt, sealed({'format':'biograph-steward.deepgo-selected-extraction.v1',
                'archive':{'md5':MAIN_MD5}, 'files':{'go.obo':{'source_member':'data/go.obo', **fingerprints(member)}}}))
            pin = fingerprints(receipt)['sha256']
            extraction(receipt, pin, MAIN_MD5, {'go.obo'})
            with self.assertRaisesRegex(ValueError,'archive'):
                extraction(receipt, pin, 'wrong publisher source', {'go.obo'})
            member.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'changed'):
                extraction(receipt, pin, MAIN_MD5, {'go.obo'})

    def test_only_fixed_namespace_selections_enter_view(self):
        self.assertEqual(len(selected_paths(('mf','bp'),True)),17)
        cc = selected_paths(('cc',)); self.assertEqual(len(cc),7)
        self.assertTrue(all(x.startswith('cc/') for x in cc))
        self.assertFalse(selected_paths(('mf','bp'),True) & cc)


if __name__ == '__main__': unittest.main()
