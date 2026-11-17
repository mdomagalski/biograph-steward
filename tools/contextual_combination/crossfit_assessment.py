# SPDX-License-Identifier: GPL-3.0-only
"""One fixed cross-fitted arm on the already consumed six-cell BP reference.

Reuse unchanged native curves/counts/bootstrap. Earlier points, saved draw
peaks and contrasts remain literal read-only inputs. This is development,
not independent biological confirmation or an application promotion gate.
"""
import argparse
import copy
import importlib
import json
from pathlib import Path
import traceback

from tools.learned_combination.core import need
from tools.learned_combination.reference import file_sha256
from tools.learned_combination.runner import now, write_json
from .assessment import SETTINGS, VIEWS, bootstrap_contrast, open_seal, pinned_json, validate_source_manifest
from .annotation_prior_assessment import load_original_counts, combined_bootstrap, NEW_ARMS as PRIOR_ARMS
from .current_refit_assessment import NEW_ARMS as REFIT_ARMS, required_pairs
from .crossfit_training import ARM, NAMESPACE as NS, PARENTS, COUNTS, VALIDATION_ROLE, validate_plan

ASPECT = 'bp'
ANCHOR = 'validation_selected_context'
ORIGINAL_REPORT_SHA256 = '2dfebc4e855df8682335484cb39b5100f518363fa74b1b24b66ca3c4cdffdf98'
ANNOTATION_PRIOR_REPORT_SHA256 = '76189617f4285a9b7f8ff253280642849ca1a117d80901b893c260e420601d9d'
PREVIOUS_REPORT_SHA256 = 'b7792b0737835d374f2335735aa254e90a609d9a73bf0bfd9f99f9586065eac0'
SOURCE_MODULES = {
    'assessment': __name__,
    'crossfit_training': 'tools.contextual_combination.crossfit_training',
    'crossfit_prepare': 'tools.contextual_combination.crossfit_prepare',
    'training_context': 'tools.contextual_combination.training_context',
    'training': 'tools.contextual_combination.training',
    'context_io': 'tools.contextual_combination.context_io',
    'native_stacker': 'tools.contextual_combination.native_stacker',
    'postprocessing': 'tools.contextual_combination.postprocessing',
    'native_assessment': 'tools.contextual_combination.assessment',
    'annotation_prior_assessment': 'tools.contextual_combination.annotation_prior_assessment',
    'current_refit_assessment': 'tools.contextual_combination.current_refit_assessment',
    'ordinary_counts': 'tools.learned_combination.ordinary_counts',
    'paired_bootstrap': 'tools.cafa_reference.paired_bootstrap',
    'native_adapter': 'tools.learned_combination.native_adapter',
}


def authorization(cfg):
    need(cfg.get('format') == 'biograph-steward.crossfit-assessment.v1'
         and cfg.get('parent_authorized_consumed_reference_assessment') is True,
         'explicit parent authorization required before source/reference access.')
    need(cfg.get('development_followup_on_consumed_reference') is True
         and cfg.get('independent_confirmation') is False,
         'consumed-reference development required; no independent confirmation.')


def validate_forecast_provenance(meta, plan_sha):
    need(meta.get('format') == 'biograph-steward.crossfit-context-forecast.v1'
         and meta.get('status') == 'complete' and meta.get('arm') == ARM
         and meta.get('namespace') == NS and meta.get('parent_axis') == PARENTS
         and meta.get('plan_sha256') == plan_sha,
         'complete fixed BP cross-fit forecast required.')
    expected = {'development_after_reference_opening': True, 'reference_previously_consumed': True,
        'independent_confirmation': False, 'final_reference_labels_read_for_forecasting': False,
        'final_reference_metrics_computed': False, 'forecast_phase_scientific_metrics_computed': False,
        'consumed_validation_used_for_SWA': True, 'no_DeepGO_features_or_heads_read': True,
        'models_fitted': True, 'automatic_graph_or_app_promotion': False}
    need(all(meta.get(k) is v for k, v in expected.items())
         and meta.get('validation_metric_role') == VALIDATION_ROLE
         and meta.get('upper_roundoff_tolerance', 0.) == 0.
         and (meta.get('in_models'), meta.get('in_goa'), meta.get('n_layers')) == (2, 40, 8),
         'truthful consumed-validation/final-reference/architecture provenance required.')
    # Normal native SWA legitimately computes metrics on the old validation.
    # Do not require current_validation_metric_computed=False or relabel the
    # internal phase-local fresh flag as an independent study.


