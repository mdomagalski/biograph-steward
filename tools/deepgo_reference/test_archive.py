"""Invented archive payloads only; never load models, pickles or GO labels."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from biograph_steward.client import digest
from . import archive as a


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def bundle(self, rows):
        path = self.root / 'author.tar.gz'
        with tarfile.open(path, 'w:gz') as tar:
            for name, body, kind in rows:
                info = tarfile.TarInfo(name); info.type = kind
                if kind == tarfile.REGTYPE:
                    info.size = len(body); tar.addfile(info, io.BytesIO(body))
                else:
                    info.linkname = 'outside/not-followed'; tar.addfile(info)
        return path

    def index(self, path):
        raw = path.read_bytes()
        return a.index(path, len(raw), hashlib.md5(raw).hexdigest(), self.root / 'index.json')

    def test_exact_selection_copies_only_opaque_inference_files(self):
        path = self.bundle([('./data/go.obo', b'invented ontology', tarfile.REGTYPE),
                            ('./data/mf/terms.pkl', b'NOT A PICKLE', tarfile.REGTYPE),
                            ('./data/mf/deepgozero_esm_plus_0.th', b'NOT A CHECKPOINT', tarfile.REGTYPE),
                            ('./data/mf/test_data.pkl', b'UNSELECTED LABEL TRAP', tarfile.REGTYPE),
                            ('./unused/link', b'', tarfile.SYMTYPE)])
        index = self.index(path)
        selection = self.root / 'selected.json'
        selection.write_text(json.dumps({'data/go.obo': 'go.obo', 'data/mf/terms.pkl': 'mf/terms.pkl',
            'data/mf/deepgozero_esm_plus_0.th': 'mf/deepgozero_esm_plus_0.th'}))
        out = self.root / 'selected'
        report = a.extract(path, self.root / 'index.json', a.fingerprints(self.root / 'index.json')['sha256'], selection, out)
        self.assertEqual((out / 'mf/terms.pkl').read_bytes(), b'NOT A PICKLE')
        self.assertEqual(len(report['files']), 3)
        self.assertFalse((out / 'mf/test_data.pkl').exists())
        self.assertFalse(report['pickle_or_checkpoint_deserialized'])
        self.assertFalse(report['links_followed'])
        self.assertEqual(index['member_count'], 5)

    def test_publisher_hash_failure_precedes_archive_parsing(self):
        path = self.root / 'not-a-tar'; path.write_bytes(b'not a tar')
        with self.assertRaisesRegex(ValueError, 'publisher'):
            a.index(path, path.stat().st_size, '0' * 32, self.root / 'index.json')

    def test_traversal_and_duplicate_canonical_members_are_rejected(self):
        for names in [('../go.obo',), ('/data/go.obo',), ('data/go.obo', './data/go.obo')]:
            with self.subTest(names=names):
                path = self.bundle([(name, b'x', tarfile.REGTYPE) for name in names])
                with self.assertRaises(ValueError): self.index(path)

    def test_reference_payload_and_selected_links_are_not_admitted(self):
        path = self.bundle([('data/mf/test_data.pkl', b'LABEL TRAP', tarfile.REGTYPE),
                            ('data/mf/deepgozero_esm_plus_0.th', b'', tarfile.LNKTYPE)])
        self.index(path); pin = a.fingerprints(self.root / 'index.json')['sha256']
        for name in ('data/mf/test_data.pkl', 'data/mf/deepgozero_esm_plus_0.th'):
            selection = self.root / 'selected.json'; selection.write_text(json.dumps({name: 'model.th'}))
            with self.subTest(member=name), self.assertRaises(ValueError):
                a.extract(path, self.root / 'index.json', pin, selection, self.root / 'selected')
            self.assertFalse((self.root / 'selected').exists())

    def test_changed_archive_or_index_cannot_enter_extraction(self):
        path = self.bundle([('data/go.obo', b'x', tarfile.REGTYPE)])
        self.index(path); index = self.root / 'index.json'; pin = a.fingerprints(index)['sha256']
        selection = self.root / 'selected.json'; selection.write_text('{"data/go.obo":"go.obo"}')
        path.write_bytes(path.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'archive changed'):
            a.extract(path, index, pin, selection, self.root / 'selected')
        value = json.loads(index.read_text()); value['member_count'] = 999
        index.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'index FILE'):
            a.extract(path, index, pin, selection, self.root / 'selected')

    def test_destination_traversal_and_receipt_collision_fail_before_copy(self):
        path = self.bundle([('data/go.obo', b'x', tarfile.REGTYPE)])
        self.index(path); index = self.root / 'index.json'; pin = a.fingerprints(index)['sha256']
        for destination in ('../go.obo', '/tmp/escape', 'extraction.json'):
            selection = self.root / 'selected.json'; selection.write_text(json.dumps({'data/go.obo': destination}))
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                a.extract(path, index, pin, selection, self.root / 'selected')


if __name__ == '__main__':
    unittest.main()
