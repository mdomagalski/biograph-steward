"""Aggregate-only publication of all42 native NK/LK profile outcomes."""
import argparse
from html import escape
from pathlib import Path
import json

from biograph_steward.client import utcnow,write_json,digest
from biograph_steward.file_utils import new_output,sha
from biograph_steward.scientific_assessment import _task_tree
from .archive import need,sealed
from .publish import read,public_paths_absent,table,METRICS

SETTINGS=('no_knowledge','limited')
ASPECTS=('biological_process','molecular_function','cellular_component')
CONTROLS=('strict_alias_localplus','official_nonexperimental')


def prepare(source,expected,freeze,freeze_expected,previous,previous_expected,output):
    source,freeze,previous=map(Path,(source,freeze,previous))
    for p,h in ((source,expected),(freeze,freeze_expected),(previous,previous_expected)):
        need(sha(p)==h,'saved nonPK aggregate/freeze/previous FILE differs.')
    result,policy,old=map(read,(source,freeze,previous))
    need(result.get('format')=='biograph-steward.deepgo-nonpk-evaluation.v1.results'
         and policy.get('format')=='biograph-steward.deepgo-nonpk-evaluation.v1.freeze'
         and result['evaluation_freeze_file_sha256']==freeze_expected
         and result['previous_aggregate_file_sha256']==previous_expected,'native nonPK source binding differs.')
    need(result['known_exclusion']is policy['known_exclusion']is None
         and result['focus_namespace']==policy['focus_namespace']=='molecular_function'
         and policy['previous_reference_outcomes_exposed']is True,'do not substitute PK exclusion/focus semantics.')
    need(result['runtime']=={'python':'3.10.12','numpy':'1.26.4','scipy':'1.13.1','pandas':'2.2.3'},'measurement runtime differs.')
    need(result['producer_protocol_file_sha256']==policy['producer_protocol_file_sha256']
         and result['forecast_manifest_file_sha256']==policy['forecast_manifest_file_sha256']
         and result['lifecycle_done_file_sha256']==policy['lifecycle_done_file_sha256'], 'completed forecast/restore lineage differs.')
    need(result['earlier_36_outcome_rows']==old['rows'] and len(old['rows'])==36
         and result['denominators']==old['denominators'],'all previous36 outcomes and denominators must remain exact.')
    new=result['new_outcome_rows']
    need(result['expected_outcome_slots']==42 and len(new)==6
         and {(r['setting'],r['namespace'],r['method'])for r in new}=={(s,a,'deepgose')for s in SETTINGS for a in ASPECTS},
         'all six new profile cells/42total outcomes required.')
    denominators={(d['setting'],d['namespace']):d for d in old['denominators']}
    for r in new:
        d=denominators[r['setting'],r['namespace']]
        need(r['known_exclusion']is None and r['eligible_proteins']==d['eligible_proteins']
             and r['IA_eligible_proteins']==d['IA_eligible_proteins'],'new native eligible denominator differs.')
    pairs=result['paired_comparisons'];required={(s,c,k)for s in SETTINGS for c in CONTROLS for k in ('ordinary','IA_weighted')}
    need(len(pairs)==8 and {(r['setting'],r['comparator'],r['readout'])for r in pairs}==required
         and all(r['namespace']=='molecular_function'and r['candidate']=='deepgose'for r in pairs),'all eight MFO contrasts against both controls required.')
    agreements=result['native_MFO_point_count_agreements']
    need(set(agreements)=={s+'/'+m for s in SETTINGS for m in ('deepgose',*CONTROLS)},'all six fresh MFO count agreements required.')
    for key,a in agreements.items():
        setting,_=key.split('/');d=denominators[setting,'molecular_function']
        need(a['author_point_agreement_passed']is True and a['known_exclusion']is None
             and a['namespace']=='molecular_function' and a['raw_reference_proteins']==d['author_recognized_target_IDs']
             and a['ordinary_eligible']==d['eligible_proteins'] and a['IA_weighted_eligible']==d['IA_eligible_proteins']
             and all(x['max_absolute_curve_difference']<=1e-12 for x in a['checks'].values()), 'native no-exclusion MFO count gate differs.')
    reports=result['uncertainty_reports'];need(set(reports)==set(SETTINGS),'both shared-draw reports required.')
    for setting,b in reports.items():
        need(b['content_sha256']==digest({k:v for k,v in b.items()if k!='content_sha256'})
             and b['draws']==2000 and b['seed']==20261113 and b['numpy']=='1.26.4'
             and b['shared_protein_samples_across_all_arms']is True
             and b['raw_proteins']==denominators[setting,'molecular_function']['author_recognized_target_IDs']
             and set(b['scores'])=={'deepgose',*CONTROLS},'shared native MFO uncertainty scope differs.')
        need([{'setting':setting,'namespace':'molecular_function',**r}for r in b['comparisons']]==
             [r for r in pairs if r['setting']==setting],'nested and flat intervals differ.')
    need(result['all_existing_controls_negatives_and_missing_retained']is True
         and result['app_default_or_consumer_changed']is result['original_PK_protocol_or_results_changed']is False
         and result['new_reference_release']is result['raw_reference_or_forecast_rows_included']is False,
         'no-adoption/old-result/privacy flags differ.')
    public=_task_tree(result,sanitize=True);_task_tree(public);public_paths_absent(public)
    need(public['new_outcome_rows']==new and public['earlier_36_outcome_rows']==old['rows']
         and public['paired_comparisons']==pairs,'sanitizer changed a native outcome or contrast.')
    report=sealed({'format':'biograph-steward.deepgo-nonpk-evaluation.v1.public-results','created_at':utcnow(),
        'source_report_file_sha256':expected,'source_report_content_sha256':result['content_sha256'],
        'evaluation_freeze_file_sha256':freeze_expected,'previous36_report_file_sha256':previous_expected,
        'results':public,'outcome_slots':42,'MFO_paired_intervals':8,'development_exposed_reference':True,
        'operator_paths_or_raw_cases_included':False,'automatic_adoption':False,
        'publisher_implementation_sha256':sha(__file__)})
    out=new_output(output,source,freeze,previous);write_json(out/'report.json',report);render(report,out/'report.html')
    write_json(out/'publication_manifest.json',sealed({'format':'biograph-steward.deepgo-nonpk-evaluation.v1.publication-manifest',
        'source_report_file_sha256':expected,'files':{n:sha(out/n)for n in ('report.json','report.html')},
        'outcome_slots':42,'MFO_paired_intervals':8,'operator_paths_or_raw_cases_included':False,'automatic_adoption':False}))
    return report


