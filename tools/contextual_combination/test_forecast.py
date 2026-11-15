"""Fail-closed input/reuse/coverage checks without a model or future labels."""
import gzip
import hashlib
from pathlib import Path
import tempfile
import unittest

from tools.contextual_combination.forecast import (
    fasta_records, ids, qualify_partition, query_frame, saved_sparse_scores,
)


class ForecastContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def file(self, name, body):
        path = self.root / name
        path.write_text(body)
        return path

    def spec(self, path):
        return {'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_same_accession_changed_tail_cannot_reuse_first1022_cache(self):
        # The author truncates features, but reuse deliberately requires the
        # stricter documented full-sequence equality boundary.
        seq_a = 'A' * 1022 + 'C'
        seq_b = 'A' * 1022 + 'D'
        old = {'P1': {'sequence_sha256': hashlib.sha256(seq_a.encode()).hexdigest()}}
        new = {'P1': {'sequence_sha256': hashlib.sha256(seq_b.encode()).hexdigest()}}
        with self.assertRaises(ValueError):
            qualify_partition(['P1'], ['P1'], old, new)
        self.assertEqual(qualify_partition(['P1'], [], old, new), ([], ['P1']))

    def test_complete_frame_does_not_drop_novel_or_changed_sequences(self):
        old = {'P1': {'sequence_sha256': 'a'}, 'P2': {'sequence_sha256': 'b'}}
        new = {'P1': {'sequence_sha256': 'a'}, 'P2': {'sequence_sha256': 'c'},
               'P3': {'sequence_sha256': 'd'}}
        self.assertEqual(qualify_partition(['P1', 'P2', 'P3'], ['P1'], old, new),
                         (['P1'], ['P2', 'P3']))
        with self.assertRaises(ValueError):
            qualify_partition(['P1', 'P2', 'P3'], ['P1'], old, {'P1': new['P1']})

    def test_repeated_cached_identity_fails_before_model(self):
        with self.assertRaises(ValueError):
            qualify_partition(['P1'], ['P1', 'P1'],
                              {'P1': {'sequence_sha256': 'a'}},
                              {'P1': {'sequence_sha256': 'a'}})

    def test_literal_bare_fasta_header_preserves_identity_join(self):
        path = self.file('valid.fasta', '>P1\nACD\nEFG\n>P2\nMXX\n')
        self.assertEqual(fasta_records(path), {'P1': 'ACDEFG', 'P2': 'MXX'})
        for name, body in [('description', '>P1 source description\nAAA\n'),
                           ('uniprot', '>sp|P1|NAME\nAAA\n'),
                           ('repeated', '>P1\nAAA\n>P1\nCCC\n'),
                           ('empty', '>P1\n>P2\nAAA\n'),
                           ('preamble', 'AAA\n>P1\nCCC\n')]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                fasta_records(self.file(name + '.fasta', body))

    def test_identity_file_is_pinned_sorted_unique(self):
        path = self.file('targets.txt', 'P1\nP2\n')
        pin = self.spec(path)
        self.assertEqual(ids(pin), ['P1', 'P2'])
        path.write_text('P1\nP3\n')
        with self.assertRaises(ValueError):
            ids(pin)
        for body in ('P2\nP1\n', 'P1\nP1\n'):
            path.write_text(body)
            with self.assertRaises(ValueError):
                ids(self.spec(path))

    def test_missing_graph_nodes_stay_in_original_denominator(self):
        targets = ['P1', 'P2', 'P3']
        present, absent = query_frame(targets, {'P3': 1, 'P1': 0})
        self.assertEqual(present, ['P1', 'P3'])
        self.assertEqual(absent, ['P2'])
        self.assertEqual(set(present) | set(absent), set(targets))

    def sparse(self, name, body):
        path = self.root / name
        with gzip.open(path, 'wt') as stream:
            stream.write(body)
        return self.spec(path)

    def test_literal_sparse_values_and_identical_crossframe_repeats(self):
        first = self.sparse('first.gz', 'P1\tGO:0000001\t1.0000000000000002\nP2\tGO:0000002\t0.4\n')
        second = self.sparse('second.gz', 'P1\tGO:0000001\t1.0000000000000002\n')
        result = saved_sparse_scores([first, second], {'P1'})
        self.assertEqual(result, {('P1', 'GO:0000001'): 1.0000000000000002})

    def test_conflicting_old_scores_cannot_be_silently_selected(self):
        first = self.sparse('first.gz', 'P1\tGO:0000001\t0.3\n')
        second = self.sparse('second.gz', 'P1\tGO:0000001\t0.4\n')
        with self.assertRaises(ValueError):
            saved_sparse_scores([first, second], {'P1'})

    def test_nonfinite_or_zero_sparse_old_scores_fail(self):
        for raw in ('nan', 'inf', '-0.1', '0', '1.01'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                saved_sparse_scores([self.sparse('bad.gz', 'P1\tGO:0000001\t' + raw + '\n')], {'P1'})


if __name__ == '__main__':
    unittest.main()
