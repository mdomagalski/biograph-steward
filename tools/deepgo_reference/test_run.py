"""Offline producer-boundary checks with invented metadata, never model labels."""
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from biograph_steward.client import write_json
from .archive import sealed, fingerprints
from .run import FORMAT, PARAMETERS, load, read_seal, write_lines
from .scores import raw_rows


class ProducerBoundaryTests(unittest.TestCase):
    def test_protocol_pin_and_runtime_drift_cannot_enter_producer(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'protocol.json'
            value = sealed({'format':FORMAT+'.freeze','parameters':PARAMETERS,
                'all_six_cohort_aspect_outcomes_required':True,'producer_files_sha256':{},
                'runtime':{'invented':'fixed profile'}})
            write_json(path,value); sha=fingerprints(path)['sha256']
            with patch('tools.deepgo_reference.run.runtime',return_value={'invented':'fixed profile'}):
                self.assertEqual(load(folder,sha)['format'],FORMAT+'.freeze')
                with self.assertRaisesRegex(ValueError,'FILE'):
                    load(folder,'0'*64)
            with patch('tools.deepgo_reference.run.runtime',return_value={'invented':'changed'}):
                with self.assertRaisesRegex(ValueError,'runtime'):
                    load(folder,sha)

    def test_raw_forecast_preserves_zero_and_small_values_below_native_cut(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'invented.tsv.gz'
            write_lines(path,raw_rows(['Q00001'],['GO:0000001','GO:0000002'],[[0.,0.00001]]))
            with gzip.open(path,'rt') as stream: rows=stream.read().splitlines()
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0],'Q00001\tGO:0000001\t0')
            self.assertEqual(float(rows[1].split('\t')[2]),0.00001)

    def test_edited_sealed_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'invented.json'; value=sealed({'format':'invented','complete':True})
            write_json(path,value);read_seal(path,'invented')
            value['complete']=False;write_json(path,value)
            with self.assertRaisesRegex(ValueError,'seal'):
                read_seal(path,'invented')


if __name__=='__main__':unittest.main()
