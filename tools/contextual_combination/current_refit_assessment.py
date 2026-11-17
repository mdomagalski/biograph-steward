# SPDX-License-Identifier: GPL-3.0-only
"""Six-cell consumed-reference assessment of one fixed refit and source controls.

Reuses original native parsers, curves, counts and paired bootstrap; it introduces
no new endpoint, truth construction, success gate or model selection.
"""
import argparse
import copy
import json
from pathlib import Path
import traceback

from tools.learned_combination.core import need, LOCALPLUS_UPPER_ROUNDOFF
from tools.learned_combination.reference import file_sha256
from tools.learned_combination.runner import now, write_json
from .assessment import SETTINGS, VIEWS, bootstrap_contrast, open_seal, pinned_json, validate_source_manifest
from .annotation_prior_assessment import load_original_counts, combined_bootstrap

PLAN_SHA256 = '8128b0c3cbda794cb8cd75b711609cfed1f1a150ef81ba3e90339cd4815ecca9'
ORIGINAL_REPORT_SHA256 = '2dfebc4e855df8682335484cb39b5100f518363fa74b1b24b66ca3c4cdffdf98'
PREVIOUS_REPORT_SHA256 = '76189617f4285a9b7f8ff253280642849ca1a117d80901b893c260e420601d9d'
REFIT = 'current_T0_positive_union_context_refit'
UNION_LP = 'retained_and_current_curated_LocalPlus'
UNION_PRIOR = 'T0_nonexperimental_plus_retained_curated_prior'
NEW_ARMS = (REFIT, UNION_LP, UNION_PRIOR)
PREVIOUS_NEW_ARMS = ('context_plus_T0_annotation_prior', 'T0_annotation_only_099')
NS = 'biological_process'
ASPECT = 'bp'
SOURCE_COMPARATORS = ('localplus', 'localplus_updated_seeds', 'localplus_T0_curated',
                      'validation_selected_context', 'native_T0_nonexperimental')


def authorization(cfg):
    need(cfg.get('format') == 'biograph-steward.current-refit-assessment.v1'
         and cfg.get('parent_authorized_consumed_reference_assessment') is True,
         'explicit parent authorization required before source/reference access.')
    need(cfg.get('development_followup_on_consumed_reference') is True
         and cfg.get('independent_confirmation') is False,
         'consumed-reference development status required; no independent confirmation.')


def validate_plan(plan):
    need(plan['format'] == 'biograph-steward.current-T0-union-refit-development-plan.v1'
         and plan['reference_already_consumed'] is True
         and plan['independent_confirmation'] is False
         and plan['original_primary_comparison_unchanged'] is True
         and plan['arms'] == {name: [NS] for name in NEW_ARMS}, 'fixed three-arm BP-only development plan required.')
    model = plan['model']
    need(model['new_fit_count'] == 1 and model['epochs'] == 20
         and model['fitting_identity_count'] == 4040 and model['final_identity_count'] == 3300
         and model['frozen_epoch_indices_zero_based_in_native_rank_order'] == [10, 12, 11]
         and plan['evaluation']['selection_adoption_or_new_primary_success_gate'] is False,
         'fixed fitting/checkpoint/no-selection scope changed.')


def validate_forecast_provenance(meta, arm):
    need(arm in NEW_ARMS and meta.get('arm') == arm and meta.get('namespace') == NS,
         'explicit fixed BP forecast arm required.')
    need(meta.get('plan_sha256') == PLAN_SHA256
         and meta.get('development_after_reference_opening') is True
         and meta.get('reference_previously_consumed') is True
         and meta.get('independent_confirmation') is False
         and meta.get('final_reference_labels_read_for_forecasting') is False
         and meta.get('scientific_metrics_computed') is False
         and meta.get('models_fitted') is (arm == REFIT)
         and meta.get('current_validation_metric_computed') is False,
         'truthful consumed/fitting/no-current-validation forecast provenance required.')
    tolerance = meta.get('upper_roundoff_tolerance', 0.)
    need(tolerance == 0. or (arm == UNION_LP and tolerance == LOCALPLUS_UPPER_ROUNDOFF),
         'only unchanged native LocalPlus may use its original qualified epsilon; no clipping.')
    return 'localplus_T0_curated' if arm == UNION_LP else arm


