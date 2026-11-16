"""Invented source fixtures qualify the current-tool controller, not biology."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from biograph_steward import source_agent as agent
from biograph_steward.client import digest
from biograph_steward.evidence_extension import publish_extension
from biograph_steward.model_transport import JSONModelClient
import test_string_physical_source as physical_fixture
import test_goa_locations as location_fixture
import test_native_pathway_question as pathway_fixture


def value(schema):
    if 'const' in schema:return schema['const']
    if 'anyOf' in schema:return value(schema['anyOf'][-1])
    if schema.get('type')=='object':return {k:value(v) for k,v in schema['properties'].items()}
    if schema.get('type')=='array':return [value(schema['items']) for _ in range(schema.get('minItems',1))]
    if 'enum' in schema:return schema['enum'][0]
    return 'Select the bounded saved source context.'


class FakeModel:
    kind='injected_test_model';model='INVENTED-model';max_output_tokens=1200
    def __init__(self,change=None):self.calls=[];self.change=change
    def generate(self,prompt,schema,policy,audit=None):
        phase=json.loads(prompt.split('\nUntrusted input data:\n',1)[1])['phase']
        output=value(schema)
        if self.change:output=self.change(phase,output)
        self.calls.append({'phase':phase,'schema':deepcopy(schema),'output':deepcopy(output)})
        return {'status':'completed','output':output,'model_calls':1,'provider_kind':self.kind,'model_requested':self.model,
                'schema_sha256':digest(schema),'request_sha256':digest(prompt),'response_sha256':digest(output)}


def reseal(result):
    result['content_sha256']=digest({k:v for k,v in result.items() if k!='content_sha256'})
    return result


class SourceAgentPhysicalTests(unittest.TestCase):
    def setUp(self):
        self.fixture=physical_fixture.NativePhysicalTests('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        _,self.folder,_,self.graph=self.fixture.workspace();self.protein='UniProtKB:P04637'
        self.question='Inspect candidate native STRING physical associations with '+self.protein+'.'
    def run_agent(self,**kwargs):
        return agent.run_source_agent(self.question,self.graph,source_run='physical',source_folder=self.folder,
                                      client=kwargs.pop('client',FakeModel()),**kwargs)

    def test_actual_query_all_paths_and_selected_passport_are_preserved_without_live_scores(self):
        before=deepcopy(self.graph);events=[];client=FakeModel()
        with patch('biograph_steward.physical_ranking.collect_ranking',side_effect=AssertionError('No live lookup')):
            result=self.run_agent(client=client,event_callback=events.append)
            agent.verify_source_agent_result(result,self.graph,'physical',self.folder)
        self.assertEqual(result['status'],'completed');self.assertEqual(result['trace']['provider_kind'],'injected_test_model')
        self.assertEqual(result['trace']['model_calls'],3);self.assertEqual(result['answer']['coverage']['matching_proteins'],2)
        self.assertEqual(len(result['answer']['citations']),2);self.assertEqual(len(result['inspections']),1)
        self.assertEqual(len(result['focus_graph']['edges']),2)
        self.assertTrue(result['inspections'][0]['passport']['sections'])
        self.assertTrue(all(p['proposal_only'] and not p['applied'] and p['decision'] in {'keep','abstain'} for p in result['proposals']))
        self.assertEqual(self.graph,before);self.assertFalse(result['proposals_applied'])
        self.assertEqual([e['event'] for e in events],['request_intent','model_response','tool_result','request_intent','model_response','tool_result','request_intent','model_response'])
        self.assertTrue(all('Untrusted input data:' in s['request']['prompt'] for s in result['trace']['steps']))

    def test_accepted_empty_is_a_real_query_not_an_agent_abstention_or_candidate_fallback(self):
        client=FakeModel();self.question='Inspect accepted native STRING physical associations with '+self.protein+'.'
        result=self.run_agent(client=client,constraints={'view':'accepted'})
        self.assertEqual(result['status'],'completed_empty');self.assertEqual(len(client.calls),1)
        self.assertEqual(result['query_result']['returned_proteins'],0)
        self.assertEqual(result['query_result']['availability']['inspectable_proteins'],2)
        self.assertEqual(result['proposals'],[]);self.assertFalse(result['trace']['preflight_blocked'])

    def test_preflight_guard_is_not_credited_as_model_reasoning(self):
        for question in ['Show direct binding of '+self.protein+' confirmed by pull-down assay.',
                         'Show colon-tissue-specific physical associations with '+self.protein+'.',
                         'Show native physical associations of PROTEIN_NOT_IN_THIS_WORKSPACE.']:
            with self.subTest(question=question),patch.object(agent,'configured_source_agent_client',side_effect=AssertionError('No model factory')):
                result=agent.run_source_agent(question,self.graph,source_run='physical')
            self.assertEqual(result['status'],'scope_rejected');self.assertEqual(result['trace']['model_calls'],0)
            self.assertTrue(result['trace']['preflight_blocked']);self.assertEqual(result['trace']['decision_origin'],'preflight_guard')

    def test_model_cannot_change_anchor_view_cap_or_native_eligibility(self):
        for field,bad in [('protein_id','UniProtKB:P00533'),('view','accepted'),('max_results',30),('source_support','all_source_annotations')]:
            def change(phase,output):
                if phase=='plan':output['arguments'][field]=bad
                return output
            with self.subTest(field=field):
                model=FakeModel(change);result=self.run_agent(client=model)
                self.assertEqual(result['status'],'invalid_plan');self.assertEqual(len(model.calls),1)
                self.assertIsNone(result['plan']);self.assertIsNone(result['query_result'])
                self.assertEqual(model.calls[0]['output']['arguments'][field],bad)

    def test_source_assertion_batch_limit_never_substitutes_first_record(self):
        citation={'id':'E001','source_assertion_ids':['assertion:'+str(i) for i in range(33)]}
        with patch.object(agent,'inspect_selection',side_effect=AssertionError('No partial inspection')):
            with self.assertRaisesRegex(ValueError,'complete citation inspection'):
                agent._inspect_citation(self.graph,citation,'physical')

    def test_boolean_is_not_a_numeric_budget(self):
        def change(phase,output):
            if phase=='plan':output['arguments']['max_results']=True
            return output
        result=self.run_agent(client=FakeModel(change),constraints={'max_results':1})
        self.assertEqual(result['status'],'invalid_plan')
        with self.assertRaises(ValueError):self.run_agent(constraints={'max_results':True})

    def test_unknown_or_duplicate_inspection_does_not_hide_valid_query_results(self):
        for ids in [['E999'],['E001','E001']]:
            def change(phase,output):
                if phase=='inspection_priority':output['citation_ids']=ids
                return output
            model=FakeModel(change);result=self.run_agent(client=model)
            self.assertEqual(result['status'],'invalid_inspection');self.assertEqual(len(model.calls),2)
            self.assertEqual(result['answer']['coverage']['matching_proteins'],2);self.assertEqual(result['inspections'],[])

    def test_unjustified_prune_and_generated_science_are_rejected_not_rewritten(self):
        for extra in [{'decision':'prune'},{'reason':'This is biologically false because confidence is low.'}]:
            def change(phase,output):
                if phase=='review_proposals':output['proposals'][0].update(extra)
                return output
            result=self.run_agent(client=FakeModel(change))
            self.assertEqual(result['status'],'invalid_proposal');self.assertEqual(result['proposals'],[])
            self.assertEqual(result['answer']['coverage']['matching_proteins'],2)
            self.assertFalse(result['proposals_applied'])
            agent.verify_source_agent_result(result,self.graph,'physical',self.folder)

    def test_raw_trace_and_scope_are_preserved_when_model_abstains(self):
        def abstain(phase,output):return {'action':'abstain','reason':'Cannot choose this tool.'}
        result=self.run_agent(client=FakeModel(abstain))
        self.assertEqual(result['status'],'abstained');self.assertFalse(result['trace']['preflight_blocked'])
        self.assertEqual(result['trace']['model_calls'],1);self.assertEqual(result['trace']['decision_origin'],'model_output')
        self.assertIsNone(result['answer']);agent.verify_source_agent_result(result,self.graph,'physical',self.folder)

    def test_saved_replay_rejects_resealed_graph_or_source_changes(self):
        result=self.run_agent();changed=deepcopy(result)
        changed['focus_graph']['edges'][0]['source_scores_raw']['physical_combined_score']=999
        with self.assertRaisesRegex(ValueError,'differs'):agent.verify_source_agent_result(reseal(changed),self.graph,'physical',self.folder)
        changed_graph=deepcopy(self.graph);changed_graph['review_events'].append({'invented':'changed'})
        with self.assertRaisesRegex(ValueError,'graph or review'):agent.verify_source_agent_result(result,changed_graph,'physical',self.folder)

    def test_model_failure_and_recording_failure_preserve_truthful_zero_or_one_call(self):
        model=FakeModel()
        def unavailable(*args,**kwargs):
            model.calls.append({'failed':True})
            return {'status':'model_error','output':None,'model_calls':1,'provider_kind':'injected_test_model','error':'Invented transport failure'}
        model.generate=unavailable
        result=self.run_agent(client=model)
        self.assertEqual(result['status'],'model_error');self.assertEqual(result['trace']['model_calls'],1)
        self.assertEqual(result['trace']['tool_calls'],[])
        agent.verify_source_agent_result(result,self.graph,'physical',self.folder)
        model=FakeModel()
        def broken_sink(event):raise OSError('Invented recording failure')
        result=self.run_agent(client=model,event_callback=broken_sink)
        self.assertEqual(result['status'],'recording_error');self.assertEqual(model.calls,[])
        self.assertEqual(result['trace']['model_calls'],0);self.assertEqual(result['trace']['decision_origin'],'recording_failure')
        agent.verify_source_agent_result(result,self.graph,'physical',self.folder)
        model=FakeModel()
        def response_sink_failure(event):
            if event['event']=='model_response':raise OSError('Invented post-response disk failure')
        result=self.run_agent(client=model,event_callback=response_sink_failure)
        self.assertEqual(result['status'],'recording_error');self.assertEqual(len(model.calls),1)
        self.assertEqual(result['trace']['model_calls'],1);self.assertEqual(len(result['trace']['steps']),1)
        agent.verify_source_agent_result(result,self.graph,'physical',self.folder)

    def test_configured_transport_reuses_existing_role_with_bounded_output(self):
        model=FakeModel();model.max_output_tokens=1600
        with patch.object(agent,'selected_provider',return_value='nim'),patch.object(agent,'JSONModelClient',return_value=model) as factory:
            self.assertIs(agent.configured_source_agent_client(),model)
        factory.assert_called_once_with(role='planner',provider='nim');self.assertEqual(model.max_output_tokens,1200)

    def test_canonical_job_roundtrip_preserves_exact_request_replay(self):
        result=self.run_agent()
        stored=json.loads(json.dumps(result,sort_keys=True))
        self.assertEqual(agent.verify_source_agent_result(stored,self.graph,'physical',self.folder),result)

    def test_model_source_projection_is_bounded_without_altering_full_passport(self):
        result=self.run_agent();p=deepcopy(result['inspections'][0]['passport'])
        p['sections']=p['sections']*100
        p['sections'][0]['fields']['invented_large_field']='X'*10000
        original=deepcopy(p)
        view=agent._inspection_model_view([{'citation_id':'E001','passport':p}])[0]
        self.assertLess(len(json.dumps(view)),6500);self.assertEqual(p,original)
        self.assertEqual(view['section_count'],len(p['sections']))
        self.assertLess(view['shown_sections'],view['section_count']);self.assertIn('Omitted fields are not absent',view['projection_note'])
        self.assertEqual(view['full_passport_sha256'],digest(p))

    def test_resealed_trace_changes_cannot_claim_different_model_or_tool_execution(self):
        result=self.run_agent()
        for mutate in [lambda r:r['trace']['tool_calls'].clear(),
                       lambda r:r['trace']['steps'][0]['model_trace']['output'].update(reason='Altered output'),
                       lambda r:r['trace']['steps'][1]['request'].update(prompt='Altered source input'),
                       lambda r:r['trace'].update(model_calls=True),
                       lambda r:r['proposals'][0].update(reason='New unsupported fact')]:
            changed=deepcopy(result);mutate(changed)
            with self.assertRaises(ValueError):agent.verify_source_agent_result(reseal(changed),self.graph,'physical',self.folder)

    def test_real_existing_transport_path_records_injected_identity_and_payload_schema(self):
        payloads=[]
        def transport(payload):
            payloads.append(deepcopy(payload));output=value(payload['guided_json'])
            return {'model':'INVENTED-model','choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(output)}}]}
        client=JSONModelClient(role='planner',provider='nim',model='INVENTED-model',endpoint='http://127.0.0.1:9999/v1/chat/completions',api='nim_chat',transport=transport)
        client.max_output_tokens=1200
        result=self.run_agent(client=client)
        self.assertEqual(result['status'],'completed');self.assertEqual(len(payloads),3)
        self.assertTrue(all(p['max_tokens']==1200 and 'guided_json' in p for p in payloads))
        self.assertEqual(result['trace']['provider_kind'],'injected_test_model')
        self.assertTrue(all(s['model_trace']['request_sha256']==digest(p) for s,p in zip(result['trace']['steps'],payloads)))


class SourceAgentLocationTests(unittest.TestCase):
    def test_native_all_code_location_is_executed_and_original_codes_remain(self):
        f=location_fixture.NativeLocationTests('runTest');f.setUp();self.addCleanup(f.doCleanups);f.publish()
        graph=publish_extension(f.run,{'goa':f.publication},f.root/'location');protein=f.native[0]['subject']
        before=deepcopy(graph)
        result=agent.run_source_agent('Show candidate native GO location annotations for '+protein+'.',graph,source_run='location',client=FakeModel())
        self.assertEqual(result['status'],'completed');self.assertEqual(result['plan']['tool'],'native_location')
        self.assertEqual(result['query_result']['records'][0]['evidence_code'],'TAS')
        self.assertIn('TAS',json.dumps(result['inspections'][0]['passport']))
        self.assertEqual(graph,before);agent.verify_source_agent_result(result,graph,'location')
        self.assertNotIn('native_physical',[t['name'] for t in agent.source_catalogue(graph)['tools']])


class SourceAgentPathwayTests(unittest.TestCase):
    def test_exact_revision_native_eligibility_and_gene_level_context_are_not_weakened(self):
        f=pathway_fixture.NativePathwayQuestionTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        before=deepcopy(f.graph)
        expected=f.question(source_support='native_supported')
        grouped=max(expected['citations'],key=lambda c:len(c['source_assertion_ids']))
        self.assertGreater(len(grouped['source_assertion_ids']),1)
        def priority(phase,output):
            if phase=='inspection_priority':output['citation_ids']=[grouped['id']]
            return output
        with patch('biograph_steward.qualified_workspace.read_pathway_history',return_value=f.packet):
            result=agent.run_source_agent('Show candidate archived pathway context for '+f.protein+'.',f.graph,source_run='qualified',source_folder=f.out,client=FakeModel(priority))
            self.assertEqual(result['status'],'completed');self.assertEqual(result['plan']['arguments']['source_support'],'native_supported')
            self.assertEqual({c['source_model_id'] for c in result['answer']['citations']},{'WP1_r10'})
            self.assertTrue(any(c['historical_source']['status']=='compatible_gene_level_xref' for c in result['answer']['citations']))
            batch=result['inspections'][0]
            self.assertEqual(batch['inspected_assertion_ids'],grouped['source_assertion_ids'])
            self.assertEqual(len(batch['passports']),len(grouped['source_assertion_ids']))
            self.assertEqual(batch['passport'],batch['passports'][0]);self.assertEqual(batch['omitted_assertion_ids'],[])
            self.assertTrue(batch['complete_citation_inspection'])
            self.assertEqual(result['trace']['tool_calls'][1]['source_reads'],len(batch['passports']))
            self.assertEqual(result['proposals'][0]['source_assertion_ids'],batch['inspected_assertion_ids'])
            agent.verify_source_agent_result(result,f.graph,'qualified',f.out)
            altered=deepcopy(result);altered['inspections'][0]['passports'].pop()
            with self.assertRaisesRegex(ValueError,'coverage differs'):
                agent.verify_source_agent_result(reseal(altered),f.graph,'qualified',f.out)
        self.assertEqual(f.graph,before)


if __name__=='__main__':unittest.main()
