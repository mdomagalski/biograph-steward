"""Invented identities and score bytes; no model/reference data is loaded."""
from collections import Counter
import gzip
import io
from pathlib import Path
import tempfile
import unittest

from tools.deepgo_reference.archive import fingerprints
from tools.deepgo_reference.nonpk import copy_rows, identities


class Cohort(unittest.TestCase):
    def test_original_identity_populations_and_pins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); all_ids = ['P'+str(i).zfill(5) for i in range(547)]
            groups = {'no_knowledge':all_ids[:133], 'limited':all_ids[133:]}
            sizes = {'no_knowledge':dict(BPO=44, MFO=39, CCO=118),
                     'limited':dict(BPO=227, MFO=60, CCO=197)}
            values = {'targets.txt':all_ids}
            for setting, ids in groups.items():
                values[setting+'_targets.txt'] = ids
                for aspect, n in sizes[setting].items():
                    values[setting+'_'+aspect+'.txt'] = ids[:n]
            cfg = {'frames':{}}; upstream = {'files':{}, 'counts':sizes}
            for name, ids in values.items():
                p = root/name; p.write_text('\n'.join(ids)+'\n')
                pin = fingerprints(p)['sha256']
                cfg['frames'][name] = {'file':str(p), 'sha256':pin}; upstream['files'][name] = pin
            self.assertEqual(len(identities(cfg, upstream)['targets.txt']), 547)
            # Even a newly rehashed input cannot change original membership.
            p = root/'no_knowledge_MFO.txt'; p.write_text('\n'.join(all_ids[133:172])+'\n')
            cfg['frames'][p.name]['sha256'] = fingerprints(p)['sha256']
            with self.assertRaises(ValueError): identities(cfg, upstream)
            upstream['files'][p.name] = cfg['frames'][p.name]['sha256']
            with self.assertRaises(ValueError): identities(cfg, upstream)

    def test_literal_cached_rows_and_head_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'scores.tsv.gz'
            rows = b'P00001\tGO:0000001\t0.12345678901234567\nP00001\tGO:0000002\t0.4\nP00002\tGO:0000001\t0.9\n'
            with gzip.open(p, 'wb') as stream: stream.write(rows)
            out = io.BytesIO(); counts = Counter()
            copy_rows(p, {'P00001'}, ['GO:0000001','GO:0000002'], out, counts)
            self.assertEqual(out.getvalue(), b'\n'.join(rows.splitlines()[:2])+b'\n')
            self.assertEqual(counts, {'P00001':2})
            with self.assertRaises(ValueError):
                copy_rows(p, {'P00001'}, ['GO:0000002','GO:0000001'], io.BytesIO(), Counter())
            with self.assertRaises(ValueError):
                copy_rows(p, {'P00001'}, ['GO:0000001','GO:0000002'], io.BytesIO(), counts)


if __name__ == '__main__': unittest.main()
