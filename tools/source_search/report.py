"""Render only sealed retrieval aggregates, never questions or reference IDs."""
import argparse
import html
import json

from tools.biored_agent.report import aggregate_page,verified
from biograph_steward.file_utils import sha

NAMES={'direct_native_query':'One native full-question query',
       'unskilled_agent':'Nano controller, base procedure',
       'procedure_skill_agent':'Same controller + reviewed search skill'}


def render(source,output,diagnostic=None):
    value=verified(source)
    if value.get('format')!='biograph-steward.source-search-reference-comparison.v1':
        raise ValueError('Not a supported sealed source-search aggregate.')
    esc=html.escape
    percent=lambda x:'unavailable'if x is None else f'{100*x:.2f}%'
    shown=lambda x:'unreported'if x is None else str(x)
    rows=[];costs=[];trajectories=[]
    for name,label in NAMES.items():
        m=value['metrics'][name];c=value['execution_costs'][name];tokens=c['observed_token_counts']
        fields=[label,str(m['fixed_questions']),str(m['scorable_reference_questions']),
            percent(m['mean_reference_recall_at_10']),percent(m['mean_reference_hit_at_10']),
            str(m['returned_IDs']),str(m['exact_get_resolved_article_IDs']),
            json.dumps(m['system_status_counts'],sort_keys=True)]
        rows.append('<tr>'+''.join('<td>'+esc(x)+'</td>'for x in fields)+'</tr>')
        fields=[label,shown(c['model_calls']),shown(c['tokenizer_model_service_requests']),
            shown(c['native_process_executions']),shown(c['direct_fetch_invocations']),shown(c['cache_hits']),
            shown(tokens.get('prompt_tokens')),shown(tokens.get('completion_tokens')),
            shown(c['exact_upstream_HTTP_request_count'])]
        costs.append('<tr>'+''.join('<td>'+esc(x)+'</td>'for x in fields)+'</tr>')
        if name in value['agent_trajectory_summaries']:
            t=value['agent_trajectory_summaries'][name]
            trajectories.append('<h3>'+esc(label)+'</h3><p>'+esc(
                f"Early finishes: {t['early_finish_cases_before_four_calls']}; second search used: {t['cases_using_second_search']}; "
                f"abstract requested: {t['cases_requesting_abstract']}; distinct successfully opened article IDs: "
                f"{t['distinct_successfully_opened_article_ID_count']}; controller feedback events: "
                f"{sum(t.get('controller_feedback_event_counts',{}).values())}.")+'</p><pre>'+esc(json.dumps(t['tool_order_counts'],indent=2))+'</pre>')
    contrasts=[]
    for c in value.get('paired_comparisons')or []:
        low,high=c['paired_95_percentile_interval']
        contrasts.append('<li>'+esc(f"{NAMES[c['candidate']]} minus {NAMES[c['comparator']]}: "
            f"{100*c['observed_mean_difference']:+.2f} percentage points; paired 95% interval "
            f"{100*low:+.2f} to {100*high:+.2f} points.")+'</li>')
    limitations=''.join('<li>'+esc(x)+'</li>'for x in value['limitations'])
    diagnostic_html=''
    if diagnostic is not None:
        d=verified(diagnostic)
        if d.get('format')!='biograph-steward.first-search-execution-diagnostic.v1' or d['lineage']['main_report_file_sha256']!=sha(source):
            raise ValueError('First-attempt diagnostic does not match this assessment.')
        diagnostic_rows=[]
        for name in ('unskilled_agent','procedure_skill_agent'):
            r=d['metrics'][name]
            fields=[NAMES[name],percent(r['first_attempt_mean_reference_recall_at_10']),
                percent(r['final_output_mean_reference_recall_at_10']),
                percent(value['metrics']['direct_native_query']['mean_reference_recall_at_10']),
                json.dumps(r['first_attempt_statuses'],sort_keys=True)]
            diagnostic_rows.append('<tr>'+''.join('<td>'+esc(x)+'</td>'for x in fields)+'</tr>')
        diagnostic_html=f'''<section><h2>Where can useful retrieval be lost?</h2>
<p>This separately sealed error-localization diagnostic was chosen after execution failures were observed, before reference release.
It uses only the first attempted search, including failed, empty and partial results, in native order through ten IDs.
A case with no executed search stays empty; later successful queries, best-query selection and unions are excluded.</p>
<div class="table"><table><thead><tr><th>Agent condition</th><th>First search Recall@10</th><th>Final Recall@10</th>
<th>Direct native control Recall@10</th><th>First-search statuses</th></tr></thead><tbody>{''.join(diagnostic_rows)}</tbody></table></div>
<p>This locates loss between query retrieval and completion/ranking. It is not a new primary comparison or a validated replacement pipeline.
It makes no hypothetical cost-saving claim; all actual executed calls remain in the main cost table.</p></section>'''
    feedback_note=('<p>This is the separately frozen recoverable-duplicate follow-up. Only an exact duplicate executed-search request gets an explicit error observation within the same four-call budget. It performs no duplicate source/cache call; all other invalid or model outputs remain terminal. The original fail-fast comparison is retained separately.</p>'
        if value.get('duplicate_feedback_enabled')else '')
    body=f'''<section><h1>Can a reusable search procedure improve paper retrieval?</h1>
<p class="scope">{esc(value['scope'])}</p><p>Twenty-four fixed human-authored BioASQ11 questions: twelve factoid and twelve list questions.
Both agent arms use the same NVIDIA Nano 8B model, two-search/one-abstract tool budget and four-call cap.
Only the short attributed search procedure differs. The direct native query has a smaller tool budget and no model cost.</p>
<p>All fixed forecasts are sealed before selected reference-document values are interpreted. Failed and unavailable cases stay in the denominator.
This compares paper retrieval, not whether a paper establishes a scientific claim or adds independent evidence beyond Pharos.</p>{feedback_note}</section>
<section><h2>All fixed arms</h2><div class="table"><table><thead><tr><th>Method</th><th>Questions</th><th>Scorable references</th>
<th>Mean Recall@10</th><th>Hit@10</th><th>Returned IDs</th><th>Resolved abstract IDs</th><th>Statuses</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div><p>Recall divides matched reference PMIDs by the question's known-positive document list;
questions receive equal weight. A returned candidate is a retrieval handoff, not a claim it was opened or verified.</p>
<ul>{''.join(contrasts)or '<li>Paired uncertainty unavailable; empty reference cases remain explicit.</li>'}</ul>
<p>Intervals use 2,000 shared question-bootstrap draws and are conditional descriptions of this small public retrospective sample.</p></section>
{diagnostic_html}<section><h2>Actual choices and source inspection</h2>{''.join(trajectories)}
<p>Variable trajectories do not establish benefit. Only resolved exact-PMID abstract gets count as successfully opened;
search-result titles and final handed-off IDs remain distinguishable from read source text.</p></section>
<section><h2>Recorded execution costs</h2><div class="table"><table><thead><tr><th>Method</th><th>Model requests</th>
<th>Tokenizer requests</th><th>Native search processes</th><th>Exact-fetch invocations</th><th>Cache hits</th>
<th>Input tokens</th><th>Output tokens</th><th>Upstream HTTP requests</th></tr></thead><tbody>{''.join(costs)}</tbody></table></div>
<p>Native process counts are not HTTP counts: the pinned upstream client can make more than one exchange internally.
Token usage is recorded when returned; no dollar-price table is assumed. Shared immutable source captures avoid re-querying identical requests.</p></section>
<section><h2>Interpretation and reproducibility</h2><ul>{limitations}</ul>
<p>Excluding known viewed publisher examples does not certify unseen evaluation. Complete model-training and native-tool development/tuning membership are not independently audited for these public questions.</p>
<p>The free capability uses the pinned <a href="https://github.com/genomoncology/biomcp/releases/tag/v0.9.3">BioMCP 0.9.3</a>
PubMed search plus the existing exact-PMID parser. It does not require paid PaperQA/Edison access.
Only PubMed is selected; native ontology suggestions are disabled through the published source-disable option.
Source dataset: <a href="https://doi.org/10.5281/zenodo.7655130">author BioASQ11 deposit</a>, CC-BY-2.5.
No live graph was changed.</p><pre>{esc(json.dumps(value['lineage'],indent=2))}</pre></section>'''
    return aggregate_page('Bounded reference-paper retrieval',body,value,output)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    p.add_argument('--diagnostic');a=p.parse_args();print(render(a.source,a.output,a.diagnostic))