def validate_plan_evaluation(plan):
    validate_plan(plan)
    expected = {'views': list(VIEWS), 'settings': list(SETTINGS), 'namespace': NS,
        'bootstrap_draws': 2000, 'bootstrap_seed': 20261113, 'earlier_methods': 22,
        'prior_comparisons_retained': 192, 'new_candidate_comparisons': 132,
        'complete_method_rows': 138, 'complete_contrast_rows': 324,
        'previous_completed_report_sha256': PREVIOUS_REPORT_SHA256,
        'all_forecasts_and_model_choice_sealed_before_development_assessment': True,
        'native_curve_count_agreement_required': True}
    need(all(plan.get('evaluation', {}).get(k) == v for k, v in expected.items()),
         'complete fixed six-cell/22-control native evaluation scope required.')


def old_cell_chain(original, annotation, previous):
    """Require complete earlier rows and preserve every earlier point literally."""
    names = set(original['methods'])
    need(len(names) == 17 and ANCHOR in names and not names & set(PRIOR_ARMS + REFIT_ARMS),
         'all17 original BP methods required.')
    need(set(annotation['methods']) == names | set(PRIOR_ARMS)
         and set(previous['methods']) == names | set(PRIOR_ARMS + REFIT_ARMS)
         and len(previous['methods']) == 22, 'all22 earlier methods required.')
    for name, row in original['methods'].items():
        need(annotation['methods'][name] == row, 'original method readout changed.')
    for name, row in annotation['methods'].items():
        need(previous['methods'][name] == row, 'earlier development method readout changed.')
    need(original['status'] == annotation['status'] == previous['status'],
         'earlier native reference availability differs.')
    return tuple(previous['methods'])


def earlier_count_source(cfg, original, annotation, previous, arm):
    if arm in REFIT_ARMS:
        return cfg['previous_development_results_directory'], previous
    if arm in PRIOR_ARMS:
        return cfg['annotation_prior_results_directory'], annotation
    return cfg['original_results_directory'], original


def joined_bootstrap(previous, new):
    """Reuse all old peaks/contrasts; add exactly22 paired new contrasts.

    The unchanged helper requires two arms. Its regenerated old anchor peaks
    must exactly reproduce the saved vector before that duplicate is removed.
    """
    need(len(previous['scores']) == 22 and ARM not in previous['scores']
         and set(new['scores']) == {ARM, ANCHOR}, 'complete22 controls plus one anchor required.')
    prior_names = tuple(name for name in previous['scores'] if name not in REFIT_ARMS)
    expected_pairs = set(required_pairs(prior_names))
    comparisons = previous['comparisons']
    pairs = [(r['candidate'], r['comparator']) for r in comparisons]
    need(len(expected_pairs) == len(pairs) == 32 and set(pairs) == expected_pairs,
         'all32 previous contrasts required without duplicates.')
    need(new['scores'][ANCHOR] == previous['scores'][ANCHOR],
         'regenerated native anchor peaks differ from the preserved paired draw frame.')
    candidate = copy.deepcopy(new)
    candidate['scores'] = {ARM: candidate['scores'][ARM]}
    result = combined_bootstrap(previous, candidate, candidate=ARM)
    result['comparisons'] = copy.deepcopy(comparisons) + result['comparisons']
    need(len(result['scores']) == 23 and len(result['comparisons']) == 54,
         'complete23-arm/54-contrast cell required.')
    result.update(earlier_contrasts_reused_without_recomputation=True,
        regenerated_anchor_peaks_equal_preserved_exactly=True,
        new_success_gate_or_model_selection=False)
    return result


