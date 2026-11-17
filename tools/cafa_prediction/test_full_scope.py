import unittest

from .full_source import candidate
from .full_context import ARMS


class FullScopeTests(unittest.TestCase):
    def setUp(self):
        self.row={'subject_uniprot':'P11111','object_uniprot':'Q22222','subject_STRING_ID':'ENSP0001','object_STRING_ID':'ENSP0002',
            'source_rows':'2','source_orientations':'2','min_score':'700','max_score':'700','min_provider':'STRINGDB','max_provider':'STRINGDB'}
        self.mapping={'P11111':'ENSP0001','Q22222':'ENSP0002'}

    def test_exact_reciprocal_candidate(self):
        key,score,reasons=candidate(self.row,self.mapping,set())
        self.assertEqual((key,score,reasons),(('ENSP0001','ENSP0002'),700,[]))

    def test_global_ambiguity_abstains(self):
        self.assertIn('globally_noninjective_archived_STRING_mapping',candidate(self.row,self.mapping,{'ENSP0002'})[2])

    def test_two_duplicate_same_direction_rows_rejected(self):
        self.row['source_orientations']='1'
        self.assertIn('source_reciprocal_rows_not_exactly_two',candidate(self.row,self.mapping,set())[2])

    def test_no_current_alias_rescue(self):
        self.row['subject_STRING_ID']='NULL'
        self.assertIn('missing_or_unrecognized_archived_STRING_mapping',candidate(self.row,self.mapping,set())[2])

    def test_complete_fixed_context_decomposition(self):
        self.assertEqual(ARMS,{
            'global_induced_oldseeds_fss':{'graph':'induced','seeds':'old','method':'fastsinksourceplus'},
            'global_full_oldseeds_fss':{'graph':'full','seeds':'old','method':'fastsinksourceplus'},
            'global_full_allseeds_fss':{'graph':'full','seeds':'all','method':'fastsinksourceplus'},
            'global_full_allseeds_local':{'graph':'full','seeds':'all','method':'localplus'}})


if __name__=='__main__': unittest.main()
