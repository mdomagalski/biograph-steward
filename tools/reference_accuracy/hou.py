"""Positive-label recovery against the unchanged published HOU held-out test.

Unlisted compartments are UNKNOWN. This measures recovery of released positive
curator/imaging labels, without inventing specificity or biological precision.
The exact source-only crosswalk and five arms must be frozen before labels.
"""
from collections import Counter
import argparse
import csv
import json
from pathlib import Path

from biograph_steward.client import utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.go_context_inspection import load_go_context
from tools.reference_accuracy import mitocarta as m

ARMS = ('A_raw_Pharos_scope_qualified', 'A_retained_scope_qualified',
        'B_native_location_scope_qualified', 'C_native_experimental_scope_qualified',
        'A_raw_Pharos_author_coarse_control')
LEVELS = ('level1', 'level2', 'level3')


def read_spec(spec):
    return json.loads(m.pinned(spec['file'], spec['sha256']).read_text())


def validate_maps(source, qualified):
    main = qualified['qualified_exact_GO_crosswalk']; coarse = source['crosswalk']
    m.need(bool(main) and all(coarse.get(k) == v for k, v in main.items()), 'qualified map is not an author-map subset.')
    m.need(not {'GO:0016020', 'GO:0005737', 'GO:0005634'} & main.keys(), 'lossy generic mapping entered main profile.')
    m.need(set(main.values()) <= set(source['level1']) and
           set(source['level1_to_level2']) == set(source['level1_to_level3']) == set(source['level1']),
           'released label hierarchy differs.')
    return main, coarse


def project(labels, source):
    if labels is None:
        return {level: None for level in LEVELS}
    return {'level1': sorted(labels),
        'level2': sorted({source['level1_to_level2'][x] for x in labels}),
        'level3': sorted({source['level1_to_level3'][x] for x in labels})}


def forecast(original, retained, native, eligibility, source, qualified, active, recognized):
    main, coarse = validate_maps(source, qualified)
    subjects = {r['protein_id'] for r in eligibility['rows'] if r['primary_source_eligible']}
    complete = {r['protein_id']: r['Pharos_GO_documented_complete'] for r in eligibility['rows']}
    output = {a: {p: {} for p in subjects} for a in ARMS}
    for arm in ARMS:
        crosswalk = coarse if arm == ARMS[-1] else main
        for label in source['level1']:
            terms = {uid for uid, target in crosswalk.items() if target == label}
            if arm in (ARMS[0], ARMS[1], ARMS[4]):
                graph = retained if arm == ARMS[1] else original
                rows = m.graph_predictions(graph, subjects, complete, terms, recognized)
            else:
                rows, _ = m.native_predictions(native, subjects, terms, active, experimental=arm == ARMS[3])
            for pid, row in rows.items(): output[arm][pid][label] = row['prediction']
        for pid in subjects:
            rows = output[arm][pid]
            # All labels share input-source availability. None stays abstention.
            m.need(len({v is None for v in rows.values()}) == 1, 'inconsistent source availability across labels.')
            labels = None if any(v is None for v in rows.values()) else {k for k, v in rows.items() if v == 1}
            output[arm][pid] = project(labels, source)
    return output


def read_test(path, expected, source):
    path = m.pinned(path, expected)
    result = {}
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        m.need(reader.fieldnames == ['uniprot_id','ensembl_id','level1','level2','level3','sequence'], 'released test schema differs.')
        for row in reader:
            uid = row['uniprot_id']
            m.need(uid and ('UniProtKB:' + uid) not in result, 'missing or duplicate exact test accession.')
            labels = {}
            for level in LEVELS:
                values = row[level].split(';') if row[level] else []
                m.need(len(values) == len(set(values)) and set(values) <= set(source[level]), 'unknown/duplicate author label.')
                labels[level] = sorted(values) if values else None
            result['UniProtKB:' + uid] = labels
    m.pinned(path, expected)
    return result


