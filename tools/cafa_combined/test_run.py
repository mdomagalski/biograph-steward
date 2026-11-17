import gzip
from pathlib import Path
import tempfile
import unittest

from .run import prior_groups


class PriorForecastBoundary(unittest.TestCase):
    def read(self,text,common=('P00001',)):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'old.tsv.gz'
            with gzip.open(p,'wt') as stream:stream.write(text)
            return list(prior_groups(p,{'P00001','P00002'},set(common),
                {'GO:0000001':0,'GO:0000002':1,'GO:0000003':2}))

    def test_full_precision_and_absent_head_preserved(self):
        self.assertEqual(self.read('P00001\tGO:0000001\t0.12345678901234566\n'
            'P00002\tGO:0000001\t0.5\nP00002\tGO:0000003\t0.1\n'),
            [(0,['P00001\tGO:0000001\t0.12345678901234566\n']),(2,[])])

    def test_duplicate_or_reordered_protein_fails(self):
        for text in ('P00001\tGO:0000001\t0.2\nP00001\tGO:0000001\t0.2\n',
                     'P00002\tGO:0000001\t0.2\nP00001\tGO:0000001\t0.2\n'):
            with self.subTest(text=text),self.assertRaises(ValueError):self.read(text)

    def test_repeated_or_reordered_training_head_fails(self):
        with self.assertRaises(ValueError):
            self.read('P00001\tGO:0000003\t0.2\nP00001\tGO:0000001\t0.2\n')

    def test_unknown_identity_term_and_nonpositive_score_fail(self):
        for text in ('P99999\tGO:0000001\t0.2\n','P00001\tGO:9999999\t0.2\n',
                     'P00001\tGO:0000001\tnan\n','P00001\tGO:0000001\t0\n'):
            with self.subTest(text=text),self.assertRaises(ValueError):self.read(text)


if __name__=='__main__':unittest.main()
