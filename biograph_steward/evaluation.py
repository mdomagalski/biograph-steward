"""Frozen-source comparisons and explicit, source-bound human review sheets.

Draft planning scenarios are not biomedical gold labels. Metrics remain null
until the relevant judgments exist; absent/unjudged evidence is never negative.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import csv
import hashlib
from html import escape
import json
from pathlib import Path
import shutil
import time

from . import __version__
from .client import digest, utcnow, write_json
from .reviews import read_run, read_civic
from .planning import catalogue, semantic_plan, validate_plan, execute_plan, PlannerUnavailable
from .questions import graph_basis
from .graph import _write_tsv

SUITE_FORMAT="biograph-steward.evaluation-suite.v1"
RESULT_FORMAT="biograph-steward.evaluation-result.v1"
SOURCE_FILES=("snapshot.json","review_events.json","civic_snapshot.json")
CASE_FIELDS=["case_id","case_sha256","question","reference_plan","reference_plan_correct","reviewer","notes"]
ANSWER_FIELDS=["observation_id","output_sha256","case_id","variant","question","status","plan_correct","answer_correct","citation_support","conditions_preserved","abstention_correct","review_seconds","reviewer","notes"]
EVIDENCE_FIELDS=["review_id","unit_sha256","case_id","unit_id","unit_kind","statement","source_refs","filter_state","filter_reasons","verdict","source_check","evidence_locator","filter_decision","reviewer","notes"]


def _new_directory(path):
    path=Path(path)
    if path.exists() and any(path.iterdir()):raise ValueError("Choose a new empty directory; evaluation artifacts are immutable.")
    path.mkdir(parents=True,exist_ok=True)
    return path


def _file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def engine_fingerprint():
    return {p.name:_file_sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}


def validate_cases(cases):
    if not isinstance(cases,list) or not 1<=len(cases)<=100:raise ValueError("Use 1–100 evaluation cases.")
    ids=set();groups={}
    for c in cases:
        if not isinstance(c,dict) or set(c)!={"id","question","group","split","reference_plan"}:raise ValueError("Invalid evaluation case fields.")
        if not all(isinstance(c[k],str) and 1<=len(c[k])<=4000 for k in ['id','question','group']):raise ValueError("Cases require an ID, question and group.")
        if c['id'] in ids or c['split'] not in {'development','test'}:raise ValueError("Duplicate case ID or invalid split.")
        ids.add(c['id'])
        if c['group'] in groups and groups[c['group']]!=c['split']:raise ValueError("A question group cannot cross development/test splits.")
        groups[c['group']]=c['split'];validate_plan(c['reference_plan'])
    return deepcopy(cases)


def freeze_suite(baseline, enriched, output, *, cases=None, reviewed=None, max_results=8, max_paths=3):
    if type(max_results) is not int or not 1<=max_results<=30 or type(max_paths) is not int or not 1<=max_paths<=5:
        raise ValueError("Use the same 1–30 result / 1–5 path budget for every workflow.")
    paths={'pharos':Path(baseline).resolve(),'enriched':Path(enriched).resolve()}
    if reviewed is not None:paths['reviewed']=Path(reviewed).resolve()
    graphs={name:read_run(path)[2] for name,path in paths.items()}
    base=graphs['pharos'];combined=graphs['enriched']
    if base.get('civic') or not combined.get('civic'):raise ValueError("Use a Pharos-only baseline and a CIViC-enriched copy.")
    if base['snapshot_sha256']!=combined['snapshot_sha256']:raise ValueError("Baseline and enriched runs must use the exact same Pharos snapshot.")
    old={a['id']:(a['revision'],a['lifecycle_state']) for a in base['assertions']}
    new={a['id']:(a['revision'],a['lifecycle_state']) for a in combined['assertions']}
    if any(new.get(k)!=v for k,v in old.items()):raise ValueError("Source comparison must preserve all original Pharos assertions and review states.")
    if reviewed is not None:
        r=graphs['reviewed']
        if (r['snapshot_sha256']!=combined['snapshot_sha256'] or r.get('civic_snapshot_sha256')!=combined.get('civic_snapshot_sha256')
                or {a['id']:a['revision'] for a in r['assertions']}!={a['id']:a['revision'] for a in combined['assertions']}):
            raise ValueError("Reviewed comparison must use the same source evidence and assertion revisions.")
    cases=validate_cases(cases if cases is not None else json.loads(Path(__file__).with_name('evaluation_cases.json').read_text()))
    for c in cases:validate_plan(c['reference_plan'],combined)
    output=Path(output).resolve()
    if any(output==p or p in output.parents or output in p.parents for p in paths.values()):raise ValueError("Save an evaluation suite outside its source runs.")
    output=_new_directory(output)
    sources={}
    for name,path in paths.items():
        folder=output/'sources'/name;folder.mkdir(parents=True)
        files={}
        for filename in SOURCE_FILES:
            if (path/filename).exists():
                shutil.copyfile(path/filename,folder/filename);files[filename]=_file_sha(folder/filename)
        g=graphs[name]
        sources[name]={'original_run':path.name,'files':files,'graph_basis_sha256':graph_basis(g),
                       'pharos_snapshot_sha256':g['snapshot_sha256'],'civic_snapshot_sha256':g.get('civic_snapshot_sha256'),
                       'review_events_sha256':digest(g.get('review_events',[])),'data_kind':g['data_kind']}
    manifest={'suite_format':SUITE_FORMAT,'created_at':utcnow(),'software_version':__version__,
              'engine_files':engine_fingerprint(),'sources':sources,'cases':cases,
              'budgets':{'max_results':max_results,'max_paths':max_paths},
              'reference_status':'draft_scope_plans_not_biomedical_gold',
              'protocol':{'model_calls_per_case':1,'model_call_unit':'One API request or one CLI planning turn; CLI internal HTTP attempts are not exposed.',
                          'local_query_calls_per_case':1,'network_retrieval':False,
                          'views':'Use each reference plan’s explicit view; planner must preserve it.',
                          'review_pool':'Union of returned source units plus scoped raw CIViC items, including exclusions. Pharos pool is display-bounded.',
                          'metrics':'Descriptive reviewed-pool metrics; no predictive-model or clinical-performance claim.'}}
    manifest['suite_sha256']=digest(manifest);write_json(output/'suite.json',manifest)
    return manifest


def load_suite(path):
    path=Path(path);s=json.loads((path/'suite.json').read_text())
    if s.get('suite_format')!=SUITE_FORMAT or s.get('suite_sha256')!=digest({k:v for k,v in s.items() if k!='suite_sha256'}):raise ValueError("Evaluation suite integrity check failed.")
    validate_cases(s['cases'])
    if s['engine_files']!=engine_fingerprint():raise ValueError("Evaluation code changed after freezing. Create a new suite to record the new implementation.")
    graphs={}
    for name,source in s['sources'].items():
        if name not in {'pharos','enriched','reviewed'} or not isinstance(source['files'],dict) or set(source['files'])-set(SOURCE_FILES):raise ValueError("Invalid frozen source manifest.")
        folder=path/'sources'/name
        if {p.name for p in folder.iterdir()}!=set(source['files']):raise ValueError("Frozen source file inventory changed.")
        for filename,sha in source['files'].items():
            if _file_sha(folder/filename)!=sha:raise ValueError("Frozen source bytes changed: "+name+'/'+filename)
        graphs[name]=read_run(folder)[2]
        if graph_basis(graphs[name])!=source['graph_basis_sha256']:raise ValueError("Frozen source graph/review basis changed.")
    return s,graphs


def source_units(answer):
    units={}
    for c in (answer or {}).get('citations',[]):
        if c['kind']=='variant_therapy_response':
            for edge in c['evidence_records']:
                r=edge['evidence_record'];uid='CIViC.evidence:'+str(r['id'])
                units[uid]={'id':uid,'kind':'civic_evidence_item','record':deepcopy(r),'source_refs':deepcopy(edge['publications']),
                            'statement':r.get('description',''),'source_url':'https://civicdb.org/evidence/'+str(r['id'])}
        else:
            uid=c['assertion_id'];units[uid]={'id':uid,'kind':'pharos_assertion','record':deepcopy(c),
                                             'source_refs':deepcopy(c['publications']),
                                             'statement':c['subject']+' '+c['predicate']+' '+c['object'], 'source_url':None}
    return units


def build_pool(cases,graphs,observations,enriched_civic):
    pool={}
    for obs in observations:
        for uid,u in source_units(obs.get('answer')).items():pool.setdefault((obs['case_id'],uid),u)
    excluded={r['evidence_id']:r['reason'] for r in graphs['enriched']['civic']['excluded_items']}
    for c in cases:
        p=c['reference_plan']
        if p['tool']!='civic_therapy':continue
        for item in enriched_civic['items']:
            r=item['record']
            if p['profile_id']!='all' and p['profile_id']!='CIViC.molecularprofile:'+str(r.get('molecularProfile',{}).get('id')):continue
            if p['therapy']!='both' and p['therapy'] not in {t.get('name','').casefold() for t in r.get('therapies',[])}:continue
            uid='CIViC.evidence:'+str(r['id']);source=r.get('source',{})
            pmids=['PMID:'+str(source['citationId'])] if source.get('sourceType')=='PUBMED' else []
            pool.setdefault((c['id'],uid),{'id':uid,'kind':'civic_evidence_item','record':deepcopy(r),'source_refs':pmids,
                                         'statement':r.get('description',''),'source_url':'https://civicdb.org/evidence/'+str(r['id'])})
    rows=[]
    for (case,uid),u in sorted(pool.items()):
        row={**deepcopy(u),'case_id':case,'review_id':'unit:'+digest([case,uid])[:24],
             'filter_state':('excluded' if int(uid.split(':')[-1]) in excluded else 'retained') if u['kind']=='civic_evidence_item' else 'not_applicable',
             'filter_reasons':excluded.get(int(uid.split(':')[-1]),'') if u['kind']=='civic_evidence_item' else ''}
        row['unit_sha256']=digest(row);rows.append(row)
    return rows


def run_evaluation(suite_dir,output,*,planner=None,planner_note=None,progress=None):
    suite,graphs=load_suite(suite_dir)
    output=Path(output).resolve();suite_dir=Path(suite_dir).resolve()
    if output==suite_dir or suite_dir in output.parents or output in suite_dir.parents:raise ValueError("Save results outside the frozen suite directory.")
    output=_new_directory(output)
    observations=[]
    arms=['pharos','enriched']+(['reviewed'] if 'reviewed' in graphs else [])+['planner']
    # Stable neutral variant labels permit first-pass review without an arm in
    # every row. The mapping remains available; this is not a blinded study.
    ordered=sorted(arms,key=lambda name:digest([suite['suite_sha256'],name]))
    variants={name:'V'+str(i+1) for i,name in enumerate(ordered)}
    for case_index,case in enumerate(suite['cases'],1):
        for arm in arms:
            started=time.perf_counter();graph=graphs['enriched' if arm=='planner' else arm]
            plan=deepcopy(case['reference_plan']);trace=None
            if arm=='planner':
                if planner is None:
                    result={'status':'planner_not_run','reason':planner_note or 'No model configured. No recorded or heuristic fallback was used.','answer':None,'tool_calls':0}
                    plan=None
                else:
                    try:
                        trace=planner.plan(case['question'],graph);plan=trace.get('plan')
                        if trace.get('status')!='validated' or plan is None:
                            result={'status':'planner_error' if trace.get('status')=='planner_error' else 'invalid_plan',
                                    'reason':trace.get('error','Invalid planner output'),'answer':None,'tool_calls':0}
                        else:result=execute_plan(plan,graph,source_run=arm,**suite['budgets'])
                    except (ValueError,TypeError) as exc:
                        trace={'planner_kind':getattr(planner,'kind','unknown'),'status':'planner_error',
                               'model_calls':1 if getattr(planner,'kind','') in {'live_model','live_nim','live_codex_cli','injected_test_model'} else 0,
                               'usage':None,'error':str(exc)}
                        plan=None;result={'status':'planner_error','reason':str(exc),'answer':None,'tool_calls':0}
            else:result=execute_plan(plan,graph,source_run=arm,**suite['budgets'])
            obs={'observation_id':'obs:'+digest([suite['suite_sha256'],case['id'],arm])[:24],
                 'case_id':case['id'],'group':case['group'],'split':case['split'],'arm':arm,'variant':variants[arm],
                 'question':case['question'],'plan':plan,'trace':trace,'graph_basis_sha256':graph_basis(graph),
                 'elapsed_ms':round((time.perf_counter()-started)*1000,3),**result}
            obs['returned_units']=sorted(source_units(obs['answer']))
            obs['draft_plan_agreement']=(semantic_plan(plan)==semantic_plan(case['reference_plan']) if plan is not None
                                         else False if arm=='planner' and planner is not None else None)
            obs['output_sha256']=digest(obs);observations.append(obs)
        if progress:progress(f"Completed case {case_index}/{len(suite['cases'])}: {case['id']} (planner: {observations[-1]['status']}).")
    civic=read_civic(suite_dir/'sources'/'enriched')
    pool=build_pool(suite['cases'],graphs,observations,civic)
    result={'evaluation_format':RESULT_FORMAT,'created_at':utcnow(),'suite_sha256':suite['suite_sha256'],
            'suite':suite,'variants':variants,'planner_kind':getattr(planner,'kind','not_run'),
            'observations':observations,'pool':pool,'judgments_status':'pending',
            'limitations':['Reference plans are draft scope specifications, not biomedical gold answers.',
                'No live planner result exists when planner_kind is not_run, recorded_replay or injected_test_model.',
                'Evidence recall is limited to the reviewer pool; Pharos paths are display-bounded. Unjudged evidence is not negative.',
                'Question paraphrases and repeated source items are not independent biological observations.',
                'Candidate inspection is distinct from locally accepted evidence. Local review is not a clinical or predictive-model label.',
                'Raw excluded CIViC items are supplied for filtering review; they are not exposed as accepted graph answers.']}
    result['evaluation_sha256']=digest(result)
    write_json(output/'evaluation.json',result)
    write_review_sheets(result,output)
    metrics=score_result(result)
    write_json(output/'metrics.json',metrics)
    (output/'report.html').write_text(evaluation_html(result,metrics),encoding='utf-8')
    return result,metrics


def write_review_sheets(result,path):
    cases=[{'case_id':c['id'],'case_sha256':digest(c),'question':c['question'],'reference_plan':c['reference_plan'],
            'reference_plan_correct':'','reviewer':'','notes':''} for c in result['suite']['cases']]
    answers=[{**{k:o.get(k,'') for k in ANSWER_FIELDS},'plan_correct':'','answer_correct':'','citation_support':'',
              'conditions_preserved':'','abstention_correct':'','review_seconds':'','reviewer':'','notes':''} for o in result['observations']]
    evidence=[{'review_id':u['review_id'],'unit_sha256':u['unit_sha256'],'case_id':u['case_id'],'unit_id':u['id'],
               'unit_kind':u['kind'],'statement':u['statement'],'source_refs':u['source_refs'],
               'filter_state':u['filter_state'],'filter_reasons':u['filter_reasons'],'verdict':'','source_check':'',
               'evidence_locator':'','filter_decision':'','reviewer':'','notes':''} for u in result['pool']]
    for name,rows,columns in [('case_reviews',cases,CASE_FIELDS),('answer_reviews',answers,ANSWER_FIELDS),('evidence_reviews',evidence,EVIDENCE_FIELDS)]:
        _write_tsv(Path(path)/(name+'.tsv'),rows,columns)


def verify_result(result):
    if result.get('evaluation_format')!=RESULT_FORMAT or result.get('evaluation_sha256')!=digest({k:v for k,v in result.items() if k!='evaluation_sha256'}):raise ValueError("Evaluation result integrity check failed.")


def _read_reviews(path,columns,index,key,hash_field):
    if path is None:return {}
    with Path(path).open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f,delimiter='\t')
        if reader.fieldnames!=columns:raise ValueError("Review worksheet columns changed: "+Path(path).name)
        rows={}
        for row in reader:
            if None in row or any(v is None for v in row.values()):raise ValueError("Malformed review worksheet row.")
            identity=row[key]
            if identity not in index or identity in rows or row[hash_field]!=index[identity][hash_field]:raise ValueError("Unknown, duplicate or changed review identity/hash.")
            if key!='case_id' and row.get('case_id')!=index[identity]['case_id']:raise ValueError("Worksheet case identity changed.")
            rows[identity]=row
    return rows


def score_result(result,case_reviews=None,answer_reviews=None,evidence_reviews=None):
    verify_result(result)
    cases={c['id']:{**c,'case_sha256':digest(c)} for c in result['suite']['cases']}
    observations={o['observation_id']:o for o in result['observations']}
    pool={u['review_id']:u for u in result['pool']}
    cr=_read_reviews(case_reviews,CASE_FIELDS,cases,'case_id','case_sha256')
    ar=_read_reviews(answer_reviews,ANSWER_FIELDS,observations,'observation_id','output_sha256')
    er=_read_reviews(evidence_reviews,EVIDENCE_FIELDS,pool,'review_id','unit_sha256')
    for rows,fields,allowed in [(cr,['reference_plan_correct'],{'','yes','no','uncertain'}),
                                 (ar,['plan_correct','answer_correct','citation_support','conditions_preserved','abstention_correct'],{'','yes','no','uncertain'}),
                                 (er,['verdict'],{'','relevant_supported','relevant_unsupported','irrelevant','uncertain'})]:
        for row in rows.values():
            if any(row[k] not in allowed for k in fields):raise ValueError("Unsupported reviewer judgment value.")
            if any(row[k] for k in fields) and (not row['reviewer'].strip() or not row['notes'].strip()):raise ValueError("Judgments require a reviewer and notes.")
    for row in ar.values():
        if row['review_seconds'] and (not row['review_seconds'].isdigit() or int(row['review_seconds'])>86400):raise ValueError("Review time must be integer seconds, at most 86400.")
        if observations[row['observation_id']]['status'] in {'planner_not_run','planner_error','invalid_plan'} and any(row[k] for k in ['answer_correct','citation_support','conditions_preserved']):raise ValueError("An unexecuted workflow has no answer to grade.")
    for row in er.values():
        if row['source_check'] not in {'','not_checked','record_only','abstract','full_text'} or row['filter_decision'] not in {'','correct','incorrect','uncertain'}:raise ValueError("Unsupported source-check or filtering judgment.")
        if row['verdict']=='relevant_supported' and (row['source_check'] not in {'abstract','full_text'} or not row['evidence_locator'].strip()):raise ValueError("Supported evidence requires an underlying abstract/full-text check and a locator/span.")
        if row['filter_decision'] and (not row['reviewer'].strip() or not row['notes'].strip()):raise ValueError("Filtering judgments require a reviewer and notes.")
    judgments={(pool[rid]['case_id'],pool[rid]['id']):row['verdict'] for rid,row in er.items()}
    positives={(case,uid) for (case,uid),v in judgments.items() if v=='relevant_supported'}
    approved={cid for cid,row in cr.items() if row['reference_plan_correct']=='yes'}
    ratio=lambda a,b:round(a/b,6) if b else None
    any_reviews=bool(approved or positives or any(any(row[k] for k in ['plan_correct','answer_correct','citation_support','conditions_preserved','abstention_correct']) for row in ar.values()) or any(row['verdict'] or row['filter_decision'] for row in er.values()))
    metrics={'status':'partially_reviewed' if any_reviews else 'review_pending',
             'evaluation_sha256':result['evaluation_sha256'],'suite_sha256':result['suite_sha256'],
             'cases':len(cases),'question_groups':len({c['group'] for c in cases.values()}),
             'case_splits':dict(Counter(c['split'] for c in cases.values())),
             'approved_reference_plans':len(approved),'pool_rows':len(pool),'unique_source_units':len({u['id'] for u in pool.values()}),
             'supported_pool_units':len(positives),'unjudged_or_uncertain_pool_rows':sum(judgments.get((u['case_id'],u['id']),'') in {'','uncertain'} for u in pool.values()),
             'planner_kind':result['planner_kind'],'arms':{},'filter_review':{},'scientific_improvement_established':False,
             'interpretation':'Descriptive pilot only. Review-pool recall is not corpus recall; software tests/draft plan agreement are not scientific accuracy.'}
    for arm in result['variants']:
        obs=[o for o in observations.values() if o['arm']==arm]
        returned={(o['case_id'],uid) for o in obs for uid in o['returned_units']}
        tp=len(returned & positives);negative=sum(judgments.get(k) in {'relevant_unsupported','irrelevant'} for k in returned)
        unknown=len(returned)-tp-negative
        executed=[o for o in obs if o['status'] not in {'planner_not_run','planner_error','invalid_plan'}]
        agreement=[o['draft_plan_agreement'] for o in obs if o['draft_plan_agreement'] is not None]
        approved_agreement=[o['draft_plan_agreement'] for o in obs if o['case_id'] in approved and o['draft_plan_agreement'] is not None]
        grading={}
        for field in ['plan_correct','answer_correct','citation_support','conditions_preserved','abstention_correct']:
            values=[ar[o['observation_id']][field] for o in obs if o['observation_id'] in ar and ar[o['observation_id']][field] in {'yes','no'}]
            grading[field]={'reviewed':len(values),'yes':values.count('yes'),'rate':ratio(values.count('yes'),len(values))}
        traces=[o['trace'] for o in obs if o['trace']]
        metrics['arms'][arm]={'variant':result['variants'][arm],'cases':len(obs),'statuses':dict(Counter(o['status'] for o in obs)),
            'executed_cases':len(executed),'answered_cases':sum(o['status']=='answered' for o in obs),
            'returned_case_units':len(returned),'judged_supported_returned':tp,'judged_unsupported_or_irrelevant_returned':negative,
            'unjudged_or_uncertain_returned':unknown,'judged_precision':ratio(tp,tp+negative),
            'precision_lower_bound':ratio(tp,len(returned)),'precision_upper_bound':ratio(tp+unknown,len(returned)),
            'review_pool_recall':ratio(tp,len(positives)) if executed else None,
            'draft_plan_comparisons':len(agreement),'draft_plan_agreement':ratio(sum(agreement),len(agreement)),
            'approved_plan_comparisons':len(approved_agreement),'approved_plan_agreement':ratio(sum(approved_agreement),len(approved_agreement)),
            'human_judgments':grading,'tool_calls':sum(o['tool_calls'] for o in obs),
            'model_calls':sum(t.get('model_calls',0) for t in traces),
            'elapsed_ms':round(sum(o['elapsed_ms'] for o in obs),3),
            'reported_usage':[t['usage'] for t in traces if t.get('usage')],
            'review_seconds':sum(int(ar[o['observation_id']]['review_seconds'] or 0) for o in obs if o['observation_id'] in ar)}
    for state in ['retained','excluded']:
        unique={}
        for rid,u in pool.items():
            if u['filter_state']==state and rid in er and er[rid]['filter_decision'] in {'correct','incorrect'}:
                value=er[rid]['filter_decision']
                if u['id'] in unique and unique[u['id']]!=value:raise ValueError("Conflicting filtering judgments for the same frozen source unit.")
                unique[u['id']]=value
        metrics['filter_review'][state]={'judged_unique_items':len(unique),'incorrect':list(unique.values()).count('incorrect'),
                                         'incorrect_decision_rate':ratio(list(unique.values()).count('incorrect'),len(unique))}
    for left,right,label in [('pharos','enriched','source_addition'),('enriched','reviewed','local_review'),('enriched','planner','planning')]:
        if left not in metrics['arms'] or right not in metrics['arms']:continue
        paired=[]
        for cid in cases:
            pair=[next((o for o in observations.values() if o['case_id']==cid and o['arm']==arm),None) for arm in [left,right]]
            if any(o is None or o['observation_id'] not in ar for o in pair):continue
            values=[ar[o['observation_id']]['answer_correct'] for o in pair]
            if all(v in {'yes','no'} for v in values):paired.append([int(v=='yes') for v in values])
        metrics[label]={'paired_reviewed_cases':len(paired),'answer_correct_delta':ratio(sum(r-l for l,r in paired),len(paired))}
    return metrics


def score_evaluation(path,output,*,case_reviews=None,answer_reviews=None,evidence_reviews=None):
    result=json.loads((Path(path)/'evaluation.json').read_text());metrics=score_result(result,case_reviews,answer_reviews,evidence_reviews)
    output=Path(output).resolve();source=Path(path).resolve()
    if output==source or source in output.parents:raise ValueError("Save reviewed scores outside the original results.")
    output=_new_directory(output)
    write_review_sheets(result,output)
    for name,p in [('case_reviews',case_reviews),('answer_reviews',answer_reviews),('evidence_reviews',evidence_reviews)]:
        if p:shutil.copyfile(p,output/(name+'.tsv'))
    metrics['review_files']={name:_file_sha(p) for name,p in [('case_reviews',case_reviews),('answer_reviews',answer_reviews),('evidence_reviews',evidence_reviews)] if p}
    metrics['scored_at']=utcnow()
    write_json(output/'metrics.json',metrics)
    (output/'report.html').write_text(evaluation_html(result,metrics),encoding='utf-8')
    return metrics


def evaluation_html(result,metrics):
    from .civic_context import context_html, overview_html
    esc=lambda s:escape(str(s),quote=True)
    display=lambda v:'Pending' if v is None else esc(v)
    table=''.join('<tr><td>'+esc(arm)+'</td><td>'+str(m['answered_cases'])+'/'+str(m['cases'])+'</td><td>'+str(m['unjudged_or_uncertain_returned'])+'</td><td>'+display(m['judged_precision'])+'</td><td>'+display(m['review_pool_recall'])+'</td><td>'+display(m['approved_plan_agreement'])+'</td></tr>' for arm,m in metrics['arms'].items())
    observations=[]
    for o in result['observations']:
        a=o.get('answer') or {};by_id={c['id']:c for c in a.get('citations',[])}
        statements=''.join('<li>'+esc(s['text'])+' '+esc(' '.join('['+cid+']' for cid in s['citation_ids']))
                           +''.join(context_html(by_id[cid]) for cid in s['citation_ids'])+'</li>' for s in a.get('summary',[]))
        citations=''.join('<details><summary>'+esc(c['id']+' | '+c['kind']+' | '+c['review_state'])+'</summary><pre>'+esc(json.dumps(c,indent=2))+'</pre></details>' for c in a.get('citations',[]))
        overview=overview_html(a['source_context_overview']) if a.get('source_context_overview') is not None else ''
        observations.append('<details><summary>'+esc(o['case_id']+' | '+o['variant']+' | '+o['status'])+'</summary><p>'+esc(o['question'])+'</p><p>'+esc(o['reason'])+'</p>'+overview+'<ul>'+statements+'</ul><details><summary>Plan and execution trace</summary><pre>'+esc(json.dumps({k:o[k] for k in ['observation_id','output_sha256','plan','trace','returned_units']},indent=2))+'</pre></details>'+citations+'</details>')
    evidence=[]
    for u in result['pool']:
        link='<a href="'+esc(u['source_url'])+'" target="_blank" rel="noopener noreferrer">Open source record</a>' if u['source_url'] else ''
        evidence.append('<details><summary>'+esc(u['case_id']+' | '+u['id']+' | '+u['filter_state'])+'</summary><p>'+esc(u['statement'])+'</p>'+link+'<pre>'+esc(json.dumps(u,indent=2))+'</pre></details>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BioGraph Steward evaluation</title>'
        '<style>body{max-width:1100px;margin:30px auto;padding:20px;font:16px/1.6 system-ui;color:#172b3a}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ccd9df;text-align:left;padding:10px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f7;padding:14px}details{margin:14px 0;border:1px solid #dce4e9;padding:12px;border-radius:8px}summary{cursor:pointer}.notice{background:#fff3dc;padding:18px;border-left:4px solid #ac7d2a}.small{font-size:14px;color:#506677}</style>'
        '<h1>BioGraph Steward evaluation</h1><p class="notice">'+esc(metrics['status'])+' — scientific improvement has not been established. Blank reviewer judgments remain unknown. Planner mode: '+esc(result['planner_kind'])+'.</p>'
        '<p>'+str(metrics['cases'])+' questions in '+str(metrics['question_groups'])+' groups; '+str(metrics['approved_reference_plans'])+' reviewer-approved scope plans. '+str(metrics['pool_rows'])+' question/source review rows; '+str(metrics['unique_source_units'])+' unique source units.</p>'
        '<table><thead><tr><th>Workflow</th><th>Answered</th><th>Unjudged returned units</th><th>Judged precision</th><th>Review-pool recall</th><th>Approved plan agreement</th></tr></thead><tbody>'+table+'</tbody></table>'
        '<h2>Reviewer worksheet</h2><p><a href="case_reviews.tsv" download>Download scope worksheet</a> · <a href="answer_reviews.tsv" download>Download answer worksheet</a> · <a href="evidence_reviews.tsv" download>Download evidence worksheet</a></p><p>Use <code>case_reviews.tsv</code> to review question scope, <code>answer_reviews.tsv</code> for output quality/time, and <code>evidence_reviews.tsv</code> for source support and filtering. Enter reviewer and notes for every judgment. A supported scientific claim requires an abstract/full-text check and a locator/span. Neutral variant IDs reduce repeated arm labels; their mapping is available below, so this is not a blinded study. Score completed sheets into a new directory with <code>python3 app.py evaluation-score</code>.</p>'
        '<p class="small">Use the result ZIP to obtain the three worksheets. Review a small subset first; no worksheet entry accepts a graph assertion or assigns a prediction label.</p>'
        '<h2>Questions and outputs</h2>'+''.join(observations)+'<h2>Source units, including excluded evidence</h2>'+''.join(evidence)
        +'<details><summary>Scope, metric definitions and limitations</summary><ul>'+''.join('<li>'+esc(t)+'</li>' for t in result['limitations'])+'</ul><pre>'+esc(json.dumps(metrics,indent=2))+'</pre></details>'
        '<details><summary>Frozen sources and variant mapping</summary><pre>'+esc(json.dumps({'suite_sha256':result['suite_sha256'],'evaluation_sha256':result['evaluation_sha256'],'sources':result['suite']['sources'],'variants':result['variants'],'budgets':result['suite']['budgets']},indent=2))+'</pre></details></html>')
