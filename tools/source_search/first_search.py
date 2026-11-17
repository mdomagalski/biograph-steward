"""Pre-label error localization from existing first-attempt search captures.

No new queries, model calls, reference-source reader or best-query selection.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import statistics

from biograph_steward.client import utcnow,write_json
from biograph_steward.file_utils import sha
from .prepare import load_frame,need,seal,read_sealed
from .evaluate import retrieval_metrics
from .tools import PMID

ARMS=('unskilled_agent','procedure_skill_agent')
RULE={'selection':'FIRST ATTEMPTED executed search only, including empty/partial/unavailable. Never skip to a later search.',
 'ranking':'Native candidate order, prefix at most10; no union, reranking or query selection.',
 'no_search':'Empty retrieval, full24-question denominator.',
 'readout':'Same mean question-level reference-PMID Recall@10; compare descriptively with that arm final output.',
 'status':'Execution-failure-motivated diagnostic fixed before reference release; not original primary, independent test or replacement production arm.',
 'literature':'https://aclanthology.org/2023.emnlp-main.322/',
 'literature_scope':'Query rewriting is a separable retrieval role. This is not a reproduction of the paper trainable/RL method.',
 'new_model_tool_or_reference_access':False}


def first_attempt(row):
    for history in row.get('history',[]):
        if history.get('action',{}).get('action')!='search_pubmed':continue
        result=history['tool_result'];ids=[r['pmid']for r in result['candidates']][:10]
        need(len(ids)==len(set(ids))and all(isinstance(x,str)and PMID.fullmatch(x)for x in ids),'native first-search identity differs.')
        return {'status':result['status'],'query':history['action']['query'],'ranked_pmids':ids,
            'native_capture_content_sha256':result['cache']['result_content_sha256']}
    return {'status':'no_search','query':None,'ranked_pmids':[],'native_capture_content_sha256':None}


def freeze(frozen,protocol_sha256,output):
    p,_=load_frame(frozen,protocol_sha256);out=Path(output);need(not out.exists(),'diagnostic policy already exists.')
    value=seal({'format':'biograph-steward.first-search-diagnostic-policy.v1','created_at':utcnow(),
        'producer_protocol_file_sha256':protocol_sha256,'question_frame_sha256':p['questions_sha256'],
        'rule':RULE,'implementation_sha256':sha(__file__),'metric_helper_sha256':sha(Path(__file__).with_name('evaluate.py')),
        'reference_document_values_opened':False})
    write_json(out,value);return value


def policy_value(path,pin):
    p=read_sealed(path,pin)
    need(p['format']=='biograph-steward.first-search-diagnostic-policy.v1'and p['rule']==RULE
         and p['implementation_sha256']==sha(__file__)
         and p['metric_helper_sha256']==sha(Path(__file__).with_name('evaluate.py')),'diagnostic source/rule changed.')
    return p


def derive(frozen,protocol_sha256,prediction_seal,prediction_seal_sha256,policy,policy_sha256,output):
    p,cases=load_frame(frozen,protocol_sha256);pol=policy_value(policy,policy_sha256)
    need(pol['producer_protocol_file_sha256']==protocol_sha256,'diagnostic frame differs.')
    pred=read_sealed(prediction_seal,prediction_seal_sha256)
    need(pred['format']=='biograph-steward.source-search-prediction-seal.v1'and pred['protocol_file_sha256']==protocol_sha256
         and pred['reference_document_values_opened']is False,'complete pre-reference prediction seal required.')
    for path,pin in pred['input_files_sha256'].items():need(sha(path)==pin,'sealed source/prediction changed.')
    execution=Path(pred['execution']);rows={}
    for name in ARMS:
        source=json.loads((execution/name/'results.json').read_text());need([x['case_id']for x in source]==[x['id']for x in cases],'diagnostic case frame differs.')
        rows[name]=[{'case_id':r['case_id'],**first_attempt(r)}for r in source]
    value=seal({'format':'biograph-steward.first-search-derived-forecasts.v1','created_at':utcnow(),
        'protocol_file_sha256':protocol_sha256,'prediction_seal_file_sha256':prediction_seal_sha256,
        'diagnostic_policy_file_sha256':policy_sha256,'question_frame_sha256':p['questions_sha256'],
        'rule':RULE,'rows':rows,'reference_values_opened':False,'new_tool_or_model_calls':0})
    need(not Path(output).exists(),'choose a new derived forecast output.');write_json(output,value);return value


def score(main_report,main_report_sha256,derived,derived_sha256,policy,policy_sha256,output):
    policy_value(policy,policy_sha256);main=read_sealed(main_report,main_report_sha256);pred=read_sealed(derived,derived_sha256)
    need(main['format']=='biograph-steward.source-search-reference-comparison.v1'
         and pred['format']=='biograph-steward.first-search-derived-forecasts.v1'
         and pred['diagnostic_policy_file_sha256']==policy_sha256
         and pred['prediction_seal_file_sha256']==main['lineage']['prediction_seal_file_sha256'],
         'released main assessment and first-search source differ.')
    private=Path(main_report).with_name('case_scores.private.json');need(sha(private)==main['raw_case_scores_sha256'],'released selected reference copy differs.')
    refs=json.loads(private.read_text());need(len(refs)==24,'full question denominator differs.');results={}
    for name in ARMS:
        rows=pred['rows'][name];need([r['case_id']for r in rows]==[r['case_id']for r in refs],'derived/source frame differs.')
        metrics=[retrieval_metrics(ref['reference_pmids'],row['ranked_pmids'])for ref,row in zip(refs,rows)]
        complete=all(m['status']=='scored'for m in metrics)
        mean=statistics.mean(m['recall_at_10']for m in metrics)if complete else None
        final=main['metrics'][name]['mean_reference_recall_at_10']
        results[name]={'fixed_questions':24,'scorable_reference_questions':sum(m['status']=='scored'for m in metrics),
            'first_attempt_mean_reference_recall_at_10':mean,'final_output_mean_reference_recall_at_10':final,
            'first_attempt_minus_final_mean_difference':mean-final if mean is not None and final is not None else None,
            'first_attempt_statuses':dict(Counter(r['status']for r in rows)),
            'questions_first_attempt_better_than_final':sum(m['recall_at_10']>ref['arms'][name]['recall_at_10']for m,ref in zip(metrics,refs))if complete else None,
            'questions_final_better_than_first_attempt':sum(m['recall_at_10']<ref['arms'][name]['recall_at_10']for m,ref in zip(metrics,refs))if complete else None}
    value=seal({'format':'biograph-steward.first-search-execution-diagnostic.v1','created_at':utcnow(),'rule':RULE,
        'metrics':results,'lineage':{'main_report_file_sha256':main_report_sha256,'derived_forecasts_file_sha256':derived_sha256,'diagnostic_policy_file_sha256':policy_sha256},
        'raw_questions_queries_reference_or_candidate_IDs_in_aggregate':False,'new_reference_access':False,
        'interpretation':'Error localization only. First-attempt reference recovery can be lost at later completion/ranking; these post-execution-motivated components are not new independently validated agents.'})
    need(not Path(output).exists(),'choose a new diagnostic output.');write_json(output,value);return value


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('freeze')
    for key in ('frozen','protocol-sha256','output'):p.add_argument('--'+key,required=True)
    p=sub.add_parser('derive')
    for key in ('frozen','protocol-sha256','prediction-seal','prediction-seal-sha256','policy','policy-sha256','output'):p.add_argument('--'+key,required=True)
    p=sub.add_parser('score')
    for key in ('main-report','main-report-sha256','derived','derived-sha256','policy','policy-sha256','output'):p.add_argument('--'+key,required=True)
    args=vars(parser.parse_args());command=args.pop('command');args['output']=Path(args['output'])
    v=globals()[command](**args);print(v['content_sha256'])
