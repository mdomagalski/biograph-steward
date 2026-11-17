"""Invented native GAF/ontology tests; never touch research reference files."""
import copy
import gzip
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from .provenance import (load_author,canonical_rows,support_index,explain_pairs,
                         aggregate,check_gate,read_reference_ledger,raw_source_coverage)


class ProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import Bio
            import networkx as nx
            import pandas as pd
            from biograph_steward.go_qualification import read_native_gaf
            cls.nx,cls.pd=nx,pd;cls.reader=staticmethod(read_native_gaf)
            if Bio.__version__!='1.88':raise ImportError('qualified Bio1.88 required')
        except ImportError as error:
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED')=='1':raise
            raise unittest.SkipTest(str(error))
        cls.author=Path(os.environ.get('BIOGRAPH_DEMOCAFA_SOURCE',
            str(Path(__file__).resolve().parents[2]/'runs/contextual_gain_20261115/operator/democafa_author_source')))
        if not cls.author.is_dir():
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED')=='1':raise RuntimeError('pinned democafa source required')
            raise unittest.SkipTest('pinned democafa source unavailable')
        cls.helpers,cls.accepted,cls.experimental,cls.source=load_author(cls.author)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        graph=self.nx.MultiDiGraph()
        for term in ('GO:0008150','GO:2000001','GO:2000002','GO:2000003'):
            graph.add_node(term,namespace='biological_process')
        graph.nodes['GO:2000002']['alt_id']=['GO:9000002']
        graph.add_node('GO:0003674',namespace='molecular_function')
        graph.add_edge('GO:2000001','GO:0008150',key='is_a')
        graph.add_edge('GO:2000002','GO:2000001',key='part_of')
        graph.add_edge('GO:2000003','GO:2000001',key='regulates')
        graph.add_edge('GO:0003674','GO:2000001',key='part_of')
        self.graph=self.helpers['clean_ontology_edges'](graph)

    def tearDown(self):self.temp.cleanup()

    def gaf(self,name,records):
        from tools.learned_combination.reference import file_sha256
        path=self.root/name
        with gzip.open(path,'wt') as f:
            f.write('!gaf-version: 2.2\n!generated-by: invented-fixture\n!date-generated: 2026-01-02 00:00\n')
            for fields in records:f.write('\t'.join(fields)+'\n')
        return self.reader(path,{'P1','P2'},file_sha256(path))[0]

    def record(self,term='GO:2000002',code='EXP',refs='PMID:1|DOI:10.invented/a',
               protein='P1',qualifier='involved_in',date='20260101',form='',extension='',with_from=''):
        return ['UniProtKB',protein,'invented',qualifier,term,refs,code,with_from,'P',
                'invented protein','','protein','taxon:9606',date,'invented_assigner',extension,form]

    def fixture(self):
        literal=self.record();rows=[literal,literal.copy(),self.record('GO:9000002','IC','PMID:2'),
            self.record('GO:2000001','TAS','PMID:3'),
            self.record(code='IMP',refs='PMID:5',qualifier='NOT|involved_in'),
            self.record('GO:2000003','EXP','PMID:6'),self.record(code='IEA',refs='PMID:7'),
            self.record(protein='P2',refs='PMID:4',form='UniProtKB:P2-2',
                extension='occurs_in(CL:0000000)',with_from='UniProtKB:Q1|UniProtKB:Q2')]
        first=self.gaf('invented_T0.gaf.gz',[self.record(code='IEA',refs='PMID:7',date='20250101')])
        second=self.gaf('invented_T1.gaf.gz',rows)
        return first,second

    def explain(self,pairs,first,second):
        return explain_pairs(pairs,second,first,self.graph,self.graph,
            self.helpers['replace_alternate_GO_terms'],self.accepted,self.experimental,
            self.helpers['propagate_terms'],view='invented')

    def test_gate_rejects_before_any_file_or_hash_access(self):
        with patch('tools.contextual_combination.provenance.file_sha256',side_effect=AssertionError('no hash before gate')) as hasher:
            with patch('pathlib.Path.read_text',side_effect=AssertionError('no file before gate')) as reader:
                with self.assertRaisesRegex(ValueError,'parent must authorize'):
                    check_gate({'format':'biograph-steward.postseal-provenance.v1',
                        'parent_authorized_postseal_execution':False,
                        'forecast_seal_directory':'/unopened','input_pins':{'/unopened/future_GT':'unused'}})
            hasher.assert_not_called();reader.assert_not_called()

    def test_source_graph_and_alias_policies_are_native(self):
        self.assertFalse(self.graph.has_edge('GO:2000003','GO:2000001'))
        self.assertFalse(self.graph.has_edge('GO:0003674','GO:2000001'))
        first,second=self.fixture();rows=canonical_rows(second,self.graph,self.helpers['replace_alternate_GO_terms'])
        alias=next(r for r in rows if r['native']['go_id']=='GO:9000002')
        self.assertEqual(alias['canonical_term'],'GO:2000002');self.assertTrue(alias['alias_resolved'])
        self.assertEqual(self.accepted,self.experimental|{'IC','TAS'})

    def test_all_duplicate_rows_direct_alias_ancestor_and_NOT_are_retained(self):
        first,second=self.fixture();pairs=[('P1','GO:2000001'),('P1','GO:2000002'),('P1','GO:9999999')]
        rows=self.explain(pairs,first,second);ancestor,leaf,missing=rows
        self.assertEqual(len(ancestor['positive_support']),4)
        self.assertEqual(len(leaf['positive_support']),3)
        self.assertEqual({x['evidence_family'] for x in ancestor['positive_support']},{'Experimental','IC','TAS'})
        self.assertEqual(sum(x['membership']=='literal_direct' for x in leaf['positive_support']),2)
        self.assertEqual(sum(x['membership']=='alias_direct' for x in leaf['positive_support']),1)
        self.assertEqual(len({x['native_record_id'] for x in leaf['positive_support']}),3)
        self.assertEqual(len(leaf['exact_NOT_native_record_ids']),1)
        self.assertFalse(ancestor['exact_NOT_native_record_ids'])
        self.assertFalse(missing['positive_support']);self.assertFalse(missing['no_support_means_false_label'])
        self.assertTrue(leaf['T0_nonexperimental_membership']);self.assertFalse(leaf['T0_reference_admission_membership'])
        self.assertTrue(ancestor['T0_nonexperimental_membership'])

    def test_bundles_contexts_and_row_counts_do_not_become_independent_studies(self):
        first,second=self.fixture();rows=self.explain([('P1','GO:2000001'),('P1','GO:2000002'),('P2','GO:2000002')],first,second)
        summary=aggregate(rows,second)
        self.assertEqual(summary['label_row_links'],8)
        self.assertEqual(summary['distinct_native_support_rows'],5)
        self.assertEqual(summary['distinct_reference_bundles'],4)
        self.assertEqual(summary['distinct_literal_PMID_identifiers'],4)
        self.assertFalse(summary['independent_study_count_established'])
        p2=rows[-1]['positive_support'][0]
        self.assertEqual(p2['product_form'],'UniProtKB:P2-2')
        self.assertEqual(p2['extension'],'occurs_in(CL:0000000)')
        self.assertEqual(p2['with_from'],'UniProtKB:Q1|UniProtKB:Q2')
        self.assertEqual(p2['source_relation'],'involved_in')
        self.assertEqual(len(second),8) # NOT and nonadmitted context source rows were preserved.

    def test_literal_old_row_marker_excludes_only_date_when_named_so(self):
        first=self.gaf('old_content.gaf.gz',[self.record(date='20250101')])
        second=self.gaf('new_content.gaf.gz',[self.record(date='20260101')])
        row=self.explain([('P1','GO:2000002')],first,second)[0]['positive_support'][0]
        self.assertFalse(row['T0_exact_native_row_content_present'])
        self.assertTrue(row['T0_native_row_content_except_date_present'])

    def test_descriptive_raw_source_scope_retains_nonadmitted_and_duplicate_rows(self):
        first,second=self.fixture()
        before=copy.deepcopy(second)
        scope=raw_source_coverage(second,{'P1','P2','P3'},self.accepted,self.experimental)
        self.assertEqual(second,before)
        self.assertEqual(scope['selected_native_rows'],8)
        self.assertEqual(scope['target_subjects_with_any_native_row'],2)
        self.assertEqual(scope['target_subjects_without_native_rows'],1)
        self.assertEqual(scope['selected_native_NOT_rows'],1)
        self.assertEqual(scope['reference_admission_positive_rows_before_ontology_projection'],6)
        self.assertEqual(scope['BPO_reference_admission_positive_rows_before_ontology_projection'],6)
        self.assertEqual(scope['exact_repeated_native_content_rows'],1)
        self.assertEqual(scope['selected_row_evidence_families'],
            {'Experimental':5,'IC':1,'TAS':1,'not_reference_admission':1})
        for name in ('selected_rows_with_forms','selected_rows_with_extensions','selected_rows_with_with_from'):
            self.assertEqual(scope[name],1)
        self.assertFalse(scope['ontology_or_reference_pair_filter_applied'])
        self.assertFalse(scope['independent_studies_or_complete_study_overlap_established'])
        self.assertTrue(scope['post_opening_descriptive_audit_not_performance_or_model_selection'])
        with self.assertRaisesRegex(ValueError,'exact forecast target'):
            raw_source_coverage(second,{'P1'},self.accepted,self.experimental)

    def test_frozen_native_ledger_joins_every_pair_without_threshold_selection(self):
        from tools.learned_combination.reference import file_sha256
        path=self.root/'invented_scores.tsv'
        path.write_text('EntryID\tterm\tcontrol\tcandidate\nP1\tGO:2000002\t0.9\t0.01\nP2\tGO:2000001\t0.1\t0.99\n')
        spec={'file':str(path),'sha256':file_sha256(path),'reference_positive_pairs':2,
              'all_reference_positive_pairs_retained':True,'threshold_used':None}
        pairs,scores=read_reference_ledger(spec)
        self.assertEqual(pairs,[('P1','GO:2000002'),('P2','GO:2000001')])
        self.assertEqual(scores[('P1','GO:2000002')]['candidate'],0.01)
        with self.assertRaisesRegex(ValueError,'threshold-free'):
            read_reference_ledger(dict(spec,threshold_used=.5))
        path.write_text(path.read_text()+'P1\tGO:2000002\t0.9\t0.01\n')
        with self.assertRaisesRegex(ValueError,'duplicate'):
            read_reference_ledger(dict(spec,sha256=file_sha256(path),reference_positive_pairs=3))


if __name__=='__main__':unittest.main()