def required_pairs(previous_names):
    """All frozen refit controls plus explicit source-update contrasts."""
    previous_names = tuple(previous_names)
    need(set(SOURCE_COMPARATORS) <= set(previous_names)
         and set(PREVIOUS_NEW_ARMS) <= set(previous_names)
         and not (set(previous_names) & set(NEW_ARMS)), 'complete earlier controls required.')
    pairs = [(REFIT, name) for name in previous_names + (UNION_LP, UNION_PRIOR)]
    pairs += [(candidate, name) for candidate in (UNION_LP, UNION_PRIOR) for name in SOURCE_COMPARATORS]
    pairs += [(UNION_LP, UNION_PRIOR)]
    need(len(pairs) == len(set(pairs)), 'duplicate comparison pair.')
    return pairs


def joined_bootstrap(previous, new):
    """Apply the already qualified paired-difference helper to saved old peaks."""
    import numpy as np
    joined = combined_bootstrap(previous, new, candidate=REFIT)
    saved = {(row['candidate'], row['comparator']): row for row in joined['comparisons']}
    comparisons = []
    for candidate, comparator in required_pairs(tuple(previous['scores'])):
        pair = (candidate, comparator)
        if pair in saved:
            comparisons.append(saved[pair]);continue
        first = np.asarray(joined['scores'][candidate]['bootstrap_Fmax'], dtype=np.float64)
        second = np.asarray(joined['scores'][comparator]['bootstrap_Fmax'], dtype=np.float64)
        delta = first - second
        comparisons.append({'candidate': candidate, 'comparator': comparator,
            'difference_draws': delta.tolist(), 'difference_mean': float(delta.mean()),
            'paired_95_percentile_interval': np.quantile(delta, [.025, .975]).tolist(),
            'fraction_draws_above_zero': float((delta > 0).mean()),
            'interpretation': 'Consumed-reference development; conditional unadjusted paired protein interval.'})
    joined['comparisons'] = comparisons
    joined['new_success_gate_or_model_selection'] = False
    return joined



