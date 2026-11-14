"""Sanitize saved fixed-budget aggregates; no ranking, model or case reader."""
import argparse
from html import escape
import json
from pathlib import Path

from biograph_steward.client import utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.scientific_assessment import _task_tree
from .archive import need, sealed
from .publish import read, public_paths_absent, table

FRAMES = ('primary','reserved')
ASPECTS = ('biological_process','molecular_function','cellular_component')
METHODS = ('deepgose','strict_alias_localplus')


def prepare(source, expected, freeze, freeze_expected, output):
    source, freeze = map(Path,(source,freeze))
    need(sha(source)==expected and sha(freeze)==freeze_expected,'saved shortlist source/freeze FILE differs.')
    result, policy = read(source), read(freeze)
    need(result.get('format')=='biograph-steward.deepgo-shortlist.v1.results'
         and policy.get('format')=='biograph-steward.deepgo-shortlist.v1.freeze'
         and result['freeze_file_sha256']==freeze_expected,'shortlist format/freeze binding differs.')
    need(result['k']==policy['k']==3 and policy['focus_namespace']=='molecular_function'
         and policy['previous_reference_and_metric_exposure'] is policy['no_new_shortlist_endpoint_values_seen'] is True,
         'frozen budget/focus/exposure differs.')
    need(result['runtime']==policy['runtime']=={'python':'3.10.12','numpy':'1.26.4','scipy':'1.13.1','pandas':'2.2.3'}
         and result['source_files_sha256']==policy['input_files_sha256'],'source/runtime binding differs.')
    need(result['primary_BPO_adoption_rule_changed'] is result['app_default_or_consumer_changed'] is False
         and result['raw_reference_or_forecast_rows_included'] is False,'primary/default or privacy scope differs.')
    rows = result['rows']; inventory={(f,a,m)for f in FRAMES for a in ASPECTS for m in METHODS}
    need(len(rows)==12 and {(r['frame'],r['namespace'],r['method'])for r in rows}==inventory,
         'all twelve profile/aspect rows required, including unfavorable outcomes.')
    for r in rows:
        den=policy['frames'][r['frame']]['denominators'][r['namespace']]
        ordinary, weighted=r['ordinary'],r['IA_weighted'];n=ordinary['eligible_proteins']
        need(r['k']==3 and n==den['eligible_proteins'] and weighted['eligible_proteins']==den['IA_eligible_proteins'],'eligible reference frame differs.')
        need(ordinary['TP']+ordinary['reference_unmatched_predictions']==ordinary['returned_candidates']
             and ordinary['unused_budget_slots']==3*n-ordinary['returned_candidates']
             and 0<=ordinary['TP']<=ordinary['returned_candidates']<=3*n
             and abs(ordinary['curator_supported_slots_per_fixed3_budget']-ordinary['TP']/(3*n))<=1e-12,
             'supported-slot yield or returned-budget identity differs.')
        need(ordinary['shortlist_is_ancestor_closed'] is False,'post-selection expansion changes the strict budget.')
        for kind, agreement in r['native_batch_point_agreement'].items():
            need(kind in ('ordinary','IA_weighted') and agreement['passed'] is True
                 and agreement['eligible_proteins']==r[kind]['eligible_proteins']
                 and agreement['columns']==['n','tp','fp','fn','pr','rc']
                 and agreement['relative_tolerance']==agreement['absolute_tolerance']==1e-12
                 and agreement['same_native_function_same_post_known_eligible_frame'] is True,
                 'full-frame six-column native agreement is required.')
        need(set(r['native_batch_point_agreement'])=={'ordinary','IA_weighted'},'both native readout checks required.')
    for f in FRAMES:
        for a in ASPECTS:
            matched=[r for r in rows if (r['frame'],r['namespace'])==(f,a)]
            need(len({r['native_reference_protein_order_sha256']for r in matched})==1,'paired protein order differs.')
    pairs=result['paired_comparisons']
    need(len(pairs)==6 and {(r['frame'],r['namespace'])for r in pairs}=={(f,a)for f in FRAMES for a in ASPECTS}
         and all(r['candidate']=='deepgose' and r['comparator']=='strict_alias_localplus'
             and r['metric']=='curator_supported_slots_per_fixed3_budget'
             and r['role']==('designated_focus'if r['namespace']=='molecular_function'else'secondary') for r in pairs),
         'all six matched-budget differences with frozen roles required.')
    for comparison in pairs:
        matched={r['method']:r for r in rows if (r['frame'],r['namespace'])==
                 (comparison['frame'],comparison['namespace'])}
        need(comparison['eligible_proteins']==matched['deepgose']['ordinary']['eligible_proteins']==
             matched['strict_alias_localplus']['ordinary']['eligible_proteins'],
             'paired comparison and both profile eligible populations differ.')
        difference=(matched['deepgose']['ordinary']['curator_supported_slots_per_fixed3_budget']-
                    matched['strict_alias_localplus']['ordinary']['curator_supported_slots_per_fixed3_budget'])
        need(abs(comparison['point_difference']-difference)<=1e-12,
             'paired point difference does not match saved profile yields.')
    need(result['uncertainty']=={'implementation':'scipy.stats.bootstrap','version':'1.13.1','paired':True,
        'draws':2000,'seed':20261113,'method':'percentile','confidence_level':.95,'batch':100,'multiplicity_adjusted':False},
        'paired uncertainty implementation or scope differs.')
    public=_task_tree(result,sanitize=True);_task_tree(public);public_paths_absent(public)
    need(public['rows']==rows and public['paired_comparisons']==pairs,'sanitization altered saved results.')
    report=sealed({'format':'biograph-steward.deepgo-shortlist.v1.public-results','created_at':utcnow(),
        'source_report_file_sha256':expected,'source_report_content_sha256':result['content_sha256'],
        'source_freeze_file_sha256':freeze_expected,'source_freeze_content_sha256':policy['content_sha256'],
        'results':public,'development_only':True,'primary_BPO_adoption_rule_unchanged':True,
        'app_default_or_consumer_changed':False,'operator_paths_or_raw_cases_included':False,
        'publisher_implementation_sha256':sha(__file__)})
    out=new_output(output,source,freeze);write_json(out/'report.json',report);render(report,out/'report.html')
    manifest=sealed({'format':'biograph-steward.deepgo-shortlist.v1.publication-manifest',
        'source_report_file_sha256':expected,'source_freeze_file_sha256':freeze_expected,
        'files':{n:sha(out/n)for n in ('report.json','report.html')},'profile_cells':12,'paired_intervals':6,
        'operator_paths_or_raw_cases_included':False,'app_default_or_consumer_changed':False})
    write_json(out/'publication_manifest.json',manifest);return report


