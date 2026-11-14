"""Synthetic-only boundary and execution tests; no real reference values."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import write_json
from biograph_steward.file_utils import sha
from biograph_steward.model_transport import JSONModelClient
from . import agent,prepare,tools
from .policy import SKILL


def native_result(*,complete=True,rows=None):
    return {'results':rows if rows is not None else [{'pmid':'101','title':'Synthetic source title','date':'2020-01-01','source':'pubmed','matched_sources':['pubmed']}],
        'complete':complete,'source_plan':{'candidate_sources':['pubmed'],'enrichment_sources':[]},
        'query':'native query echo','pagination':{'returned':1,'has_more':False},'_meta':{'warnings':[]}}


class ProjectionTests(unittest.TestCase):
    def test_stream_projection_does_not_emit_reference_or_answer_fields(self):
        source={'questions':[{'id':'a','type':'factoid','body':'Allowed question',
            'documents':['SECRET_GOLD_DOCUMENT'],'ideal_answer':['SECRET_GOLD_ANSWER'],
            'exact_answer':[['SECRET_GOLD_ENTITY']],'snippets':[{'text':'SECRET_GOLD_SNIPPET'}]}]}
        try:rows=list(prepare.projected_questions(io.BytesIO(json.dumps(source).encode())))
        except ImportError:self.skipTest('optional task-local pinned ijson runtime required')
        self.assertEqual(rows,[{'id':'a','type':'factoid','body':'Allowed question'}])
        self.assertNotIn('SECRET_GOLD',json.dumps(rows))

    def test_repeated_allowed_field_fails_without_echoing_values(self):
        events=[('questions.item','start_map',None),('questions.item.id','string','a'),
            ('questions.item.id','string','not_for_logs')]
        with self.assertRaisesRegex(ValueError,'repeated allowed'):
            list(prepare.projected_questions(None,parser=lambda _:iter(events)))

    def test_fixed_exclusions_and_hash_selection_are_deterministic(self):
        rows=[{'id':str(n),'type':kind,'body':f'Unseen synthetic topic {kind} {n}'}for kind,n in [('factoid',1),('factoid',2),('list',3),('list',4)]]
        rows+=[{'id':'manual','type':'factoid','body':'Pharos TCRD source question'},
               {'id':'lead','type':'list','body':'WDR5 and pancreatic cancer'}]
        a,stats=prepare.select_questions(rows,per_type=1)
        b,_=prepare.select_questions(list(reversed(rows)),per_type=1)
        self.assertEqual(a,b);self.assertEqual(len(a),2)
        self.assertEqual(stats['excluded_counts'],{'manual_Pharos_TCRD':1,'publisher_WDR5_pancreatic':1})

    def test_native_provider_plan_and_identity_are_not_guessed(self):
        value=native_result();self.assertEqual(tools.search_projection(value)['candidates'][0]['pmid'],'101')
        value['source_plan']['enrichment_sources']=['europepmc']
        with self.assertRaisesRegex(ValueError,'provider plan'):tools.search_projection(value)
        with self.assertRaisesRegex(ValueError,'shape'):tools.search_projection({'data':{'results':[]}})

    def test_empty_incomplete_result_keeps_its_native_qualifier(self):
        value=native_result(complete=False,rows=[])
        out=tools.search_projection(value)
        self.assertEqual(out['candidates'],[]);self.assertFalse(out['native_metadata']['complete'])


class CacheTests(unittest.TestCase):
    def setup_tool(self,folder,runner):
        binary=folder/'fake_binary';binary.write_bytes(b'SYNTHETIC_NOT_EXECUTABLE')
        q=prepare.seal({'format':'biograph-steward.biomcp-binary-qualification.v1',
            'binary':{'file':str(binary),'sha256':sha(binary)}})
        receipt=folder/'qualification.json';write_json(receipt,q)
        return tools.SourceTools(receipt,sha(receipt),folder/'cache',runner=runner)

    def test_same_query_uses_same_immutable_capture_across_agents(self):
        calls=[]
        def runner(args,folder):
            calls.append(args);return {'stdout':json.dumps(native_result()).encode(),'stderr':b'','exit_code':0,'process_status':'returned'}
        with tempfile.TemporaryDirectory()as temp:
            tool=self.setup_tool(Path(temp),runner);a=tool.search('synthetic topic');b=tool.search('synthetic topic')
            self.assertEqual(len(calls),1);self.assertFalse(a['cache']['cache_hit']);self.assertTrue(b['cache']['cache_hit'])
            self.assertIn('--disable-sources',calls[0]);self.assertEqual(calls[0][calls[0].index('--source')+1],'pubmed')
            p=next((Path(temp)/'cache').glob('*/native.stdout.json'));p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'cached native body'):tool.search('synthetic topic')

    def test_provider_failure_is_not_a_successful_empty_search(self):
        def runner(args,folder):return {'stdout':b'{"error":{"code":"source_unavailable"}}','stderr':b'','exit_code':1,'process_status':'returned'}
        with tempfile.TemporaryDirectory()as temp:
            r=self.setup_tool(Path(temp),runner).search('synthetic topic')
            self.assertEqual(r['status'],'unavailable');self.assertEqual(r['candidates'],[])
            self.assertEqual(r['native_error']['code'],'source_unavailable')

    def test_exit_zero_is_not_sufficient_to_call_a_source_complete(self):
        for complete,rows,expected in [(False,None,'partial'),(False,[],'unavailable'),(True,[],'completed_empty')]:
            with self.subTest(expected=expected),tempfile.TemporaryDirectory()as temp:
                def runner(args,folder):return {'stdout':json.dumps(native_result(complete=complete,rows=rows)).encode(),'stderr':b'','exit_code':0,'process_status':'returned'}
                self.assertEqual(self.setup_tool(Path(temp),runner).search('synthetic')['status'],expected)

    def test_ordinary_biomedical_brackets_colons_and_URL_text_are_delegated(self):
        for query in ('[18F]FDG and tau','HLA-DQB1*06:02','What does [example] mean?','https://example.invalid/ citation text'):
            self.assertEqual(tools.checked_query(query),query)


class FakeTools:
    def __init__(self):self.calls=[]
    def search(self,query):
        event={'cache_hit':False,'cache_key':'synthetic','result_content_sha256':'synthetic',
            'native_process_executions':1,'direct_fetch_invocations':0,'upstream_HTTP_request_count':None}
        self.calls.append(event)
        return {'tool':'search_pubmed','status':'completed','query':query,
            **tools.search_projection(native_result()),'cache':event}
    def get(self,pmid):
        event={'cache_hit':False,'cache_key':'synthetic2','result_content_sha256':'synthetic2',
            'native_process_executions':0,'direct_fetch_invocations':1,'upstream_HTTP_request_count':None}
        self.calls.append(event)
        return {'tool':'get_abstract','status':'completed','pmid':pmid,'identity_resolved':True,
            'record':{'pmid':pmid,'title':'Synthetic','abstract':[{'text':'Source text','locator':'synthetic','section':'Abstract'}]},
            'source_url':'https://example.invalid/synthetic','cache':event}


class FakeClient:
    def __init__(self,actions):self.actions=iter(actions);self.prompts=[];self.schemas=[]
    def generate(self,prompt,schema,policy,audit):
        self.prompts.append(prompt);self.schemas.append(schema)
        return {'status':'completed','output':next(self.actions),'usage':{'completion_tokens':10}}


class AgentTests(unittest.TestCase):
    def test_selective_duplicate_feedback_consumes_step_without_source_execution(self):
        actions=[{'action':'search_pubmed','case_id':'c','query':'synthetic'},
            {'action':'search_pubmed','case_id':'c','query':'synthetic'},
            {'action':'get_abstract','case_id':'c','pmid':'101'},
            {'action':'finish','case_id':'c','ranked_pmids':['101']}]
        model=FakeClient(actions);source=FakeTools()
        with tempfile.TemporaryDirectory()as temp:
            result=agent.run_case({'id':'c','body':'Synthetic','type':'list'},model,source,Path(temp)/'c',duplicate_feedback=True,
                token_counter=lambda *_:{'status':'completed','within_budget':True,'tokenizer_model_service_requests':0})
        self.assertEqual(result['status'],'completed');self.assertEqual(result['model_calls'],4)
        self.assertEqual(len(source.calls),2);self.assertEqual(result['search_queries'],['synthetic'])
        self.assertEqual(len(result['controller_rejections']),1)
        self.assertEqual(result['controller_rejections'][0]['model_step'],2)
        self.assertFalse(result['controller_rejections'][0]['feedback']['executed'])
        self.assertNotIn('controller_feedback',model.prompts[0]);self.assertNotIn('controller_feedback',model.prompts[1])
        self.assertIn('controller_feedback',model.prompts[2])
        self.assertEqual(model.schemas[3]['properties']['action'],{'const':'finish'})

    def test_legacy_and_feedback_inputs_are_identical_before_the_first_error(self):
        actions=[{'action':'search_pubmed','case_id':'c','query':'synthetic'},
            {'action':'search_pubmed','case_id':'c','query':'synthetic'},
            {'action':'finish','case_id':'c','ranked_pmids':['101']}]
        clients=[]
        with tempfile.TemporaryDirectory()as temp:
            for feedback in (False,True):
                model=FakeClient(actions);clients.append(model)
                agent.run_case({'id':'c','body':'Synthetic','type':'list'},model,FakeTools(),Path(temp)/str(feedback),
                    duplicate_feedback=feedback,token_counter=lambda *_:{'status':'completed','within_budget':True,'tokenizer_model_service_requests':0})
        self.assertEqual(clients[0].prompts,clients[1].prompts[:2]);self.assertEqual(clients[0].schemas,clients[1].schemas[:2])

    def test_feedback_never_recovers_scope_budget_or_final_identifier_errors(self):
        base=[{'action':'search_pubmed','case_id':'c','query':'first'}]
        cases=[base+[{'action':'get_abstract','case_id':'c','pmid':'999'}],
            base+[{'action':'finish','case_id':'c','ranked_pmids':['101','101']}],
            base+[{'action':'search_pubmed','case_id':'c','query':'second'},
                  {'action':'search_pubmed','case_id':'c','query':'first'}]]
        for actions in cases:
            with self.subTest(actions=actions),tempfile.TemporaryDirectory()as temp:
                result=agent.run_case({'id':'c','body':'Synthetic','type':'list'},FakeClient(actions),FakeTools(),Path(temp)/'c',
                    duplicate_feedback=True,token_counter=lambda *_:{'status':'completed','within_budget':True,'tokenizer_model_service_requests':0})
            self.assertEqual(result['status'],'invalid_action');self.assertEqual(result['controller_rejections'],[])

    def test_repeated_rejections_cannot_add_a_fifth_model_decision(self):
        actions=[{'action':'search_pubmed','case_id':'c','query':'same'}]*4
        with tempfile.TemporaryDirectory()as temp:
            source=FakeTools();result=agent.run_case({'id':'c','body':'Synthetic','type':'list'},FakeClient(actions),source,Path(temp)/'c',
                duplicate_feedback=True,token_counter=lambda *_:{'status':'completed','within_budget':True,'tokenizer_model_service_requests':0})
        self.assertEqual(result['status'],'invalid_action');self.assertEqual(result['model_calls'],4)
        self.assertEqual(len(result['controller_rejections']),2);self.assertEqual(len(source.calls),1)

    def test_native_guidance_removes_only_query_string_bounds(self):
        original=agent.action_schema('c',search_count=0,get_count=0,candidates=[])
        guidance=agent.native_guidance_schema(original)
        expected=json.loads(json.dumps(original));del expected['anyOf'][1]['properties']['query']['minLength'];del expected['anyOf'][1]['properties']['query']['maxLength']
        self.assertEqual(guidance,expected)
        self.assertEqual(original['anyOf'][1]['properties']['query']['maxLength'],2000)
        self.assertEqual(guidance['anyOf'][0]['properties']['ranked_pmids']['maxItems'],0)
        final=agent.action_schema('c',search_count=2,get_count=1,candidates=['101'],final_only=True)
        self.assertEqual(agent.native_guidance_schema(final),final)

    def test_complete_controller_still_rejects_query_and_final_bounds(self):
        ids={str(101+n):{}for n in range(11)}
        for value in ('','   ','x'*2001):
            with self.subTest(query_length=len(value)),self.assertRaises(ValueError):
                agent.checked_action({'action':'search_pubmed','case_id':'c','query':value},'c',[],[],ids)
        for value in (['101','101'],list(ids),['999']):
            with self.subTest(final=value),self.assertRaises(ValueError):
                agent.checked_action({'action':'finish','case_id':'c','ranked_pmids':value},'c',[],[],ids)
        class GuardedTools(FakeTools):
            def search(self,query):raise AssertionError('invalid model query reached a source tool')
        with tempfile.TemporaryDirectory()as temp:
            result=agent.run_case({'id':'c','body':'Synthetic','type':'list'},FakeClient([
                {'action':'search_pubmed','case_id':'c','query':' '}]),GuardedTools(),Path(temp)/'c',
                token_counter=lambda *_:{'status':'completed','within_budget':True,'tokenizer_model_service_requests':0})
        self.assertEqual(result['status'],'invalid_action');self.assertEqual(result['search_queries'],[])

    def test_malformed_abstract_identifier_is_retained_without_tool_execution(self):
        class GuardedTools(FakeTools):
            def get(self,pmid):raise AssertionError('malformed ID reached the abstract tool')
        for malformed in ([],{}):
            with self.subTest(malformed=malformed),tempfile.TemporaryDirectory()as temp:
                result=agent.run_case({'id':'c','body':'Synthetic','type':'list'},FakeClient([
                    {'action':'search_pubmed','case_id':'c','query':'synthetic'},
                    {'action':'get_abstract','case_id':'c','pmid':malformed}]),GuardedTools(),Path(temp)/'c',
                    token_counter=lambda *_:{'status':'completed','within_budget':True,'tokenizer_model_service_requests':0})
            self.assertEqual(result['status'],'invalid_action');self.assertEqual(result['abstract_get_requested_pmids'],[])
            self.assertEqual(result['model_calls'],2)

    def test_same_actions_budget_and_sources_only_skill_differs(self):
        case={'id':'case1','body':'Which synthetic papers?','type':'factoid'}
        actions=[{'action':'search_pubmed','case_id':'case1','query':'synthetic topic'},
                 {'action':'get_abstract','case_id':'case1','pmid':'101'},
                 {'action':'finish','case_id':'case1','ranked_pmids':['101']}]
        clients=[]
        with tempfile.TemporaryDirectory()as temp:
            for skill in (False,True):
                client=FakeClient(actions);clients.append(client)
                r=agent.run_case(case,client,FakeTools(),Path(temp)/str(skill),skill=skill,
                    token_counter=lambda *_:{'status':'completed','within_budget':True,'tokenizer_model_service_requests':0})
                self.assertEqual(r['status'],'completed');self.assertEqual(r['ranked_pmids'],['101']);self.assertEqual(r['model_calls'],3)
                self.assertEqual(r['abstracts_identity_resolved'],['101'])
        for a,b in zip(clients[0].prompts,clients[1].prompts):self.assertEqual(a,b.replace('\n\n'+SKILL,''))

    def test_final_identifiers_and_abstract_access_must_come_from_candidates(self):
        for value in ({'action':'finish','case_id':'c','ranked_pmids':['999']},
                      {'action':'get_abstract','case_id':'c','pmid':'999'},
                      {'action':'finish','case_id':'c','ranked_pmids':['101','101']}):
            with self.assertRaises(ValueError):agent.checked_action(value,'c',[],[],{'101':{}},final_only=False)

    def test_context_unavailable_prevents_inference_and_preserves_case(self):
        client=FakeClient([])
        with tempfile.TemporaryDirectory()as temp:
            r=agent.run_case({'id':'c','body':'Synthetic','type':'list'},client,FakeTools(),Path(temp)/'c',
                token_counter=lambda *_:{'status':'unavailable','within_budget':False,'tokenizer_model_service_requests':1})
        self.assertEqual(r['status'],'context_unavailable');self.assertEqual(r['model_calls'],0);self.assertEqual(client.prompts,[])

    def test_direct_unsupported_query_retains_an_explicit_case(self):
        class Unsupported(FakeTools):
            def search(self,query):raise tools.SourceInputError('synthetic unsupported query')
        with tempfile.TemporaryDirectory()as temp:
            r=agent.direct_case({'id':'c','body':'Synthetic','type':'list'},Unsupported(),Path(temp)/'c')
        self.assertEqual(r['status'],'unsupported_query');self.assertEqual(r['ranked_pmids'],[])
        self.assertEqual(r['tool_events'][0]['native_process_executions'],0)

    def test_tokenizer_uses_exact_existing_transport_messages(self):
        captured={}
        def generate(payload):
            captured['generation']=payload
            return {'choices':[{'message':{'content':'{"action":"finish"}'}}]}
        client=JSONModelClient(role='verifier',provider='api',model=agent.MODEL,endpoint='http://127.0.0.1:8011/v1/chat/completions',api='nim_chat',transport=generate)
        client.prompt_profile='nemotron_nano_v1';client.max_output_tokens=1200
        class Opener:
            def open(self,request,timeout):
                captured['tokenizer']=json.loads(request.data)
                return io.BytesIO(b'{"count":50,"max_model_len":16384,"tokens":[]}')
        prompt='Policy\nUntrusted input data:\n{"question":"synthetic"}'
        with patch.object(agent,'build_opener',return_value=Opener()):r=agent.count_prompt(client,prompt)
        client.generate(prompt,{'type':'object'},'synthetic')
        self.assertTrue(r['within_budget']);self.assertEqual(captured['tokenizer']['messages'],captured['generation']['messages'])
        self.assertEqual(r['conservative_context_cap'],8192)

    def test_abstract_truncation_and_not_opened_search_state_are_explicit(self):
        result=FakeTools().get('101');result['record']['abstract'][0]['text']='x'*13000
        small=agent.model_projection(result)
        self.assertTrue(small['abstract_truncated']);self.assertEqual(len(small['abstract'][0]['text']),12000)
        search=agent.model_projection(FakeTools().search('synthetic'))
        self.assertEqual(search['candidates'][0]['abstract_status'],'not_opened_in_this_search_tool')


if __name__=='__main__':unittest.main()
