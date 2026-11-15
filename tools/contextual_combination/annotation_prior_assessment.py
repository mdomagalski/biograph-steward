# SPDX-License-Identifier: GPL-3.0-only
"""A fixed development follow-up using an already consumed reference.

The original study, opening gate, controls and success flags are read only.
Only two new fixed arms receive native curves/counts. Original native-gated
protein-bootstrap draws are reused after their contribution-frame checks.
This module does not establish another independent reference opening.
"""
import argparse
import copy
import json
from pathlib import Path
import traceback

from tools.learned_combination.core import need
from tools.learned_combination.reference import file_sha256
from tools.learned_combination.runner import NS_ASPECT, now, write_json
from .assessment import (SETTINGS, VIEWS, bootstrap_contrast, open_seal,
                         pinned_json, validate_source_manifest)


CANDIDATE = 'context_plus_T0_annotation_prior'
MATCHED_PRIOR = 'T0_annotation_only_099'
ORIGINAL_PRIOR = 'native_T0_nonexperimental'
NEW_ARMS = (CANDIDATE, MATCHED_PRIOR)


def check_authorization(cfg):
    """Reject an unapproved execution before any input or reference access."""
    need(cfg.get('format') == 'biograph-steward.annotation-prior-assessment.v1'
         and cfg.get('parent_authorized_consumed_reference_assessment') is True,
         'parent must authorize this consumed-reference development assessment.')
    need(cfg.get('development_followup_on_consumed_reference') is True
         and cfg.get('independent_confirmation') is False,
         'consumed-reference status must be explicit; independent confirmation is false.')


def validate_plan(plan):
    need(plan.get('format') == 'biograph-steward.annotation-prior-development-plan.v1'
         and plan.get('reference_already_consumed') is True
         and plan.get('independent_confirmation') is False
         and plan.get('original_primary_comparison_unchanged') is True
         and plan.get('application_graph_pruning_or_default_changes') is False
         and plan.get('real_variants', {}).get('count') == 1,
         'one fixed consumed-reference development plan is required.')
    need(plan['published_operator']['annotation_score_as_float64'] == 0.9900000095367432,
         'the source-qualified Float32 annotation score changed.')


def validate_development_provenance(row):
    need(row.get('development_after_reference_opening') is True
         and row.get('reference_previously_consumed') is True
         and row.get('fresh_final_reference_claimed') is False
         and row.get('models_fitted') is False
         and row.get('scientific_metrics_computed') is False
         and row.get('forecast_scores_transformed') is True
         and 'models_fitted_or_scores_computed' not in row,
         'development forecast provenance must distinguish transformed scores from scientific metrics.')


def load_original_counts(folder, original_report, view, setting, aspect, arm, ids, tau):
    """Recheck an immutable original count file and its complete pairing frame."""
    import numpy as np

    rel = '/'.join((view, setting, aspect + '_' + arm + '_counts.npz'))
    need(rel in original_report['files'], 'original contribution artifact is missing.')
    path = Path(folder) / rel
    need(file_sha256(path) == original_report['files'][rel], 'original contribution artifact changed.')
    with np.load(path, allow_pickle=False) as source:
        row = {key: source[key] for key in ('ids', 'tau', 'ordinary', 'eligible')}
    need(np.array_equal(row['ids'], ids) and np.array_equal(row['tau'], tau),
         'original contribution protein/threshold pairing frame differs.')
    values = row['ordinary']
    need(values.shape == (len(ids), len(tau), 6)
         and np.isfinite(values).all() and (values >= 0).all()
         and row['eligible'].shape == (len(ids),), 'original native contribution values are malformed.')
    return row