def validate_producer_bindings(cfg, meta):
    """Bind completed source preparation, model, native export and input pins."""
    qualified = cfg['qualified_source_pins']; plan_sha = cfg['plan']['sha256']
    source_cfg = pinned_json(meta['source_configuration'])
    ready = pinned_json(meta['source_readiness'])
    model = pinned_json(meta['model_metadata'])
    need(source_cfg['format'] == 'biograph-steward.crossfit-context-training.v1'
         and source_cfg['plan'] == cfg['plan']
         and source_cfg['source_readiness'] == meta['source_readiness']
         and model.get('format') == 'biograph-steward.crossfit-context-model.v1'
         and model.get('status') == 'complete' and model.get('arm') == ARM
         and model.get('namespace') == NS and model.get('parent_axis') == PARENTS
         and model.get('plan_sha256') == plan_sha
         and model['source_readiness'] == meta['source_readiness']
         and model['configuration_sha256'] == meta['source_configuration']['sha256']
         and meta['model_metadata_sha256'] == meta['model_metadata']['sha256'],
         'completed outer training/configuration/readiness/model chain differs.')
    from .crossfit_training import check_source_pins, validate_native_model
    check_source_pins(source_cfg['qualified_source_pins'], ready)
    need(all(qualified.get(k) == v for k, v in source_cfg['qualified_source_pins'].items()),
         'training and assessment executable qualification pins differ.')
    for row in (model, meta):
        need(row['producer_source'] == qualified['crossfit_training']
             and row['producer_code_sha256'] == qualified['crossfit_training']['sha256']
             and row['development_after_reference_opening'] is True
             and row['reference_previously_consumed'] is True and row['independent_confirmation'] is False
             and row['consumed_validation_used_for_SWA'] is True
             and row['validation_metric_role'] == VALIDATION_ROLE
             and row['final_reference_metrics_computed'] is False
             and row['automatic_graph_or_app_promotion'] is False,
             'completed model/export producer or consumed-reference scope differs.')
    need(model['qualified_source_pins'] == source_cfg['qualified_source_pins']
         and model['source_admission'] == meta['source_admission']
         and model['final_reference_labels_read_for_fitting'] is False
         and (model['in_models'], model['in_goa'], model['n_layers']) == (2, 40, 8),
         'fixed architecture, fitting phase or input admission differs.')
    need(ready['format'] == 'biograph-steward.crossfit-graph-prevalence-features.v1'
         and ready['status'] == 'complete' and ready['plan'] == cfg['plan']
         and ready['producer_source'] == qualified['crossfit_prepare']
         and ready['parent_axis'] == PARENTS and ready['namespace'] == NS
         and ready['final_reference_labels_read_for_feature_construction'] is False,
         'completed source producer/role scope differs.')
    for filename, digest in ready['input_file_pins'].items():
        need(file_sha256(filename) == digest, 'admitted input/feature/source changed.')
    admission = pinned_json(ready['source_admission'])
    need(admission['status'] == 'passed' and admission['qualified'] is True
         and admission['plan_sha256'] == plan_sha and admission['counts'] == COUNTS
         and admission['producer_source'] == qualified['crossfit_prepare']
         and admission['native_full_fit_priors_match_original_vectors_exactly'] is True
         and admission['original_targets_and_known_mask_bytes_retained'] is True
         and admission['new_annotation_source_or_target_cells'] is False,
         'qualified full-fit/fold-source admission differs.')
    proof = model['source_admission']
    need(proof['source_admission'] == ready['source_admission']
         and proof['fold_manifest'] == ready['fold_manifest']
         and proof['parent_axis'] == PARENTS
         and proof['no_DeepGO_features_or_heads_read'] is True
         and proof['final_reference_labels_read_for_fitting'] is False
         and proof['final_reference_labels_read_for_forecasting'] is False,
         'completed fitting source proof differs from the generated roles/folds.')
    fit = pinned_json(ready['manifests']['fit']); contract = pinned_json(ready['channel_contract'])
    native_model = pinned_json(model['native_model_metadata'])
    validate_native_model(native_model, {'ready': ready, 'metas': {'fit': fit}, 'contract': contract})
    native_config = {'file': str(Path(model['native_model_metadata']['file']).parent / 'configuration.json'),
                     'sha256': native_model['configuration_sha256']}
    need(pinned_json(native_config) == source_cfg['native_training_configuration']
         and native_model['checkpoint_file'] == model['checkpoint_file']
         and native_model['checkpoint_sha256'] == model['checkpoint_sha256'],
         'native training configuration/selected checkpoint differs from the outer model.')
    native_forecast = pinned_json(meta['native_forecast_metadata'])
    need(meta['native_model_metadata'] == model['native_model_metadata']
         and native_forecast['model_metadata_sha256'] == model['native_model_metadata']['sha256']
         and native_forecast['feature_manifest_sha256'] == ready['manifests']['final']['sha256']
         and native_forecast['context_manifest_sha256'] == ready['contexts']['final']['sha256']
         and meta['proteins'] == pinned_json(ready['manifests']['final'])['proteins']
         and meta['terms'] == fit['terms'] and len(meta['terms']) == COUNTS['model_terms'],
         'native export/complete forecast identity frame differs.')
    for field in ('prediction_file', 'prediction_sha256', 'raw_prediction_file', 'raw_prediction_sha256'):
        need(meta[field] == native_forecast[field], 'outer/native forecast score files differ.')
    for path_key, hash_key in (('prediction_file', 'prediction_sha256'), ('raw_prediction_file', 'raw_prediction_sha256')):
        need(file_sha256(meta[path_key]) == meta[hash_key], 'completed forecast array changed.')
    return {'source_readiness': meta['source_readiness'], 'source_admission': ready['source_admission'],
        'model': meta['model_metadata'], 'native_export': meta['native_forecast_metadata'],
        'completed_and_qualified_producer_linkage_verified': True}


