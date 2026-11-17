"""Invented source histories and unchanged native exclusion-mask checks."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .source_coherence import (facts, known_chain_flags, label_date_partition,
                               residual_mask_audit, run, t0_presence, support_row_summary)


def row(code='IDA', qualifier='involved_in', date='20260301'):
    fields=['UniProtKB','P00001','symbol',qualifier,'GO:2000001','PMID:1',code,'',
            'P','name','','protein','taxon:9606',date,'source','','']
    return {'raw_fields':fields,'evidence_code':code,'negated':'NOT' in qualifier.split('|'),
            'annotation_date':date}


class SourceHistoryTests(unittest.TestCase):
    def test_partial_invalid_and_missing_dates_remain_unknown(self):
        for value in ('20260230','2026','2026111',None):
            source=row();source['annotation_date']=value
            self.assertIsNone(facts(source,[],{'IDA'},'20260410')[
                'annotation_date_on_or_before_T0_header'])
        source=row();del source['annotation_date']
        result=facts(source,[],{'IDA'},'20260410')
        self.assertIsNone(result['annotation_date_on_or_before_T0_header'])
        self.assertEqual(support_row_summary([result])[
            'unknown_or_invalid_annotation_date_support_rows'],1)

    def test_empty_support_is_explicit_and_does_not_verify_unmatched_labels(self):
        result=support_row_summary([])
        self.assertEqual(result['support_audit_status'],'no_eligible_support_rows')
        self.assertEqual(result['old_annotation_date_support_rows'],0)
        partition=label_date_partition({('P00001','GO:2000001')},{},{},'20260410')
        self.assertEqual(partition['counts']['unknown_or_invalid_support_date'],1)
        self.assertEqual(partition['counts']['only_after_T0'],0)

    def test_old_date_does_not_imply_presence_in_prior_snapshot(self):
        result=facts(row(),[],{'IDA','IC','TAS'},'20260410')
        self.assertTrue(result['annotation_date_on_or_before_T0_header'])
        self.assertFalse(result['literal_T0_accession_GO_present'])

    def test_nonreference_positive_presence_is_distinct_from_curated_and_NOT(self):
        source=row();accepted={'IDA','IC','TAS'}
        result=facts(source,[row('IEA')],accepted,'20260410')
        self.assertTrue(result['literal_T0_same_pair_nonreference_positive'])
        self.assertFalse(result['literal_T0_same_pair_curated_positive_before_ontology_filter'])
        result=facts(source,[row('IDA','NOT|involved_in')],accepted,'20260410')
        self.assertTrue(result['literal_T0_same_pair_NOT_context'])
        self.assertFalse(result['literal_T0_same_pair_curated_positive_before_ontology_filter'])
        self.assertFalse(result['same_evidence_code_and_qualifier_literal_T0'])

    def test_literal_date_and_context_changes_are_reported_without_repair(self):
        source=row();old=row(date='20250101');before=copy.deepcopy(old)
        result=facts(source,[old],{'IDA'},'20260410')
        self.assertFalse(result['exact_native_content_T0'])
        self.assertTrue(result['exact_native_content_except_annotation_date_T0'])
        changed=copy.deepcopy(old);changed['raw_fields'][7]='UniProtKB:OTHER'
        result=facts(source,[changed],{'IDA'},'20260410')
        self.assertFalse(result['same_evidence_qualifier_reference_and_literal_context_T0'])
        self.assertTrue(result['same_evidence_code_and_qualifier_literal_T0'])
        self.assertEqual(old,before)

    def test_missing_known_chain_cell_is_detected_but_outside_TOI_is_not_a_bug(self):
        key=('P00001','GO:2000001');direct={key};propagated={key};toi={'GO:2000001'}
        result=known_chain_flags(key,direct,propagated,toi,set())
        self.assertTrue(result['T0_propagated_and_classifier_TOI_but_missing_from_PK_known'])
        self.assertFalse(known_chain_flags(key,direct,propagated,toi,{key})[
            'T0_propagated_and_classifier_TOI_but_missing_from_PK_known'])
        self.assertFalse(known_chain_flags(key,direct,propagated,set(),set())[
            'T0_propagated_and_classifier_TOI_but_missing_from_PK_known'])

    def test_all_label_pairs_partition_by_all_support_dates_without_scores(self):
        pairs={(f'P{i}','GO:2000001') for i in range(1,5)}
        links={'a':[(('P1','GO:2000001'),'unused'),(('P3','GO:2000001'),'unused')],
               'b':[(('P2','GO:2000001'),'unused'),(('P3','GO:2000001'),'unused')],
               'c':[(('P4','GO:2000001'),'unused')]}
        source={'a':{'annotation_date':'20260410'},'b':{'annotation_date':'20260411'},
                'c':{'annotation_date':'20260230'}}
        result=label_date_partition(pairs,links,source,'20260410')
        self.assertEqual(set(result['counts'].values()),{1})
        self.assertEqual(sum(result['counts'].values()),len(pairs))
        self.assertFalse(result['performance_slice_or_publication_age'])

    def test_existing_postseal_gate_precedes_source_or_hash_access(self):
        with patch('tools.contextual_combination.source_coherence.check_gate',
                   side_effect=ValueError('gate stays closed')):
            with patch('tools.contextual_combination.source_coherence.sha',
                       side_effect=AssertionError('no source hash before gate')) as hashed:
                with self.assertRaisesRegex(ValueError,'gate stays closed'):
                    run({'format':'biograph-steward.postseal-source-coherence.v1'},'/unused')
                hashed.assert_not_called()


class NativeKnownMaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from tools.learned_combination.native_adapter import _native
            cls.native=_native()
        except (ImportError,ValueError,FileNotFoundError) as error:
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED')=='1':raise
            raise unittest.SkipTest(str(error))

    def test_actual_parsed_known_mask_flags_parent_but_keeps_unknown_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);obo=root/'invented.obo'
            obo.write_text('''format-version: 1.2

[Term]
id: GO:0008150
name: root
namespace: biological_process

[Term]
id: GO:2000001
name: parent
namespace: biological_process
is_a: GO:0008150 ! root

[Term]
id: GO:2000002
name: child
namespace: biological_process
is_a: GO:2000001 ! parent
''')
            parser=self.native['parser'];ont=parser.obo_parser(str(obo),('is_a','part_of'),None,False)
            truth=root/'truth.tsv';known=root/'known.tsv'
            truth.write_text('EntryID\tterm\taspect\nP00001\tGO:2000002\tP\n')
            known.write_text('EntryID\tterm\taspect\nP00001\tGO:2000001\tP\n')
            gt=parser.gt_parser(str(truth),ont);excluded=parser.gt_exclude_parser(str(known),gt,ont)
            result=residual_mask_audit({('P00001','GO:2000001'),('P00001','GO:2000002')},
                gt['biological_process'],excluded['biological_process'],ont['biological_process'])
            self.assertEqual(result,{'residual_pairs_present_in_exact_parsed_known_exclusion':1,
                                     'residual_pairs_absent_from_exact_parsed_GT':0})

    def test_other_namespace_uses_explicit_aspect_and_unchanged_native_propagation(self):
        import networkx as nx
        from .provenance import load_author
        author=os.environ.get('BIOGRAPH_DEMOCAFA_SOURCE',
            str(Path(__file__).resolve().parents[2]/'runs/contextual_gain_20261115/operator/democafa_author_source'))
        helpers,_,experimental,_=load_author(author)
        graph=nx.MultiDiGraph()
        graph.add_node('GO:0003674',namespace='molecular_function')
        graph.add_node('GO:2000001',namespace='molecular_function')
        graph.add_edge('GO:2000001','GO:0003674',key='is_a')
        rows=[{'native':{'subject':'UniProtKB:P00001','evidence_code':'IDA','negated':False},
               'canonical_in_view_graph':True,'canonical_term':'GO:2000001'}]
        _,curated,nonreference=t0_presence(rows,graph,experimental,helpers['propagate_terms'],
                                          'molecular_function','F')
        self.assertTrue(curated[('P00001','GO:2000001')])
        self.assertTrue(curated[('P00001','GO:0003674')])
        self.assertFalse(nonreference)
