import gzip
from pathlib import Path
import tempfile
import unittest
from .reserved_fusion import load_sequence,mix

class ReservedFusionTest(unittest.TestCase):
    def test_alt_duplicate_is_max_and_absence_is_arithmetic_zero(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);c={'GO:0000001':['GO:0000001'],'GO:0000002':['GO:0000002'],'GO:9999999':['GO:0000001']}
            with gzip.open(p/'seq.gz','wt') as f:f.write('P1\tGO:0000001\t0.4\nP1\tGO:9999999\t0.8\nP2\tGO:0000002\t0.6\n')
            seq,_=load_sequence(p/'seq.gz',{'P1','P2'},c)
            with gzip.open(p/'net.gz','wt') as f:f.write('P1\tGO:0000001\t0.2\nP2\tGO:0000001\t0.4\n')
            r=mix(p/'net.gz',seq,{'P1','P2'},c,p/'out.gz')
            with gzip.open(p/'out.gz','rt') as f:rows={(a,b):float(v) for a,b,v in (x.rstrip().split('\t') for x in f)}
            self.assertEqual(rows,{('P1','GO:0000001'):0.5,('P2','GO:0000001'):0.2,('P2','GO:0000002'):0.3})
            self.assertEqual(r['sequence_only_pairs'],1);self.assertEqual(len(seq),2)
    def test_duplicate_or_out_of_frame_model_cannot_change_denominator(self):
        for body in ['P1\tGO:0000001\t0.2\nP1\tGO:0000001\t0.3\n','P9\tGO:0000001\t0.2\n']:
            with self.subTest(body=body),tempfile.TemporaryDirectory() as d:
                p=Path(d)
                with gzip.open(p/'net.gz','wt') as f:f.write(body)
                with self.assertRaises(ValueError):mix(p/'net.gz',{}, {'P1'},{'GO:0000001':['GO:0000001']},p/'out.gz')

if __name__=='__main__':unittest.main()
