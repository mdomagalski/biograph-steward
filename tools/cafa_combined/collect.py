"""Collect native aggregate exports; no prediction, scoring or label parsing.

The immutable earlier240 outcomes are retained with six new development cells.
Only native saved curves and already checked bootstrap reports supply metrics.
"""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path

from .run import read,write,sha,digest,need

NAMESPACES=('biological_process','molecular_function','cellular_component')
METRICS={'micro_Fmax':'f_micro','IA_micro_Fmax':'f_micro_w',
         'macro_Fmax':'f','IA_macro_Fmax':'f_w'}


def native_rows(path):
    with Path(path).open(newline='')as stream:
        return list(csv.DictReader(stream,delimiter='\t'))


def sealed(path):
    value=read(path)
    need(value['content_sha256']==digest({k:v for k,v in value.items()if k!='content_sha256'}),
         'aggregate receipt seal differs: '+str(path))
    return value


def collect(combined,old_report,output):
    combined,old_report,output=map(Path,(combined,old_report,output))
    old=sealed(old_report);need(old['expected_outcome_slots']==240 and len(old['rows'])==240,
                              'earlier complete comparison inventory differs.')
    status=sealed(combined/'native_and_uncertainty_v1/status.json')
    need(status['status']=='COMPLETE_POINTS_COUNTS_AND_FIXED_UNCERTAINTY','native execution is not complete; preserve its failure/pending status.')
    producer=sealed(combined/'predictions_v2/predictions.json')
    need(producer['prior_common_raw_positive_rows_exactly_identical'] is True,'same-host forecast check failed.')
    pins={str(old_report):sha(old_report),str(combined/'native_and_uncertainty_v1/status.json'):sha(combined/'native_and_uncertainty_v1/status.json'),
          str(combined/'predictions_v2/predictions.json'):sha(combined/'predictions_v2/predictions.json')}
    denominators={(r['frame'],r['setting'],r['namespace']):r for r in old['denominators']}
    rows=[];native_reports={}
    for frame in ('primary','reserved'):
        base=combined/(frame+'_native_v1')/'partial/combined_strict_genemaniaplus'
        curve=base/'scores/evaluation_all_exact.tsv';fixed=base/'scores/fixed_threshold_0_5.json'
        allrows=native_rows(curve);fixedrows=read(fixed)['rows']
        pins.update({str(p):sha(p)for p in (curve,fixed,base/'contributions/agreement.json')})
        agreement=read(base/'contributions/agreement.json');need(agreement['author_point_agreement_passed'] is True,'new contribution/point gate failed.')
        bp=denominators[frame,'partial','biological_process']
        need((agreement['ordinary_eligible'],agreement['IA_weighted_eligible'],agreement['raw_reference_proteins'])==
             (bp['eligible_proteins'],bp['IA_eligible_proteins'],bp['author_recognized_target_IDs']),
             'BPO reference frame differs from prior native comparisons.')
        native_reports[frame]=agreement
        for ns in NAMESPACES:
            values=[r for r in allrows if r['ns']==ns]
            row={'frame':frame,'setting':'partial','method':'combined_strict_genemaniaplus','namespace':ns,
                 'eligible_proteins':denominators[frame,'partial',ns]['eligible_proteins'],
                 'IA_eligible_proteins':denominators[frame,'partial',ns]['IA_eligible_proteins'],
                 'source_curve_sha256':sha(curve),'native_curve_rows':len(values)}
            if not values:
                row.update(status='no_native_curve',reason='Unchanged author did not return this namespace; no zero score substituted.')
            else:
                need(all(math.isfinite(float(r[c]))for r in values for c in (*METRICS.values(),'s','s_w')),
                     'nonfinite native curve; preserve separately, do not silently score.')
                row['status']='scored'
                for name,column in METRICS.items():
                    best=max(values,key=lambda r:float(r[column]))
                    row[name]=float(best[column]);row[name+'_tau']=float(best['tau'])
                for name,column in (('unweighted_Smin','s'),('IA_weighted_Smin','s_w')):
                    best=min(values,key=lambda r:float(r[column]));row[name]=float(best[column]);row[name+'_tau']=float(best['tau'])
                at=max(values,key=lambda r:float(r['f_micro']))
                row['prediction_coverage_at_micro_Fmax']=float(at['cov'])
                selected=[r for r in fixedrows if r['namespace']==ns]
                need(len(selected)==1,'fixed-threshold native namespace is not unique.')
                row['fixed_0_5']=selected[0]
            rows.append(row)
    paired=[];uncertainty=[]
    for frame in ('primary','reserved'):
        path=combined/'native_and_uncertainty_v1'/(frame+'_bootstrap/report.json');r=sealed(path)
        need(r['draws']==2000 and r['seed']==20261113,'paired resampling differs.')
        pins[str(path)]=sha(path);uncertainty.append({'frame':frame,'report':r})
        paired.extend({'frame':frame,**row}for row in r['comparisons'])
    required=[r for r in paired if r['comparator']=='strict_alias_localplus']
    need(len(required)==4,'both readouts of both matched-source comparisons are required.')
    gate=all(r['paired_95_percentile_interval'][0]>0 for r in required)
    interaction_path=combined/'native_and_uncertainty_v1/interaction.json';interaction=read(interaction_path);pins[str(interaction_path)]=sha(interaction_path)
    result={'format':'biograph-steward.combined-development-results.v1',
        'title':'One exposed-label combination of historical source coverage and published GeneMANIA+',
        'scope':'Development reuse of already consumed CAFA5 PK annotations, not a fresh independent validation.',
        'model':'Unchanged published positive-only GeneMANIA/regularized Laplacian; alpha1,tol1e-5.',
        'source':{'nodes':20412,'weighted_pairs':985863,'training':'Official known_t0 only; no current/future GOA feature values.'},
        'new_outcome_slots':6,'status_counts':dict(Counter(r['status']for r in rows)),
        'new_outcome_rows':rows,'earlier_240_outcome_rows':old['rows'],
        'earlier_240_report_file_sha256':sha(old_report),'earlier_240_report_content_sha256':old['content_sha256'],
        'all_prior_controls_negatives_and_no_curve_outcomes_retained':True,
        'denominators':old['denominators'],'native_BPO_point_count_agreement':native_reports,
        'producer':producer,'paired_comparisons':paired,'uncertainty_reports':uncertainty,
        'original_cohort_four_cell_interaction':interaction,
        'oldGM_reserved':{'status':'unsupported_outside_original_source_graph','target_IDs':4806,
            'reason':'No valid old scoped GM output exists for these proteins; no invented zero-score superiority interval.'},
        'predeclared_development_retention_gate':{'passed':gate,
            'rule':'Both ordinary and IA BPO paired95% difference intervals versus matched full strict Local must be above zero on both existing cohorts.',
            'automatic_product_or_graph_change':False,'independent_confirmatory_gain_claimed':False},
        'caveats':old['caveats']+[
            'This new method/source cell was chosen after PK and NK/LK outcomes were exposed; positive outcomes are development evidence only.',
            'The original547 forecast and its benchmark are unchanged. A same-Brev547 replay supplies exact210-target reproducibility; cross-runtime value differences remain recorded.',
            'LocalPlus one-hop neighbor explanations cannot be attached to global GM diffusion scores.',
            'Full source profile includes topology, known training seeds and identifier qualification; four-cell differences are not a pure topology causal effect.'],
        'input_files_sha256':pins,'source_graph_reviews_or_prior_results_modified':False,
        'raw_reference_or_forecast_rows_included':False}
    result['content_sha256']=digest(result);output.mkdir(parents=True,exist_ok=False);write(output/'report.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('combined','old-report','output'):p.add_argument('--'+key,required=True)
    r=collect(**vars(p.parse_args()));print(json.dumps({'content_sha256':r['content_sha256'],'gate':r['predeclared_development_retention_gate']}))
