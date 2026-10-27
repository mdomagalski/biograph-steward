"""Invented controls for final orchestration; no selected source body is opened."""
from copy import deepcopy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from scripts.intact_final_common import (DEVELOPMENT, RESERVED, study_ids,
    provenance_audit, overlap_inventory, participant_pair, assess_alignment,
    summarize, fraction, ordinary)
from scripts.evaluate_intact_evidence_fidelity import evaluate_rows
from tests.test_intact_evidence_fidelity import fixture, render


def inventory(**extra):
    return {'format':'biograph-steward.intact-consumed-inventory.v1',
        'scope':'Wholly invented test inventory; no real assay rows.',
        'publication_ids':['11111111'],'dois':[],'evidence_ids':[],
        'pairs':[],'participants':[],'qualified_see_also_links':[['11111111','22222222']],**extra}


def xml_record(*,pmid='22222222',annotation=None,xrefs=None):
    return {'record_kind':'evidence','evidence_sequence':1,
        'evidence':{'xml_id':'invented-record','identifiers':[],
        'xrefs':xrefs or [],'annotations':annotation or [],'participants':[{},{}],
        'experiments':[{'xml_id':'invented-experiment','identifiers':[],
            'xrefs':[],'annotations':[],'publication':{'pubmed_id':pmid,
            'identifiers':[],'xrefs':[],'annotations':[]}}]}}


def xref(db,value):return {'database':{'name':db},'id':value,'qualifier':{'mi_id':'MI:0361','name':'see-also'}}
def note(value):return [{'topic':{'name':'comment'},'value':value}]


class FinalAccountingTests(unittest.TestCase):
    def test_exact_scope_and_order_are_closed(self):
        self.assertEqual(study_ids('reserved_final'),RESERVED)
        self.assertEqual(study_ids('development_replay'),DEVELOPMENT)
        with self.assertRaises(ValueError):study_ids('any')

    def test_zero_rows_not_success(self):
        metrics=summarize({'rows':[]},[],RESERVED)
        self.assertIsNone(metrics['strict_fidelity']['value'])
        self.assertEqual(metrics['coverage']['status'],'unevaluated_empty_stratum')
        self.assertEqual(len(metrics['per_publication']),4)

    def test_missing_outputs_preserve_entire_source_denominator(self):
        refs,_,_,_=fixture()
        result=evaluate_rows(refs,[],[],[],[],'',graph_edges=[])
        metrics=summarize(result,refs,DEVELOPMENT)
        self.assertEqual(metrics['coverage']['denominator'],4)
        self.assertEqual(metrics['strict_fidelity']['numerator'],0)
        self.assertEqual(metrics['coverage']['numerator'],0)

    def test_repeated_pair_is_not_deduplicated_out_of_denominator(self):
        refs,obs,res,edges=fixture()
        result=evaluate_rows(refs,obs,res,deepcopy(obs),deepcopy(res),render(res),graph_edges=edges)
        self.assertEqual(summarize(result,refs,DEVELOPMENT)['strict_fidelity']['numerator'],4)
        self.assertEqual(len({participant_pair(ref['reader_record']) for ref in refs}),1)

    def test_missing_evaluator_row_is_rejected(self):
        refs,_,_,_=fixture()
        with self.assertRaises(ValueError):summarize({'rows':[]},refs,DEVELOPMENT)

    def test_all_negative_literals_and_empty_strata(self):
        self.assertIsNone(fraction(0,0)['value'])
        refs,_,_,_=fixture()
        for ref,literal in zip(refs,['true','false','-','true']):ref['reader_record']['raw_cells'][35]=literal
        metrics=summarize(evaluate_rows(refs,[],[],[],[],''),refs,DEVELOPMENT)
        self.assertEqual(metrics['strata']['negative_literal']['true']['denominator'],2)
        self.assertEqual(metrics['strata']['negative_literal']['-']['denominator'],1)

    def test_exact_isoform_identity_is_not_collapsed(self):
        refs,_,_,_=fixture();row=refs[0]['reader_record'];changed=deepcopy(row)
        changed['source_fields']['primary_ids_a']['values'][0]['id']='P12345'
        self.assertNotEqual(participant_pair(row),participant_pair(changed))
        inv=overlap_inventory([{'reader_record':row}])
        self.assertIn(('uniprotkb','P12345-2'),inv['participants'])

    def test_symlink_target_refused_before_read(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);(p/'actual').write_text('invented');(p/'alias').symlink_to(p/'actual')
            with self.assertRaises(ValueError):ordinary(p/'alias')
    def test_whole_output_extras_and_duplicates_are_not_hidden_by_scoring_subset(self):
        from scripts.intact_final_common import output_inventory_checks
        refs,obs,res,_=fixture();extra=deepcopy(obs[0]);extra['source']['source_line']=999
        checks=output_inventory_checks(refs,[*obs,extra],res,obs,res)
        self.assertFalse(all(check['passed'] for check in checks))
        checks=output_inventory_checks(refs,[*obs,obs[0]],res,obs,res)
        self.assertFalse(all(check['passed'] for check in checks))

    def test_reserved_panel_has_one_global_execution_claim(self):
        from scripts import run_intact_final_evaluation as runner
        with tempfile.TemporaryDirectory() as root:
            marker=Path(root)/'fixed_access.json'
            with patch.object(runner,'RESERVED_ACCESS_MARKER',marker):
                runner.claim_reserved_execution(Path(root)/'invented_freeze.json','a'*64)
                with self.assertRaises(FileExistsError):
                    runner.claim_reserved_execution(Path(root)/'renamed_freeze.json','b'*64)