def positive_metrics(gold, predictions, classes):
    """Every released positive contributes; missing predictions remain unavailable.

    Recovery is operational coverage of positive reference labels. It does not
    give missing/unreported compartments a biological false label.
    """
    m.need(set(gold) == set(predictions), 'comparison must preserve the complete frozen frame.')
    total = recovered = unknown_output = predicted = unavailable = unavailable_labels = 0
    macro = []; per_class = {c: {'reference_positive':0, 'recovered':0} for c in classes}
    per_protein = {}
    for pid, values in gold.items():
        pred = predictions[pid]
        if values is None:
            per_protein[pid] = None; continue
        target = set(values); output = set(pred) if pred is not None else set()
        m.need(target <= set(classes) and output <= set(classes), 'unknown reference/prediction label.')
        hit = len(target & output); total += len(target); recovered += hit
        predicted += len(output); unknown_output += len(output - target)
        if pred is None: unavailable += 1; unavailable_labels += len(target)
        recall = hit / len(target) if target else None
        if recall is not None: macro.append(recall)
        per_protein[pid] = {'reference_positive':len(target),'recovered':hit,
            'source_unavailable':pred is None,'positive_reference_recovery':recall}
        for label in target:
            per_class[label]['reference_positive'] += 1
            per_class[label]['recovered'] += int(label in output)
    for row in per_class.values():
        row['recall'] = row['recovered'] / row['reference_positive'] if row['reference_positive'] else None
    return {'frozen_protein_rows':len(gold), 'reference_positive_labels':total,
        'recovered_reference_positive_labels':recovered,
        'reference_positive_labels_not_recovered':total-recovered,
        'predicted_labels':predicted,'extra_predicted_labels_truth_unknown':unknown_output,
        'unavailable_source_proteins':unavailable,'unavailable_source_reference_positive_labels':unavailable_labels,
        'micro_positive_reference_recovery':recovered/total if total else None,
        'macro_per_protein_positive_reference_recovery':sum(macro)/len(macro) if macro else None,
        'available_source_positive_reference_recovery':recovered/(total-unavailable_labels) if total>unavailable_labels else None,
        'per_class':per_class,'biological_false_positive_labels_assigned':0,
        'precision':None,'specificity':None,'F1':None,'MCC':None,'confidence_interval':None}, per_protein


def assess(test, forecasts, primary_ids, all_ids, source):
    frame = sorted(primary_ids & test.keys()); metrics = {}; private = {}
    for arm in ARMS:
        metrics[arm] = {}; private[arm] = {}
        for level in LEVELS:
            metrics[arm][level], private[arm][level] = positive_metrics(
                {p:test[p][level] for p in frame}, {p:forecasts[arm][p][level] for p in frame}, source[level])
    paired = []
    for arm in ARMS[1:]:
        for level in LEVELS:
            a = metrics[ARMS[0]][level]; b = metrics[arm][level]
            paired.append({'baseline':ARMS[0],'candidate':arm,'level':level,'paired_proteins':len(frame),
                'recovered_positive_label_difference':b['recovered_reference_positive_labels']-a['recovered_reference_positive_labels'],
                'micro_positive_reference_recovery_difference':b['micro_positive_reference_recovery']-a['micro_positive_reference_recovery']
                    if a['micro_positive_reference_recovery'] is not None and b['micro_positive_reference_recovery'] is not None else None,
                'scientific_accuracy_gain_established':False,'confidence_interval':None})
    result={'format':'biograph-steward.HOU-positive-reference-recovery.v1','held_out_reference_rows':len(test),
        'primary_protein_rows':len(primary_ids),'matched_primary_test_proteins':len(frame),
        'unmatched_primary_reference_unknown':len(primary_ids)-len(frame),
        'all_workspace_protein_coverage_only':{'protein_nodes':len(all_ids),'reference_ID_matches':len(all_ids & test.keys())},
        'all_fixed_arms_and_all_three_levels_reported':True,'metrics':metrics,'paired_descriptive_differences':paired,
        'source_overlap_and_development_exposure_excluded':False,'reference_source_masks_available':False,
        'new_independent_experiments':False,'whole_graph_accuracy_established':False,
        'unreported_compartments_used_as_negatives':False,'historical_has_annotation_truth_relabelled':False,
        'coarse_control_is_semantically_qualified_localization':False,'graph_app_or_model_default_changed':False,
        'limitations':['Positive-reference recovery is not biological precision or accuracy.',
            'HPA/UniProt/OpenCell study/source reuse is possible; released positive sets may be incomplete.',
            'Pinned author construction code permits OpenCell-only output; actual per-label dual-source provenance is unconfirmed.',
            'Canonical accession matching does not establish historical sequence, proteoform or cell-state identity.',
            'Fixed explicit GO crosswalk is incomplete; unmapped input terms are not false annotations.',
            'Source-profile and ontology-scope changes have coverage effects; no isolated causal mechanism or population gain is identified.']}
    return result, {'frame':frame,'reference':{p:test[p] for p in frame},'per_protein_metrics':private}