def validate_producer_bindings(cfg, forecast_meta):
    """Require completed outputs from the exact qualified producers and fit data."""
    qualified = cfg['qualified_source_pins']
    admission = pinned_json(cfg['fit_source_admission'])
    need(admission.get('status') == 'passed' and admission.get('qualified') is True
         and admission.get('plan_sha256') == PLAN_SHA256
         and admission['source_preparation_code']['sha256'] == qualified['fit_data']['sha256'],
         'fit admission is not passed/qualified by the exact source producer.')
    for role in ('source_preparation_code', 'source_preparation_configuration'):
        spec = admission[role]
        need(file_sha256(spec['file']) == spec['sha256'], 'admitted fit code/config changed.')
    counts = admission['counts']
    need(counts['original_full_positive_cells'] == 208835 and counts['augmented_positive_cells'] == 210776
         and counts['added_positive_cells'] == 1941 and counts['fit_universe'] == 4040
         and counts['fitting_proteins_with_additions'] == 161 and counts['original_root_positive_rows'] == 3557
         and counts['augmented_root_positive_rows'] == 3567
         and counts['original_full_positive_cells_lost'] == 0
         and counts['retention_mask_equals_original_FULL'] is True,
         'actual fit union/retention differs from the frozen source qualification.')
    refit = forecast_meta[REFIT]
    need(cfg['refit_generation_receipt'] == cfg['forecasts'][REFIT]
         and refit.get('status') == 'complete'
         and refit['producer_code_sha256'] == qualified['refit']['sha256']
         and refit['producer_source']['sha256'] == qualified['refit']['sha256'],
         'refit forecast is not the exact completed qualified-producer output.')
    need(file_sha256(refit['producer_source']['file']) == refit['producer_source']['sha256'],
         'actual forecast producer code changed.')
    model = pinned_json(refit['model_metadata'])
    need(refit['model_metadata_sha256'] == refit['model_metadata']['sha256']
         and model.get('status') == 'complete' and model['plan_sha256'] == PLAN_SHA256
         and model['producer_code_sha256'] == qualified['refit']['sha256']
         and model['namespace'] == NS and model['n_layers'] == 8 and model['in_goa'] == 40
         and model['original_model_metadata_sha256'] == '1839d2d09ad62b4ee6770fb623dc62dbca4b9ad2ab8c7ba91680c62b5acef2dc'
         and model['frozen_epoch_indices_zero_based'] == [10,12,11] and model['native_callback_calls'] == 20
         and model['current_validation_metric_computed'] is False
         and model['current_validation_predictions_or_metrics_computed'] is False
         and model['reference_previously_consumed'] is True and model['independent_confirmation'] is False
         and model['native_train_and_SWA_bodies_changed'] is False
         and model['uniform_three_parameter_state_average_max_abs'] <= 1e-6,
         'completed model/checkpoint/source/frozen-schedule provenance differs.')
    need(file_sha256(model['checkpoint_file']) == model['checkpoint_sha256'], 'completed model weights changed.')
    source_cfg = pinned_json(refit['source_configuration'])
    ready = pinned_json(refit['source_readiness'])
    need(source_cfg['plan']['sha256'] == PLAN_SHA256 and source_cfg['namespace'] == NS and source_cfg['seed'] == 20261115
         and source_cfg['source_readiness'] == model['source_readiness'] == refit['source_readiness']
         and refit['source_configuration']['sha256'] == model['configuration_sha256']
         and ready['source_admission'] == cfg['fit_source_admission']
         and ready['manifests']['targets']['sha256'] == admission['target_manifest_sha256']
         and admission['target_manifest'] == ready['manifests']['targets']
         and model['source_admission']['source_admission_sha256'] == cfg['fit_source_admission']['sha256'],
         'actual model/readiness/target/source-admission chain differs.')
    controls = pinned_json(cfg['control_generation_receipt'])
    need(controls.get('status') == 'complete' and controls.get('plan_sha256') == PLAN_SHA256
         and controls['source_code_sha256'] == qualified['controls']['sha256']
         and controls['arms'] == {a:{NS:cfg['forecasts'][a]} for a in (UNION_LP,UNION_PRIOR)},
         'source controls are not the exact two completed qualified-producer forecasts.')
    control_cfg_spec = {'file':str(Path(cfg['control_generation_receipt']['file']).parent/'configuration.json'),
                        'sha256':controls['configuration_sha256']}
    control_cfg = pinned_json(control_cfg_spec)
    need(control_cfg['source_plan']['sha256'] == PLAN_SHA256
         and control_cfg['candidate_fit_manifest'] == ready['manifests']['targets'],
         'source controls do not use the exact matched augmented fit information.')
    for arm in (UNION_LP,UNION_PRIOR):
        meta = forecast_meta[arm]
        need(meta.get('status') == 'complete' and meta['configuration_sha256'] == controls['configuration_sha256'],
             'completed source-control forecast/config binding differs.')
        gate = pinned_json(meta['generation_receipt'])
        need(gate['plan_sha256'] == PLAN_SHA256
             and gate['source_code_sha256'] == qualified['controls']['sha256']
             and gate['configuration_sha256'] == controls['configuration_sha256']
             and gate['new_forecast_arrays_generated_at_receipt'] is False
             and meta['generation_receipt']['sha256'] == controls['generation_receipt_sha256'],
             'source-control array generation was not preceded by the exact source/config gate.')
    return {'fit_admission':cfg['fit_source_admission'],'refit_model':refit['model_metadata'],
            'refit_forecast':cfg['forecasts'][REFIT],'control_delivery':cfg['control_generation_receipt'],
            'matched_fit_target_manifest':ready['manifests']['targets'],
            'completed_and_qualified_producer_linkage_verified':True}


