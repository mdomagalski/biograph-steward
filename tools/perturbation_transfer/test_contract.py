"""Fail-closed freeze checks, independent of any scientific reference."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.perturbation_transfer.run import evaluate, prepare


class ContractTests(unittest.TestCase):
    def test_missing_replication_is_rejected_before_preparation(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'config.json'
            p.write_text(json.dumps({'references': [{'name': 'K562'}]}))
            with self.assertRaisesRegex(ValueError, 'exactly K562 and RPE1'):
                prepare(p, Path(folder) / 'frozen')
            self.assertFalse((Path(folder) / 'frozen').exists())

    def test_duplicate_cell_is_not_a_replication(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'config.json'
            p.write_text(json.dumps({'references': [{'name': 'K562'}, {'name': 'K562'}]}))
            with self.assertRaisesRegex(ValueError, 'exactly K562 and RPE1'):
                prepare(p, Path(folder) / 'frozen')

    def test_protocol_tampering_cannot_redefine_an_assessment(self):
        with tempfile.TemporaryDirectory() as folder:
            frozen = Path(folder) / 'frozen'; frozen.mkdir()
            (frozen / 'protocol.json').write_text('{"changed": true}')
            output = Path(folder) / 'results'
            with self.assertRaisesRegex(ValueError, 'separately recorded'):
                evaluate(frozen, output, '0' * 64)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