def run(contract_path, expected, context, output):
    contract_path=m.pinned(contract_path,expected);contract=json.loads(contract_path.read_text())
    m.need(contract['format']=='biograph-steward.HOU-positive-reference-frozen-contract.v1'
           and contract['status']=='frozen_before_cohort_label_join' and set(contract['arms'])==set(ARMS), 'frozen HOU contract differs.')
    source=read_spec(contract['source_readiness']);qualified=read_spec(contract['qualified_mapping'])
    eligibility=read_spec(contract['source_eligibility'])
    for name in ('author_test','author_release_metadata','author_paper','source_notebook'):
        s=contract[name];m.pinned(s['file'],s['sha256'])
    m.need(qualified['source_crosswalk_sha256']==contract['source_readiness']['sha256'], 'mapping source binding differs.')
    main,coarse=validate_maps(source,qualified)
    m.need(len(main)==107 and len(coarse)==160,'pre-frozen mapping counts differ.')
    for spec in source['input_pins'].values():m.pinned(spec['file'],spec['sha256'])
    inputs=eligibility['input_pins']
    for spec in inputs.values():m.pinned(spec['file'],spec['sha256'])
    original=json.loads(Path(inputs['original_graph']['file']).read_text());retained=json.loads(Path(inputs['current_graph']['file']).read_text())
    _,active,recognized,ontology=m.mitochondrial_terms(inputs['ontology']['file'],inputs['ontology']['sha256'],'GO:0005739')
    report,native,_=load_go_context(context)
    m.need(report['source']['gaf_sha256']==inputs['native_GAF']['sha256']
           and report['source_graph_file_sha256']==inputs['original_graph']['sha256'],'native complete-source binding differs.')
    forecasts=forecast(original,retained,native,eligibility,source,qualified,active,recognized)
    folder=new_output(output,contract_path.parent,context);code_sha=sha(__file__)
    seal={'format':'biograph-steward.HOU-predictions-before-reference-join.v1','created_at':utcnow(),
        'contract_sha256':expected,'producer_sha256':code_sha,'mitocarta_source_sha256':sha(m.__file__),
        'cohort_reference_labels_joined':False,'metrics_computed':False,
        'qualified_map_count':len(main),'unaltered_coarse_map_count':len(coarse),'forecasts':forecasts}
    write_json(folder/'predictions_before_reference_join.json',seal);seal_sha=sha(folder/'predictions_before_reference_join.json')
    test=read_test(contract['author_test']['file'],contract['author_test']['sha256'],source)
    primary={r['protein_id'] for r in eligibility['rows'] if r['primary_source_eligible']}
    all_ids={r['protein_id'] for r in eligibility['rows']}
    result,private=assess(test,forecasts,primary,all_ids,source)
    m.need(result['matched_primary_test_proteins']==contract['cohort']['matched_released_held_out_test_proteins']
           and result['all_workspace_protein_coverage_only']['reference_ID_matches']==contract['cohort']['full218_reference_coverage_only'], 'frozen identity-only frame differs.')
    result.update(created_at=utcnow(),contract_sha256=expected,prediction_seal_sha256=seal_sha,
        producer_sha256=code_sha,reference_file_sha256=contract['author_test']['sha256'],
        main_exact_GO_crosswalk_count=len(main),excluded_lossy_author_assignments=160-len(main),
        preserved_coarse_control_GO_crosswalk_count=len(coarse))
    for spec in [*inputs.values(),*source['input_pins'].values(),contract['source_readiness'],contract['qualified_mapping'],contract['source_eligibility']]:m.pinned(spec['file'],spec['sha256'])
    m.pinned(contract_path,expected)
    m.need(sha(__file__)==code_sha and sha(m.__file__)==seal['mitocarta_source_sha256']
           and sha(folder/'predictions_before_reference_join.json')==seal_sha,'producer/helper/prediction seal changed.')
    write_json(folder/'cases.private.json',private);write_json(folder/'report.json',result)
    write_json(folder/'execution_receipt.json',{'format':'biograph-steward.HOU-source-execution.v1',
        'contract_sha256':expected,'producer_sha256':code_sha,'mitocarta_source_sha256':sha(m.__file__),
        'predictions_sealed_before_reference_join':True,'native_full_source_replayed':True,
        'source_pins':{**inputs,**source['input_pins']},'model_calls':0,'graph_or_prior_reference_changes':False,
        'files':{p.name:sha(p) for p in sorted(folder.iterdir()) if p.is_file()}})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--contract',type=Path,required=True);p.add_argument('--contract-sha256',required=True)
    p.add_argument('--context',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r=run(a.contract,a.contract_sha256,a.context,a.out)
    print(json.dumps({'matched_primary_test_proteins':r['matched_primary_test_proteins'],
        'metrics':{arm:{level:{k:v for k,v in x.items() if k!='per_class'} for level,x in levels.items()} for arm,levels in r['metrics'].items()}},sort_keys=True))


if __name__=='__main__':main()
