"""Publish a bounded aggregate-only development addendum, not an app change.

Reuses the application's existing tested aggregate-tree sanitizer. Complete
point inventories and paired intervals are preserved; only operator paths are
removed/replaced by their already saved FILE hashes. No raw labels are read.
"""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
from html import escape
import json
from pathlib import Path

from .run import read,write,sha,digest,need
from biograph_steward.scientific_assessment import _task_tree


def prepare(source,old_report,expected,output):
    source,old_report,output=map(Path,(source,old_report,output))
    original=read(source);old=read(old_report)
    need(sha(source)==expected and original['content_sha256']==digest({k:v for k,v in original.items()if k!='content_sha256'}),
         'development source aggregate differs.')
    need(original['earlier_240_report_file_sha256']==sha(old_report)
         and original['earlier_240_report_content_sha256']==old['content_sha256'],
         'earlier complete comparison binding differs.')
    value=deepcopy(original);value.pop('content_sha256')
    need(len(value['new_outcome_rows'])==6 and len(value['earlier_240_outcome_rows'])==240,
         'preserve the complete new and earlier outcome inventories.')
    for row in value['earlier_240_outcome_rows']:
        if 'source' in row:
            path=row.pop('source');need(path in old['native_aggregate_source_files_sha256'],'earlier native curve has no FILE binding.')
            row['source_curve_sha256']=old['native_aggregate_source_files_sha256'][path]
    public=_task_tree(value,sanitize=True);_task_tree(public)
    need(public['new_outcome_rows']==value['new_outcome_rows'],'sanitization changed a new native outcome.')
    need(public['paired_comparisons']==value['paired_comparisons'],'sanitization changed a paired interval.')
    output.mkdir(parents=True,exist_ok=False)
    prior={'format':'biograph-steward.combined-development-prior240.v1',
        'source_report_file_sha256':original['earlier_240_report_file_sha256'],
        'source_report_content_sha256':original['earlier_240_report_content_sha256'],
        'rows':public.pop('earlier_240_outcome_rows'),'denominators':public['denominators'],
        'raw_reference_or_forecast_rows_included':False,'operator_paths_included':False}
    prior['content_sha256']=digest(prior);write(output/'prior_240_outcomes.json',prior)
    public['earlier_240_inventory']={'file_name':'prior_240_outcomes.json','rows':240,
        'file_sha256':sha(output/'prior_240_outcomes.json'),'content_sha256':prior['content_sha256']}
    controls={'genemaniaplus','localplus','strict_alias_localplus','official_nonexperimental','official_prott5_cosine3','official_naive','official_blast','fastsinksourceplus'}
    public['prior_BPO_control_rows']=[r for r in prior['rows']if r['namespace']=='biological_process'and r['setting']=='partial'and r['method']in controls]
    baselines={(r['frame'],r['namespace']):r for r in prior['rows']if r['setting']=='partial'and r['method']=='strict_alias_localplus'}
    changes=[]
    for new in public['new_outcome_rows']:
        baseline=baselines[new['frame'],new['namespace']]
        changes.append({'frame':new['frame'],'namespace':new['namespace'],'eligible_proteins':new['eligible_proteins'],
            'comparison':'combined GM versus matched full strict Local',
            'candidate_status':new['status'],'comparator_status':baseline['status'],
            'point_differences':{name:new[name]-baseline[name]for name in ('micro_Fmax','IA_micro_Fmax','macro_Fmax','IA_macro_Fmax')}
                if new['status']==baseline['status']=='scored'else None,
            'candidate_fixed_0_5':new.get('fixed_0_5'),'comparator_fixed_0_5':baseline.get('fixed_0_5')})
    public['matched_profile_metric_changes']=changes
    report={'format':'biograph-steward.combined-development-publication.v1','created_at':datetime.now(timezone.utc).isoformat(),
        'source_report_file_sha256':expected,'source_report_content_sha256':original['content_sha256'],
        'results':public,'operator_paths_included':False,'raw_reference_or_forecast_rows_included':False,
        'live_graph_or_previous_comparison_modified':False,'source_sanitizer_implementation_sha256':sha(Path(__import__('biograph_steward.scientific_assessment',fromlist=['x']).__file__)),
        'producer_implementation_sha256':sha(__file__)}
    report['content_sha256']=digest(report)
    raw=json.dumps(report,ensure_ascii=True,allow_nan=False)
    need(not any(x in raw for x in ('/Users/','/home/','/private/','/tmp/','"case_id"','"protein_id"','"GO_ID"')),
         'operator paths or case identifiers remain in public output.')
    write(output/'report.json',report)
    render(report,output/'report.html')
    summary={'format':'biograph-steward.combined-development-compact-summary.v1',
        'source_public_report_file_sha256':sha(output/'report.json'),'source_public_report_content_sha256':report['content_sha256'],
        **{k:public[k]for k in ('scope','source','new_outcome_rows','matched_profile_metric_changes',
            'paired_comparisons','predeclared_development_retention_gate','oldGM_reserved','earlier_240_inventory','caveats')},
        'all_new_aspects_and_operating_point_tradeoffs_retained':True,'raw_cases_or_operator_paths_included':False}
    summary['content_sha256']=digest(summary);write(output/'summary.json',summary)
    manifest={'format':report['format']+'.manifest','created_at':report['created_at'],
        'report_content_sha256':report['content_sha256'],
        'files':{name:sha(output/name)for name in ('report.json','report.html','summary.json','prior_240_outcomes.json')},
        'operator_paths_or_raw_cases_included':False,'app_or_graph_modified':False}
    manifest['content_sha256']=digest(manifest);write(output/'publication_manifest.json',manifest)
    return report