def prepare_inputs(cfg):
    """Admit all frozen forecasts before any reference metrics are computed."""
    authorization(cfg)
    plan = pinned_json(cfg['plan']); validate_plan_evaluation(plan)
    review = pinned_json(cfg['independent_plan_review'])
    need(review.get('qualified') is True and review.get('plan_sha256') == cfg['plan']['sha256']
         and review.get('development_followup_on_consumed_reference') is True
         and review.get('qualified_source_pins') == cfg['qualified_source_pins'],
         'qualified source/protocol review of these exact executable versions required.')
    need(set(SOURCE_MODULES) <= set(cfg['qualified_source_pins']), 'all executed source pins required.')
    for role, module_name in SOURCE_MODULES.items():
        module = importlib.import_module(module_name); spec = cfg['qualified_source_pins'][role]
        need(file_sha256(spec['file']) == spec['sha256'] == file_sha256(module.__file__),
             'running qualified executable source changed: ' + role)
    meta = pinned_json(cfg['forecast']); validate_forecast_provenance(meta, cfg['plan']['sha256'])
    producer = validate_producer_bindings(cfg, meta)
    need(cfg['original_report']['sha256'] == ORIGINAL_REPORT_SHA256
         and cfg['annotation_prior_report']['sha256'] == ANNOTATION_PRIOR_REPORT_SHA256
         and cfg['previous_development_report']['sha256'] == PREVIOUS_REPORT_SHA256,
         'immutable original/earlier-development report pins required.')
    original_cfg, seal = open_seal(cfg['original_seal_directory'])
    need(file_sha256(Path(cfg['original_seal_directory']) / 'forecast_seal.json')
         == plan['original_forecast_seal_sha256'], 'original forecast seal changed.')
    targets = tuple(Path(original_cfg['targets']['file']).read_text().splitlines())
    need(len(targets) == len(set(targets)) == 3300, 'complete original3300 ordered targets required.')
    source = validate_source_manifest(cfg['forecast'], targets, arm=ARM, namespace=NS)
    original = pinned_json(cfg['original_report']); annotation = pinned_json(cfg['annotation_prior_report'])
    previous = pinned_json(cfg['previous_development_report'])
    need(original['forecast_seal_sha256'] == plan['original_forecast_seal_sha256']
         and annotation['original_report']['sha256'] == ORIGINAL_REPORT_SHA256
         and previous['original_report_sha256'] == ORIGINAL_REPORT_SHA256
         and previous['previous_development_report_sha256'] == ANNOTATION_PRIOR_REPORT_SHA256
         and previous['original_primary_comparison_unchanged'] is True
         and previous['development_followup_on_consumed_reference'] is True
         and previous['independent_confirmation'] is False,
         'earlier fixed assessment chain differs from the immutable study.')
    for view in VIEWS:
        for setting in SETTINGS:
            key = setting + '/' + NS
            old_cell_chain(original['views'][view]['cells'][key], annotation['views'][view]['cells'][key],
                           previous['views'][view]['cells'][key])
    return plan, original_cfg, seal, original, annotation, previous, targets, source, producer


