"""Freeze comparison choices and score completed predictions against native labels.

The final label reader requires a separate prediction seal containing complete
tool/agent outputs. Unknown is never a correct negative in full accuracy.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import random
import zipfile

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import sha
from .prepare import DATA_SHA, RELATIONS, need
from .predict import load_frame
from .agent import GUIDANCE, MAX_CALLS, MAX_TOOLS, MAX_OUTPUT_TOKENS, POLICY_NAME, MODEL

ALLOWED_GENE_RELATIONS={'None','Association','Positive_Correlation','Negative_Correlation','Bind'}


def sealed(path):
    value=json.loads(Path(path).read_text())
    need(value.get('content_sha256')==digest({k:v for k,v in value.items() if k!='content_sha256'}),'report seal differs.')
    return value


def code_pins():
    base=Path(__file__).parent
    paths=[base/n for n in ('prepare.py','predict.py','agent.py','passages.py','evaluate.py')]
    paths += [base.parents[1]/'biograph_steward'/n for n in ('model_transport.py','client.py','file_utils.py')]
    return {str(p.relative_to(base.parents[1])):sha(p) for p in paths}


def freeze(frame_dir,development,development_flat,runtime,output):
    frame,cases=load_frame(frame_dir);development=sealed(Path(development)/'execution.json');output=Path(output)
    flat=sealed(Path(development_flat)/'execution.json');runtime=Path(runtime)
    observation=json.loads(runtime.read_text())
    need(frame['partition']=='test','final freeze requires the project-unopened BC8 test frame.')
    need(development['status']=='completed' and development['completed_cases']==32,'finish 32 development integration controls.')
    need(flat['status']=='completed' and flat['completed_cases']==32 and flat['mode']=='flat'
         and development['mode']=='agent' and development['frame_content_sha256']==flat['frame_content_sha256'],
         'finish the same 32 flat-context development integration controls.')
    need(development['policy_sha256']==flat['policy_sha256']==digest(GUIDANCE),'development policy differs.')
    pins=code_pins()
    need(development['implementation_sha256']==flat['implementation_sha256']==pins['tools/biored_agent/agent.py']
         and development['transport_implementation_sha256']==flat['transport_implementation_sha256']==pins['biograph_steward/model_transport.py'],
         'development did not validate this controller/transport implementation.')
    need(observation['derived_observation']['model']==MODEL and observation['health_http_status']==200,
         'served model observation differs.')
    need(not output.exists(),'choose a new comparison freeze.')
    value={'format':'biograph-steward.biored-comparison-freeze.v1','created_at':utcnow(),
        'frame_content_sha256':frame['content_sha256'],'cases':len(cases),'independent_publications':len({r['pmid'] for r in cases}),
        'case_id_order':[r['id'] for r in cases],'policy':POLICY_NAME,'policy_sha256':digest(GUIDANCE),'code_sha256':pins,
        'model':MODEL,'max_model_calls_per_case':MAX_CALLS,'max_read_tools_per_case':MAX_TOOLS,
        'max_output_tokens_per_call':MAX_OUTPUT_TOKENS,'maximum_output_tokens':len(cases)*MAX_CALLS*MAX_OUTPUT_TOKENS,
        'maximum_flat_context_model_calls_per_case':1,'maximum_flat_output_tokens':len(cases)*MAX_OUTPUT_TOKENS,
        'maximum_combined_agent_and_flat_output_tokens':len(cases)*(MAX_CALLS+1)*MAX_OUTPUT_TOKENS,
        'agent_history':'Explicit multi-step action/tool-result history in each request data; transport itself is stateless.',
        'development_execution_content_sha256':development['content_sha256'],
        'development_flat_execution_content_sha256':flat['content_sha256'],
        'runtime_observation_sha256':sha(runtime),'runtime_observation':observation['derived_observation'],
        'test_relation_labels_opened':False,
        'arms':['always_None','typed_co_mention','specialist_native','specialist_type_guard','flat_context_LLM','source_audit_agent'],
        'primary_metrics':['full_denominator_exact_relation_accuracy_unknown_wrong','micro_exact_positive_relation_F1'],
        'secondary_metrics':['entity_pair_precision_recall_F1','false_positive_negative_counts','coverage','invalid_outputs','per_type_confusion'],
        'paired_uncertainty':'5000 fixed-seed paired publication bootstrap replicates; one preselected case per publication. CIs are descriptive fixed-frame uncertainty, not a simultaneous whole-graph guarantee.',
        'adoption_rule':'No agent default promotion unless lower 95% paired bootstrap bounds for both exact accuracy and exact positive-relation F1 exceed zero against native specialist, type-guarded specialist and flat-context same-model control; report every arm and all abstentions regardless.',
        'biological_scope':'Expert source-relative relation annotation; not whole-Pharos biological truth or independent experimental validation.',
        'reference_limitations':['Gold entity annotations are supplied; this is not end-to-end NER/grounding.',
            'Public pretraining/checkpoint exposure cannot be fully independently audited.',
            'Native None is no qualifying relation in the permitted abstract, not biological irrelevance.',
            'Novelty/direction are separate annotations, not primary outcomes; corpus Bind is not synonymous with direct physical binding.']}
    value['content_sha256']=digest(value);write_json(output,value);return value


def load_outputs(frame,cases,specialist,agent):
    specialist,agent=Path(specialist),Path(agent)
    sr,ar=sealed(specialist/'execution.json'),sealed(agent/'execution.json')
    need(sr['status']=='completed' and ar['status']=='completed' and sr['completed_cases']==ar['completed_cases']==len(cases),
         'all predictions must finish before reference outcomes open.')
    need(sr['frame_content_sha256']==ar['frame_content_sha256']==frame['content_sha256'],'prediction frame mismatch.')
    need(sha(specialist/'predictions.jsonl')==sr['predictions_sha256'] and sha(agent/'results.json')==ar['results_sha256'],
         'prediction content changed.')
    sp=[json.loads(line) for line in (specialist/'predictions.jsonl').read_text().splitlines()]
    ag=json.loads((agent/'results.json').read_text())
    need([r['case_id'] for r in sp]==[r['id'] for r in cases]==[r['case_id'] for r in ag],'prediction inventory/order differs.')
    return sr,ar,sp,ag


def seal_predictions(frame_dir,freeze_path,specialist,agent,flat,output):
    frame,cases=load_frame(frame_dir);contract=sealed(freeze_path);output=Path(output)
    need(contract['frame_content_sha256']==frame['content_sha256'] and contract['code_sha256']==code_pins(),'frozen method/frame changed.')
    sr,ar,sp,ag=load_outputs(frame,cases,specialist,agent)
    _,fr,_,fl=load_outputs(frame,cases,specialist,flat)
    need(ar['policy_sha256']==contract['policy_sha256'],'agent semantic policy differs.')
    need(fr['policy_sha256']==contract['policy_sha256'] and fr['mode']=='flat' and ar['mode']=='agent', 'same-model flat/agent comparison differs.')
    need(ar['implementation_sha256']==fr['implementation_sha256']==contract['code_sha256']['tools/biored_agent/agent.py']
         and ar['transport_implementation_sha256']==fr['transport_implementation_sha256']==contract['code_sha256']['biograph_steward/model_transport.py']
         and sr['implementation_sha256']==contract['code_sha256']['tools/biored_agent/predict.py'],
         'predictions used an implementation different from the frozen method.')
    need(not output.exists(),'choose a new prediction freeze.')
    value={'format':'biograph-steward.biored-prediction-freeze.v1','created_at':utcnow(),
        'comparison_content_sha256':contract['content_sha256'],'frame_content_sha256':frame['content_sha256'],
        'specialist_content_sha256':sr['content_sha256'],'agent_content_sha256':ar['content_sha256'],
        'flat_context_content_sha256':fr['content_sha256'],
        'completed_cases':len(cases),'specialist_prediction_file_sha256':sr['predictions_sha256'],
        'agent_prediction_file_sha256':ar['results_sha256'],'test_relation_labels_opened':False,'code_sha256':code_pins()}
    value['content_sha256']=digest(value);write_json(output,value);return value


def native_labels(data_zip,frame,cases):
    need(sha(data_zip)==DATA_SHA,'reference archive changed.')
    selected={r['author_tsv_line']:r for r in cases};gold={}
    with zipfile.ZipFile(data_zip) as archive:
        raw=archive.read(frame['tsv_member'])
    for line_no,line in enumerate(raw.splitlines(),1):
        if line_no not in selected:continue
        c=selected[line_no];parts=line.decode().split('\t')
        need(len(parts)==9 and parts[:6]==c['masked_tsv'].split('\t')[:6], 'reference native input join differs.')
        need(parts[6] in RELATIONS,'unknown native relation category; do not invent a mapping.')
        gold[c['id']]=parts[6]
    need(len(gold)==len(cases),'reference inventory incomplete.')
    return [gold[c['id']] for c in cases]


def metrics(gold,pred):
    need(len(gold)==len(pred) and bool(gold),'empty/misaligned scoring frame.')
    positives=set(RELATIONS)-{'None'}
    tp=sum(g==p and g in positives for g,p in zip(gold,pred))
    fp=sum(p in positives and p!=g for g,p in zip(gold,pred))
    fn=sum(g in positives and p!=g for g,p in zip(gold,pred))
    ptp=sum(g in positives and p in positives for g,p in zip(gold,pred))
    pfp=sum(g=='None' and p in positives for g,p in zip(gold,pred))
    pfn=sum(g in positives and p not in positives for g,p in zip(gold,pred))
    def score(a,b,c):
        precision=a/(a+b) if a+b else 0.;recall=a/(a+c) if a+c else 0.
        return {'tp':a,'fp':b,'fn':c,'precision':precision,'recall':recall,
                'f1':2*a/(2*a+b+c) if 2*a+b+c else 0.}
    return {'cases':len(gold),'exact_correct':sum(g==p for g,p in zip(gold,pred)),
        'exact_accuracy':sum(g==p for g,p in zip(gold,pred))/len(gold),
        'coverage':sum(p!='Unresolved' for p in pred)/len(gold),'unresolved':pred.count('Unresolved'),
        'exact_positive_relation':score(tp,fp,fn),'entity_pair':score(ptp,pfp,pfn),
        'native_None_cases':gold.count('None'),'confusion':dict(Counter(g+' -> '+p for g,p in zip(gold,pred)))}


def execution_cost(path,report,results):
    """Read only recorded serving usage, never infer a price or rationale quality."""
    path=Path(path);totals=Counter();missing=Counter()
    for result in results:
        case_path=path/result['case_id'].replace(':','_')
        for index in range(1,result['model_calls']+1):
            trace=json.loads((case_path/f'model_call_{index}.json').read_text())
            for key in ('prompt_tokens','completion_tokens','total_tokens'):
                value=(trace.get('usage') or {}).get(key)
                if isinstance(value,(int,float)):totals[key]+=value
                else:missing[key]+=1
            totals['transport_requests']+=trace.get('transport_requests',1)
    return {'model_calls':report['model_calls'],'tool_reads':report['tool_reads'],
        'reported_token_usage':dict(totals),'usage_fields_missing_calls':dict(missing),
        'sum_case_elapsed_seconds':sum(r['elapsed_seconds'] for r in results),
        'statuses':dict(Counter(r['status'] for r in results)),
        'tool_selection_sequences':dict(Counter(' -> '.join(r['tools_used']) for r in results)),
        'model_driven_tools':report['model_driven_tools'],'inference_price_assumed':False,
        'selection_warning':'Repeatedly reading every tool in the same order does not demonstrate adaptive or efficient agent behavior.'}


def paired(gold,a,b,repeats=5000):
    rng=random.Random('biograph-biored-paired-publication-v1');rows=[];n=len(gold)
    for _ in range(repeats):
        take=[rng.randrange(n) for _ in range(n)]
        aa=metrics([gold[i] for i in take],[a[i] for i in take]);bb=metrics([gold[i] for i in take],[b[i] for i in take])
        rows.append((aa['exact_accuracy']-bb['exact_accuracy'],aa['exact_positive_relation']['f1']-bb['exact_positive_relation']['f1']))
    def interval(k):
        x=sorted(r[k] for r in rows);return [x[int(.025*repeats)],x[min(repeats-1,int(.975*repeats))]]
    aw=sum(ga==pa and ga!=pb for ga,pa,pb in zip(gold,a,b));bw=sum(ga==pb and ga!=pa for ga,pa,pb in zip(gold,a,b));discordant=aw+bw
    p=min(1.,2*sum(math.comb(discordant,k) for k in range(min(aw,bw)+1))/(2**discordant)) if discordant else 1.
    return {'candidate_only_correct':aw,'comparator_only_correct':bw,'exact_McNemar_two_sided_p':p,
        'accuracy_delta_95pct_paired_bootstrap':interval(0),'exact_relation_F1_delta_95pct_paired_bootstrap':interval(1),
        'bootstrap_replicates':repeats,'scope':'Fixed selected source cases, not a whole-Pharos population estimate.'}


def score(frame_dir,contract_path,prediction_freeze,data_zip,specialist,agent,flat,output):
    frame,cases=load_frame(frame_dir);contract=sealed(contract_path);frozen=sealed(prediction_freeze);output=Path(output)
    need(not output.exists(),'choose a new scored output.')
    need(frozen['comparison_content_sha256']==contract['content_sha256'] and frozen['code_sha256']==code_pins()==contract['code_sha256'],
         'comparison method/predictions changed before label access.')
    sr,ar,sp,ag=load_outputs(frame,cases,specialist,agent)
    _,fr,_,fl=load_outputs(frame,cases,specialist,flat)
    need(sr['content_sha256']==frozen['specialist_content_sha256'] and ar['content_sha256']==frozen['agent_content_sha256'],
         'outcomes may open only against exact frozen predictions.')
    need(fr['content_sha256']==frozen['flat_context_content_sha256'],'flat-context predictions changed.')
    # First and only final outcome opening occurs after all checks above.
    opened=utcnow();gold=native_labels(data_zip,frame,cases)
    native=[r['relation'] for r in sp]
    guarded=[]
    for c,p in zip(cases,native):
        allowed=ALLOWED_GENE_RELATIONS-({'Bind'} if c['type1']=='DiseaseOrPhenotypicFeature' else set())
        guarded.append(p if p in allowed else 'Unresolved')
    arms={'always_None':['None']*len(cases),'typed_co_mention':['Association']*len(cases),
        'specialist_native':native,'specialist_type_guard':guarded,'flat_context_LLM':[r['relation'] for r in fl],
        'source_audit_agent':[r['relation'] for r in ag]}
    result={name:metrics(gold,pred) for name,pred in arms.items()}
    comparisons={name:paired(gold,arms['source_audit_agent'],arms[name]) for name in ('specialist_native','specialist_type_guard','flat_context_LLM')}
    specialist_comparisons={name:paired(gold,arms[name],arms['typed_co_mention'])
                            for name in ('specialist_native','specialist_type_guard')}
    groups={}
    for group in sorted({c['type1']+'--'+c['type2'] for c in cases}):
        take=[i for i,c in enumerate(cases) if c['type1']+'--'+c['type2']==group]
        groups[group]={name:metrics([gold[i] for i in take],[pred[i] for i in take]) for name,pred in arms.items()}
    adopt=all(all(c[k][0]>0 for k in ('accuracy_delta_95pct_paired_bootstrap','exact_relation_F1_delta_95pct_paired_bootstrap'))
              for c in comparisons.values())
    output.mkdir(parents=True)
    write_json(output/'case_scores.json',[{'case_id':c['id'],'pmid':c['pmid'],'gold_native_relation':g,
        'predictions':{name:pred[i] for name,pred in arms.items()}} for i,(c,g) in enumerate(zip(cases,gold))])
    report={'format':'biograph-steward.biored-source-comparison.v1','created_at':utcnow(),'labels_first_opened_at':opened,
        'frame_content_sha256':frame['content_sha256'],'comparison_content_sha256':contract['content_sha256'],
        'prediction_freeze_content_sha256':frozen['content_sha256'],'test_cases':len(cases),'test_publications':len({c['pmid'] for c in cases}),
        'gold_label_counts':dict(Counter(gold)),'metrics':result,'agent_paired_comparisons':comparisons,
        'specialist_vs_co_mention_paired_comparisons':specialist_comparisons,'per_entity_type_metrics':groups,
        'execution_costs':{'source_audit_agent':execution_cost(agent,ar,ag),
                           'flat_context_LLM':execution_cost(flat,fr,fl),
                           'specialist_native':{'execution_content_sha256':sr['content_sha256'],
                                                'model_calls':0,'note':'Published native specialist model inference; not LLM/API calls.'}},
        'agent_default_adoption_criterion_passed':adopt,'live_graph_changed':False,
        'case_scores_sha256':sha(output/'case_scores.json'),'interpretation':contract['biological_scope'],
        'limitations':contract['reference_limitations']}
    report['content_sha256']=digest(report);write_json(output/'report.json',report);return report


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    f=sub.add_parser('freeze')
    for n in ('frame','development','development-flat','runtime','output'):f.add_argument('--'+n,required=True)
    s=sub.add_parser('seal-predictions')
    for n in ('frame','contract','specialist','agent','flat','output'):s.add_argument('--'+n,required=True)
    e=sub.add_parser('score')
    for n in ('frame','contract','prediction-freeze','data-zip','specialist','agent','flat','output'):e.add_argument('--'+n,required=True)
    a=p.parse_args()
    if a.command=='freeze':r=freeze(a.frame,a.development,a.development_flat,a.runtime,a.output)
    elif a.command=='seal-predictions':r=seal_predictions(a.frame,a.contract,a.specialist,a.agent,a.flat,a.output)
    else:r=score(a.frame,a.contract,a.prediction_freeze,a.data_zip,a.specialist,a.agent,a.flat,a.output)
    print(json.dumps({k:v for k,v in r.items() if k in ('format','content_sha256','test_cases','agent_default_adoption_criterion_passed')},indent=2))


if __name__=='__main__':main()
