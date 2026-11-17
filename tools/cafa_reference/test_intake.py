"""Outcome-boundary and source-integrity controls for optional CAFA5 intake."""
import io
import json
import tempfile
from pathlib import Path
import tarfile
import unittest

from tools.cafa_reference.intake import future_identities, regular_members, node_frame


class IntakeTests(unittest.TestCase):
    def test_future_GO_bytes_are_never_decoded_or_returned(self):
        # Invalid UTF8 in the future GO field proves the metadata reader does not
        # decode the field; only exact protein identity and author aspect leave it.
        values, n = future_identities(iter([b'EntryID\tterm\taspect\n',
            b'P04637\t\xff\xfe\tBPO\n', b'P04637\tstill opaque\tBPO\n',
            b'Q13315\tnot inspected\tMFO\n']))
        self.assertEqual(n, 3)
        self.assertEqual(values, {'BPO': {'P04637'}, 'MFO': {'Q13315'}, 'CCO': set()})
        self.assertNotIn('opaque', json.dumps({k: sorted(v) for k,v in values.items()}))

    def test_header_and_identity_are_not_silently_inferred(self):
        for body in ([b'protein\tterm\taspect\n'],
                     [b'EntryID\tterm\taspect\n', b'TP53\tGO:123\tBPO\n'],
                     [b'EntryID\tterm\taspect\n', b'P04637-2\tGO:123\tBPO\n'],
                     [b'EntryID\tterm\taspect\n', b'P04637\tGO:123\tunknown\n']):
            with self.subTest(body=body), self.assertRaises(ValueError): future_identities(iter(body))

    def test_archive_links_and_traversal_do_not_enter_intake(self):
        for name, kind in (('../truth.tsv', tarfile.REGTYPE), ('safe/file', tarfile.SYMTYPE)):
            b = io.BytesIO()
            with tarfile.open(fileobj=b, mode='w') as t:
                m = tarfile.TarInfo(name); m.type = kind; t.addfile(m)
            b.seek(0)
            with tarfile.open(fileobj=b) as t, self.assertRaises(ValueError): regular_members(t)

    def test_node_frame_requires_exact_unique_accessions(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'nodes.tsv'
            p.write_text('node_id\tresolution_status\tcanonical_graph_node_present\nUniProtKB:P04637\tresolved\ttrue\n')
            self.assertEqual(node_frame(p), {'P04637'})
            p.write_text(p.read_text()+'UniProtKB:P04637\tresolved\ttrue\n')
            with self.assertRaises(ValueError): node_frame(p)


if __name__ == '__main__': unittest.main()
