import io
import unittest
from .historical_aliases import HEADER,read_aliases,summarize_pair

class HistoricalAliasesTest(unittest.TestCase):
    def test_native_alternatives_are_preserved_without_chosen_rescue(self):
        text=HEADER+'\n9606.ENSP1\tP12345\tEnsembl_UniProt_AC\n9606.ENSP2\tP12345\tBLAST_UniProt_AC\n'
        aliases,rows=read_aliases(io.StringIO(text),{'P12345'})
        r=summarize_pair('P12345','ENSP3',aliases)
        self.assertEqual(rows,2);self.assertEqual(r['native_alias_status'],'historical_aliases_point_elsewhere')
        self.assertEqual(set(r['all_native_alias_alternatives']),{'9606.ENSP1','9606.ENSP2'})
        self.assertFalse(r['sequence_or_isoform_equivalence_inferred'])
    def test_blast_does_not_become_Ensembl_provenance(self):
        r=summarize_pair('P12345','ENSP1',{'P12345':{'9606.ENSP1':['BLAST_UniProt_AC']}})
        self.assertEqual(r['native_alias_status'],'exact_alias_other_provenance')
        self.assertFalse(r['unique_Ensembl_source_matches_selected'])
    def test_wrong_version_header_or_taxon_is_not_guessed(self):
        with self.assertRaises(ValueError):read_aliases(io.StringIO('#protein alias source\n'),set())
        with self.assertRaises(ValueError):read_aliases(io.StringIO(HEADER+'\n10090.ENSP1\tP12345\tEnsembl_UniProt_AC\n'),{'P12345'})
    def test_duplicate_exact_mapping_is_not_overwritten(self):
        row='9606.ENSP1\tP12345\tEnsembl_UniProt_AC\n'
        with self.assertRaises(ValueError):read_aliases(io.StringIO(HEADER+'\n'+row+row),{'P12345'})

if __name__=='__main__':unittest.main()
