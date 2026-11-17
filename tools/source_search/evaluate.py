"""Seal all fixed retrieval outputs before exact-scope reference-document access.

Only selected BioASQ document URLs are interpreted after the durable release
event. Exact/ideal answers and snippets are not assessment inputs. This is a
positive document-reference retrieval measurement, not a truth or entailment
classifier. It uses ordinary Recall@10 and paired question resampling.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import random
import re
import statistics
from urllib.parse import urlsplit

from biograph_steward.client import digest,utcnow,write_json
from biograph_steward.file_utils import sha
from .prepare import load_frame,need,seal,read_sealed,projected_questions
from .tools import PMID
from .agent import (action_schema,native_guidance_schema,GUIDANCE_POLICY,checked_action,
    DuplicateSearchError,duplicate_observation,DUPLICATE_FEEDBACK_POLICY)

ARMS=('direct_native_query','unskilled_agent','procedure_skill_agent')
POLICY={'cutoff':10,'primary':['procedure_skill_agent','unskilled_agent'],
 'metric':'Mean question-level reference-document Recall@10; each of the24 questions has equal weight.',
 'secondary':['reference_hit_at_10','candidate_ID_provenance','resolved_exact_get_IDs','source_and_model_failures','costs'],
 'missing_system_output':'Empty retrieval, retaining the original question denominator; not a biological false label.',
 'empty_reference':'Unscorable reference retained explicitly; primary comparison unavailable rather than inventing a zero denominator.',
 'bootstrap':{'draws':2000,'seed':20261114,'unit':'question','shared_draws':True,
  'percentiles':'Python statistics.quantiles(n=40,method=inclusive):2.5% and97.5%'},
 'gold_fields':['documents for exact selected question IDs only'],
 'not_measured':['biological truth','source entailment','official BioASQ leaderboard','model-unseen generalization'],
 'duplicate_feedback':'When separately frozen enabled, only literal duplicate executed-search rejections become executed:false observations. Four model calls and actual source budgets remain unchanged; all other errors terminal.',
 'raw_cases_in_aggregate':False}


def freeze_policy(frozen,protocol_sha256,output):
    protocol,_=load_frame(frozen,protocol_sha256);output=Path(output)
    need(not output.exists(),'choose a new evaluation-policy file.')
    value=seal({'format':'biograph-steward.source-search-evaluation-policy.v1','created_at':utcnow(),
        'producer_protocol_file_sha256':protocol_sha256,'producer_protocol_content_sha256':protocol['content_sha256'],
        'arms':list(ARMS),'policy':POLICY,'implementation_sha256':sha(__file__),
        'frozen_producer_implementation_files':protocol['files'],
        'duplicate_feedback_enabled':protocol.get('duplicate_feedback',False),
        'controller_feedback_policy':DUPLICATE_FEEDBACK_POLICY if protocol.get('duplicate_feedback',False)else None,
        'reference_document_values_opened':False})
    write_json(output,value);return value


def verify_policy(path,expected,protocol_sha256):
    value=read_sealed(path,expected)
    need(value['format']=='biograph-steward.source-search-evaluation-policy.v1'
         and value['producer_protocol_file_sha256']==protocol_sha256 and value['policy']==POLICY
         and value['arms']==list(ARMS)and value['implementation_sha256']==sha(__file__),
         'evaluation method/source changed.')
    return value


def ordinary_file(path,expected):
    p=Path(path);need(p.is_file()and not p.is_symlink()and sha(p)==expected,'pinned result/source file differs.')


def verify_request_guidance(row,traces,intents):
    """Reconstruct action-state schemas without any reference values."""
    need(len(traces)==len(intents)==row['model_calls'],'request state inventory differs.')
    history=[h for h in row.get('history',[])if 'action'in h]
    rejected=row.get('controller_rejections',[])
    need(isinstance(rejected,list),'invalid controller-rejection inventory.')
    by_step={r['model_step']:r for r in rejected}
    need(len(by_step)==len(rejected)and all(type(k)is int and 1<=k<=len(traces)for k in by_step),
         'controller-rejection step is duplicate/outside its trace frame.')
    candidates={};searches=[];opened=[];history_index=0
    for step,(trace,intent)in enumerate(zip(traces,intents)):
        accepted=action_schema(row['case_id'],search_count=len(searches),get_count=len(opened),
            candidates=candidates,final_only=step==3)
        guidance=native_guidance_schema(accepted)
        need(trace['schema_sha256']==intent['schema_sha256']==digest(guidance)
             and trace['full_controller_acceptance_schema_sha256']==intent['full_controller_acceptance_schema_sha256']==digest(accepted)
             and trace['native_guidance_policy']==intent['native_guidance_policy']==GUIDANCE_POLICY,
             'native guidance/full controller acceptance or action state differs.')
        if step+1 in by_step:
            r=by_step[step+1]
            need(row.get('duplicate_feedback_enabled')is True and step<3
                 and trace['status']=='completed'and r['action']==trace['output']
                 and r['feedback']==duplicate_observation(),'unqualified recoverable controller event.')
            try:checked_action(r['action'],row['case_id'],searches,opened,candidates,final_only=step==3)
            except DuplicateSearchError:pass
            except (ValueError,TypeError):raise ValueError('Source search: only a typed duplicate search can receive feedback.')from None
            else:raise ValueError('Source search: feedback action was not a duplicate rejection.')
            continue
        if history_index<len(history):
            h=history[history_index];history_index+=1
            action=h['action'];need(action==trace['output'],'tool action differs from its generated value.')
            need(action.get('action')in {'search_pubmed','get_abstract'},'executed history contains a non-source action.')
            checked_action(action,row['case_id'],searches,opened,candidates,final_only=step==3)
            if action['action']=='search_pubmed':
                searches.append(action['query'])
                for candidate in h['tool_result']['candidates']:candidates[candidate['pmid']]=candidate
            else:opened.append(action['pmid'])
    need(history_index==len(history)and list(candidates)==row['candidate_pmids']
         and searches==row['search_queries']and opened==row['abstract_get_requested_pmids'],
         'saved tool history differs from its candidate/query frame.')
    if row['status']=='completed':
        need(traces and traces[-1]['status']=='completed'and traces[-1]['output']=={
            'action':'finish','case_id':row['case_id'],'ranked_pmids':row['ranked_pmids']},
            'final handoff differs from its last model output.')


def trajectory_summary(rows):
    """Aggregate exercised choices; never disclose article/question identities."""
    orders=Counter();early=second=gets=without_tools=0;resolved=set();rejections=Counter();feedback_cases=0
    for row in rows:
        actions=[h['action']['action']for h in row.get('history',[])if 'action'in h]
        orders[' > '.join(actions)if actions else 'no_source_tool']+=1
        early+=row['status']=='completed'and row['model_calls']<4
        second+=len(row['search_queries'])>=2
        gets+=bool(row['abstract_get_requested_pmids'])
        without_tools+=row['status']=='completed'and not actions
        resolved.update(row['abstracts_identity_resolved'])
        feedback_cases+=bool(row.get('controller_rejections'))
        rejections.update(r['feedback']['error_code']for r in row.get('controller_rejections',[]))
    return {'tool_order_counts':dict(sorted(orders.items())),'early_finish_cases_before_four_calls':early,
        'completed_without_source_tool_cases':without_tools,'cases_using_second_search':second,
        'cases_requesting_abstract':gets,'distinct_successfully_opened_article_ID_count':len(resolved),
        'cases_with_controller_feedback':feedback_cases,'controller_feedback_event_counts':dict(rejections),
        'article_identities_in_aggregate':False,
        'interpretation':'Choice/trajectory variation describes execution, not retrieval benefit or biological correctness.'}


def seal_predictions(frozen,protocol_sha256,execution,execution_sha256,cache,policy,policy_sha256,output):
    protocol,cases=load_frame(frozen,protocol_sha256);verify_policy(policy,policy_sha256,protocol_sha256)
    execution,cache,output=map(Path,(execution,cache,output));need(not output.exists(),'choose a new prediction seal.')
    top=read_sealed(execution/'execution.json',execution_sha256)
    need(top['format']=='biograph-steward.source-search-agent.v1.blocked-execution'and top['status']=='completed'
         and top['mode']=='all'and top['completed_cases']==24 and set(top['arms'])==set(ARMS)
         and top['protocol_file_sha256']==protocol_sha256 and top['reference_labels_opened']is False,
         'all fixed blocked-comparison outputs must finish before reference access.')
    need(top.get('duplicate_feedback_enabled',False)==protocol.get('duplicate_feedback',False),
         'frozen controller feedback condition differs.')
    ids=[c['id']for c in cases];pins={str((execution/'execution.json').resolve()):execution_sha256,
        str(Path(policy).resolve()):policy_sha256};summaries={};all_cache_files={}
    for arm in ARMS:
        spec=top['arms'][arm];arm_path=execution/arm/'execution.json'
        need(Path(spec['file']).resolve()==arm_path.resolve(),'arm file is outside its expected execution folder.')
        report=read_sealed(arm_path,spec['sha256'])
        need(report['content_sha256']==spec['content_sha256']and report['mode']==arm and report['status']=='completed'
             and report['completed_cases']==24 and report['protocol_file_sha256']==protocol_sha256,
             'fixed arm is incomplete or belongs to another frame.')
        results_file=execution/arm/'results.json';ordinary_file(results_file,report['results_sha256'])
        rows=json.loads(results_file.read_text());need([r['case_id']for r in rows]==ids,'arm question frame/order differs.')
        for row in rows:
            need(row['content_sha256']==digest({k:v for k,v in row.items()if k!='content_sha256'}),'case content seal differs.')
            ranked=row['ranked_pmids'];candidate=row['candidate_pmids']
            need(isinstance(ranked,list)and len(ranked)<=10 and len(ranked)==len(set(ranked))
                 and all(isinstance(x,str)and PMID.fullmatch(x)for x in ranked)
                 and set(ranked)<=set(candidate),'output identifier was not an exact returned candidate.')
            need(row['no_reference_labels_read']is True and row['model_calls']<=(0 if arm=='direct_native_query'else 4),
                 'reference/model budget boundary differs.')
            if arm!='direct_native_query':need(row['procedure_skill']==(arm=='procedure_skill_agent'),'skill condition differs.')
            if arm!='direct_native_query':need(row.get('duplicate_feedback_enabled',False)==protocol.get('duplicate_feedback',False),
                 'case feedback condition differs.')
            case_folder=execution/arm/row['case_id']
            for name,expected in row['files'].items():
                need(Path(name).name==name,'case file must be an ordinary immediate name.')
                file=case_folder/name;ordinary_file(file,expected);pins[str(file.resolve())]=expected
            result_file=case_folder/'result.json';ordinary_file(result_file,sha(result_file));pins[str(result_file.resolve())]=sha(result_file)
            need(json.loads(result_file.read_text())==row,'arm case copy differs from its saved result.')
            traces=sorted((p for p in case_folder.glob('model_call_*.json')if p.is_file()),
                key=lambda p:int(p.stem.rsplit('_',1)[1]))
            need(len(traces)==row['model_calls'],'model trace count differs.')
            for trace_path in traces:
                trace=json.loads(trace_path.read_text())
                need(trace['request_settings']['max_output_tokens']==1200 and trace['model_requested']==protocol['model']
                     and trace['execution_guard']['retries']==0 and trace['execution_guard']['repair_calls']==0,
                     'generation settings/retry contract differs.')
            if arm!='direct_native_query':
                intents=[json.loads((case_folder/('request_intent_'+p.stem.rsplit('_',1)[1]+'.json')).read_text())for p in traces]
                verify_request_guidance(row,[json.loads(p.read_text())for p in traces],intents)
                for rejected in row.get('controller_rejections',[]):
                    file=case_folder/('controller_feedback_'+str(rejected['model_step'])+'.json')
                    need(file.name in row['files']and json.loads(file.read_text())==rejected,
                         'controller feedback file differs from its sealed case.')
            actions=[h['action']for h in row.get('history',[])if 'action'in h]
            need(sum(a['action']=='search_pubmed'for a in actions)<=2 and sum(a['action']=='get_abstract'for a in actions)<=1,
                 'source-tool action budget differs.')
            for event in row['tool_events']:
                key=event.get('cache_key')
                if key is None:
                    need(row['status']=='unsupported_query'and event['native_process_executions']==0,'unrecorded source invocation.')
                    continue
                need(re.fullmatch(r'[0-9a-f]{64}',key),'invalid source-cache key.')
                folder=cache/key;cache_file=folder/'result.json';cached=json.loads(cache_file.read_text())
                need(cached.get('content_sha256')==event['result_content_sha256']
                     and cached['content_sha256']==digest({k:v for k,v in cached.items()if k!='content_sha256'})
                     and digest(cached['request'])==key,'source capture differs from the observed model tool result.')
                all_cache_files[str(cache_file.resolve())]=sha(cache_file)
                for name,expected in cached['files'].items():
                    need(Path(name).name==name,'source capture member must be an ordinary immediate name.')
                    file=folder/name;ordinary_file(file,expected);all_cache_files[str(file.resolve())]=expected
        pins[str(arm_path.resolve())]=spec['sha256'];pins[str(results_file.resolve())]=report['results_sha256']
        summaries[arm]={'execution_content_sha256':report['content_sha256'],'cases':24,'results_file_sha256':report['results_sha256'],
            'model_calls':report['model_calls'],'statuses':report['statuses']}
    need(sum(s['model_calls']for s in summaries.values())<=192,'blocked generation budget exceeded.')
    pins.update(all_cache_files)
    value=seal({'format':'biograph-steward.source-search-prediction-seal.v1','created_at':utcnow(),
        'protocol_file_sha256':protocol_sha256,'execution_file_sha256':execution_sha256,'execution':str(execution.resolve()),
        'policy_file_sha256':policy_sha256,'evaluation_policy':POLICY,'arm_summaries':summaries,
        'input_files_sha256':pins,'reference_document_values_opened':False,'question_count':24})
    write_json(output,value);return value


def reference_pmid(value):
    need(isinstance(value,str),'reference document is not a string URL.')
    url=urlsplit(value)
    need(url.scheme in {'http','https'}and not url.query and not url.fragment
         and url.username is None and url.password is None,'unsupported reference document URL.')
    match=None
    if url.hostname in {'www.ncbi.nlm.nih.gov','ncbi.nlm.nih.gov'}:match=re.fullmatch(r'/pubmed/([1-9][0-9]{0,9})/?',url.path)
    elif url.hostname=='pubmed.ncbi.nlm.nih.gov':match=re.fullmatch(r'/([1-9][0-9]{0,9})/?',url.path)
    need(match is not None,'reference document is not an admitted PubMed identity.')
    return match.group(1)


def selected_documents(stream,positions,*,parser=None):
    """Interpret document strings only at already fixed selected ordinals."""
    if parser is None:
        import ijson
        need(ijson.__version__=='3.4.0.post0','use the pinned task-local parser.')
        parser=ijson.parse
    index=-1;current=None;out={}
    for prefix,event,value in parser(stream):
        if prefix=='questions.item'and event=='start_map':
            index+=1;current={'id':None,'pmids':[]}if index in positions else None
        elif current is not None:
            if prefix=='questions.item.id'and event=='string':current['id']=value
            elif prefix=='questions.item.documents.item'and event=='string':current['pmids'].append(reference_pmid(value))
            elif prefix=='questions.item'and event=='end_map':
                need(current['id']==positions[index],'reference ordinal/identity binding differs.')
                out[current['id']]=sorted(set(current['pmids']),key=int);current=None
    need(set(out)==set(positions.values()),'selected reference frame is incomplete.')
    return out


def retrieval_metrics(reference,ranked):
    need(len(ranked)<=10 and len(ranked)==len(set(ranked)),'retrieval list is not a unique top10.')
    if not reference:return {'status':'unscorable_reference_empty','recall_at_10':None,'reference_hit_at_10':None}
    overlap=set(reference)&set(ranked)
    return {'status':'scored','reference_documents':len(reference),'matched_reference_documents':len(overlap),
        'returned_documents':len(ranked),'recall_at_10':float(Fraction(len(overlap),len(reference))),
        'reference_hit_at_10':int(bool(overlap))}


def paired_bootstrap(scores,draws=2000,seed=20261114):
    need(draws==2000 and seed==20261114 and set(scores)==set(ARMS),'fixed question bootstrap differs.')
    n=len(scores[ARMS[0]]);need(n==24 and all(len(v)==n for v in scores.values()),'fixed24-question resampling frame differs.')
    rng=random.Random(seed);multiplicities=[];values={name:[]for name in ARMS}
    for _ in range(draws):
        counts=Counter(rng.randrange(n)for _ in range(n));multiplicities.append([counts.get(i,0)for i in range(n)])
        for name,row in scores.items():values[name].append(sum(counts.get(i,0)*row[i]for i in range(n))/n)
    comparisons=[]
    for a,b in [('procedure_skill_agent','unskilled_agent'),('procedure_skill_agent','direct_native_query'),('unskilled_agent','direct_native_query')]:
        delta=[x-y for x,y in zip(values[a],values[b])];cuts=statistics.quantiles(delta,n=40,method='inclusive')
        comparisons.append({'candidate':a,'comparator':b,'observed_mean_difference':statistics.mean(scores[a])-statistics.mean(scores[b]),
            'paired_95_percentile_interval':[cuts[0],cuts[-1]],'fraction_draws_above_zero':sum(x>0 for x in delta)/draws})
    return multiplicities,comparisons


def release_score(frozen,protocol_sha256,prediction_seal,prediction_seal_sha256,policy,policy_sha256,output):
    protocol,cases=load_frame(frozen,protocol_sha256);verify_policy(policy,policy_sha256,protocol_sha256)
    prediction=read_sealed(prediction_seal,prediction_seal_sha256)
    need(prediction['format']=='biograph-steward.source-search-prediction-seal.v1'
         and prediction['protocol_file_sha256']==protocol_sha256 and prediction['policy_file_sha256']==policy_sha256
         and prediction['reference_document_values_opened']is False,'complete reviewed prediction seal required.')
    for path,expected in prediction['input_files_sha256'].items():ordinary_file(path,expected)
    reference=Path(protocol['reference']['file']);ordinary_file(reference,protocol['reference']['sha256'])
    folder=Path(output);folder.mkdir(parents=True,exist_ok=False)
    event=seal({'format':'biograph-steward.source-search-reference-access-event.v1','created_at':utcnow(),
        'protocol_file_sha256':protocol_sha256,'prediction_seal_file_sha256':prediction_seal_sha256,'policy_file_sha256':policy_sha256,
        'reference_source_sha256':protocol['reference']['sha256'],'expected_reference_values_interpreted_before_event':False,
        'permitted_fields':'Only document URLs for the exact24fixedIDs. All answer/snippet fields remain unused.',
        'root_review_required':'Operator must obtain the requested root review before invoking this release step.'})
    write_json(folder/'truth_access_started.json',event)
    chosen={c['id']for c in cases}
    with reference.open('rb')as stream:positions={i:r['id']for i,r in enumerate(projected_questions(stream))if r['id']in chosen}
    need(len(positions)==24,'selected question identities changed.')
    # First permitted document-reference interpretation follows the durable event.
    with reference.open('rb')as stream:gold=selected_documents(stream,positions)
    execution=Path(prediction['execution']);by_arm={name:json.loads((execution/name/'results.json').read_text())for name in ARMS}
    case_scores=[];scores={name:[]for name in ARMS};all_scorable=True
    for i,case in enumerate(cases):
        row={'case_id':case['id'],'question_type':case['type'],'reference_pmids':gold[case['id']],'arms':{}}
        for name in ARMS:
            result=by_arm[name][i];m=retrieval_metrics(gold[case['id']],result['ranked_pmids']);row['arms'][name]=m
            scores[name].append(m['recall_at_10']);all_scorable&=m['status']=='scored'
        case_scores.append(row)
    write_json(folder/'case_scores.private.json',case_scores)
    comparisons=None
    if all_scorable:
        weights,comparisons=paired_bootstrap(scores);write_json(folder/'question_multiplicities.json',weights)
    metrics={}
    costs={};trajectories={}
    for name in ARMS:
        rows=by_arm[name];returned=sum(len(r['ranked_pmids'])for r in rows)
        if name!='direct_native_query':trajectories[name]=trajectory_summary(rows)
        arm_file=execution/name/'execution.json';arm=json.loads(arm_file.read_text());token_totals=Counter()
        for usage in arm.get('model_usage',[]):
            if isinstance(usage,dict):
                for key,value in usage.items():
                    if type(value)is int:token_totals[key]+=value
        costs[name]={k:arm.get(k)for k in ('model_calls','tokenizer_model_service_requests','native_process_executions',
            'direct_fetch_invocations','cache_hits','exact_upstream_HTTP_request_count')}
        costs[name].update(observed_token_counts=dict(token_totals),
            usage_responses=sum(isinstance(u,dict)for u in arm.get('model_usage',[])),dollar_cost=None,
            cost_note='No API/model price table assumed; failed responses can lack token usage. Native process count is not HTTP request count.')
        metrics[name]={'fixed_questions':24,'scorable_reference_questions':sum(r['arms'][name]['status']=='scored'for r in case_scores),
            'mean_reference_recall_at_10':statistics.mean(scores[name])if all_scorable else None,
            'mean_reference_hit_at_10':statistics.mean(r['arms'][name]['reference_hit_at_10']for r in case_scores)if all_scorable else None,
            'system_status_counts':dict(Counter(r['status']for r in rows)),'returned_IDs':returned,
            'all_final_IDs_are_controller_checked_native_candidates':True,
            'candidate_ID_validity_fraction':1.0 if returned else None,
            'exact_get_requested_IDs':sum(len(r['abstract_get_requested_pmids'])for r in rows),
            'exact_get_resolved_article_IDs':sum(len(r['abstracts_identity_resolved'])for r in rows),
            'get_results_with_nonempty_abstract':sum(bool(h.get('tool_result',{}).get('record',{}).get('abstract'))for r in rows for h in r.get('history',[])if h.get('action',{}).get('action')=='get_abstract'and h.get('tool_result',{}).get('record')),
            'interpretation':'Identifier/provenance checks are not source entailment, comprehensive relevance or biological accuracy.'}
    report=seal({'format':'biograph-steward.source-search-reference-comparison.v1','created_at':utcnow(),
        'title':'Bounded biomedical reference-paper retrieval, with and without an attributed search procedure',
        'scope':'Small public retrospective reference-document assessment; not biological truth, model-unseen testing or an official BioASQ submission.',
        'fixed_questions':24,'question_types':dict(Counter(c['type']for c in cases)),'all_reference_questions_scorable':all_scorable,
        'duplicate_feedback_enabled':protocol.get('duplicate_feedback',False),
        'controller_feedback_policy':DUPLICATE_FEEDBACK_POLICY if protocol.get('duplicate_feedback',False)else None,
        'comparison_stage':'prelabel_execution_failure_motivated_followup'if protocol.get('duplicate_feedback',False)else 'original_fail_fast_comparison',
        'metrics':metrics,'paired_comparisons':comparisons,'execution_costs':costs,
        'agent_trajectory_summaries':trajectories,'policy':POLICY,
        'source':{'doi':'10.5281/zenodo.7655130','version':'BioASQ11','license':'CC-BY-2.5','sha256':protocol['reference']['sha256']},
        'lineage':{'protocol_file_sha256':protocol_sha256,'prediction_seal_file_sha256':prediction_seal_sha256,
            'policy_file_sha256':policy_sha256,'release_event_content_sha256':event['content_sha256']},
        'raw_case_scores_sha256':sha(folder/'case_scores.private.json'),'raw_questions_answers_references_in_report':False,
        'limitations':['The public historical dataset may occur in model training; project-new is not model-unseen.',
            'Reference document lists are incomplete positive judgments; an unlisted paper is not shown irrelevant or biologically false.',
            'Shared live PubMed infrastructure, sources and model create dependence; question bootstrap intervals are conditional/descriptive.',
            'All fixed cases, unavailable sources and failed model outputs remain; no post-outcome prompt/model selection.',
            'Returning candidate IDs is a retrieval handoff, not a claim that all papers were opened/read or support a biological assertion.'],
        'app_graph_changed':False})
    for path,expected in prediction['input_files_sha256'].items():ordinary_file(path,expected)
    write_json(folder/'report.json',report);return report


def inspect_recovery(frozen,protocol_sha256,prediction_seal,prediction_seal_sha256,output):
    """Observed shared payload prefixes and completions, without references."""
    protocol,cases=load_frame(frozen,protocol_sha256)
    need(protocol.get('duplicate_feedback')is True,'a separately frozen feedback follow-up is required.')
    prior=protocol['recovery_followup']['original_prediction_seal']
    old=read_sealed(prior['file'],prior['sha256']);new=read_sealed(prediction_seal,prediction_seal_sha256)
    need(old['format']==new['format']=='biograph-steward.source-search-prediction-seal.v1'
         and old['reference_document_values_opened']is new['reference_document_values_opened']is False
         and new['protocol_file_sha256']==protocol_sha256,'both reviewed forecasts must precede reference access.')
    for p in (old,new):
        for name,pin in p['input_files_sha256'].items():ordinary_file(name,pin)
    counts={};prefix={'paired_agent_cases':48,'cases_with_two_generation_attempts':0,
        'same_first_request_payload_cases':0,'exact_shared_payload_prefix_requests':0,
        'completed_output_comparable_prefix_requests':0,'equal_parsed_output_prefix_requests':0,
        'cases_with_parsed_output_change_under_same_payload':0}
    for arm in ARMS[1:]:
        before=json.loads((Path(old['execution'])/arm/'results.json').read_text())
        after=json.loads((Path(new['execution'])/arm/'results.json').read_text())
        need([r['case_id']for r in before]==[r['id']for r in cases]==[r['case_id']for r in after],
             'original/follow-up question frame differs.')
        counts[arm]={'original_valid_final_completions':sum(r['status']=='completed'for r in before),
            'followup_valid_final_completions':sum(r['status']=='completed'for r in after),
            'original_model_calls':sum(r['model_calls']for r in before),'followup_model_calls':sum(r['model_calls']for r in after),
            'original_statuses':dict(Counter(r['status']for r in before)),
            'followup_statuses':dict(Counter(r['status']for r in after)),
            'explicit_rejected_duplicate_observations':sum(len(r.get('controller_rejections',[]))for r in after)}
        for a,b in zip(before,after):
            changed=False
            if a['model_calls']and b['model_calls']:prefix['cases_with_two_generation_attempts']+=1
            for step in range(1,min(a['model_calls'],b['model_calls'])+1):
                paths=[Path(p['execution'])/arm/a['case_id']/f'model_call_{step}.json'for p in (old,new)]
                x,y=(json.loads(path.read_text())for path in paths)
                if x['request_sha256']!=y['request_sha256']:break
                prefix['exact_shared_payload_prefix_requests']+=1
                if step==1:prefix['same_first_request_payload_cases']+=1
                if x['status']==y['status']=='completed':
                    prefix['completed_output_comparable_prefix_requests']+=1
                    prefix['equal_parsed_output_prefix_requests']+=x['output']==y['output']
                    changed|=x['output']!=y['output']
            prefix['cases_with_parsed_output_change_under_same_payload']+=changed
    old_count=sum(r['original_valid_final_completions']for r in counts.values())
    new_count=sum(r['followup_valid_final_completions']for r in counts.values())
    value=seal({'format':'biograph-steward.source-search-recovery-operational-check.v1','created_at':utcnow(),
        'counts':counts,'observed_shared_payload_prefix':prefix,
        'operational_retention_criterion':{'passed':new_count>old_count,'original_valid_finals':old_count,
            'followup_valid_finals':new_count,'rule':'More valid final completions overall, with both sealed guard/budget gates intact.'},
        'lineage':{'original_prediction_seal_file_sha256':prior['sha256'],
            'followup_prediction_seal_file_sha256':prediction_seal_sha256,'followup_protocol_file_sha256':protocol_sha256},
        'reference_values_opened':False,'raw_questions_queries_or_article_IDs_in_aggregate':False,
        'interpretation':'Observed payload/output agreement is recorded, not assumed deterministic model replay. More valid finals alone is not a retrieval or biological-accuracy gain.'})
    need(not Path(output).exists(),'choose a new operational check output.');write_json(output,value);return value


def compare_recovery(original_report,original_report_sha256,followup_report,followup_report_sha256,
                     operational_check,operational_check_sha256,output):
    """Same-arm paired retrieval comparison; no new reference-source reader."""
    a=read_sealed(original_report,original_report_sha256);b=read_sealed(followup_report,followup_report_sha256)
    op=read_sealed(operational_check,operational_check_sha256)
    need(a['format']==b['format']=='biograph-steward.source-search-reference-comparison.v1'
         and op['format']=='biograph-steward.source-search-recovery-operational-check.v1'
         and a['lineage']['prediction_seal_file_sha256']==op['lineage']['original_prediction_seal_file_sha256']
         and b['lineage']['prediction_seal_file_sha256']==op['lineage']['followup_prediction_seal_file_sha256'],
         'reference comparisons do not bind the frozen operational check.')
    private=[]
    for path,report in ((original_report,a),(followup_report,b)):
        p=Path(path).with_name('case_scores.private.json');ordinary_file(p,report['raw_case_scores_sha256']);private.append(json.loads(p.read_text()))
    need(len(private[0])==len(private[1])==24 and [(r['case_id'],r['reference_pmids'])for r in private[0]]==
         [(r['case_id'],r['reference_pmids'])for r in private[1]],'released reference questions or positive IDs differ.')
    direct=[[r['arms']['direct_native_query']['recall_at_10']for r in rows]for rows in private]
    need(direct[0]==direct[1],'shared direct native-control retrieval differs.')
    all_scored=a['all_reference_questions_scorable']and b['all_reference_questions_scorable'];differences=[]
    for arm in ARMS[1:]:
        row={'agent_condition':arm,'status':'scored'if all_scored else 'unscorable_reference_empty'}
        if all_scored:
            scores={'direct_native_query':direct[0],
                'unskilled_agent':[r['arms'][arm]['recall_at_10']for r in private[0]],
                'procedure_skill_agent':[r['arms'][arm]['recall_at_10']for r in private[1]]}
            _,contrasts=paired_bootstrap(scores);c=contrasts[0]
            row.update(candidate='explicit_duplicate_feedback',comparator='original_fail_fast',
                observed_mean_difference=c['observed_mean_difference'],paired_95_percentile_interval=c['paired_95_percentile_interval'],
                fraction_draws_above_zero=c['fraction_draws_above_zero'],
                positive_reference_retrieval_interval=c['paired_95_percentile_interval'][0]>0)
        differences.append(row)
    value=seal({'format':'biograph-steward.source-search-recovery-reference-comparison.v1','created_at':utcnow(),
        'scope':'One execution-failure-motivated policy fixed before reference access; same public retrospective24 questions, not independent biological validation.',
        'operational_retention_criterion':op['operational_retention_criterion'],
        'original_primary_skill_minus_base':a['paired_comparisons'][0]if a['paired_comparisons']else None,
        'followup_primary_skill_minus_base':b['paired_comparisons'][0]if b['paired_comparisons']else None,
        'same_condition_recovery_differences':differences,'shared_direct_native_control_mean_recall_at_10':a['metrics']['direct_native_query']['mean_reference_recall_at_10'],
        'observed_shared_payload_prefix':op['observed_shared_payload_prefix'],
        'actual_execution_costs':{'original':a['execution_costs'],'followup':b['execution_costs']},
        'lineage':{'original_report_file_sha256':original_report_sha256,'followup_report_file_sha256':followup_report_sha256,
            'operational_check_file_sha256':operational_check_sha256},
        'new_reference_source_access_or_model_calls':False,'raw_cases_in_aggregate':False,
        'limitations':['Public model-training overlap remains incompletely auditable.','Reference lists are incomplete positive paper judgments, not comprehensive relevance or biological truth.',
            'Intervals are conditional question-bootstrap descriptions; no multiplicity-adjusted universal winner is claimed.',
            'No graph ingestion, independent-evidence vote, or hypothetical cost-saving comparison was performed.']})
    need(not Path(output).exists(),'choose a new recovery comparison output.');write_json(output,value);return value


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('freeze-policy')
    for key in ('frozen','protocol-sha256','output'):p.add_argument('--'+key,required=True)
    p=sub.add_parser('seal-predictions')
    for key in ('frozen','protocol-sha256','execution','execution-sha256','cache','policy','policy-sha256','output'):p.add_argument('--'+key,required=True)
    p=sub.add_parser('release-score')
    for key in ('frozen','protocol-sha256','prediction-seal','prediction-seal-sha256','policy','policy-sha256','output'):p.add_argument('--'+key,required=True)
    p=sub.add_parser('inspect-recovery')
    for key in ('frozen','protocol-sha256','prediction-seal','prediction-seal-sha256','output'):p.add_argument('--'+key,required=True)
    p=sub.add_parser('compare-recovery')
    for key in ('original-report','original-report-sha256','followup-report','followup-report-sha256','operational-check','operational-check-sha256','output'):p.add_argument('--'+key,required=True)
    args=vars(parser.parse_args());command=args.pop('command').replace('-','_');args['output']=Path(args['output'])
    result=globals()[command](**args)
    print(json.dumps({k:v for k,v in result.items()if k in ('format','content_sha256','question_count','fixed_questions','all_reference_questions_scorable')},indent=2))
