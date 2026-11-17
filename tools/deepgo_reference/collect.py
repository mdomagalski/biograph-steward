"""Collect six native development outcomes without a new scoring formula.

The complete earlier240+six combined-GM outcomes remain alongside this single
published model profile. Only saved native curves/point-count agreement and the
already fixed paired-bootstrap reports supply new values. No reference rows,
GO/protein cases, forecast scores or selection of a favorable aspect is read.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

from biograph_steward.client import utcnow, write_json
from biograph_steward.file_utils import new_output
from tools.cafa_combined.collect import native_rows, METRICS, NAMESPACES
from .archive import fingerprints, need, sealed
from .run import FORMAT, read_seal


def saved_point(values, fixed_rows, namespace):
    """Summarize native saved columns, retaining independently selected maxima."""
    if not values:
        return {'status':'no_native_curve',
            'reason':'Unchangedauthorreturnednonamespacecurve; nozeroorprecision/recallinvented.'}
    if not all(math.isfinite(float(row[column])) for row in values
               for column in (*METRICS.values(),'s','s_w')):
        return {'status':'nonfinite_native_curve',
            'reason':'Nativecurvecontainsnonfinitevalues; preserveitwithoutinventinganendpoint.'}
    result={'status':'scored'}
    for name, column in METRICS.items():
        best=max(values,key=lambda row:float(row[column]))
        result[name]=float(best[column]);result[name+'_tau']=float(best['tau'])
    for name, column in (('unweighted_Smin','s'),('IA_weighted_Smin','s_w')):
        best=min(values,key=lambda row:float(row[column]))
        result[name]=float(best[column]);result[name+'_tau']=float(best['tau'])
    micro=max(values,key=lambda row:float(row['f_micro']))
    result['prediction_coverage_at_micro_Fmax']=float(micro['cov'])
    fixed=[row for row in fixed_rows if row['namespace']==namespace]
    need(len(fixed)==1,'savednativefixed0.5namespacemissingorrepeated.')
    # Includes explicit no_native_curve/coverage statuses unchanged. The native
    # cov ratio may exceed1 in small source frames; never clamp it or call it a
    # probability. Existing benchmark source caveats remain part of the result.
    result['fixed_0_5']=fixed[0]
    return result


def collect(jobs, jobs_sha256, status, status_sha256, previous_report,
            previous_report_sha256, output):
    jobs,status,previous_report=map(Path,(jobs,status,previous_report))
    for path,pin in ((jobs,jobs_sha256),(status,status_sha256),(previous_report,previous_report_sha256)):
        need(fingerprints(path)['sha256']==pin,'sourceaggregateFILEpindiffers.')
    job=read_seal(jobs,FORMAT+'.native-jobs')
    execution=read_seal(status,FORMAT+'.native-continuation')
    old=read_seal(previous_report,'biograph-steward.combined-development-results.v1')
    need(execution['status']=='COMPLETE_POINTS_COUNTS_AND_FIXED_UNCERTAINTY'
         and execution['jobs_file_sha256']==jobs_sha256,
         'completefixednativepoint/count/uncertaintyrunrequired; preservefailedstatusotherwise.')
    need(len(old['earlier_240_outcome_rows'])==240 and len(old['new_outcome_rows'])==6,
         'earliercomplete240+sixmethodsourceoutcomesdiffer.')
    denominators={(row['frame'],row['setting'],row['namespace']):row for row in old['denominators']}
    pins={str(path):pin for path,pin in ((jobs,jobs_sha256),(status,status_sha256),(previous_report,previous_report_sha256))}
    rows,agreements=[],{}
    for frame,spec in job['jobs'].items():
        root=Path(spec['output'])/'partial/deepgose'
        curve=root/'scores/evaluation_all_exact.tsv';fixed=root/'scores/fixed_threshold_0_5.json'
        agreement_file=root/'contributions/agreement.json'
        agreement=json.loads(agreement_file.read_text())
        need(agreement['author_point_agreement_passed'] is True,'nativepoint/contributionagreementfailed.')
        bp=denominators[frame,'partial','biological_process']
        need((agreement['ordinary_eligible'],agreement['IA_weighted_eligible'],agreement['raw_reference_proteins'])==
             (bp['eligible_proteins'],bp['IA_eligible_proteins'],bp['author_recognized_target_IDs']),
             'BPOraw/ordinary/IAreferenceframediffersfromearliercomparators.')
        agreements[frame]=agreement
        native=native_rows(curve);fixed_rows=json.loads(fixed.read_text())['rows']
        for path in (curve,fixed,agreement_file):pins[str(path)]=fingerprints(path)['sha256']
        for namespace in NAMESPACES:
            values=[row for row in native if row['ns']==namespace]
            d=denominators[frame,'partial',namespace]
            rows.append({'frame':frame,'setting':'partial','method':'deepgose','namespace':namespace,
                'eligible_proteins':d['eligible_proteins'],'IA_eligible_proteins':d['IA_eligible_proteins'],
                'native_curve_rows':len(values),'source_curve_sha256':pins[str(curve)],
                **saved_point(values,fixed_rows,namespace)})
    need(len(rows)==6,'alltwocohorts/threeaspectsrequired.')
    paired,reports=[],{}
    for frame,spec in execution['bootstrap_reports'].items():
        path=Path(spec['report_file'])
        need(fingerprints(path)['sha256']==spec['report_file_sha256'],'bootstrapreportFILEdiffers.')
        report=read_seal(path,'biograph-steward.cafa5-paired-protein-bootstrap.v1')
        need(report['draws']==2000 and report['seed']==20261113
             and report['content_sha256']==spec['report_content_sha256'],'pairedresamplingscopediffers.')
        reports[frame]=report;pins[str(path)]=spec['report_file_sha256']
        paired.extend({'frame':frame,**row} for row in report['comparisons'])
    required={(frame,kind) for frame in ('primary','reserved') for kind in ('ordinary','IA_weighted')}
    need({(row['frame'],row['readout']) for row in paired}==required and len(paired)==4
         and all(row['candidate']=='deepgose' and row['comparator']=='strict_alias_localplus' for row in paired),
         'fixedbothcohorts/bothreadoutLocalcontrastsdiffer.')
    passed=all(row['paired_95_percentile_interval'][0]>0 for row in paired)
    result=sealed({'format':FORMAT+'.results','created_at':utcnow(),
        'title':'OnepublishedDeepGO-SEsequence/ontologyprofileonexposedCAFA5PKannotations',
        'scope':'DEVELOPMENTreuseofalreadyconsumed1,294+4,806PKtargets; notanewindependentwholegraphaccuracyestimate.',
        'new_outcome_slots':6,'new_outcome_rows':rows,'status_counts':dict(Counter(row['status'] for row in rows)),
        'earlier_240_outcome_rows':old['earlier_240_outcome_rows'],
        'earlier_six_combined_GM_outcome_rows':old['new_outcome_rows'],
        'earlier_complete_comparison_file_sha256':previous_report_sha256,
        'all_prior_controls_negatives_and_no_curve_outcomes_retained':True,
        'denominators':old['denominators'],'native_BPO_point_count_agreement':agreements,
        'paired_comparisons':paired,'uncertainty_reports':reports,
        'predeclared_development_retention_gate':{'passed':passed,
            'rule':'BothordinaryandIA BPOpaired95%lowerdifferenceboundsversusfullstrictLocalabovezeroinBOTHcohorts.',
            'automatic_product_or_graph_change':False,'independent_confirmatory_gain_claimed':False},
        'input_files_sha256':pins,'raw_reference_or_forecast_rows_included':False,
        'caveats':old['caveats']+[
            'PublishedDeepGO-SEsix-checkpointensembles/first1022residues/float32averaging, correctedCCartifactandnativeCLIparity; noauthorGATmodelreconstruction.',
            'Rawpre-presentationmodelvaluesareevaluated, notthedefaultCLI0.1cut/three-decimaldisplay.',
            'Reported2021trainingversusLocal2023knownseedsisapracticalprofilecomparison, notisolatedalgorithm, PPIincrementoraxiom-onlycausaleffect.',
            'Actualauthortrainingmembership/homologydisjointnesswasnotreconstructed; PKdoesnotclaimpreviouslyunseenproteins.',
            'NoqualifiedMLPcontrolcheckpointwasfoundinthetwosuppliedinferencearchives; nonewasinventedorretrained.',
            'Missingdatedsource-sequencesretainalloriginalevaluationdenominators; nomodernfallbackorreferencecoveragefilter.',
            'Fmaxoptimizesabenchmarkthreshold; allfixed0.5tradeoffsandmacro/IAresultsretained.Noacceptanceprobabilityorautomaticbiologicalclaimisassigned.']})
    out=new_output(output,jobs,status,previous_report)
    write_json(out/'report.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('jobs','jobs-sha256','status','status-sha256','previous-report','previous-report-sha256','output'):
        parser.add_argument('--'+key,required=True)
    value=collect(**vars(parser.parse_args()))
    print(json.dumps({'format':value['format'],'content_sha256':value['content_sha256'],
        'retention_gate':value['predeclared_development_retention_gate']['passed']}))
