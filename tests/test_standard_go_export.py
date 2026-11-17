"""Invented native records exercise exact semantics, not biological accuracy."""
from copy import deepcopy
import unittest

from biograph_steward.assertions import build_assertions
from biograph_steward.go_qualification import GAF_FIELDS,native_record
from biograph_steward.standard_go_export import project_graph,PROFILE,RELATIONS
from biograph_steward.standard_export import project_graph as reactome_projection
from test_goa_questions import fixture


def graph_fixture():
    graph=fixture()
    for node in graph['nodes']:
        node['identifier_mapped']=True;node.setdefault('name',node.get('sym',node['id']))
    for edge in graph['edges']:
        row=edge['evidence_record'];n=row['native_record'];fields=list(n['raw_fields']);fields[14]='BHF-UCL'
        parsed=deepcopy(n['parsed']);parsed['Assigned_By']='BHF-UCL'
        native=native_record(n['source_line'],'\t'.join(fields),fields,parsed,n['source_gaf_sha256'])
        row['native_record']=native;row['assigned_by']='BHF-UCL';edge['primary_source_raw']='BHF-UCL'
        edge['observation']=deepcopy(row)
    return graph


def change_native(graph,line,field,value):
    edge=next(e for e in graph['edges'] if e['evidence_record']['native_record']['source_line']==line)
    row=edge['evidence_record'];n=row['native_record'];fields=list(n['raw_fields']);fields[GAF_FIELDS.index(field)]=value
    parsed=deepcopy(n['parsed']);parsed[field]=value.split('|') if isinstance(parsed[field],list) else value
    row['native_record']=native_record(n['source_line'],'\t'.join(fields),fields,parsed,n['source_gaf_sha256'])
    for key,nkey in [('relation_literal','relation_literal'),('assigned_by','assigned_by'),('evidence_code','evidence_code')]:row[key]=row['native_record'][nkey]
    edge['observation']=deepcopy(row)
    return edge


class NativeGoProjectionTests(unittest.TestCase):
    def test_source_relations_are_not_strengthened_and_all_originals_have_ledger_rows(self):
        graph=graph_fixture();before=deepcopy(graph);result=project_graph(graph)
        self.assertEqual(graph,before);self.assertEqual(result['profile'],PROFILE)
        self.assertEqual(len(result['edges']),4);self.assertEqual(len(result['native_go_records']),5)
        self.assertIn('pinned_Biolink_Protein_enables_domain_incompatible_under_supported_BMT_API',
            next(row for row in result['edge_mapping'] if row['status']=='excluded')['reasons'])
        originals={e['id']:e for e in graph['edges']}
        for edge in result['edges']:
            native=originals[edge['id']]['evidence_record']['native_record']
            self.assertEqual(edge['predicate'],RELATIONS[native['relation_literal']][0])
            self.assertEqual(edge['primary_knowledge_source'],'infores:bhf-ucl')
            self.assertEqual(edge['aggregator_knowledge_source'],['infores:goa'])
            self.assertEqual(edge['knowledge_level'],'not_provided')
            self.assertNotIn('confidence',edge)
        self.assertEqual({r['source_edge_id'] for r in result['edge_mapping']},set(originals))
        self.assertEqual(reactome_projection(graph)['edges'],[])

    def test_unknown_assigner_is_preserved_without_inventing_an_infores(self):
        graph=graph_fixture();change_native(graph,1,'Assigned_By','CAFA');result=project_graph(graph)
        self.assertEqual(len(result['edges']),3)
        row=next(r for r in result['edge_mapping'] if 'assigning_database_without_reviewed_registered_infores_mapping' in r['reasons'])
        self.assertIn('assigning_database_without_reviewed_registered_infores_mapping',row['reasons'])
        self.assertEqual(len(result['native_go_records']),5)

    def test_nonexperimental_native_row_stays_in_sidecar_and_excluded_ledger(self):
        graph=graph_fixture();changed=change_native(graph,1,'Evidence','TAS')
        before=deepcopy(graph);result=project_graph(graph)
        self.assertEqual(graph,before)
        self.assertEqual(len(result['edges']),3)
        self.assertNotIn(changed['id'],{edge['id'] for edge in result['edges']})
        self.assertEqual(len(result['native_go_records']),5)
        original=next(row for row in result['native_go_records'] if row['source_edge_id']==changed['id'])
        self.assertEqual(original['native_record']['evidence_code'],'TAS')
        ledger=next(row for row in result['edge_mapping'] if row['source_edge_id']==changed['id'])
        self.assertEqual(ledger['status'],'excluded')
        self.assertIn('outside_existing_native_positive_context_gate',ledger['reasons'])

    def test_context_or_distinct_product_and_not_rows_do_not_become_unqualified_positive_edges(self):
        for field,value in [('Annotation_Extension','occurs_in(CL:0000000)'),('Gene_Product_Form_ID','UniProtKB:P12345-2'),('Qualifier','NOT|acts_upstream_of')]:
            graph=graph_fixture();change_native(graph,1,field,value)
            with self.subTest(field=field):
                result=project_graph(graph);self.assertEqual(len(result['edges']),3)
                self.assertEqual(len(result['native_go_records']),5)

    def test_canonical_equal_form_is_allowed_and_unsupported_relation_is_ledgered(self):
        graph=graph_fixture();change_native(graph,1,'Gene_Product_Form_ID','UniProtKB:P12345')
        self.assertEqual(len(project_graph(graph)['edges']),4)
        graph=graph_fixture();change_native(graph,1,'Qualifier','acts_upstream_of_or_within')
        result=project_graph(graph);self.assertEqual(len(result['edges']),3)
        self.assertTrue(any('native_relation_outside_four_reviewed_RO_mappings' in row['reasons'] for row in result['edge_mapping']))

    def test_relabelled_annotation_or_source_assertion_conflict_fails_closed(self):
        graph=graph_fixture();graph['edges'][0]['qualifiers']['go_relation']='involved_in'
        with self.assertRaises(ValueError):project_graph(graph)


if __name__=='__main__':unittest.main()