def run(cfg, output):
    import numpy as np
    from cafaeval.parser import gt_parser, gt_exclude_parser, update_toi
    from tools.learned_combination.native_adapter import native_ontologies, align_predictions, evaluate_native
    from tools.learned_combination.ordinary_counts import contributions, verify_curve
    from .training import project_native_forecasts

    plan, original_cfg, seal, original, annotation, previous, targets, source, producer = prepare_inputs(cfg)
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'complete_forecast_admission.json', {
        'format': 'biograph-steward.crossfit-complete-forecast-admission.v1', 'created_at': now(),
        'plan_sha256': cfg['plan']['sha256'], 'complete_ordered_targets': len(targets), 'namespace': NS,
        'forecast': source, 'producer_bindings': producer, 'qualified_source_pins': cfg['qualified_source_pins'],
        'source_protocol_review': cfg['independent_plan_review'], 'reference_previously_consumed': True,
        'new_metrics_computed_by_this_admission': False, 'independent_confirmation': False})
    report = {'format': 'biograph-steward.crossfit-development-assessment.v1', 'created_at': now(),
        'plan_sha256': cfg['plan']['sha256'], 'development_followup_on_consumed_reference': True,
        'independent_confirmation': False, 'original_primary_comparison_unchanged': True,
        'new_success_gate_or_model_selection': False, 'graph_pruning_or_app_promotion': False,
        'original_report_sha256': ORIGINAL_REPORT_SHA256,
        'annotation_prior_report_sha256': ANNOTATION_PRIOR_REPORT_SHA256,
        'previous_development_report_sha256': PREVIOUS_REPORT_SHA256,
        'original_public_summary_sha256': plan['original_public_summary_sha256'],
        'original_forecast_seal_sha256': plan['original_forecast_seal_sha256'],
        'target_count': len(targets), 'new_arm_scopes': {ARM: [NS]}, 'views': {},
        'reference_interpretation': original['reference_interpretation'],
        'interpretation': 'Consumed-reference development only; no new primary gate, independent confirmation or automatic promotion.'}
    tau = np.arange(.001, 1, .001)
    try:
        for view in VIEWS:
            refs = original_cfg['references'][view]
            for spec in refs.values():
                need(file_sha256(spec['file']) == spec['sha256'], 'original reference source changed.')
            ont = update_toi(native_ontologies(refs['obo']['file']), refs['toi']['file'])
            view_result = {'reference_pins': refs, 'cells': {}}; report['views'][view] = view_result
            for setting in SETTINGS:
                key = setting + '/' + NS
                old_cell = original['views'][view]['cells'][key]
                prior_cell = previous['views'][view]['cells'][key]
                cell = copy.deepcopy(prior_cell)
                cell.update(development_followup_on_consumed_reference=True, independent_confirmation=False,
                            earlier_methods_read_only=True)
                view_result['cells'][key] = cell
                source_frame = Path(cfg['original_results_directory']) / view / setting
                truth = source_frame / 'truth.tsv'; rel = '/'.join((view, setting, 'truth.tsv'))
                need(file_sha256(truth) == original['files'][rel], 'original native truth subset changed.')
                gt = gt_parser(str(truth), ont)
                frame = output / view / setting; frame.mkdir(parents=True)
                if NS not in gt:
                    need(old_cell['status'] == 'reference_absent', 'original reference availability changed.')
                    cell['methods'][ARM] = {'status': 'reference_absent', 'native_micro_fmax': None}
                    write_json(frame / 'bp_summary.json', cell); continue
                need(old_cell['status'] == prior_cell['status'] == 'evaluated', 'earlier evaluated cell missing.')
                ex = None
                if setting == 'PK':
                    known = source_frame / 'known.tsv'; rel = '/'.join((view, setting, 'known.tsv'))
                    need(file_sha256(known) == original['files'][rel], 'original known subset changed.')
                    ex = gt_exclude_parser(str(known), gt, ont)
                ids = np.asarray([p for p, _ in sorted(gt[NS].ids.items(), key=lambda item: item[1])])
                eligible_original = None; anchor = None
                for arm, method in prior_cell['methods'].items():
                    directory, source_report = earlier_count_source(cfg, original, annotation, previous, arm)
                    row = load_original_counts(directory, source_report, view, setting, ASPECT, arm, ids, tau)
                    if eligible_original is None: eligible_original = row['eligible'].copy()
                    need(np.array_equal(row['eligible'], eligible_original), 'earlier native row admission differs.')
                    if method['eligible_proteins']:
                        need(method['native_curve_agreement'].get('author_point_agreement_passed') is True,
                             'earlier method lacks its full native-curve gate.')
                    if arm == ANCHOR: anchor = row
                    del row
                print(now(), 'CROSSFIT_DEVELOPMENT_EVALUATE', view, setting, ARM, flush=True)
                meta = pinned_json(cfg['forecast']); validate_forecast_provenance(meta, cfg['plan']['sha256'])
                need(file_sha256(meta['prediction_file']) == meta['prediction_sha256'], 'sealed forecast array changed.')
                values = np.load(meta['prediction_file'], mmap_mode='r', allow_pickle=False)
                pred, projection = project_native_forecasts(meta['proteins'], meta['terms'], values, ont[NS], upper_roundoff_tolerance=0.)
                pred = align_predictions({NS: pred}, {NS: gt[NS]})
                exclude = None if ex is None else {NS: ex[NS]}
                curve, points = evaluate_native(pred, {NS: gt[NS]}, ont, gt_exclude=exclude, tau=tau, n_cpu=cfg.get('n_cpu', 4))
                curve.to_csv(frame / (ASPECT + '_' + ARM + '_curves.tsv'), sep='\t', index=False)
                counts, eligible = contributions(pred[NS], gt[NS], ont[NS], tau, exclude=None if ex is None else ex[NS])
                need(np.array_equal(eligible, eligible_original), 'new native eligible frame differs from original.')
                residual = int(np.count_nonzero(counts[:, 0, 1] + counts[:, 0, 3]))
                parity = verify_curve(counts, curve, namespace=NS) if residual else {'status': 'unscorable_no_residual_reference_proteins'}
                array = {'ids': ids, 'tau': tau, 'ordinary': counts}
                np.savez_compressed(frame / (ASPECT + '_' + ARM + '_counts.npz'), **array, eligible=eligible)
                point = points.get(NS)
                cell['methods'][ARM] = {'native_micro_fmax': point, 'status': 'evaluated' if point is not None else 'no_native_coverage',
                    'pre_exclusion_GT_proteins': int(eligible.sum()), 'eligible_proteins': residual,
                    'raw_native_reference_proteins': len(ids), 'native_curve_agreement': parity,
                    'forecast_projection': projection, 'development_followup_on_consumed_reference': True}
                old_boot = prior_cell.get('bootstrap')
                can_boot = len(ids) > 1 and old_boot is not None and old_boot.get('status') != 'unavailable' and point is not None
                if can_boot:
                    need(anchor is not None, 'preserved native anchor contribution frame required.')
                    cell['bootstrap'] = joined_bootstrap(old_boot, bootstrap_contrast({ARM: array, ANCHOR: anchor}, ARM))
                else:
                    # Preserve earlier bootstrap even when the new arm is unscorable.
                    cell['crossfit_bootstrap'] = {'status': 'unavailable', 'reason': 'No new paired contrast inferred; earlier results preserved.'}
                write_json(frame / 'bp_summary.json', cell)
                del values, pred, counts, array, anchor
            write_json(output / view / 'view_summary.json', view_result)
        report['method_rows'] = sum(len(c['methods']) for v in report['views'].values() for c in v['cells'].values())
        report['contrast_rows'] = sum(len(c.get('bootstrap', {}).get('comparisons', [])) for v in report['views'].values() for c in v['cells'].values())
        need(report['method_rows'] == 138 and report['contrast_rows'] == 324,
             'complete fixed138-point/324-contrast development output not available; no fabricated replacement.')
        report['files'] = {str(p.relative_to(output)): file_sha256(p) for p in output.rglob('*') if p.is_file()}
        write_json(output / 'report.json', report)
        return report
    except Exception as error:
        write_json(output / 'failure.json', {'created_at': now(), 'exception': repr(error), 'traceback': traceback.format_exc(),
            'partial_results_preserved': True, 'development_followup_on_consumed_reference': True, 'original_study_unchanged': True})
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True); p.add_argument('--output'); p.add_argument('--admit-only', action='store_true')
    args = p.parse_args(); cfg = json.loads(Path(args.config).read_text())
    if args.admit_only:
        values = prepare_inputs(cfg)
        print(json.dumps({'status': 'admitted', 'plan_sha256': cfg['plan']['sha256'], 'arm': ARM,
            'targets': len(values[6]), 'new_metrics_computed': False, 'independent_confirmation': False}))
    else:
        need(args.output is not None, 'distinct output required.'); run(cfg, args.output)


if __name__ == '__main__': main()