def render(report,path):
    v=report['results'];esc=lambda x:escape(str(x),quote=True)
    names={'no_knowledge':'No knowledge (NK)','limited':'Limited knowledge (LK)'}
    def row(r):return[names[r['setting']],r['namespace'],r['method'],r['status'],r['eligible_proteins'],r['IA_eligible_proteins'],
        *(r.get(k)for k in METRICS),r.get('unweighted_Smin'),r.get('IA_weighted_Smin')]
    headers=['Setting','Aspect','Profile','Native status','Eligible N','IA N','Micro Fmax','IA micro','Macro','IA macro','Smin','IA Smin']
    new=v['new_outcome_rows'];old=v['earlier_36_outcome_rows']
    focus=[r for r in new+old if r['namespace']=='molecular_function'and r['method']in ('deepgose',*CONTROLS)]
    parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DeepGO native NK/LK development comparison</title><style>body{font:16px system-ui;line-height:1.5;max-width:1450px;margin:2rem auto;padding:0 1rem;color:#203343}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:.6rem;border-bottom:1px solid #ccd5df;text-align:left}.table{overflow:auto}.scope{background:#fff1d5;padding:1rem}details{margin:1rem 0}code{overflow-wrap:anywhere}</style>',
      '<h1>DeepGO on the existing lower-knowledge reference</h1><p class="scope">DEVELOPMENT: these NK/LK reference outcomes were previously exposed. MFO is the designated focus; all42 outcomes and eight intervals are retained. Knowledge category does not establish unseen training sequences. No independent-study, whole-graph-accuracy or automatic-adoption claim is made.</p>',
      '<h2>Molecular function against both fixed controls</h2>',table(headers,[row(r)for r in focus]),
      '<h2>All eight paired MFO intervals</h2>',table(['Setting','Comparator','Readout','95% lower','95% upper','Mean difference'],
        [[names[r['setting']],r['comparator'],r['readout'],*r['paired_95_percentile_interval'],r['difference_mean']]for r in v['paired_comparisons']]),
      '<p>DeepGO minus comparator; native 2,000 shared protein draws, seed20261113. Conditional descriptive intervals are not independent studies or multiplicity-adjusted confirmation. Small native MFO populations remain explicit.</p>',
      '<h2>All six new native outcomes</h2>',table(headers,[row(r)for r in new]),
      '<details><summary>Complete unchanged earlier36 outcomes, including every control and missing/negative state</summary>',table(headers,[row(r)for r in old]),'</details>',
      '<h2>Fixed0.5 operating points</h2><p>Missing native values stay not returned. The same numeric score is not calibrated confidence.</p>',
      table(['Setting','Aspect','Profile','PPV','Recall','F1','Native status'],
        [[names[r['setting']],r['namespace'],r['method'],*((r.get('fixed_0_5')or{}).get(k)for k in ('PPV','recall','F1','status'))]for r in new+[r for r in old if r['namespace']=='molecular_function'and r['method']in CONTROLS]]),
      '<h2>Source and interpretation</h2><p>The same official no-exclusion pipeline is used: exclude=None,fill,normcafa,commonontology/IA/TOI,noorphans and fixed.001grid. The PK known-mask adapter is not used. Fmax maximizes a benchmark threshold; it is not percent scientific accuracy.</p><ul>',
      ''.join('<li>'+esc(x)+'</li>'for x in v['limitations']),'</ul>',
      '<p><a href="report.json">All42 outcomes, eight intervals, native checks and source/runtime pins</a> · <a href="publication_manifest.json">FILE manifest</a></p>',
      '<p>Source report FILE SHA256: <code>'+esc(report['source_report_file_sha256'])+'</code></p></html>']
    Path(path).write_text(''.join(parts))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source','expected','freeze','freeze-expected','previous','previous-expected','output'):p.add_argument('--'+key,required=True)
    v=prepare(**vars(p.parse_args()));print(json.dumps({'format':v['format'],'content_sha256':v['content_sha256']}))
