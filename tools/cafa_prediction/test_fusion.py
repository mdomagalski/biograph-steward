"""Fixed score arithmetic and file boundaries use invented predictions only."""
import gzip
from pathlib import Path
import sqlite3
import tempfile
import unittest

from .fusion import load_scores, FUSIONS, verify_baselines
from .run import sha, write
from biograph_steward.client import digest


class FixedFusionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = sqlite3.connect(':memory:'); self.addCleanup(self.db.close)
        self.db.execute('CREATE TABLE scores(protein TEXT,term TEXT,blast REAL DEFAULT 0,prott5_cosine1 REAL DEFAULT 0,fastsinksourceplus REAL DEFAULT 0,localplus REAL DEFAULT 0,PRIMARY KEY(protein,term)) WITHOUT ROWID')

    def test_equal_union_with_implicit_zero_and_literal_max_duplicates(self):
        a, b = self.root / 'a.tsv', self.root / 'b.tsv.gz'
        a.write_text('A1\tGO:0000001\t0.8\nA1\tGO:0000001\t0.6\nA1\tGO:0000002\t0.3\n')
        with gzip.open(b, 'wt') as f: f.write('A1\tGO:0000001\t0.4\nA1\tGO:0000003\t1\n')
        load_scores(self.db, a, {'A1'}, 'blast')
        load_scores(self.db, b, {'A1'}, 'fastsinksourceplus')
        rows = self.db.execute('SELECT term,.5*blast+.5*fastsinksourceplus FROM scores ORDER BY term').fetchall()
        self.assertEqual([r[0] for r in rows], ['GO:0000001', 'GO:0000002', 'GO:0000003'])
        for actual, expected in zip([r[1] for r in rows], [.6,.15,.5]): self.assertAlmostEqual(actual, expected)

    def test_invalid_scores_and_targets_are_not_rescaled_clipped_or_admitted(self):
        p = self.root / 'bad.tsv'
        for text in ('nan', 'inf', '-.1', '100'):
            with self.subTest(score=text), self.assertRaises(ValueError):
                p.write_text('A1\tGO:0000001\t' + text + '\n')
                load_scores(self.db,p,{'A1'},'blast')
        p.write_text('B2\tGO:0000001\t0.5\n')
        with self.assertRaisesRegex(ValueError,'outside'): load_scores(self.db,p,{'A1'},'blast')
        with self.assertRaisesRegex(ValueError,'column'): load_scores(self.db,p,{'B2'},'unreviewed')

    def test_four_prespecified_matched_components_remain_fixed(self):
        self.assertEqual(FUSIONS, {'blast_fss_half':('blast','fastsinksourceplus'),
            'blast_local_half':('blast','localplus'),
            'prott5_cosine1_fss_half':('prott5_cosine1','fastsinksourceplus'),
            'prott5_cosine1_local_half':('prott5_cosine1','localplus')})

    def test_explicit_official_aliases_combine_before_arithmetic_unknowns_remain_outside(self):
        p = self.root / 'alias.tsv'
        p.write_text('A1\tGO:0000009\t0.8\nA1\tGO:0000001\t0.6\nA1\tGO:0000008\t0.9\n')
        diagnostic = load_scores(self.db,p,{'A1'},'blast',
            {'GO:0000009':['GO:0000001'], 'GO:0000001':['GO:0000001']})
        rows = self.db.execute('SELECT term,blast FROM scores').fetchall()
        self.assertEqual(rows,[('GO:0000001',.8)])
        self.assertEqual(diagnostic['explicit_alternative_ID_rows_resolved'],1)
        self.assertEqual(diagnostic['outside_frozen_ontology_rows_ignored'],1)

    def test_native_float64_roundoff_is_retained_without_score_clipping(self):
        p = self.root / 'roundoff.tsv'
        value = 1.000000000000001
        p.write_text('A1\tGO:0000001\t' + repr(value) + '\n')
        diagnostic = load_scores(self.db,p,{'A1'},'localplus')
        self.assertEqual(self.db.execute('SELECT localplus FROM scores').fetchone()[0],value)
        self.assertEqual(diagnostic['scores_in_upper_float64_roundoff_band'],1)

    def test_official_component_files_must_match_qualified_frame_and_hashes(self):
        targets=self.root/'targets.txt';targets.write_text('A1\n')
        blast=self.root/'blast.tsv';blast.write_text('A1\tGO:0000001\t0.2\n')
        p5=self.root/'p5.tsv';p5.write_text('A1\tGO:0000001\t0.4\n')
        q=self.root/'qualification.json'
        value={'format':'biograph-steward.official-cafa5-baseline-intake.v1','status':'completed',
            'future_GO_labels_opened':False,'score_rescaling':False,'target_file_sha256':sha(targets),
            'files':{'official_blast.tsv.gz':{'sha256':sha(blast)},'official_prott5_cosine1.tsv.gz':{'sha256':sha(p5)}}}
        value['content_sha256']=digest(value);write(q,value)
        config={'baseline_qualification':str(q),'targets':str(targets),'blast':str(blast),'prott5_cosine1':str(p5)}
        verify_baselines(config)
        blast.write_text('A1\tGO:0000001\t0.3\n')
        with self.assertRaisesRegex(ValueError,'component bytes'):verify_baselines(config)


if __name__ == '__main__': unittest.main()