def combined_bootstrap(original, new, *, candidate=CANDIDATE):
    """Reuse old draw peaks; apply the existing difference/quantile arithmetic."""
    import numpy as np

    need(original['draws'] == new['draws'] == 2000
         and original['seed'] == new['seed'] == 20261113
         and original['raw_proteins'] == new['raw_proteins']
         and original['ordinary_only'] is True and new['ordinary_only'] is True
         and original['shared_protein_samples_across_all_arms'] is True
         and new['shared_protein_samples_across_all_arms'] is True,
         'original/new bootstrap draws do not share the fixed protein design.')
    need(candidate in new['scores'] and not (set(original['scores']) & set(new['scores'])),
         'new bootstrap names must be distinct and include the fixed candidate.')
    result = copy.deepcopy(new)
    result['scores'] = {**copy.deepcopy(original['scores']), **copy.deepcopy(new['scores'])}
    vectors = {}
    for name, row in result['scores'].items():
        values = np.asarray(row['bootstrap_Fmax'], dtype=np.float64)
        need(values.shape == (2000,) and np.isfinite(values).all()
             and (values >= 0).all() and (values <= 1).all(), 'invalid preserved bootstrap peak vector.')
        vectors[name] = values
    comparisons = []
    for name, values in vectors.items():
        if name == candidate:
            continue
        difference = vectors[candidate] - values
        comparisons.append({'candidate': candidate, 'comparator': name,
            'difference_draws': difference.tolist(), 'difference_mean': float(difference.mean()),
            'paired_95_percentile_interval': np.quantile(difference, [.025, .975]).tolist(),
            'fraction_draws_above_zero': float((difference > 0).mean()),
            'interpretation': 'Post-opening development on a consumed reference; conditional unadjusted paired protein interval.'})
    result['comparisons'] = comparisons
    result['original_native_gated_draws_reused_without_recomputation'] = True
    result['development_followup_on_consumed_reference'] = True
    result['independent_confirmation'] = False
    return result


def prior_equivalence(original_point, matched_point, original_bootstrap, new_bootstrap):
    """A score-height control must preserve every Fmax peak, not each curve."""
    import numpy as np

    need(original_point == matched_point, 'matched annotation-only Fmax point differs; stop for integration review.')
    if original_point is None:
        need(original_bootstrap is None and new_bootstrap is None,
             'unscorable prior cannot claim paired-draw equivalence.')
        return {'status': 'unavailable_no_native_prior_coverage', 'equivalence_claimed': False}
    need(original_bootstrap is not None and new_bootstrap is not None,
         'matched annotation-only control requires all paired-draw peaks.')
    first = np.asarray(original_bootstrap['scores'][ORIGINAL_PRIOR]['bootstrap_Fmax'], dtype=np.float64)
    second = np.asarray(new_bootstrap['scores'][MATCHED_PRIOR]['bootstrap_Fmax'], dtype=np.float64)
    need(first.shape == second.shape == (2000,) and np.isfinite(first).all()
         and np.isfinite(second).all() and np.array_equal(first, second),
         'matched annotation-only paired Fmax peaks differ; stop for integration review.')
    return {'status': 'passed', 'native_point_exactly_equal': True,
            'all_2000_paired_draw_peaks_exactly_equal': True,
            'complete_curves_expected_identical': False,
            'reason': 'Moving every positive binary score to Float32(.99) changes upper-grid coverage, not the optimized peak.'}