def render(report,path):
    v=report['results'];esc=lambda x:escape(str(x),quote=True)
    def number(x):return 'Not reported'if x is None else format(x,'.6f')if type(x)is float else str(x)
    def table(headers,rows):
        return '<div class="table"><table><thead><tr>'+''.join('<th>'+esc(x)+'</th>'for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(number(x))+'</td>'for x in row)+'</tr>'for row in rows)+'</tbody></table></div>'
    cohorts={'primary':'Original PK','reserved':'Additional PK'}
    aspects={'biological_process':'Biological process','molecular_function':'Molecular function','cellular_component':'Cellular component'}
    methods={'combined_strict_genemaniaplus':'Full GM+ (development)','genemaniaplus':'Old scoped GM+',
        'localplus':'Old scoped Local+','strict_alias_localplus':'Full strict Local+',
        'official_nonexperimental':'Nonexperimental annotations','official_prott5_cosine3':'ProtT5 k=3',
        'official_naive':'Frequency','official_blast':'BLAST','fastsinksourceplus':'Old FSS+ (prior primary)'}
    def point(row):
        return [cohorts.get(row['frame'],row['frame']),aspects.get(row['namespace'],row['namespace']),methods.get(row['method'],row['method']),row['status'],row['eligible_proteins'],
            *(row.get(k)for k in ('micro_Fmax','IA_micro_Fmax','macro_Fmax','IA_macro_Fmax'))]
    new=v['new_outcome_rows'];allrows=new+v['prior_BPO_control_rows']
    controls={'combined_strict_genemaniaplus','genemaniaplus','localplus','strict_alias_localplus','official_nonexperimental','official_prott5_cosine3','official_naive','official_blast','fastsinksourceplus'}
    focus=[r for r in allrows if r['namespace']=='biological_process'and r['setting']=='partial'and r['method']in controls]
    headers=['Cohort','Aspect','Method','Status','Eligible N','Micro Fmax','IA micro','Macro','IA macro']
    gate=v['predeclared_development_retention_gate']
    parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Combined historical source and published GM</title><style>body{font:16px system-ui;line-height:1.5;max-width:1400px;margin:2rem auto;padding:0 1rem;color:#203343}table{border-collapse:collapse;font-size:13px;width:100%}th,td{padding:.6rem;border-bottom:1px solid #ccd5df;text-align:left}.table{overflow:auto}details{border:1px solid #ccd5df;padding:1rem;margin:1rem 0}.scope{background:#fff1d5;padding:1rem}code{overflow-wrap:anywhere}</style>',
        '<h1>Combined historical source and published GeneMANIA+</h1>',
        '<p class="scope">Exposed-label development comparison. The earlier 240 outcomes and original negative candidate remain unchanged. These are temporal curator-annotation recovery results, not whole-graph biological accuracy.</p>',
        '<p><strong>Predeclared development retention gate: '+('passed'if gate['passed']else'not passed')+'.</strong> No automatic app, graph or review change follows.</p>',
        '<h2>Biological-process comparison</h2>',table(headers,[point(r)for r in focus]),
        '<h2>All six new outcomes</h2><p>Original and additional cohorts contain 1,294 and 4,806 fixed protein identities; native eligible counts vary by GO aspect. Missing fixed-cutoff values remain not returned by the native author curve, not zero-valued precision or recall.</p>',table(headers,[point(r)for r in new]),
        '<h2>All-aspect changes versus full strict Local</h2>',table(['Cohort','Aspect','Micro difference','IA micro difference','Macro difference','IA macro difference'],
            [[cohorts[r['frame']],aspects[r['namespace']],*(r['point_differences'].get(k)if r['point_differences']else None for k in ('micro_Fmax','IA_micro_Fmax','macro_Fmax','IA_macro_Fmax'))]for r in v['matched_profile_metric_changes']]),
        '<h2>Fixed paired BPO comparisons</h2>',table(['Cohort','Candidate','Comparator','Readout','95% lower','95% upper','Mean difference'],
            [[cohorts[r['frame']],methods.get(r['candidate'],r['candidate']),methods.get(r['comparator'],r['comparator']),r['readout'],*r['paired_95_percentile_interval'],r['difference_mean']]for r in v['paired_comparisons']]),
        '<p>Intervals are conditional paired protein resamples; they are not independent studies or multiplicity-adjusted confirmation. Fmax optimizes over the unchanged native threshold grid and is not percent scientific accuracy.</p>',
        '<details><summary>Fixed-0.5 operating-point trade-offs, including the matched Local comparator</summary>',table(['Cohort','Aspect','Method','PPV','Recall','F1','Native status'],
            [[cohorts[r['frame']],aspects[r['namespace']],name,fixed.get('PPV'),fixed.get('recall'),fixed.get('F1'),fixed.get('status')]for r in v['matched_profile_metric_changes'] for name,fixed in (('Combined GM',r['candidate_fixed_0_5']or{}),('Full strict Local',r['comparator_fixed_0_5']or{}))]),'</details>',
        '<p><a href="prior_240_outcomes.json">Complete earlier 240 outcomes</a>, including every negative and unsupported row, remain available separately. The compact <a href="summary.json">summary.json</a> retains all six new cells and MFO/CCO/fixed-cutoff trade-offs.</p>',
        '<details><summary>Scientific boundaries and provenance</summary><p>'+esc(gate['rule'])+'</p><ul>'+''.join('<li>'+esc(x)+'</li>'for x in v['caveats'])+'</ul><p>Source aggregate FILE SHA256: <code>'+esc(report['source_report_file_sha256'])+'</code></p><p>Source content SHA256: <code>'+esc(report['source_report_content_sha256'])+'</code></p><p>Complete native Smin, threshold, count-agreement, interaction, source-runtime and FILE-pin metadata remain in report.json. No raw reference cases or forecast rows are published here.</p></details></html>']
    Path(path).write_text(''.join(parts))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source','old-report','expected','output'):p.add_argument('--'+key,required=True)
    r=prepare(**vars(p.parse_args()));print(json.dumps({'content_sha256':r['content_sha256']}))
