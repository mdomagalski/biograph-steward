"""Fixed legacy export bytes and filesystem-free readable-export replay."""
from copy import deepcopy
import csv
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.graph import _write_tsv, _write_tsv_rows
from biograph_steward.questions import _physical_paths_bytes


class TsvSerializationTests(unittest.TestCase):
    def test_stream_and_file_preserve_legacy_bytes_and_spreadsheet_safety(self):
        columns = ['id', 'text', 'none', 'list', 'mapping', 'number', 'boolean', 'missing']
        rows = [
            {'id': '=1+1', 'text': 'Café\t"quoted"\nline\r\nnext', 'none': None,
             'list': ['α', None, {'x': 1}], 'mapping': {'z': 'β', 'a': [1, 2]},
             'number': -3, 'boolean': False, 'ignored': 'unused'},
            {'id': '+SUM(A1)', 'text': '-plain', 'none': None, 'list': [],
             'mapping': {}, 'number': 0, 'boolean': True},
            {'id': '@name', 'text': '=formula'},
            {'id': '-prefix', 'text': 'ordinary\rcarriage'},
        ]
        # CPython gh-67044 changed bare-CR quoting and was backported to
        # selected maintenance releases. Probe only this native CSV detail;
        # do not assume that all supported interpreters serialize it alike.
        # https://github.com/python/cpython/issues/67044
        native_cr = io.StringIO(newline='')
        csv.writer(native_cr, delimiter='\t', lineterminator='\n').writerow(['ordinary\rcarriage'])
        self.assertIn(native_cr.getvalue(), ('ordinary\rcarriage\n', '"ordinary\rcarriage"\n'))
        cr_cell = native_cr.getvalue()[:-1]
        # Fixed pre-refactor bytes pin all other quoting, non-ASCII text,
        # embedded newlines, JSON ordering and spreadsheet-safe cells.
        expected = (
            'id\ttext\tnone\tlist\tmapping\tnumber\tboolean\tmissing\n'
            '\'=1+1\t"Café\t""quoted""\nline\r\nnext"\t\t'
            '"[""\\u03b1"", null, {""x"": 1}]"\t'
            '"{""z"": ""\\u03b2"", ""a"": [1, 2]}"\t-3\tFalse\t\n'
            '\'+SUM(A1)\t\'-plain\t\t[]\t{}\t0\tTrue\t\n'
            '\'@name\t\'=formula\t\t\t\t\t\t\n'
            f'\'-prefix\t{cr_cell}\t\t\t\t\t\t\n'
        ).encode('utf-8')
        before = deepcopy(rows)
        output = io.StringIO(newline='')
        _write_tsv_rows(output, rows, columns)
        self.assertEqual(output.getvalue().encode('utf-8'), expected)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'legacy.tsv'
            _write_tsv(path, rows, columns)
            self.assertEqual(path.read_bytes(), expected)
        self.assertEqual(rows, before)

    def test_path_replay_needs_no_files_or_temporary_directory(self):
        answer = {'results': [{'protein': {'id': 'TEST:1', 'sym': '=α'}, 'paths': [{
            'id': 'p1', 'kind': 'shared_pathway', 'review_status': 'candidate',
            'node_ids': ['TEST:1', 'TEST:2'], 'assertion_ids': ['a1'],
            'citation_ids': ['@c1'], 'ignored': 'unused'}]}]}
        expected = (
            'protein_id\tprotein_symbol\tid\tkind\treview_status\tnode_ids\tassertion_ids\tcitation_ids\n'
            'TEST:1\t\'=α\tp1\tshared_pathway\tcandidate\t'
            '"[""TEST:1"", ""TEST:2""]"\t"[""a1""]"\t"[""@c1""]"\n'
        ).encode('utf-8')
        before = deepcopy(answer)
        with (
            patch('tempfile.TemporaryDirectory', side_effect=AssertionError('No scratch directory')),
            patch('tempfile.mkdtemp', side_effect=AssertionError('No scratch directory')),
            patch.object(Path, 'open', side_effect=AssertionError('No filesystem needed')),
        ):
            self.assertEqual(_physical_paths_bytes(answer), expected)
        self.assertEqual(answer, before)


if __name__ == '__main__':
    unittest.main()