def prepare_inputs(cfg):
    """Verify the original study and separately admitted development outputs."""
    check_authorization(cfg)
    plan = pinned_json(cfg['plan']);validate_plan(plan)
    review = pinned_json(cfg['independent_plan_review'])
    need(review.get('qualified') is True
         and review.get('plan_sha256') == cfg['plan']['sha256']
         and review.get('development_followup_on_consumed_reference') is True,
         'qualified independent review of this exact development plan is required.')
    seal_path = Path(cfg['original_seal_directory']) / 'forecast_seal.json'
    need(file_sha256(seal_path) == plan['original_forecast_seal_sha256'], 'original forecast seal changed.')
    original_cfg, seal_receipt = open_seal(cfg['original_seal_directory'])
    original = pinned_json(cfg['original_report'])
    need(cfg['original_report']['sha256'] == plan['original_raw_report_sha256']
         and original['forecast_seal_sha256'] == plan['original_forecast_seal_sha256'],
         'original report/seal differs from the fixed follow-up plan.')
    delivery = pinned_json(cfg['merge_delivery'])
    validate_development_provenance(delivery)
    producer = cfg['qualified_producer_source']
    need(file_sha256(producer['file']) == producer['sha256'] == delivery['source_code_sha256'],
         'delivery is not bound to the independently qualified producer source.')
    author = plan['published_operator']
    need(delivery.get('format') == 'biograph-steward.annotation-prior-development-delivery.v1'
         and delivery['original_forecast_seal_sha256'] == plan['original_forecast_seal_sha256']
         and delivery['author_operation']['commit'] == author['revision']
         and delivery['author_operation']['file_sha256'] == author['source_sha256'],
         'delivery is not bound to the approved original seal and author operation.')
    producer_cfg_path = Path(cfg['merge_delivery']['file']).parent / 'configuration.json'
    producer_cfg = pinned_json({'file': str(producer_cfg_path), 'sha256': delivery['config_sha256']})
    need(set(producer_cfg) == {'format', 'original_seal_directory', 'original_seal_sha256', 'author_script'}
         and producer_cfg['format'] == 'biograph-steward.annotation-prior-development.v1'
         and Path(producer_cfg['original_seal_directory']).resolve() == Path(cfg['original_seal_directory']).resolve()
         and producer_cfg['original_seal_sha256'] == plan['original_forecast_seal_sha256']
         and producer_cfg['author_script']['sha256'] == author['source_sha256']
         and file_sha256(producer_cfg['author_script']['file']) == author['source_sha256'],
         'producer configuration is not bound to the fixed approved inputs.')
    targets = tuple(Path(original_cfg['targets']['file']).read_text().splitlines())
    arms = {CANDIDATE: delivery['forecasts'], MATCHED_PRIOR: delivery['matched_prior_forecasts']}
    need(all(set(specs) == set(NS_ASPECT) for specs in arms.values()),
         'all three aspects and both fixed new arms are required.')
    for arm, aspects in arms.items():
        for ns, spec in aspects.items():
            meta = pinned_json(spec)
            validate_development_provenance(meta)
            expected_inputs = {'original_forecast_seal_sha256': plan['original_forecast_seal_sha256'],
                'targets': original_cfg['targets'],
                'selected_model_forecast': original_cfg['arms']['validation_selected_context'][ns],
                'strict_T0_nonexperimental_control': original_cfg['arms'][ORIGINAL_PRIOR][ns],
                'source_inputs_reused_from_original_seal': True,
                'competition_labels_curated_annotations_or_T1_source_accepted': False}
            operation = meta['operation']
            need(meta['original_source_pins'] == expected_inputs
                 and operation['operation'] == 'literal (EntryID,term) union followed by MAX'
                 and operation['author_annotation_score_dtype'] == 'float32'
                 and operation['author_annotation_score_exact'] == author['annotation_score_as_float64']
                 and operation['target_order_preserved'] is True
                 and operation['aliases_resolved_by_operator'] is False
                 and operation['new_soft_MIN_or_ontology_operation'] is False
                 and operation['parent_downcast_clipping_or_rounding'] is False,
                 'forecast is not bound to the fixed original inputs and exact authored union operation.')
            if arm == MATCHED_PRIOR:
                need(meta.get('matched_prior_only') is True and meta.get('model_forecast_is_exactly_zero') is True,
                     'matched prior must explicitly use an exactly zero model.')
            else:
                need(not meta.get('matched_prior_only') and not meta.get('model_forecast_is_exactly_zero'),
                     'the selected-model merge cannot be replaced by a prior-only forecast.')
            validate_source_manifest(spec, targets, arm=arm, namespace=ns)
            paired = pinned_json(arms[MATCHED_PRIOR if arm == CANDIDATE else CANDIDATE][ns])
            need(meta['proteins'] == paired['proteins'] and meta['terms'] == paired['terms'],
                 'merged and matched-prior forecasts must use the identical complete union axis.')
    return plan, original_cfg, seal_receipt, original, arms, targets