def render(report,path):
    value=report['results'];esc=lambda x:escape(str(x),quote=True)
    cohorts={'primary':'Original PK','reserved':'Additional PK'}
    aspects={'biological_process':'BPO','molecular_function':'MFO','cellular_component':'CCO'}
    rows=value['rows']
    html=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fixed three-slot curator support</title><style>body{font:16px system-ui;line-height:1.5;max-width:1400px;margin:2rem auto;padding:0 1rem;color:#203343}.table{overflow:auto}table{border-collapse:collapse;font-size:13px;width:100%}th,td{padding:.6rem;border-bottom:1px solid #ccd5df;text-align:left}.scope{background:#fff1d5;padding:1rem}code{overflow-wrap:anywhere}</style>',
      '<h1>Curator support within a fixed three-slot review budget</h1><p class="scope">DEVELOPMENT on the same previously exposed 6,100-protein reference. MFO is the designated focus; all BPO/CCO results remain visible. This endpoint is neither whole-graph accuracy nor global Fmax. The earlier failed BPO adoption rule and LocalPlus default remain unchanged.</p>',
      '<p>Supported slots divide matching later curator annotations by three times the eligible population. Abstentions leave slots unused; missing reference annotations and unused slots are not labeled false biology. PPV among returned candidates is a separate quantity.</p>',
      table(['Cohort','Aspect','Profile','Eligible N','Supported slots / 3-budget','PPV among returned','Recall','Filled budget','Coverage'],
        [[cohorts[r['frame']],aspects[r['namespace']],r['method'],r['ordinary']['eligible_proteins'],
          *(r['ordinary'][k]for k in ('curator_supported_slots_per_fixed3_budget','PPV_among_returned','micro_recall','filled_slot_fraction','prediction_coverage'))]for r in rows]),
      '<h2>All six paired budget differences</h2><p>DeepGO minus strict LocalPlus; shared paired SciPy percentile resampling, 2,000 draws, seed 20261113. Conditional, not multiplicity adjusted or independent biological replication.</p>',
      table(['Cohort','Aspect','Role','Point difference','95% lower','95% upper'],
        [[cohorts[r['frame']],aspects[r['namespace']],r['role'],r['point_difference'],*r['paired_95_percentile_interval']]for r in value['paired_comparisons']]),
      '<h2>Specificity and related-term diagnostics</h2><p>An ancestor/descendant pair can occupy two slots. These counts and IA summaries describe the unchanged shortlist; they never filter or rerank it. Multiple related terms are not independent discoveries.</p>',
      table(['Cohort','Aspect','Profile','IA PPV','IA recall','Mean IA / returned','Supported IA / 3-budget','Lists with related pair','Related pairs'],
        [[cohorts[r['frame']],aspects[r['namespace']],r['method'],r['IA_weighted']['PPV_among_returned'],r['IA_weighted']['micro_recall'],
          *(r['ordinary'][k]for k in ('mean_IA_per_returned_term','curator_supported_IA_per_fixed3_budget','shortlists_with_ancestor_related_pair','ancestor_related_pairs'))]for r in rows]),
      '<h2>Boundaries</h2><ul>'+''.join('<li>'+esc(x)+'</li>'for x in value['limitations'])+'</ul>',
      '<p>Ranking uses the common native alias/fill representation and known/root/TOI qualification. Strict cardinality is an application-budget adaptation. No ancestor expansion follows selection; scores are not confidence probabilities.</p>',
      '<p><a href="report.json">Complete saved aggregates, all native checks and source/runtime pins</a> · <a href="publication_manifest.json">FILE manifest</a></p>',
      '<p>Source report FILE SHA256: <code>'+esc(report['source_report_file_sha256'])+'</code></p></html>']
    Path(path).write_text(''.join(html))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source','expected','freeze','freeze-expected','output'):p.add_argument('--'+key,required=True)
    v=prepare(**vars(p.parse_args()));print(json.dumps({'format':v['format'],'content_sha256':v['content_sha256']}))