class FinalLineageTests(unittest.TestCase):
    def test_absent_annotations_keep_independence_unknown(self):
        result=provenance_audit({'22222222':[xml_record()]},[],inventory())
        self.assertEqual(result['study_independence'],'unverified')
        self.assertFalse(result['excluded_publication_ids']);self.assertFalse(result['ambiguous_dataset_statements'])

    def test_generic_see_also_to_consumed_study_does_not_exclude(self):
        result=provenance_audit({'22222222':[xml_record(xrefs=[xref('pubmed','11111111')])]},[],inventory())
        self.assertFalse(result['excluded_publication_ids'])

    def test_explicit_shared_data_consumed_link_excludes(self):
        record=xml_record(annotation=note('Primary dataset is reported in referenced publication'),xrefs=[xref('pubmed','11111111')])
        result=provenance_audit({'22222222':[record]},[],inventory())
        self.assertEqual(result['excluded_publication_ids'],['22222222'])

    def test_qualified_comment_without_resolved_link_stops(self):
        record=xml_record(annotation=note('Subsidiary dataset is described elsewhere'))
        result=provenance_audit({'22222222':[record]},[],inventory())
        self.assertEqual(result['status'],'blocked_ambiguous_dataset_lineage')

    def test_shared_component_is_excluded_together(self):
        first=xml_record(annotation=note('Primary dataset'),xrefs=[xref('pubmed','11111111'),xref('pubmed','33333333')])
        second=xml_record(annotation=note('Subsidiary dataset'),xrefs=[xref('pubmed','22222222')])
        result=provenance_audit({'22222222':[first],'33333333':[second]},[],inventory())
        self.assertEqual(result['excluded_publication_ids'],['22222222','33333333'])

    def test_exact_study_identity_excluded_even_without_annotations(self):
        result=provenance_audit({'11111111':[xml_record(pmid='11111111')]},[],inventory())
        self.assertEqual(result['excluded_publication_ids'],['11111111'])

    def test_pair_participant_overlap_only_exposure(self):
        refs,_,_,_=fixture();row=refs[0]['reader_record'];row['row_status']='evidence';row['line_number']=1
        result=provenance_audit({'22222222':[xml_record()]},[{'publication_id':'pubmed:22222222','reader_record':row}],
            inventory(pairs=[participant_pair(row)],participants=[['uniprotkb','P12345-2']]))
        self.assertFalse(result['excluded_publication_ids']);self.assertTrue(result['exact_exposure'][0]['exact_pair_exposed'])

    def test_generic_evidence_citation_is_not_identity_exposure(self):
        record=xml_record(xrefs=[xref('intact','CONSUMED')])
        result=provenance_audit({'22222222':[record]},[],inventory(evidence_ids=[['intact','CONSUMED']]))
        self.assertFalse(result['excluded_publication_ids'])

    def test_one_comment_with_consumed_and_selected_links_propagates_component(self):
        first=xml_record(annotation=note('Primary dataset'),xrefs=[xref('pubmed','11111111'),xref('pubmed','33333333')])
        result=provenance_audit({'22222222':[first],'33333333':[xml_record(pmid='33333333',xrefs=[xref('pubmed','22222222')])]},[],inventory())
        self.assertEqual(result['excluded_publication_ids'],['22222222','33333333'])

    def test_method_reference_with_dataset_comment_does_not_certify_reuse(self):
        ref=xref('pubmed','11111111');ref['qualifier']={'mi_id':'MI:0686','name':'method citation'}
        record=xml_record(annotation=note('Primary dataset'),xrefs=[ref])
        result=provenance_audit({'22222222':[record]},[],inventory())
        self.assertFalse(result['excluded_publication_ids']);self.assertTrue(result['ambiguous_dataset_statements'])

    def test_nonreciprocal_dataset_link_requires_adjudication(self):
        record=xml_record(annotation=note('Primary dataset'),xrefs=[xref('pubmed','11111111')])
        result=provenance_audit({'22222222':[record]},[],inventory(qualified_see_also_links=[]))
        self.assertFalse(result['excluded_publication_ids']);self.assertTrue(result['ambiguous_dataset_statements'])

    def test_negative_and_missing_context_are_not_lineage_exclusions(self):
        refs,_,_,_=fixture();row=refs[0]['reader_record'];row.update(row_status='evidence',line_number=1);row['raw_cells'][35]='true'
        result=provenance_audit({'22222222':[xml_record()]},[{'publication_id':'pubmed:22222222','reader_record':row}],inventory())
        self.assertFalse(result['excluded_publication_ids'])