def run(cfg, output):
    import numpy as np
    from cafaeval.parser import gt_parser, gt_exclude_parser, update_toi
    from tools.learned_combination.native_adapter import native_ontologies, align_predictions, evaluate_native
    from tools.learned_combination.ordinary_counts import contributions, verify_curve
    from .training import project_native_forecasts

    plan, original_cfg, seal_receipt, original, arms, targets = prepare_inputs(cfg)
    output = Path(output);output.mkdir(parents=True, exist_ok=False)
    # This is deliberately not named a reference-opening gate.
    write_json(output / 'consumed_reference_execution_receipt.json', {
        'created_at': now(), 'development_followup_on_consumed_reference': True,
        'independent_confirmation': False, 'reference_previously_opened': True,
        'original_study_unchanged': True, 'original_report': cfg['original_report'],
        'plan': cfg['plan'], 'independent_plan_review': cfg['independent_plan_review'],
        'merge_delivery': cfg['merge_delivery']})
    tau = np.arange(.001, 1, .001)
    report = {'format': 'biograph-steward.annotation-prior-development-assessment.v1',
        'created_at': now(), 'development_followup_on_consumed_reference': True,
        'independent_confirmation': False, 'original_primary_comparison_unchanged': True,
        'new_success_gate_or_model_selection': False, 'graph_pruning_or_app_promotion': False,
        'original_report': cfg['original_report'], 'plan': cfg['plan'],
        'original_forecast_seal_sha256': plan['original_forecast_seal_sha256'],
        'target_count': len(targets), 'views': {},
        'arm_aspect_scopes': {**original['arm_aspect_scopes'],
                              **{arm: list(specs) for arm, specs in arms.items()}},
        'reference_interpretation': original['reference_interpretation'],
        'interval_interpretation': 'Conditional unadjusted descriptive intervals on an already consumed reference; independent confirmation is not established.'}
    try:
        for view in VIEWS:
            refs = original_cfg['references'][view]
            for spec in refs.values():
                need(file_sha256(spec['file']) == spec['sha256'], 'original reference source changed.')
            ont = update_toi(native_ontologies(refs['obo']['file']), refs['toi']['file'])
            view_result = {'reference_pins': refs, 'cells': {}};report['views'][view] = view_result
            for setting in SETTINGS:
                source_frame = Path(cfg['original_results_directory']) / view / setting
                original_truth = source_frame / 'truth.tsv'
                truth_rel = '/'.join((view, setting, 'truth.tsv'))
                need(file_sha256(original_truth) == original['files'][truth_rel], 'original native truth subset changed.')
                gt = gt_parser(str(original_truth), ont)
                ex = None
                if setting == 'PK' and gt:
                    known = source_frame / 'known.tsv';known_rel = '/'.join((view, setting, 'known.tsv'))
                    need(file_sha256(known) == original['files'][known_rel], 'original native known subset changed.')
                    ex = gt_exclude_parser(str(known), gt, ont)
                frame = output / view / setting;frame.mkdir(parents=True)
                for ns, aspect in NS_ASPECT.items():
                    key = setting + '/' + ns;old_cell = original['views'][view]['cells'][key]
                    cell = copy.deepcopy(old_cell)
                    cell.pop('source_slice_points', None)
                    cell.pop('positive_reference_score_ledger', None)
                    cell['original_methods_and_bootstrap_read_only'] = True
                    for field in ('bootstrap', 'GCN_MLP_bootstrap', 'updated_seed_bootstrap',
                                  'updated_seed_soft_bootstrap', 'current_T0_curated_bootstrap'):
                        cell.pop(field, None)
                    view_result['cells'][key] = cell
                    if ns not in gt:
                        need(old_cell['status'] == 'reference_absent', 'original reference availability changed.')
                        cell['new_arms'] = {'status': 'reference_absent'}
                        write_json(frame / (aspect + '_summary.json'), cell);continue
                    need(old_cell['status'] == 'evaluated', 'original evaluated cell is missing.')
                    ids = np.asarray([p for p, _ in sorted(gt[ns].ids.items(), key=lambda item: item[1])])
                    original_eligible = None
                    for arm, method in old_cell['methods'].items():
                        row = load_original_counts(cfg['original_results_directory'], original,
                                                   view, setting, aspect, arm, ids, tau)
                        if original_eligible is None: original_eligible = row['eligible'].copy()
                        need(np.array_equal(row['eligible'], original_eligible), 'original native admission masks differ.')
                        if method['eligible_proteins']:
                            need(method['native_curve_agreement'].get('author_point_agreement_passed') is True,
                                 'an original control lacks its native full-curve gate.')
                        del row
                    arrays = {}
                    for arm in NEW_ARMS:
                        print(now(), 'DEVELOPMENT_EVALUATE', view, setting, ns, arm, flush=True)
                        meta = pinned_json(arms[arm][ns])
                        values = np.load(meta['prediction_file'], mmap_mode='r', allow_pickle=False)
                        pred, projection = project_native_forecasts(meta['proteins'], meta['terms'], values,
                            ont[ns], upper_roundoff_tolerance=0.)
                        pred = align_predictions({ns: pred}, {ns: gt[ns]})
                        exclude = None if ex is None else {ns: ex[ns]}
                        curve, points = evaluate_native(pred, {ns: gt[ns]}, ont, gt_exclude=exclude,
                            tau=tau, n_cpu=cfg.get('n_cpu', original_cfg['n_cpu']))
                        curve.to_csv(frame / (aspect + '_' + arm + '_curves.tsv'), sep='\t', index=False)
                        counts, eligible = contributions(pred[ns], gt[ns], ont[ns], tau,
                            exclude=None if ex is None else ex[ns])
                        need(np.array_equal(eligible, original_eligible), 'new native row admission differs from the original.')
                        residual = int(np.count_nonzero(counts[:, 0, 1] + counts[:, 0, 3]))
                        parity = verify_curve(counts, curve, namespace=ns) if residual else {
                            'status': 'unscorable_no_residual_reference_proteins'}
                        arrays[arm] = {'ids': ids, 'tau': tau, 'ordinary': counts}
                        np.savez_compressed(frame / (aspect + '_' + arm + '_counts.npz'),
                            **arrays[arm], eligible=eligible)
                        point = points.get(ns)
                        cell['methods'][arm] = {'native_micro_fmax': point,
                            'status': 'evaluated' if point is not None else 'no_native_coverage',
                            'pre_exclusion_GT_proteins': int(eligible.sum()), 'eligible_proteins': residual,
                            'raw_native_reference_proteins': len(ids), 'native_curve_agreement': parity,
                            'forecast_projection': projection,
                            'development_followup_on_consumed_reference': True}
                        del pred, values
                    old_boot = old_cell.get('bootstrap')
                    can_boot = (len(ids) > 1 and old_boot is not None
                        and old_boot.get('status') != 'unavailable'
                        and all(cell['methods'][arm]['status'] == 'evaluated' for arm in NEW_ARMS))
                    new_boot = bootstrap_contrast(arrays, CANDIDATE) if can_boot else None
                    cell['matched_prior_integration_gate'] = prior_equivalence(
                        old_cell['methods'][ORIGINAL_PRIOR]['native_micro_fmax'],
                        cell['methods'][MATCHED_PRIOR]['native_micro_fmax'], old_boot if can_boot else None, new_boot)
                    if can_boot:
                        cell['bootstrap'] = combined_bootstrap(old_boot, new_boot)
                    else:
                        cell['bootstrap'] = {'status': 'unavailable',
                            'reason': 'original paired design or new native coverage unavailable; no confirmation claimed'}
                    cell['development_followup_on_consumed_reference'] = True
                    cell['independent_confirmation'] = False
                    write_json(frame / (aspect + '_summary.json'), cell)
                    del arrays
            write_json(output / view / 'view_summary.json', view_result)
        report['files'] = {str(p.relative_to(output)): file_sha256(p)
                           for p in output.rglob('*') if p.is_file()}
        write_json(output / 'report.json', report)
        return report
    except Exception as error:
        write_json(output / 'failure.json', {'created_at': now(), 'exception': repr(error),
            'traceback': traceback.format_exc(), 'partial_results_preserved': True,
            'development_followup_on_consumed_reference': True,
            'original_study_unchanged': True})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True);parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(json.loads(Path(args.config).read_text()), Path(args.output))


if __name__ == '__main__':
    main()
