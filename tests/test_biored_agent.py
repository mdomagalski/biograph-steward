"""Invented-data controls for outcome masking, bounded tools and honest scores."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from tools.biored_agent.prepare import source_inputs, masked_candidates
from tools.biored_agent.agent import action_schema, checked_action, tool_result, run_case, run_flat_case
from tools.biored_agent.passages import resolve_units
from tools.biored_agent.evaluate import metrics, load_outputs, paired, execution_cost
from tools.biored_agent.secondary import primary_boundary,clustered_intervals
from biograph_steward.client import digest, write_json


def case():
    text='A regulates B.'
    doc=source_inputs(('1|t|A regulates B.\n1|a|The effect was observed.\n'
        '1\t0\t1\tA\tGeneOrGeneProduct\t11;12\n'
        '1\t12\t13\tB\tGeneOrGeneProduct\t22\n'
        '1\tPositive_Correlation\t11\t22\tNovel\n').encode())['1']
    doc['source_units']=[{'id':'unit:one','start':0,'end':len(doc['text']),'text':doc['text']}]
    return {'id':'example','pmid':'1','id1':'11','id2':'22','type1':'GeneOrGeneProduct',
        'type2':'GeneOrGeneProduct','document':doc,'source_url':'https://pubmed.ncbi.nlm.nih.gov/1/'}


class BioRedAgentTests(unittest.TestCase):
    def test_native_outcome_columns_are_discarded_without_decoding(self):
        raw=b'1\tGeneOrGeneProduct\tGeneOrGeneProduct\t11\t22\tnative input\t\xff\xff\t\xfe\t\xfd\n'
        rows=masked_candidates(raw)
        self.assertEqual(rows[0]['masked_tsv'].split('\t')[-3:],['None']*3)
        self.assertEqual(rows[0]['model_text'],'native input')

    def test_native_entity_memberships_and_text_are_preserved_without_relations(self):
        c=case();self.assertEqual(c['document']['entities'][0]['native_ids'],['11','12'])
        self.assertEqual(c['document']['entities'][0]['id'],'11;12')
        self.assertNotIn('Positive_Correlation',json.dumps(c))
        with self.assertRaises(ValueError):source_inputs(b'1|t|Text\n1|a|Abstract\n1\t0\t3\tBAD\tGeneOrGeneProduct\t11\n')

    def test_state_specific_schema_exposes_only_remaining_capabilities(self):
        schema=action_schema('example',available_tools=['get_specialist_relation'])
        self.assertEqual(schema['anyOf'][0]['properties']['tool']['enum'],['get_specialist_relation'])
        final=action_schema('example',available_tools=[])['anyOf']
        self.assertTrue(all(branch['properties']['action']['const']=='conclude' for branch in final))
        self.assertEqual(schema['anyOf'][1]['properties']['evidence_unit_ids']['maxItems'],3)
        self.assertEqual(final[0]['properties']['evidence_unit_ids']['minItems'],1)
        self.assertEqual(final[1]['properties']['evidence_unit_ids']['minItems'],0)
        self.assertNotIn('None',final[0]['properties']['relation']['enum'])
        self.assertEqual(final[1]['properties']['relation']['enum'],['None','Unresolved'])
        with self.assertRaises(ValueError):action_schema('example',available_tools=['read_gold_labels'])

    def test_repeated_tool_and_hallucinated_quote_fail_without_repair(self):
        c=case()
        with self.assertRaises(ValueError):checked_action({'action':'read_tool','case_id':'example','tool':'inspect_document'},c,['inspect_document'])
        value={'action':'conclude','case_id':'example','relation':'Positive_Correlation','evidence_unit_ids':['unit:one']}
        self.assertEqual(checked_action(value,c,['inspect_document'])['quotes'],[c['document']['text']])
        value['evidence_unit_ids']=['unprovided:unit']
        with self.assertRaises(ValueError):checked_action(value,c,['inspect_document'])

    def test_definitive_negative_requires_document_but_unresolved_does_not(self):
        c=case();value={'action':'conclude','case_id':'example','relation':'None','evidence_unit_ids':[]}
        with self.assertRaises(ValueError):checked_action(value,c,[])
        self.assertEqual(checked_action(value,c,['inspect_document'])['relation'],'None')
        value['relation']='Unresolved';self.assertEqual(checked_action(value,c,[])['relation'],'Unresolved')

    def test_tools_return_only_native_inputs_and_uncalibrated_specialist(self):
        c=case();doc=tool_result('inspect_document',c,{})
        self.assertEqual(doc['source_units'][0]['text'],c['document']['text'])
        mentions=tool_result('inspect_entity_mentions',c,{})
        self.assertEqual(len(mentions['mentions']),2)
        model=tool_result('get_specialist_relation',c,{'relation':'Bind','relation_sigmoid_scores':{'Bind':.8}})
        self.assertFalse(model['probabilities_calibrated'])
        self.assertNotIn('gold',model)

    def test_unknown_never_becomes_a_correct_negative_and_wrong_type_counts_twice(self):
        r=metrics(['None','Bind'],['Unresolved','Unresolved'])
        self.assertEqual((r['exact_accuracy'],r['coverage'],r['entity_pair']['f1']),(0,0,0))
        r=metrics(['Bind'],['Association'])
        self.assertEqual((r['exact_positive_relation']['fp'],r['exact_positive_relation']['fn']),(1,1))
        self.assertEqual(r['entity_pair']['f1'],1)

    def test_incomplete_prediction_run_rejects_before_reference_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sp=root/'tool';ag=root/'agent';sp.mkdir();ag.mkdir()
            for out in (sp,ag):
                report={'status':'running','completed_cases':0,'frame_content_sha256':'frame'}
                report['content_sha256']=digest(report);write_json(out/'execution.json',report)
            with self.assertRaises(ValueError):load_outputs({'content_sha256':'frame'},[{'id':'example'}],sp,ag)

    def test_source_ids_never_resolve_to_changed_or_unprovided_text(self):
        c=case();self.assertEqual(resolve_units(c['document'],['unit:one'])[0]['text'],c['document']['text'])
        with self.assertRaises(ValueError):resolve_units(c['document'],[['not-a-string']])
        with self.assertRaises(ValueError):resolve_units(c['document'],['unit:one','unit:one'])
        c['document']['source_units'][0]['text']='A different statement.'
        with self.assertRaises(ValueError):resolve_units(c['document'],['unit:one'])

    def test_agent_reads_feedback_and_can_finish_before_all_tools(self):
        class Client:
            def __init__(self):self.requests=[]
            def generate(self,prompt,schema,policy,audit=None):
                self.requests.append((json.loads(prompt.split('\nUntrusted input data:\n')[1]),schema))
                action=({'action':'read_tool','case_id':'example','tool':'inspect_document'} if len(self.requests)==1 else
                    {'action':'conclude','case_id':'example','relation':'Association','evidence_unit_ids':['unit:one']})
                return {'status':'completed','output':action}
        client=Client()
        with tempfile.TemporaryDirectory() as tmp:
            r=run_case(case(),{},client,Path(tmp)/'case')
        self.assertEqual((r['model_calls'],r['tools_used'],r['relation']),(2,['inspect_document'],'Association'))
        data,schema=client.requests[1]
        self.assertEqual(data['history'][0]['tool_result']['source_units'][0]['id'],'unit:one')
        self.assertNotIn('inspect_document',schema['anyOf'][0]['properties']['tool']['enum'])
        self.assertEqual(r['final']['quotes'],[case()['document']['text']])

    def test_flat_ablation_supplies_identical_tools_without_model_tool_choices(self):
        class Client:
            def generate(self,prompt,schema,policy,audit=None):
                self.data=json.loads(prompt.split('\nUntrusted input data:\n')[1])
                return {'status':'completed','output':{'action':'conclude','case_id':'example','relation':'None','evidence_unit_ids':[]}}
        client=Client();specialist={'relation':'Bind','relation_sigmoid_scores':{'Bind':.8}}
        with tempfile.TemporaryDirectory() as tmp:r=run_flat_case(case(),specialist,client,Path(tmp)/'case')
        self.assertEqual(r['model_calls'],1);self.assertFalse(r['model_driven_tools'])
        self.assertEqual([x['tool_result']['tool'] for x in client.data['history']],
                         ['inspect_document','inspect_entity_mentions','get_specialist_relation'])

    def test_paired_full_accuracy_keeps_abstentions_as_errors(self):
        r=paired(['None','Bind'],['None','Bind'],['Unresolved','Association'],repeats=100)
        self.assertEqual((r['candidate_only_correct'],r['comparator_only_correct']),(2,0))
        self.assertEqual(r['accuracy_delta_95pct_paired_bootstrap'],[1.,1.])
        self.assertEqual(r['exact_McNemar_two_sided_p'],.5)

    def test_execution_accounting_uses_recorded_tokens_and_keeps_missing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'case_one';folder.mkdir()
            write_json(folder/'model_call_1.json',{'usage':{'prompt_tokens':12,'completion_tokens':3,'total_tokens':15},'transport_requests':1})
            write_json(folder/'model_call_2.json',{'usage':None,'transport_requests':1})
            report={'model_calls':2,'tool_reads':1,'model_driven_tools':True}
            results=[{'case_id':'case:one','model_calls':2,'elapsed_seconds':.5,'status':'model_error','tools_used':['inspect_document']}]
            r=execution_cost(root,report,results)
        self.assertEqual(r['reported_token_usage'],{'prompt_tokens':12,'completion_tokens':3,'total_tokens':15,'transport_requests':2})
        self.assertEqual(r['usage_fields_missing_calls']['total_tokens'],1)
        self.assertFalse(r['inference_price_assumed'])

    def test_secondary_reference_waits_for_complete_primary_prediction_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'primary.json'
            value={'format':'biograph-steward.biored-prediction-freeze.v1','completed_cases':127,
                   'frame_content_sha256':'primary-frame','code_sha256':{}}
            value['content_sha256']=digest(value);write_json(path,value)
            with self.assertRaisesRegex(ValueError,'all primary'):
                primary_boundary({'primary_cases':128,'primary_frame_content_sha256':'primary-frame'},path)

    def test_cluster_bootstrap_retains_all_correlated_rows_from_each_publication(self):
        # Row resampling would hide the fact that all errors belong to one paper.
        pmids=['one']*100+['two'];gold=['Bind']*100+['None'];pred=['Bind']*101
        r=clustered_intervals(pmids,gold,{'specialist_native':pred},repeats=200)
        self.assertEqual(r['publications'],2)
        self.assertEqual(r['arm_intervals']['specialist_native']['exact_accuracy'],[0.,1.])


if __name__=='__main__':unittest.main()