def prepare_inputs(cfg):
    """Admit complete forecasts/qualified sources without new reference scoring."""
    authorization(cfg)
    need(cfg['plan']['sha256'] == PLAN_SHA256, 'frozen plan hash required.')
    plan = pinned_json(cfg['plan']);validate_plan(plan)
    review = pinned_json(cfg['independent_plan_review'])
    need(review.get('qualified') is True and review.get('plan_sha256') == PLAN_SHA256
         and review.get('development_followup_on_consumed_reference') is True,
         'independent source/plan qualification of this exact development required.')
    need(set(cfg['qualified_source_pins']) >= {'assessment', 'refit', 'fit_data', 'controls'},
         'all executed producer/assessor sources must be qualified.')
    need(review.get('qualified_source_pins') == cfg['qualified_source_pins'],
         'review and execution source versions differ.')
    for spec in cfg['qualified_source_pins'].values():
        need(file_sha256(spec['file']) == spec['sha256'], 'qualified executable source changed.')
    need(Path(cfg['qualified_source_pins']['assessment']['file']).resolve() == Path(__file__).resolve(),
         'qualified assessor source is not the running module.')
    need(cfg['original_report']['sha256'] == ORIGINAL_REPORT_SHA256
         and cfg['previous_development_report']['sha256'] == PREVIOUS_REPORT_SHA256,
         'unchanged original/prior-development report pins required.')
    original_cfg, seal = open_seal(cfg['original_seal_directory'])
    need(file_sha256(Path(cfg['original_seal_directory'])/'forecast_seal.json') == plan['original_forecast_seal_sha256'],
         'original forecast seal changed.')
    original = pinned_json(cfg['original_report'])
    previous = pinned_json(cfg['previous_development_report'])
    need(previous['original_report']['sha256'] == ORIGINAL_REPORT_SHA256
         and previous['original_primary_comparison_unchanged'] is True
         and previous['development_followup_on_consumed_reference'] is True
         and previous['independent_confirmation'] is False,
         'earlier fixed development source does not match the immutable study.')
    targets = tuple(Path(original_cfg['targets']['file']).read_text().splitlines())
    need(len(targets) == len(set(targets)) == 3300, 'complete original3300 target identities required.')
    need(set(cfg['forecasts']) == set(NEW_ARMS), 'all three fixed forecasts required before any evaluation.')
    sources = {};metas = {}
    for arm, spec in cfg['forecasts'].items():
        meta = pinned_json(spec)
        metas[arm] = meta
        guard_name = validate_forecast_provenance(meta, arm)
        # Existing helper only uses the semantic name to constrain native LP epsilon.
        sources[arm] = validate_source_manifest(spec, targets, arm=guard_name, namespace=NS)
    validate_producer_bindings(cfg, metas)
    return plan, original_cfg, seal, original, previous, targets, sources


