"""Matched bounded source-search agents using the existing JSONModelClient.

No reference-document or answer reader is imported here. Both model conditions
share tools, budgets, schema and base policy; only the attributed skill differs.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlsplit,urlunsplit
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import URLError,HTTPError

from biograph_steward.client import digest,utcnow,write_json
from biograph_steward.file_utils import sha
from biograph_steward.model_transport import JSONModelClient,_NoRedirect
from .policy import BASE_POLICY,SKILL,MODEL,MAX_CALLS,MAX_OUTPUT_TOKENS
from .prepare import need,seal,load_frame
from .tools import SourceTools,SourceInputError,checked_query,PMID

FORMAT='biograph-steward.source-search-agent.v1'
CONTEXT_CAP=8192
GUIDANCE_POLICY={'version':2,'removed_from_native_guidance':['search_pubmed.query.minLength','search_pubmed.query.maxLength'],
    'acceptance':'The unchanged checked_query/checked_action controller enforces nonblank, at-most2000-character queries, IDs, shapes and budgets before tool execution.',
    'retained_native_guidance':'Object shape, action/case/PMID constants and enums, and all array limits.'}
DUPLICATE_FEEDBACK_POLICY={'version':1,'recoverable':'Only an exact literal duplicate of an already executed search.',
    'executed':False,'new_source_or_cache_invocations':0,'model_step_consumed':True,
    'all_other_invalid_actions':'Terminal; no additional advice, fallback or normalization.',
    'fourth_call':'Finish only, unchanged.',
    'feedback_message':'The exact search query was already executed; duplicate source execution was blocked.'}


class DuplicateSearchError(ValueError):
    """Selective read-only business validation, not a source/runtime failure."""


def duplicate_observation():
    return {'isError':True,'executed':False,'error_code':'duplicate_search',
        'content':[{'type':'text','text':DUPLICATE_FEEDBACK_POLICY['feedback_message']}]}


def model_projection(result):
    """A declared compact projection, with complete source bodies kept in cache."""
    base={k:result[k]for k in ('tool','status','query','pmid')if k in result}
    base['full_capture_content_sha256']=result.get('cache',{}).get('result_content_sha256')
    if result['tool']=='search_pubmed':
        rows=[]
        for row in result['candidates']:
            title=row.get('title')
            rows.append({'pmid':row['pmid'],'title':title[:400]if isinstance(title,str)else None,
                'title_truncated':isinstance(title,str)and len(title)>400,'date':row.get('date'),'source':row.get('source'),
                'abstract_status':'not_opened_in_this_search_tool'})
        meta=result.get('native_metadata',{})
        base.update(candidates=rows,native_complete=meta.get('complete'),source_plan=meta.get('source_plan'),
            pagination=meta.get('pagination'),native_error=result.get('native_error'),
            warnings=meta.get('_meta',{}).get('warnings')if isinstance(meta.get('_meta'),dict)else None,
            projection='PMID/title/date/source and availability only. Detailed native ranking/query/diagnostics remain in the pinned capture; omitted fields are not asserted absent.')
    else:
        record=result.get('record');base['identity_resolved']=result.get('identity_resolved',False)
        if record:
            remaining=12000;passages=[];truncated=False
            for passage in record['abstract']:
                text=passage['text'];take=text[:remaining];remaining-=len(take)
                if len(take)<len(text):truncated=True
                if take:passages.append({**passage,'text':take,'text_truncated':len(take)<len(text)})
            base.update(title=record['title'],abstract=passages,abstract_truncated=truncated,
                abstract_character_limit=12000,source_url=result['source_url'],doi=record.get('doi'),
                publication_types=record.get('publication_types'),correction_types=record.get('correction_types'),
                projection='Selected exact PubMed title/abstract spans. Any truncation is explicit; complete XML remains in the pinned capture.')
        else:base['record']=None
    return base


def count_prompt(client,prompt):
    """Installed vLLM0.8.5 chat tokenizer; no inference or new model load."""
    need(client.loopback,'this experiment uses only the existing locally forwarded model.')
    need(client.prompt_profile=='nemotron_nano_v1'and client.api=='nim_chat',
         'tokenize the exact qualified Nano message transform, not another transport profile.')
    parsed=urlsplit(client.endpoint);endpoint=urlunsplit((parsed.scheme,parsed.netloc,'/tokenize','',''))
    payload={'model':MODEL,'messages':[{'role':'system','content':'detailed thinking off'},
        {'role':'user','content':prompt}],'add_generation_prompt':True,'add_special_tokens':False}
    headers={'Content-Type':'application/json'}
    if client.key:headers['Authorization']='Bearer '+client.key
    request=Request(endpoint,data=json.dumps(payload,ensure_ascii=True).encode(),headers=headers)
    started=time.perf_counter()
    try:
        with build_opener(_NoRedirect(),ProxyHandler({})).open(request,timeout=20)as response:raw=response.read(500001)
        need(len(raw)<=500000,'tokenizer response exceeds bound.');v=json.loads(raw)
        need(type(v.get('count'))is int and v['count']>=0 and type(v.get('max_model_len'))is int,'invalid tokenizer count.')
        return {'status':'completed','prompt_tokens':v['count'],'native_max_model_len':v['max_model_len'],
            'conservative_context_cap':CONTEXT_CAP,'reserved_output_tokens':MAX_OUTPUT_TOKENS,
            'within_budget':v['count']+MAX_OUTPUT_TOKENS<=min(CONTEXT_CAP,v['max_model_len']),
            'tokenizer_model_service_requests':1,'inference_calls':0,'request_sha256':digest(payload),
            'latency_ms':round((time.perf_counter()-started)*1000,3),
            'source':'https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/entrypoints/openai/protocol.py'}
    except (HTTPError,URLError,OSError,ValueError,TypeError)as error:
        return {'status':'unavailable','error_type':type(error).__name__,'within_budget':False,
            'tokenizer_model_service_requests':1,'inference_calls':0}


def action_schema(case_id,*,search_count,get_count,candidates,final_only=False):
    ids=sorted(set(candidates),key=int)
    final={'type':'object','additionalProperties':False,'properties':{'action':{'const':'finish'},
        'case_id':{'const':case_id},'ranked_pmids':{'type':'array','minItems':0,'maxItems':min(10,len(ids)),
            'items':{'type':'string','enum':ids}if ids else {'type':'string'}}},
        'required':['action','case_id','ranked_pmids']}
    branches=[final]
    if not final_only and search_count<2:
        branches.append({'type':'object','additionalProperties':False,'properties':{'action':{'const':'search_pubmed'},
            'case_id':{'const':case_id},'query':{'type':'string','minLength':1,'maxLength':2000}},
            'required':['action','case_id','query']})
    if not final_only and get_count<1 and ids:
        branches.append({'type':'object','additionalProperties':False,'properties':{'action':{'const':'get_abstract'},
            'case_id':{'const':case_id},'pmid':{'type':'string','enum':ids}},'required':['action','case_id','pmid']})
    return {'anyOf':branches}if len(branches)>1 else final


def checked_action(value,case_id,searches,opened,candidates,*,final_only=False):
    need(isinstance(value,dict)and value.get('case_id')==case_id,'model case identity differs.')
    action=value.get('action')
    if action=='finish':
        need(set(value)=={'action','case_id','ranked_pmids'},'invalid final shape.')
        ids=value['ranked_pmids']
        need(isinstance(ids,list)and len(ids)<=10 and all(isinstance(p,str)and PMID.fullmatch(p)for p in ids)
             and len(ids)==len(set(ids))and set(ids)<=set(candidates),'final list contains unsupported/duplicate IDs.')
        return value
    need(not final_only,'the final model call must finish.')
    if action=='search_pubmed':
        need(set(value)=={'action','case_id','query'}and len(searches)<2,'invalid or over-budget search.')
        checked_query(value['query'])
        if value['query']in searches:raise DuplicateSearchError('Source search: duplicate search is not permitted.')
    elif action=='get_abstract':
        need(set(value)=={'action','case_id','pmid'}and not opened and value['pmid']in candidates,
             'abstract access is outside the returned candidate frame or budget.')
    else:raise ValueError('Source search: unknown action.')
    return value


def native_guidance_schema(acceptance_schema):
    """Avoid the verified large bounded-string native index workload only.

    This does not broaden accepted actions. The existing complete controller
    still validates each generated value before invoking any source tool.
    """
    guidance=deepcopy(acceptance_schema)
    for branch in guidance.get('anyOf',[guidance]):
        properties=branch.get('properties',{})
        if properties.get('action',{}).get('const')=='search_pubmed':
            query=properties['query'];query.pop('minLength',None);query.pop('maxLength',None)
    return guidance


def run_case(case,client,tools,output,*,skill=False,token_counter=None,duplicate_feedback=False):
    need(set(case)=={'id','body','type'},'only projected question fields may enter the agent.')
    need(type(duplicate_feedback)is bool,'duplicate feedback must be an explicit boolean.')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    searches=[];opened=[];candidates={};history=[];dialogue=[];rejections=[];traces=[];final=None;status='budget_exhausted'
    tool_offset=len(tools.calls);started=time.perf_counter();tokenizations=[];token_counter=token_counter or count_prompt
    for step in range(MAX_CALLS):
        prompt_history=[({'action':h['action'],'tool_result':model_projection(h['tool_result'])}
            if 'action'in h else h)for h in dialogue]
        data={'case_id':case['id'],'question':case['body'],'question_type':case['type'],'history':prompt_history,
            'remaining_searches':2-len(searches),'remaining_abstract_gets':1-len(opened),
            'remaining_model_calls':MAX_CALLS-step,'final_list_required_now':step==MAX_CALLS-1}
        guidance=BASE_POLICY+('\n\n'+SKILL if skill else '')
        prompt=guidance+'\nUntrusted input data:\n'+json.dumps(data,ensure_ascii=True)
        acceptance_schema=action_schema(case['id'],search_count=len(searches),get_count=len(opened),candidates=candidates,final_only=step==MAX_CALLS-1)
        schema=native_guidance_schema(acceptance_schema)
        budget=token_counter(client,prompt);tokenizations.append(budget);write_json(output/f'tokenization_{step+1}.json',budget)
        if budget.get('status')!='completed' or not budget.get('within_budget'):
            status='context_unavailable'if budget.get('status')!='completed'else 'context_budget_exceeded';break
        write_json(output/f'request_intent_{step+1}.json',{'created_at':utcnow(),'case_id':case['id'],
            'prompt_sha256':digest(prompt),'schema_sha256':digest(schema),
            'full_controller_acceptance_schema_sha256':digest(acceptance_schema),'native_guidance_policy':GUIDANCE_POLICY,
            'max_output_tokens':MAX_OUTPUT_TOKENS})
        trace=client.generate(prompt,schema,'biograph_source_search_v1',audit={'case_id':case['id'],'step':step+1,
            'procedure_skill':skill,'arbitrary_tools':False,'reference_labels_available':False,
            'full_controller_acceptance_schema_sha256':digest(acceptance_schema),'native_guidance_policy':GUIDANCE_POLICY})
        write_json(output/f'model_call_{step+1}.json',trace);traces.append(trace)
        if trace.get('status')!='completed':status=trace.get('status','model_error');break
        try:action=checked_action(trace.get('output'),case['id'],searches,opened,candidates,final_only=step==MAX_CALLS-1)
        except DuplicateSearchError as exc:
            if duplicate_feedback and step<MAX_CALLS-1:
                observation=duplicate_observation()
                rejected={'model_step':step+1,'action':trace['output'],'feedback':observation}
                rejections.append(rejected);write_json(output/f'controller_feedback_{step+1}.json',rejected)
                dialogue.append({'rejected_action':trace['output'],'controller_feedback':observation})
                continue
            status='invalid_action';history.append({'controller_error':str(exc)});break
        except (ValueError,TypeError) as exc:
            status='invalid_action';history.append({'controller_error':str(exc)});break
        if action['action']=='finish':final=action;status='completed';break
        if action['action']=='search_pubmed':
            searches.append(action['query']);result=tools.search(action['query'])
            for candidate in result['candidates']:candidates[candidate['pmid']]=candidate
        else:
            opened.append(action['pmid']);result=tools.get(action['pmid'])
        event={'action':action,'tool_result':result};history.append(event);dialogue.append(event)
        write_json(output/f'tool_result_{len(history)}.json',result)
    events=tools.calls[tool_offset:]
    result=seal({'format':FORMAT,'case_id':case['id'],'status':status,'ranked_pmids':final['ranked_pmids']if final else [],
        'candidate_pmids':list(candidates),'abstract_get_requested_pmids':opened,
        'abstracts_identity_resolved':[h['tool_result']['pmid']for h in history if h.get('action',{}).get('action')=='get_abstract'and h['tool_result'].get('identity_resolved')],
        'search_queries':searches,'model_calls':len(traces),'procedure_skill':skill,'tool_events':events,
        'model_usage':[t.get('usage')for t in traces],'model_statuses':[t.get('status')for t in traces],
        'tokenizations':tokenizations,'tokenizer_model_service_requests':sum(t['tokenizer_model_service_requests']for t in tokenizations),
        'elapsed_seconds':time.perf_counter()-started,'history':history,
        'duplicate_feedback_enabled':duplicate_feedback,'controller_rejections':rejections,
        'no_reference_labels_read':True,'biological_truth_or_entailment_measured':False,'live_graph_changes':0,
        'files':{p.name:sha(p)for p in output.iterdir()if p.is_file()}})
    write_json(output/'result.json',result);return result


def direct_case(case,tools,output):
    need(set(case)=={'id','body','type'},'only projected question fields may enter direct search.')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    # Reuse native full-question cleanup/ranking; no custom keyword algorithm.
    query=' '.join(case['body'].split())
    try:value=tools.search(query)
    except SourceInputError as error:
        value={'tool':'search_pubmed','status':'unsupported_query','query':query,'candidates':[],
            'error_type':type(error).__name__,'reason':str(error),
            'cache':{'tool':'search_pubmed','cache_hit':False,'native_process_executions':0,
                'direct_fetch_invocations':0,'upstream_HTTP_request_count':None}}
    write_json(output/'tool_result.json',value)
    result=seal({'format':FORMAT,'case_id':case['id'],'status':value['status'],
        'ranked_pmids':[r['pmid']for r in value['candidates']],'candidate_pmids':[r['pmid']for r in value['candidates']],
        'search_queries':[' '.join(case['body'].split())],'direct_query_normalization':'Whitespace collapse only; native provider question cleanup unchanged.',
        'abstract_get_requested_pmids':[],'abstracts_identity_resolved':[],
        'model_calls':0,'procedure_skill':False,'model_usage':[],'tool_events':[value['cache']],
        'source_result_status':value['status'],'no_reference_labels_read':True,'biological_truth_or_entailment_measured':False,
        'files':{'tool_result.json':sha(output/'tool_result.json')}})
    write_json(output/'result.json',result);return result


def run(frozen,protocol_sha256,output,*,cache,mode,endpoint='http://127.0.0.1:8011/v1/chat/completions',client=None):
    if mode=='all':return run_all(frozen,protocol_sha256,output,cache=cache,endpoint=endpoint,client=client)
    need(mode in {'direct_native_query','unskilled_agent','procedure_skill_agent'},'unknown fixed arm.')
    protocol,cases=load_frame(frozen,protocol_sha256);output=Path(output);need(not output.exists(),'choose a new execution output.')
    feedback=protocol.get('duplicate_feedback',False);need(type(feedback)is bool,'invalid frozen duplicate-feedback flag.')
    binary=protocol['binary_qualification'];tools=SourceTools(binary['file'],binary['sha256'],cache)
    if mode!='direct_native_query'and client is None:
        client=JSONModelClient(role='verifier',provider='api',model=MODEL,endpoint=endpoint,api='nim_chat')
        client.prompt_profile='nemotron_nano_v1';client.max_output_tokens=MAX_OUTPUT_TOKENS;client.timeout=120
    output.mkdir(parents=True)
    header={'format':FORMAT+'.execution','created_at':utcnow(),'status':'running','mode':mode,
        'protocol_file_sha256':protocol_sha256,'protocol_content_sha256':protocol['content_sha256'],
        'model':MODEL if client else None,'endpoint':endpoint if client else None,'model_calls_per_case_cap':MAX_CALLS if client else 0,
        'token_cap_per_call':MAX_OUTPUT_TOKENS if client else 0,'schema_api':'existing nim_chat guided_json',
        'question_count':len(cases),'reference_labels_opened':False,'app_graph_changes':False}
    write_json(output/'execution.json',header);results=[]
    for case in cases:
        case_output=output/case['id']
        result=direct_case(case,tools,case_output)if mode=='direct_native_query'else run_case(case,client,tools,case_output,skill=mode=='procedure_skill_agent',duplicate_feedback=feedback)
        results.append(result);write_json(output/'results.partial.json',results)
        print(json.dumps({'completed':len(results),'total':len(cases),'status':result['status'],'model_calls':result['model_calls']}),flush=True)
    load_frame(frozen,protocol_sha256)
    write_json(output/'results.json',results)
    report=seal({**header,'status':'completed','completed_cases':len(results),'results_sha256':sha(output/'results.json'),
        'model_calls':sum(r['model_calls']for r in results),'statuses':dict(Counter(r['status']for r in results)),
        'model_usage':[u for r in results for u in r['model_usage']],
        'native_process_executions':sum(e['native_process_executions']for e in tools.calls),
        'direct_fetch_invocations':sum(e['direct_fetch_invocations']for e in tools.calls),'cache_hits':sum(e['cache_hit']for e in tools.calls),
        'exact_upstream_HTTP_request_count':None,'no_transport_retries_or_hidden_model_calls':True,
        'duplicate_feedback_enabled':feedback,'duplicate_feedback_observations':sum(len(r.get('controller_rejections',[]))for r in results)})
    write_json(output/'execution.json',report);return report


def run_all(frozen,protocol_sha256,output,*,cache,endpoint,client=None):
    """Question-blocked matched comparison; no gold/reference reader exists here."""
    protocol,cases=load_frame(frozen,protocol_sha256);output=Path(output);need(not output.exists(),'choose a new blocked-comparison output.')
    feedback=protocol.get('duplicate_feedback',False);need(type(feedback)is bool,'invalid frozen duplicate-feedback flag.')
    b=protocol['binary_qualification'];tools=SourceTools(b['file'],b['sha256'],cache)
    if client is None:
        client=JSONModelClient(role='verifier',provider='api',model=MODEL,endpoint=endpoint,api='nim_chat')
        client.prompt_profile='nemotron_nano_v1';client.max_output_tokens=MAX_OUTPUT_TOKENS;client.timeout=120
    names=('direct_native_query','unskilled_agent','procedure_skill_agent');output.mkdir(parents=True)
    first=set(r['id']for r in sorted(cases,key=lambda r:hashlib.sha256(('source-search-arm-order-v1|'+r['id']).encode()).hexdigest())[:12])
    results={name:[]for name in names}
    header={'format':FORMAT+'.blocked-execution','created_at':utcnow(),'status':'running','mode':'all',
        'protocol_file_sha256':protocol_sha256,'protocol_content_sha256':protocol['content_sha256'],
        'model':MODEL,'endpoint':endpoint,'question_count':len(cases),'reference_labels_opened':False,
        'counterbalance':'12 unskilled-first and12 skill-first by fixed salted-SHA metadata order',
        'unskilled_first_case_ids':sorted(first),'model_generation_request_cap':192,'maximum_output_tokens':230400,
        'direct_control':'One native full-question PubMed query, whitespace collapse only; cost is reported separately.',
        'duplicate_feedback_enabled':feedback,'controller_feedback_policy':DUPLICATE_FEEDBACK_POLICY if feedback else None,
        'source_cache':'All conditions share immutable query/binary/adapter-bound captures; no provider retry is invented by this controller.'}
    write_json(output/'execution.json',header)
    for name in names:(output/name).mkdir()
    for i,case in enumerate(cases,1):
        results['direct_native_query'].append(direct_case(case,tools,output/'direct_native_query'/case['id']))
        order=('unskilled_agent','procedure_skill_agent')if case['id']in first else ('procedure_skill_agent','unskilled_agent')
        for name in order:
            r=run_case(case,client,tools,output/name/case['id'],skill=name=='procedure_skill_agent',duplicate_feedback=feedback);results[name].append(r)
        for name in names:write_json(output/name/'results.partial.json',results[name])
        print(json.dumps({'completed_question_blocks':i,'total':len(cases),'latest_statuses':{name:results[name][-1]['status']for name in names}}),flush=True)
    load_frame(frozen,protocol_sha256)
    arm_reports={}
    for name in names:
        path=output/name/'results.json';write_json(path,results[name]);events=[e for r in results[name]for e in r['tool_events']]
        report=seal({'format':FORMAT+'.execution','created_at':utcnow(),'status':'completed','mode':name,
            'protocol_file_sha256':protocol_sha256,'protocol_content_sha256':protocol['content_sha256'],
            'completed_cases':len(results[name]),'question_count':len(cases),'results_sha256':sha(path),
            'model_calls':sum(r['model_calls']for r in results[name]),'statuses':dict(Counter(r['status']for r in results[name])),
            'model_usage':[u for r in results[name]for u in r['model_usage']],
            'tokenizer_model_service_requests':sum(r.get('tokenizer_model_service_requests',0)for r in results[name]),
            'native_process_executions':sum(e['native_process_executions']for e in events),
            'direct_fetch_invocations':sum(e['direct_fetch_invocations']for e in events),'cache_hits':sum(e['cache_hit']for e in events),
            'exact_upstream_HTTP_request_count':None,'no_transport_retries_or_hidden_model_calls':True,
            'duplicate_feedback_enabled':feedback,'duplicate_feedback_observations':sum(len(r.get('controller_rejections',[]))for r in results[name]),
            'reference_labels_opened':False})
        write_json(output/name/'execution.json',report)
        arm_reports[name]={'file':str((output/name/'execution.json').resolve()),'sha256':sha(output/name/'execution.json'),'content_sha256':report['content_sha256']}
    report=seal({**header,'status':'completed','completed_cases':len(cases),'arms':arm_reports,
        'model_calls':sum(r['model_calls']for name in names for r in results[name]),
        'no_reference_labels_read':True,'app_graph_changes':False})
    write_json(output/'execution.json',report);return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('frozen','protocol-sha256','output','cache','mode'):p.add_argument('--'+name,required=True)
    p.add_argument('--endpoint',default='http://127.0.0.1:8011/v1/chat/completions')
    r=run(**vars(p.parse_args()));print(json.dumps({k:r[k]for k in ('status','mode','completed_cases','model_calls','content_sha256')},indent=2))
