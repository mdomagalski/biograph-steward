"""Invented source identities and public-reference proxy boundary checks."""
import hashlib
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools.reference_accuracy import ppi_network_types as n

A='9606.ENSP00000000001';B='9606.ENSP00000000002';C='9606.ENSP00000000003'


def mapping():
    return n.crosswalk({'P00001':'MAA','P00002':'MBB','P00003':'MCC'},
        {A:'MAA',B:'MBB',C:'MCC'}, {'P00001':{A},'P00002':{B},'P00003':{C}})


def reference(pair=('P00001','P00002'),gold=1):
    return {'pair':pair,'gold':gold,'source_label':{1:'positive',0:'negative',None:'unknown'}[gold],
            'publications':['1'],'reference':{'invented':True}}


class NetworkTypeTests(unittest.TestCase):
    def test_fasta_identity_is_literal_full_human_canonical(self):
        self.assertEqual(n.sequence_records([('sp|P00001|INVENTED OX=9606','MAA')],canonical=True),{'P00001':'MAA'})
        for header,sequence in [('tr|P00001|X OX=9606','MAA'),('sp|P00001|X OX=10090','MAA'),('sp|P00001-2|X OX=9606','MAA'),('sp|P00001|X OX=9606','MaA')]:
            with self.subTest(header=header,sequence=sequence),self.assertRaises(ValueError):n.sequence_records([(header,sequence)],canonical=True)
        with self.assertRaises(ValueError):n.sequence_records([(A,'MAA'),(A,'MAA')],canonical=False)
        with self.assertRaises(ValueError):n.sequence_records([(A+' description','MAA')],canonical=False)

    def test_only_native_UniProt_AC_provenance_enters_direct_aliases(self):
        text=n.ALIAS_HEADER+'\n'+A+'\tP00001\tUniProt_AC\n'+B+'\tP00002\tEnsembl_UniProt\n'+C+'\tP00003\tBLAST_UniProt_AC\n'
        aliases,meta=n.read_aliases(StringIO(text),{'P00001','P00002','P00003'})
        self.assertEqual(aliases,{'P00001':{A}});self.assertEqual(meta['native_alias_rows'],3)
        with self.assertRaisesRegex(ValueError,'duplicate direct canonical'):
            n.read_aliases(StringIO(text+A+'\tP00001\tUniProt_AC\n'),{'P00001'})

    def test_reciprocal_ambiguity_is_not_resolved_by_score_or_sequence(self):
        for aliases,expected in [({'P00001':{A,B}},'ambiguous_direct_STRING_aliases'),
            ({'P00001':{A},'P00002':{A}},'ambiguous_reciprocal_canonical_accessions')]:
            rows=n.crosswalk({'P00001':'MAA','P00002':'MBB'},{A:'MAA',B:'MBB'},aliases)
            self.assertEqual(rows['P00001']['admission'],expected);self.assertIsNone(rows['P00001']['selected_STRING_ID'])

    def test_sequence_mismatch_missing_source_and_secondary_names_abstain(self):
        for seqs,aliases,reason in [({A:'MAB'},{'P00001':{A}},'full_sequence_mismatch'),
            ({},{'P00001':{A}},'STRING_sequence_missing'),({A:'MAA'},{},'missing_direct_UniProt_AC_alias')]:
            row=n.crosswalk({'P00001':'MAA'},seqs,aliases)['P00001']
            self.assertEqual(row['admission'],reason);self.assertIsNone(row['selected_STRING_ID'])
        self.assertEqual(mapping()['P00001']['canonical_sequence_sha256'],hashlib.sha256(b'MAA').hexdigest())

    def test_self_absent_and_collapsed_source_identities_are_unavailable(self):
        self.assertEqual(n.mapped_pair(('P00001','P00001'),mapping())[1],'self_pair_outside_proxy_domain')
        self.assertEqual(n.mapped_pair(('P00001','P99999'),mapping())[1],'accession_outside_reviewed_canonical_reference')
        m=mapping();m['P00002']['selected_STRING_ID']=A
        self.assertEqual(n.mapped_pair(('P00001','P00002'),m)[1],'distinct_accessions_collapsed_to_same_STRING_ID')

    def test_reverse_native_rows_must_agree_and_explicit_zero_survives(self):
        text=n.LINK_HEADER+'\n'+A+' '+B+' 0\n'+B+' '+A+' 0\n'
        values,meta=n.read_links(StringIO(text),{(A,B)},{A,B})
        self.assertEqual(values,{(A,B):0.});self.assertEqual(meta['queried_pairs_seen_in_both_directions'],1)
        for tail in [B+' '+A+' 1\n',A+' '+B+' 0\n']:
            with self.assertRaises(ValueError):n.read_links(StringIO(n.LINK_HEADER+'\n'+A+' '+B+' 0\n'+tail),{(A,B)},{A,B})

    def test_invalid_source_score_or_unknown_source_node_rejects(self):
        for suffix in ['1001','-1','nan','0.7']:
            with self.assertRaises(ValueError):n.read_links(StringIO(n.LINK_HEADER+'\n'+A+' '+B+' '+suffix+'\n'),{(A,B)},{A,B})
        with self.assertRaises(ValueError):n.read_links(StringIO(n.LINK_HEADER+'\n'+A+' '+B+' 200\n'),{(A,B)},{A})

    def test_absent_edge_is_presence_only_not_numeric_zero_or_negative_gold(self):
        row=n.annotate([reference()],mapping(),{'functional':{(A,B):.8},'physical':{}})[0]
        self.assertEqual(row['scores']['functional_presence_proxy'],1)
        self.assertEqual(row['scores']['physical_presence_proxy'],0)
        self.assertIsNone(row['scores']['physical_native_weight']);self.assertEqual(row['gold'],1)
        row=n.annotate([reference()],mapping(),{'functional':{(A,B):0.},'physical':{}})[0]
        self.assertEqual(row['scores']['functional_native_weight'],0.)

    def test_unknown_gold_and_source_mapping_never_become_false(self):
        m=mapping();m['P00001']['selected_STRING_ID']=None;m['P00001']['admission']='invented_missing'
        rows=n.annotate([reference(gold=None)],m,{'functional':{},'physical':{}})
        self.assertIsNone(rows[0]['gold']);self.assertTrue(all(v is None for v in rows[0]['scores'].values()))

    def test_fixed_pairwise_ranking_uses_intersection_and_preserves_adverse_result(self):
        # Two common returned rows order oppositely; a third functional-only
        # negative must not enter the paired physical/functional comparison.
        rows=n.annotate([reference(),reference(('P00001','P00003'),0),reference(('P00002','P00003'),0)],mapping(),
            {'functional':{(A,B):.9,(A,C):.1,(B,C):.7},'physical':{(A,B):.1,(A,C):.9}})
        # The optional native sklearn implementation is exercised by the
        # separately pinned actual assessment. This core fixture injects its
        # known tiny-case outputs to check cohort admission and loss retention,
        # without adding a second ranking implementation or a core dependency.
        def native_fixture_rank(values,arm):
            scores=[r['scores'][arm] for r in values if r['gold'] is not None and r['scores'][arm] is not None]
            auc=1. if scores==[.9,.1] else 0. if scores==[.1,.9] else None
            return {'scored_pairs':len(scores),'AUROC':auc,'average_precision':auc}
        with patch.object(n.p,'ranking_metrics',side_effect=native_fixture_rank):
            result=n.summarize(rows)
        joint=result['paired_both_native_weights'];self.assertEqual(joint['pairs'],2)
        self.assertEqual(joint['arms']['functional']['AUROC'],1.)
        self.assertEqual(joint['arms']['physical']['AUROC'],0.)
        self.assertEqual(joint['physical_minus_functional']['AUROC'],-1.)
        self.assertEqual(result['arms']['physical_native_weight']['unavailable_label_counts'],{'negative':1})

    def test_single_class_remains_undefined_and_missing_mapping_in_denominator(self):
        rows=n.annotate([reference(),reference(('P00001','P99999'))],mapping(),{'functional':{(A,B):.9},'physical':{}})
        with patch.object(n.p,'ranking_metrics',return_value={'AUROC':None,'average_precision':None}):
            result=n.summarize(rows)
        self.assertIsNone(result['paired_both_native_weights']['physical_minus_functional']['AUROC'])
        self.assertEqual(result['reference_rows'],2)
        self.assertEqual(result['arms']['functional_presence_proxy']['natural_boolean_decision']['abstain'],1)
        self.assertIsNone(result['arms']['functional_native_weight']['ranking']['average_precision'])

    def test_implementation_receipt_is_exclusive_before_any_join(self):
        with TemporaryDirectory() as tmp:
            b=Path(tmp);plan=b/'plan.json';out=b/'implementation.json'
            plan.write_text(json.dumps({'format':n.FORMAT,'status':'frozen_before_new_score_gold_join'}))
            with patch.object(n,'runtime_binding',return_value={'invented':'same'}):
                result=n.seal_implementation(plan,n.sha(plan),out)
                self.assertFalse(result['new_score_gold_join_performed'])
                with self.assertRaisesRegex(ValueError,'exclusive implementation receipt'):
                    n.seal_implementation(plan,n.sha(plan),out)

    def test_changed_helper_receipt_rejects_before_any_source_or_gold_read(self):
        with TemporaryDirectory() as tmp:
            b=Path(tmp);plan=b/'plan.json';receipt=b/'implementation.json';out=b/'out'
            plan.write_text(json.dumps({'format':n.FORMAT,'status':'frozen_before_new_score_gold_join',
                'arms':list(n.ARMS),'no_fit_or_threshold_selection':True,
                'identity_admission':{'alias_source_tokens':['UniProt_AC']}}))
            receipt.write_text(json.dumps({'format':n.FORMAT+'.implementation','plan_sha256':n.sha(plan),
                'new_score_gold_join_performed':False,'runtime':{'invented':'original helper'}}))
            with patch.object(n,'runtime_binding',return_value={'invented':'changed helper'}):
                with self.assertRaisesRegex(ValueError,'implementation/runtime changed'):
                    n.run(plan,n.sha(plan),receipt,n.sha(receipt),out)
            self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
