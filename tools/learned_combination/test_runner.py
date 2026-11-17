"""The phase guards and source-frame restrictions are part of the measurement."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .protocol import PROTOCOL
from .reference import file_sha256
from .runner import config, subset_reference, write_json


class PhaseTests(unittest.TestCase):
    def test_protocol_and_source_pins_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, cfg = root / 'source', root / 'config.json'
            source.write_text('fixed input')
            body = {'protocol': PROTOCOL, 'input_pins': {str(source): file_sha256(source)}}
            write_json(cfg, body)
            self.assertEqual(config(cfg), body)
            source.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'pinned input changed'):
                config(cfg)

    def test_immutable_phase_receipts_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'receipt.json'
            write_json(path, {'original': True})
            with self.assertRaises(FileExistsError):
                write_json(path, {'original': False})
            self.assertTrue(json.loads(path.read_text())['original'])

    def test_reference_restriction_uses_literal_ids_not_substrings_or_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b, out = root / 'a.tsv', root / 'b.tsv', root / 'out.tsv'
            a.write_text('EntryID\tterm\taspect\nP12345\tGO:0000001\tF\nP12345-2\tGO:0000002\tF\n')
            b.write_text('EntryID\tterm\taspect\nQ12345\tGO:0000003\tP\nP12345\tGO:0000004\tC\n')
            audit = subset_reference([a, b], ['P12345'], out)
            self.assertEqual(audit['source_rows'], 4)
            self.assertEqual(audit['retained_rows'], 2)
            self.assertEqual(out.read_text(), 'EntryID\tterm\taspect\nP12345\tGO:0000001\tF\nP12345\tGO:0000004\tC\n')
            with self.assertRaises(FileExistsError):
                subset_reference([a], ['P12345'], out)

    def test_evaluation_requires_a_forecast_seal_before_any_network(self):
        from .assessment import evaluate
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Native numerical imports may be unavailable in ordinary app CI;
            # this guard is also exercised in the isolated native integration.
            try:
                import cafaeval  # noqa: F401
            except ImportError:
                self.skipTest('requires separately pinned native CAFA runtime')
            with patch('urllib.request.urlopen') as request:
                with self.assertRaises(FileNotFoundError):
                    evaluate({}, root / 'missing-seal', root / 'out')
                request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