def run(cfg, output):
    import numpy as np
    from cafaeval.parser import gt_parser, gt_exclude_parser, update_toi
    from tools.learned_combination.native_adapter import native_ontologies, align_predictions, evaluate_native
    from tools.learned_combination.ordinary_counts import contributions, verify_curve
    from .training import project_native_forecasts

    plan, original_cfg, seal, original, previous, targets, sources = prepare_inputs(cfg)
    output = Path(output);output.mkdir(parents=True, exist_ok=False)
    write_json(output/'complete_forecast_admission.json', {'format':'biograph-steward.current-refit-complete-forecast-admission.v1',
        'created_at':now(),'plan_sha256':PLAN_SHA256,'complete_ordered_targets':3300,'namespace':NS,
        'all_fixed_arms_admitted':sources,'independent_plan_review':cfg['independent_plan_review'],
        'qualified_source_pins':cfg['qualified_source_pins'],'reference_previously_consumed':True,
        'new_metrics_computed_by_this_admission':False,'original_study_unchanged':True})
    report={'format':'biograph-steward.current-refit-development-assessment.v1','created_at':now(),
        'plan_sha256':PLAN_SHA256,'development_followup_on_consumed_reference':True,
        'independent_confirmation':False,'original_primary_comparison_unchanged':True,
        'new_success_gate_or_model_selection':False,'graph_pruning_or_app_promotion':False,
        'original_report_sha256':ORIGINAL_REPORT_SHA256,'previous_development_report_sha256':PREVIOUS_REPORT_SHA256,
        'original_public_summary_sha256':plan['original_public_summary_sha256'],
        'original_forecast_seal_sha256':plan['original_forecast_seal_sha256'],
        'target_count':len(targets),'new_arm_scopes':{a:[NS] for a in NEW_ARMS},'views':{},
        'reference_interpretation':original['reference_interpretation'],
        'interpretation':'All six original BP cells; frozen source-update development, not independent confirmation or adoption.'}
    tau=np.arange(.001,1,.001)
    try:
        for view in VIEWS:
            refs=original_cfg['references'][view]
            for spec in refs.values():
                need(file_sha256(spec['file'])==spec['sha256'],'original reference source changed.')
            ont=update_toi(native_ontologies(refs['obo']['file']),refs['toi']['file'])
            view_result={'reference_pins':refs,'cells':{}};report['views'][view]=view_result
            for setting in SETTINGS:
                key=setting+'/'+NS
                old_cell=original['views'][view]['cells'][key]
                prior_cell=previous['views'][view]['cells'][key]
                need(set(prior_cell['methods'])==set(old_cell['methods'])|set(PREVIOUS_NEW_ARMS),
                     'earlier source controls/candidates are incomplete.')
                for arm,method in old_cell['methods'].items():
                    need(prior_cell['methods'][arm]==method,'earlier original method readouts changed.')
                cell=copy.deepcopy(prior_cell)
                for field in ('bootstrap','GCN_MLP_bootstrap','updated_seed_bootstrap','updated_seed_soft_bootstrap',
                              'current_T0_curated_bootstrap','source_slice_points','positive_reference_score_ledger'):
                    cell.pop(field,None)
                cell['development_followup_on_consumed_reference']=True;cell['independent_confirmation']=False
                cell['earlier_methods_read_only']=True;view_result['cells'][key]=cell
                source_frame=Path(cfg['original_results_directory'])/view/setting
                truth=source_frame/'truth.tsv';truth_rel='/'.join((view,setting,'truth.tsv'))
                need(file_sha256(truth)==original['files'][truth_rel],'original native truth subset changed.')
                gt=gt_parser(str(truth),ont)
                frame=output/view/setting;frame.mkdir(parents=True)
                if NS not in gt:
                    need(old_cell['status']=='reference_absent','original reference availability changed.')
                    for arm in NEW_ARMS:cell['methods'][arm]={'status':'reference_absent','native_micro_fmax':None}
                    write_json(frame/'bp_summary.json',cell);continue
                need(old_cell['status']==prior_cell['status']=='evaluated','original evaluated cell missing.')
                ex=None
                if setting=='PK':
                    known=source_frame/'known.tsv';known_rel='/'.join((view,setting,'known.tsv'))
                    need(file_sha256(known)==original['files'][known_rel],'original known subset changed.')
                    ex=gt_exclude_parser(str(known),gt,ont)
                ids=np.asarray([p for p,_ in sorted(gt[NS].ids.items(),key=lambda item:item[1])])
                eligible_original=None
                for arm,method in prior_cell['methods'].items():
                    historical=arm not in PREVIOUS_NEW_ARMS
                    directory=cfg['original_results_directory'] if historical else cfg['previous_development_results_directory']
                    source_report=original if historical else previous
                    row=load_original_counts(directory,source_report,view,setting,ASPECT,arm,ids,tau)
                    if eligible_original is None:eligible_original=row['eligible'].copy()
                    need(np.array_equal(row['eligible'],eligible_original),'earlier native row admission differs.')
                    if method['eligible_proteins']:
                        need(method['native_curve_agreement'].get('author_point_agreement_passed') is True,
                             'earlier method lacks its full native-curve gate.')
                    del row
                arrays={}
                for arm in NEW_ARMS:
                    print(now(),'REFIT_DEVELOPMENT_EVALUATE',view,setting,arm,flush=True)
                    meta=pinned_json(cfg['forecasts'][arm]);validate_forecast_provenance(meta,arm)
                    values=np.load(meta['prediction_file'],mmap_mode='r',allow_pickle=False)
                    pred,projection=project_native_forecasts(meta['proteins'],meta['terms'],values,ont[NS],
                        upper_roundoff_tolerance=meta.get('upper_roundoff_tolerance',0.))
                    pred=align_predictions({NS:pred},{NS:gt[NS]})
                    exclude=None if ex is None else {NS:ex[NS]}
                    curve,points=evaluate_native(pred,{NS:gt[NS]},ont,gt_exclude=exclude,tau=tau,n_cpu=cfg.get('n_cpu',6))
                    curve.to_csv(frame/(ASPECT+'_'+arm+'_curves.tsv'),sep='\t',index=False)
                    counts,eligible=contributions(pred[NS],gt[NS],ont[NS],tau,exclude=None if ex is None else ex[NS])
                    need(np.array_equal(eligible,eligible_original),'new native eligible frame differs from original.')
                    residual=int(np.count_nonzero(counts[:,0,1]+counts[:,0,3]))
                    parity=verify_curve(counts,curve,namespace=NS) if residual else {'status':'unscorable_no_residual_reference_proteins'}
                    arrays[arm]={'ids':ids,'tau':tau,'ordinary':counts}
                    np.savez_compressed(frame/(ASPECT+'_'+arm+'_counts.npz'),**arrays[arm],eligible=eligible)
                    point=points.get(NS)
                    cell['methods'][arm]={'native_micro_fmax':point,'status':'evaluated' if point is not None else 'no_native_coverage',
                        'pre_exclusion_GT_proteins':int(eligible.sum()),'eligible_proteins':residual,
                        'raw_native_reference_proteins':len(ids),'native_curve_agreement':parity,
                        'forecast_projection':projection,'development_followup_on_consumed_reference':True}
                    del pred,values
                old_boot=prior_cell.get('bootstrap')
                can_boot=(len(ids)>1 and old_boot is not None and old_boot.get('status')!='unavailable'
                    and all(cell['methods'][a]['status']=='evaluated' for a in NEW_ARMS))
                if can_boot:
                    new_boot=bootstrap_contrast(arrays,REFIT)
                    cell['bootstrap']=joined_bootstrap(old_boot,new_boot)
                else:
                    cell['bootstrap']={'status':'unavailable','reason':'A declared new arm or original paired frame lacks native coverage; every method/cell is retained, no contrast inferred.'}
                write_json(frame/'bp_summary.json',cell);del arrays
            write_json(output/view/'view_summary.json',view_result)
        report['files']={str(p.relative_to(output)):file_sha256(p) for p in output.rglob('*') if p.is_file()}
        write_json(output/'report.json',report)
        return report
    except Exception as error:
        write_json(output/'failure.json',{'created_at':now(),'exception':repr(error),'traceback':traceback.format_exc(),
            'partial_results_preserved':True,'development_followup_on_consumed_reference':True,'original_study_unchanged':True})
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--output');p.add_argument('--admit-only',action='store_true')
    args=p.parse_args();cfg=json.loads(Path(args.config).read_text())
    if args.admit_only:
        values=prepare_inputs(cfg);print(json.dumps({'status':'admitted','plan_sha256':PLAN_SHA256,'arms':list(NEW_ARMS),'targets':len(values[5]),'new_metrics_computed':False}))
    else:
        need(args.output is not None,'distinct output required.');run(cfg,args.output)


if __name__=='__main__':main()