class FinalProjectionTests(unittest.TestCase):
    def alignment(self):
        return {'rows':[{'source':{'source_line':1},'alignment':'unique','xml_evidence_sequence':1,'checks':[{'status':'equal'}]},
                        {'source':{'source_line':2},'alignment':'unique','xml_evidence_sequence':1,'checks':[{'status':'equal'}]}],
                'multiple_mitab_rows_per_xml_record':[{'xml_sequence':1,'mitab_rows':2}], 'unmatched_xml_sequences':[]}
    def test_explicit_nary_views_preserved_not_double_experiment(self):
        raw=['-']*42;raw[15]='psi-mi:MI:1060(spoke expansion)'
        records=[{'ledger':{'source_line':n},'reader_record':{'raw_cells':raw}} for n in (1,2)]
        xml=[{'evidence_sequence':1,'evidence':{'participants':[{}, {}, {}]}}]
        self.assertFalse(assess_alignment(self.alignment(),records,xml))
    def test_unexplained_multiple_views_stop(self):
        records=[{'ledger':{'source_line':n},'reader_record':{'raw_cells':['-']*42}} for n in (1,2)]
        xml=[{'evidence_sequence':1,'evidence':{'participants':[{},{}]}}]
        self.assertTrue(assess_alignment(self.alignment(),records,xml))
    def test_unresolved_identity_or_critical_mismatch_stops(self):
        alignment=self.alignment();alignment['multiple_mitab_rows_per_xml_record']=[]
        alignment['rows'][0]['checks']=[{'status':'unresolved'}]
        self.assertTrue(assess_alignment(alignment,[],[]))

if __name__=='__main__':unittest.main()
