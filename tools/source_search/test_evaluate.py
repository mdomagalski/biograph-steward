"""Synthetic reference IDs only; never import or open a real BioASQ case."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import write_json
from biograph_steward.file_utils import sha
from . import evaluate as e
from biograph_steward.client import digest


class ReferenceBoundaryTests(unittest.TestCase):
    def test_only_selected_document_events_are_interpreted(self):
        events=[('questions.item','start_map',None),('questions.item.id','string','outside'),
            ('questions.item.documents.item','string',object()),('questions.item.exact_answer','string',object()),
            ('questions.item','end_map',None),('questions.item','start_map',None),
            ('questions.item.documents.item','string','https://pubmed.ncbi.nlm.nih.gov/101/'),
            ('questions.item.id','string','selected'),('questions.item.ideal_answer.item','string',object()),
            ('questions.item','end_map',None)]
        self.assertEqual(e.selected_documents(None,{1:'selected'},parser=lambda _:iter(events)),{'selected':['101']})

    def test_reference_identity_mismatch_and_nonpubmed_URL_fail_closed(self):
        events=[('questions.item','start_map',None),('questions.item.id','string','other'),('questions.item','end_map',None)]
        with self.assertRaisesRegex(ValueError,'identity'):e.selected_documents(None,{0:'selected'},parser=lambda _:iter(events))
        for url in ['https://example.invalid/101','https://user:password@pubmed.ncbi.nlm.nih.gov/101',
                    'https://pubmed.ncbi.nlm.nih.gov/101?other=1','https://pubmed.ncbi.nlm.nih.gov/0']:
            with self.subTest(url=url),self.assertRaises(ValueError):e.reference_pmid(url)

    def test_old_and_current_literal_pubmed_URL_shapes_match(self):
        for url in ['http://www.ncbi.nlm.nih.gov/pubmed/101','https://pubmed.ncbi.nlm.nih.gov/101/']:
            self.assertEqual(e.reference_pmid(url),'101')

    def test_utility_or_incomplete_arm_manifest_cannot_release_reference(self):
        with tempfile.TemporaryDirectory()as temp:
            folder=Path(temp);value=e.seal({'format':'utility','status':'completed'})
            write_json(folder/'execution.json',value)
            with patch.object(e,'load_frame',return_value=({},[])),patch.object(e,'verify_policy',return_value={}):
                with self.assertRaisesRegex(ValueError,'all fixed blocked'):
                    e.seal_predictions(folder,'protocol',folder,sha(folder/'execution.json'),folder,'policy','pin',folder/'new.json')

    def test_invalid_prediction_seal_stops_before_reference_file_open(self):
        with patch.object(e,'load_frame',return_value=({},[])),patch.object(e,'verify_policy',return_value={}),\
             patch.object(e,'read_sealed',return_value={'format':'not_a_prediction_seal'}):
            with self.assertRaisesRegex(ValueError,'complete reviewed prediction seal'):
                e.release_score('no-real-data','p','no-real-seal','s','policy','q','no-output')


class MetricTests(unittest.TestCase):
    def test_same_condition_recovery_intervals_reuse_released_fixed_questions(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);reports=[]
            for phase,recall,seal_pin in [('old',.25,'oldseal'),('new',.5,'newseal')]:
                folder=root/phase;folder.mkdir()
                cases=[{'case_id':str(i),'reference_pmids':['101'],'arms':{
                    'direct_native_query':{'recall_at_10':0.},'unskilled_agent':{'recall_at_10':recall},
                    'procedure_skill_agent':{'recall_at_10':recall}}}for i in range(24)]
                write_json(folder/'case_scores.private.json',cases)
                report=e.seal({'format':'biograph-steward.source-search-reference-comparison.v1',
                    'lineage':{'prediction_seal_file_sha256':seal_pin},'raw_case_scores_sha256':sha(folder/'case_scores.private.json'),
                    'all_reference_questions_scorable':True,'paired_comparisons':[{'retained_original_primary':phase}],
                    'metrics':{'direct_native_query':{'mean_reference_recall_at_10':0.}},'execution_costs':{}})
                write_json(folder/'report.json',report);reports.append(folder/'report.json')
            op=e.seal({'format':'biograph-steward.source-search-recovery-operational-check.v1',
                'lineage':{'original_prediction_seal_file_sha256':'oldseal','followup_prediction_seal_file_sha256':'newseal'},
                'operational_retention_criterion':{'passed':True},'observed_shared_payload_prefix':{}})
            write_json(root/'op.json',op)
            value=e.compare_recovery(reports[0],sha(reports[0]),reports[1],sha(reports[1]),root/'op.json',sha(root/'op.json'),root/'comparison.json')
            self.assertEqual(value['original_primary_skill_minus_base'],{'retained_original_primary':'old'})
            self.assertEqual(len(value['same_condition_recovery_differences']),2)
            for row in value['same_condition_recovery_differences']:
                self.assertEqual(row['observed_mean_difference'],.25)
                self.assertEqual(row['paired_95_percentile_interval'],[.25,.25])
            self.assertFalse(value['new_reference_source_access_or_model_calls'])
            command=[sys.executable,'-m','tools.source_search.evaluate','compare-recovery',
                '--original-report',str(reports[0]),'--original-report-sha256',sha(reports[0]),
                '--followup-report',str(reports[1]),'--followup-report-sha256',sha(reports[1]),
                '--operational-check',str(root/'op.json'),'--operational-check-sha256',sha(root/'op.json'),
                '--output',str(root/'cli_comparison.json')]
            completed=subprocess.run(command,cwd=Path(__file__).parents[2],capture_output=True,text=True,timeout=20)
            self.assertEqual(completed.returncode,0,completed.stderr)
            cli=json.loads((root/'cli_comparison.json').read_text())
            self.assertEqual(cli['same_condition_recovery_differences'],value['same_condition_recovery_differences'])

    def test_guidance_state_pins_preserve_full_acceptance_contract(self):
        def state(candidates,searches):
            accepted=e.action_schema('c',search_count=searches,get_count=0,candidates=candidates)
            return {'status':'completed','schema_sha256':digest(e.native_guidance_schema(accepted)),
                'full_controller_acceptance_schema_sha256':digest(accepted),'native_guidance_policy':e.GUIDANCE_POLICY}
        first=state({},0);first['output']={'action':'search_pubmed','case_id':'c','query':'synthetic'}
        second=state({'101':{}},1);second['output']={'action':'finish','case_id':'c','ranked_pmids':['101']}
        row={'case_id':'c','status':'completed','ranked_pmids':['101'],'model_calls':2,'history':[{'action':first['output'],'tool_result':{'candidates':[{'pmid':'101'}]}}],
            'candidate_pmids':['101'],'search_queries':['synthetic'],'abstract_get_requested_pmids':[]}
        e.verify_request_guidance(row,[first,second],[dict(first),dict(second)])
        second['full_controller_acceptance_schema_sha256']='bad'
        with self.assertRaisesRegex(ValueError,'full controller'):
            e.verify_request_guidance(row,[first,second],[dict(first),dict(second)])

    def test_feedback_replay_keeps_execution_state_and_rejects_unexecuted_fake_queries(self):
        def state(ids,searches,output):
            accepted=e.action_schema('c',search_count=searches,get_count=0,candidates=ids)
            return {'status':'completed','output':output,'schema_sha256':digest(e.native_guidance_schema(accepted)),
                'full_controller_acceptance_schema_sha256':digest(accepted),'native_guidance_policy':e.GUIDANCE_POLICY}
        search={'action':'search_pubmed','case_id':'c','query':'same'}
        first=state({},0,search);duplicate=state({'101':{}},1,search)
        final=state({'101':{}},1,{'action':'finish','case_id':'c','ranked_pmids':['101']})
        rejected={'model_step':2,'action':search,'feedback':e.duplicate_observation()}
        row={'case_id':'c','status':'completed','ranked_pmids':['101'],'model_calls':3,
            'history':[{'action':search,'tool_result':{'candidates':[{'pmid':'101'}]}}],
            'candidate_pmids':['101'],'search_queries':['same'],'abstract_get_requested_pmids':[],
            'duplicate_feedback_enabled':True,'controller_rejections':[rejected]}
        e.verify_request_guidance(row,[first,duplicate,final],[dict(first),dict(duplicate),dict(final)])
        rejected['action']={**search,'query':'not previously executed'};duplicate['output']=rejected['action']
        with self.assertRaisesRegex(ValueError,'not a duplicate'):
            e.verify_request_guidance(row,[first,duplicate,final],[dict(first),dict(duplicate),dict(final)])

    def test_invented_executed_duplicate_and_unknown_get_fail_controller_replay(self):
        def state(ids,searches,output):
            accepted=e.action_schema('c',search_count=searches,get_count=0,candidates=ids)
            return {'status':'completed','output':output,'schema_sha256':digest(e.native_guidance_schema(accepted)),
                'full_controller_acceptance_schema_sha256':digest(accepted),'native_guidance_policy':e.GUIDANCE_POLICY}
        first={'action':'search_pubmed','case_id':'c','query':'same'}
        for bad in (first,{'action':'get_abstract','case_id':'c','pmid':'999'}):
            traces=[state({},0,first),state({'101':{}},1,bad)]
            row={'case_id':'c','status':'invalid_action','ranked_pmids':[],'model_calls':2,
                'history':[{'action':first,'tool_result':{'candidates':[{'pmid':'101'}]}},
                    {'action':bad,'tool_result':{'candidates':[{'pmid':'101'}]}}],
                'candidate_pmids':['101'],'search_queries':['same'],'abstract_get_requested_pmids':[]}
            with self.subTest(action=bad),self.assertRaises(ValueError):
                e.verify_request_guidance(row,traces,[dict(t)for t in traces])

    def test_trajectory_counts_do_not_publish_article_identities_or_claim_gain(self):
        row={'status':'completed','model_calls':3,'history':[{'action':{'action':'search_pubmed'}},{'action':{'action':'get_abstract'}}],
            'search_queries':['synthetic'],'abstract_get_requested_pmids':['101'],'abstracts_identity_resolved':['101']}
        out=e.trajectory_summary([row,row])
        self.assertEqual(out['distinct_successfully_opened_article_ID_count'],1)
        self.assertEqual(out['cases_requesting_abstract'],2);self.assertEqual(out['early_finish_cases_before_four_calls'],2)
        self.assertEqual(out['tool_order_counts'],{'search_pubmed > get_abstract':2})
        self.assertNotIn('101',json.dumps(out))

    def test_recall_uses_known_positive_reference_only(self):
        result=e.retrieval_metrics(['101','102','103'],['101','999'])
        self.assertAlmostEqual(result['recall_at_10'],1/3);self.assertEqual(result['reference_hit_at_10'],1)
        self.assertNotIn('false_positives',result);self.assertNotIn('biological_accuracy',result)

    def test_empty_system_retrieval_is_miss_but_empty_reference_is_unscorable(self):
        result=e.retrieval_metrics(['101'],[])
        self.assertEqual(result['recall_at_10'],0);self.assertEqual(result['status'],'scored')
        result=e.retrieval_metrics([],['101'])
        self.assertIsNone(result['recall_at_10']);self.assertEqual(result['status'],'unscorable_reference_empty')

    def test_fixed_shared_question_resampling_is_reproducible(self):
        scores={'direct_native_query':[0.]*24,'unskilled_agent':[.25]*24,'procedure_skill_agent':[.5]*24}
        weights,contrasts=e.paired_bootstrap(scores);again,_=e.paired_bootstrap(scores)
        self.assertEqual(weights,again);self.assertEqual(len(weights),2000)
        self.assertTrue(all(len(row)==24 and sum(row)==24 for row in weights))
        primary=contrasts[0]
        self.assertEqual(primary['observed_mean_difference'],.25)
        self.assertEqual(primary['paired_95_percentile_interval'],[.25,.25])


if __name__=='__main__':unittest.main()
