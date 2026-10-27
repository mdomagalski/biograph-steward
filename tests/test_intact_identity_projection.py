"""Invented-only controls for the post-exposure qualified-identity component."""
from copy import deepcopy
import unittest
from tests.test_intact_evidence_fidelity import fixture
from scripts.intact_identity_projection import complete_identity_ids,compare_identity_projection


def ref(db,identity,qualifier='MI:0356'):
    return {'database':{'name':db},'id':identity,'qualifier':{'mi_id':qualifier}}


def sample(extra=()):
    originals=deepcopy(fixture()[0][:1]);original=originals[0]['reader_record']
    pmid=originals[0]['ledger']['publication_id'].removeprefix('pubmed:')
    original['interaction']['negative']=False
    source_ids=[ref('intact','SYNTHETIC'),*extra]
    original['source_fields']['evidence_ids']['values']=source_ids
    original['source_fields']['publication_ids']['values']=[ref('pubmed',pmid)]
    participants=[]
    for index,side in enumerate(('a','b')):
        identity=original['source_fields']['primary_ids_'+side]['values'][0]
        participants.append({'interactor':{'identifiers':[ref('uniprotkb',identity['id'])],
            'xrefs':[],'organism':{'taxid':9606},'type':{'mi_id':'MI:0326'}},
            'biological_role':{'mi_id':'MI:0499'},'experimental_roles':[{'term':{'mi_id':'MI:0496' if index==0 else 'MI:0498'}}]})
    xml=[{'evidence_sequence':1,'evidence':{'identifiers':deepcopy(source_ids),'xrefs':[],
        'experiments':[{'publication':{'pubmed_id':pmid},'detection_method':{'mi_id':'MI:0006'},
            'host_organisms':[{'taxid':4932,'common_name':'synthetic yeast host'}]}],
        'interaction_types':[{'mi_id':'MI:0914'}],'negative':False,'participants':participants}}]
    return pmid,originals,xml


class QualifiedIdentityProjectionTests(unittest.TestCase):
    def test_original_narrow_identifiers_still_compare(self):
        pmid,originals,xml=sample()
        result=compare_identity_projection(pmid,originals,xml)
        self.assertFalse(result['changed_alias_comparisons'])
        self.assertFalse(result['join_errors'])
        self.assertTrue(result['non_alias_field_comparisons_unchanged'])

    def test_extra_PDB_EMDB_identity_references_preserved(self):
        pmid,originals,xml=sample([ref('wwpdb','9abc'),ref('emdb','EMD-12345'),ref('imex','IM-SYNTHETIC-1','MI:0662')])
        result=compare_identity_projection(pmid,originals,xml)
        self.assertEqual(result['raw_v1_comparison']['critical_field_counts'].get('different'),1)
        self.assertNotIn('different',result['development_identity_comparison']['critical_field_counts'])
        self.assertEqual(len(result['changed_alias_comparisons']),1)
        self.assertTrue(result['unchanged_narrow_record_join'])

    def test_see_also_and_method_citations_never_become_identities(self):
        evidence={'identifiers':[ref('intact','SYNTHETIC')],
            'xrefs':[ref('wwpdb','9abc','MI:0361'),ref('emdb','EMD-54321','MI:0686')]}
        self.assertEqual(complete_identity_ids(evidence),{('intact','SYNTHETIC')})

    def test_IMEx_primary_qualifier_applies_only_to_IMEx(self):
        evidence={'identifiers':[ref('imex','IM-FAKE','MI:0662'),ref('wwpdb','9abc','MI:0662')],'xrefs':[]}
        self.assertEqual(complete_identity_ids(evidence),{('imex','IM-FAKE')})

    def test_missing_structural_identity_remains_mismatch(self):
        pmid,originals,xml=sample([ref('emdb','EMD-12345')])
        xml[0]['evidence']['identifiers']=[ref('intact','SYNTHETIC')]
        result=compare_identity_projection(pmid,originals,xml)
        self.assertEqual(result['development_identity_comparison']['critical_field_counts']['different'],1)

    def test_wrong_structural_identity_remains_mismatch(self):
        pmid,originals,xml=sample([ref('emdb','EMD-12345')])
        xml[0]['evidence']['identifiers'][-1]['id']='EMD-54321'
        result=compare_identity_projection(pmid,originals,xml)
        self.assertEqual(result['development_identity_comparison']['critical_field_counts']['different'],1)

    def test_missing_narrow_record_join_is_not_repaired_by_other_alias(self):
        pmid,originals,xml=sample([ref('emdb','EMD-12345')])
        xml[0]['evidence']['identifiers']=[ref('emdb','EMD-12345')]
        result=compare_identity_projection(pmid,originals,xml)
        self.assertTrue(result['join_errors']);self.assertFalse(result['changed_alias_comparisons'])
        self.assertEqual(result['development_identity_comparison']['rows'][0]['alignment'],'missing')

    def test_ambiguous_narrow_record_join_remains_a_stop(self):
        pmid,originals,xml=sample([ref('emdb','EMD-12345')])
        duplicate=deepcopy(xml[0]);duplicate['evidence_sequence']=2;xml.append(duplicate)
        result=compare_identity_projection(pmid,originals,xml)
        self.assertTrue(result['join_errors']);self.assertFalse(result['changed_alias_comparisons'])
        self.assertEqual(result['development_identity_comparison']['rows'][0]['alignment'],'ambiguous_multiple_xml_records')

    def test_unqualified_identifiers_are_not_guessed(self):
        self.assertFalse(complete_identity_ids({'identifiers':[{'database':{'name':'wwpdb'},'id':'9abc'}],'xrefs':[]}))

if __name__=='__main__':unittest.main()
