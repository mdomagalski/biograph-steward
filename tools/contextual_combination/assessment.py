# SPDX-License-Identifier: GPL-3.0-only
"""Seal label-free forecasts, then run both pinned temporal reference views.

Uses the existing native evaluator, alias/MAX intake, curve-parity gate and
paired protein bootstrap. No alternative metric or annotation construction is
implemented here. A complete forecast seal must exist before references open.
"""
import argparse
import json
import math
from pathlib import Path
import traceback

from tools.learned_combination.core import LOCALPLUS_UPPER_ROUNDOFF, need, validate_axes
from tools.learned_combination.reference import file_sha256
from tools.learned_combination.runner import NS_ASPECT, now, subset_reference, write_json
from .protocol import PROTOCOL


VIEWS = ('native', 'fixed_T0')
SETTINGS = ('PK', 'NK', 'LK')
CANDIDATE = 'validation_selected_context'
REQUIRED_ARMS = tuple(PROTOCOL['evaluation']['controls']) + (CANDIDATE,)
# A source-qualified development extension may be declared only for BPO. The
# existing complete three-aspect families and final candidate remain mandatory.
OPTIONAL_ASPECT_ARMS = {'coded_context_gcn': ('biological_process',)}
CONTEXT_ARMS = ('context_mlp', 'context_gcn', 'coded_context_gcn')


def pinned_json(spec):
    need(file_sha256(spec['file']) == spec['sha256'], 'changed pinned metadata: ' + spec['file'])
    return json.loads(Path(spec['file']).read_text())


def validate_source_manifest(spec, targets, *, arm, namespace):
    """Scan only forecast values; require literal full target identities."""
    import numpy as np

    meta = pinned_json(spec)
    proteins, terms = validate_axes(meta['proteins'], meta['terms'])
    need(proteins == tuple(targets), 'forecast does not retain the full ordered target union.')
    need(meta['namespace'] == namespace, 'forecast namespace metadata differs.')
    need(meta.get('final_reference_labels_read_for_forecasting') is False,
         'label-free forecast provenance must be explicit.')
    tolerance = meta.get('upper_roundoff_tolerance', 0.)
    need(tolerance == 0. or (arm in ('localplus', 'localplus_model_axis_raw')
                            and tolerance == LOCALPLUS_UPPER_ROUNDOFF),
         'only literal LocalPlus arms may use their qualified upper-roundoff allowance.')
    need(file_sha256(meta['prediction_file']) == meta['prediction_sha256'], 'forecast values changed.')
    values = np.load(meta['prediction_file'], mmap_mode='r', allow_pickle=False)
    need(values.dtype in (np.dtype('float32'), np.dtype('float64'))
         and values.shape == (len(proteins), len(terms)), 'forecast shape/dtype differs from explicit axes.')
    for start in range(0, len(proteins), 32):
        block = values[start:start + 32]
        need(np.isfinite(block).all() and (block >= 0).all() and (block <= 1 + tolerance).all(),
             'nonfinite or unqualified forecast probability; no clipping is permitted.')
    return {**spec, 'prediction_file': meta['prediction_file'],
            'prediction_sha256': meta['prediction_sha256'], 'rows': len(proteins),
            'columns': len(terms), 'dtype': str(values.dtype), 'upper_roundoff_tolerance': tolerance}


def select_context_arm(scores, namespace):
    """Highest consumed-validation SWA score, with a fixed simplicity tie rule."""
    required = {'context_mlp', 'context_gcn'}
    allowed = required | ({'coded_context_gcn'} if namespace == 'biological_process' else set())
    need(namespace in NS_ASPECT and required <= set(scores) <= allowed,
         'complete predeclared contextual validation candidates required.')
    for score in scores.values():
        need(not isinstance(score, bool) and isinstance(score, (float, int))
             and math.isfinite(score) and 0 <= score <= 1, 'finite consumed-validation Fmax scores required.')
    return max(scores, key=lambda arm: (scores[arm], -CONTEXT_ARMS.index(arm)))


def validate_choice_aliases(arms, choices):
    """The selected arm must literally reuse its preselected candidate scores."""
    need(choices['fresh_final_reference_opened'] is False, 'model choice followed final-reference access.')
    for ns in NS_ASPECT:
        row = choices['selections'][ns]
        selected = row['selected_arm']
        need(selected in CONTEXT_ARMS and selected in arms and ns in arms[selected],
             'selected contextual arm must be explicitly declared for this aspect.')
        need(selected == select_context_arm(row['validation_scores'], ns),
             'selected contextual arm is not the fixed consumed-validation winner.')
        eligible = {a for a in CONTEXT_ARMS if a in arms and ns in arms[a]}
        need(set(row['validation_scores']) == eligible,
             'every eligible declared contextual candidate must enter validation selection.')
        need(set(row['model_metadata']) == set(row['validation_scores']), 'every validation score needs its model-source pin.')
        for arm, score in row['validation_scores'].items():
            model_spec = row['model_metadata'][arm]
            model = pinned_json(model_spec)
            need(model['namespace'] == ns and model['fresh_final_reference_opened'] is False
                 and model['validation_ordinary_micro_fmax'] == score,
                 'reported validation score differs from its source model metadata.')
            forecast = pinned_json(arms[arm][ns])
            need(forecast['model_metadata_sha256'] == model_spec['sha256'],
                 'final contextual forecast is not bound to its validation-selected model.')
            need(model['n_layers'] == (0 if arm == 'context_mlp' else 8),
                 'declared contextual arm has the wrong native layer count.')
            if arm == 'coded_context_gcn':
                from .training import axis_sha
                channels = model['context_channels']
                need(len(channels) == len(set(channels)) == model['in_goa'] == 40
                     and axis_sha(channels) == model['context_channels_sha256']
                     and forecast['context_channels'] == channels
                     and forecast['in_goa'] == 40
                     and forecast['context_channels_sha256'] == model['context_channels_sha256'],
                     'coded-context model and forecast channel identities/order differ.')
            else:
                # Original immutable one-channel model artifacts predate the
                # variable-context API. Their pinned v4 training constructor
                # explicitly used in_goa1; never rewrite those source files.
                need(model.get('in_goa', 1) == 1 and forecast.get('in_goa', 1) == 1,
                     'legacy one-channel contextual arm has a different context width.')
        chosen = pinned_json(arms[CANDIDATE][ns])
        source = pinned_json(arms[selected][ns])
        need(chosen['proteins'] == source['proteins'] and chosen['terms'] == source['terms']
             and chosen['prediction_sha256'] == source['prediction_sha256']
             and chosen['model_metadata_sha256'] == source['model_metadata_sha256'],
             'selected final scores differ from the preselected contextual arm.')


def validate_source_slices(spec, targets):
    result = pinned_json(spec)
    need(result['fresh_final_reference_opened'] is False, 'coverage slices must be defined before outcomes.')
    universe = set(targets)
    for row in result['slices'].values():
        need(row.get('definition') and len(row['ids']) == len(set(row['ids']))
             and set(row['ids']) <= universe, 'source slice must retain explicit unique in-frame IDs and definition.')
    for partition in result.get('partitions', []):
        seen = set()
        for name in partition:
            ids = set(result['slices'][name]['ids'])
            need(not (seen & ids), 'source partition overlaps.')
            seen.update(ids)
        need(seen == universe, 'source partition does not retain the complete target union.')
    return result


def source_slice_points(arrays, definitions):
    """Describe fixed source subgroups using the already native-gated counts.

    The established micro_fmax arithmetic receives summed per-protein counts.
    These are descriptive derived readouts, without new fitting or inference
    from a favorable subgroup to the full comparison.
    """
    import numpy as np
    from tools.cafa_reference.paired_bootstrap import micro_fmax

    first = next(iter(arrays.values()))
    result = {}
    for name, spec in definitions['slices'].items():
        wanted = set(spec['ids'])
        rows = np.asarray([p in wanted for p in first['ids']], dtype=bool)
        item = {'definition': spec['definition'], 'full_source_slice_proteins': len(wanted),
                'raw_native_reference_proteins': int(rows.sum()), 'methods': {},
                'readout': 'descriptive subset of full-curve-gated native per-protein counts',
                'deployed_threshold_or_model_selection': False,
                'evaluation_threshold_optimization': 'benchmark Fmax on the already fixed grid'}
        for arm, array in arrays.items():
            values = array['ordinary'][rows]
            residual = int(np.count_nonzero(values[:, 0, 1] + values[:, 0, 3]))
            coverage = bool(np.any(values[:, :, 0] > 0))
            point = (float(micro_fmax(values, np.ones((1, len(values)), dtype=np.float64))[0])
                     if residual and coverage else None)
            item['methods'][arm] = {'eligible_proteins': residual, 'derived_micro_fmax': point,
                                   'positive_forecast_coverage_on_grid': coverage}
        result[name] = item
    return result


def seal(cfg, output):
    """Pin every source/forecast and the choices before any new term decoding.

    Reference files are not opened in this phase, even for hashing. Their hashes
    were supplied by the separate native construction pipeline. This is an
    access-order boundary for a retrospective comparison, not a blindness claim.
    """
    need(cfg['format'] == 'biograph-steward.contextual-assessment.v1'
         and cfg['protocol'] == PROTOCOL, 'assessment configuration/protocol differs.')
    need(set(cfg['references']) == set(VIEWS), 'both declared reference views required.')
    need(set(REQUIRED_ARMS) <= set(cfg['arms']), 'complete predeclared comparator arms required.')
    need(set(cfg['arms']) <= set(REQUIRED_ARMS) | set(OPTIONAL_ASPECT_ARMS),
         'an undeclared comparator or development family was supplied.')
    need(file_sha256(cfg['targets']['file']) == cfg['targets']['sha256'], 'target-identity metadata changed.')
    targets = tuple(Path(cfg['targets']['file']).read_text().splitlines())
    need(len(targets) == cfg['protocol']['cohort']['count'] and len(set(targets)) == len(targets),
         'the complete unique 3,300-target union must be retained.')
    reference_paths = {spec['file'] for refs in cfg['references'].values() for spec in refs.values()}
    need(not (set(cfg['source_pins']) & reference_paths),
         'reference files must not enter the label-free source-pin scan.')
    for path, expected in cfg['source_pins'].items():
        need(file_sha256(path) == expected, 'source or prior-stage receipt changed: ' + path)
    choices = pinned_json(cfg['choices'])
    validate_choice_aliases(cfg['arms'], choices)
    slices = validate_source_slices(cfg['source_slices'], targets) if cfg.get('source_slices') else None
    files = {}
    for arm, aspects in cfg['arms'].items():
        expected = set(OPTIONAL_ASPECT_ARMS.get(arm, NS_ASPECT))
        need(set(aspects) == expected, 'arm differs from its declared aspect scope.')
        files[arm] = {ns: validate_source_manifest(spec, targets, arm=arm, namespace=ns)
                      for ns, spec in aspects.items()}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'configuration.json', cfg)
    result = {'created_at': now(), 'format': 'biograph-steward.contextual-forecast-seal.v1',
              'protocol': PROTOCOL, 'configuration_sha256': file_sha256(output / 'configuration.json'),
              'target_count': len(targets), 'forecasts': files,
              'choices_sha256': cfg['choices']['sha256'], 'choices': choices,
              'source_slices': slices,
              'future_GO_labels_opened': False, 'reference_files_opened_by_seal': False,
              'source_pins': cfg['source_pins']}
    write_json(output / 'forecast_seal.json', result)
    return result


def open_seal(folder):
    """Recheck all pinned forecasts and sources before accepting reference paths."""
    folder = Path(folder)
    receipt = json.loads((folder / 'forecast_seal.json').read_text())
    need(receipt['format'] == 'biograph-steward.contextual-forecast-seal.v1'
         and receipt['protocol'] == PROTOCOL and receipt['future_GO_labels_opened'] is False,
         'complete unchanged pre-reference forecast seal required.')
    cfg_path = folder / 'configuration.json'
    need(file_sha256(cfg_path) == receipt['configuration_sha256'], 'sealed assessment configuration changed.')
    cfg = json.loads(cfg_path.read_text())
    need(cfg['protocol'] == PROTOCOL, 'frozen protocol changed.')
    targets = tuple(Path(cfg['targets']['file']).read_text().splitlines())
    need(file_sha256(cfg['targets']['file']) == cfg['targets']['sha256'], 'sealed target identities changed.')
    for path, expected in receipt['source_pins'].items():
        need(file_sha256(path) == expected, 'sealed source changed: ' + path)
    need(pinned_json(cfg['choices']) == receipt['choices'], 'sealed model choices changed.')
    validate_choice_aliases(cfg['arms'], receipt['choices'])
    if cfg.get('source_slices'):
        need(validate_source_slices(cfg['source_slices'], targets) == receipt['source_slices'],
             'source-defined coverage slices changed after sealing.')
    for arm, aspects in cfg['arms'].items():
        for ns, spec in aspects.items():
            need(validate_source_manifest(spec, targets, arm=arm, namespace=ns)
                 == receipt['forecasts'][arm][ns], 'sealed forecast metadata differs.')
    return cfg, receipt


def bootstrap_contrast(arrays, candidate):
    """Reuse the unchanged paired-bootstrap helper with an explicit name adapter."""
    from tools.learned_combination.ordinary_counts import paired_bootstrap

    need(candidate in arrays and 'learned_mix' not in arrays, 'explicit distinct candidate name required.')
    mapping = {('learned_mix' if name == candidate else name): value for name, value in arrays.items()}
    result = paired_bootstrap(mapping)
    result['candidate_name_adapter'] = {'learned_mix': candidate}
    result['scores'][candidate] = result['scores'].pop('learned_mix')
    for comparison in result['comparisons']:
        need(comparison['candidate'] == 'learned_mix', 'unexpected reused candidate identity.')
        comparison['candidate'] = candidate
    return result


def positive_interval(cell, comparator):
    if cell.get('status') != 'evaluated' or 'bootstrap' not in cell:
        return False
    boot = cell['bootstrap']
    if boot.get('status') == 'unavailable':
        return False
    contrast = next((c for c in boot['comparisons'] if c['comparator'] == comparator), None)
    if contrast is None:
        return False
    candidate_point = cell['methods'][CANDIDATE]['native_micro_fmax']
    control_point = cell['methods'][comparator]['native_micro_fmax']
    return bool(candidate_point is not None and control_point is not None
                and candidate_point > control_point and contrast['paired_95_percentile_interval'][0] > 0)


def evaluate(sealed, output):
    """Open both immutable reference views, retaining all nine declared cells."""
    import numpy as np
    from cafaeval.parser import gt_parser, gt_exclude_parser, update_toi
    from tools.learned_combination.native_adapter import native_ontologies, align_predictions, evaluate_native
    from tools.learned_combination.ordinary_counts import contributions, verify_curve
    from .training import project_native_forecasts

    cfg, receipt = open_seal(sealed)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'reference_opening_gate.json', {
        'created_at': now(), 'forecast_seal_sha256': file_sha256(Path(sealed) / 'forecast_seal.json'),
        'all_forecasts_reverified': True, 'reference_opened_after_forecast_sealing': True})
    tau = np.arange(.001, 1, .001)
    targets = tuple(Path(cfg['targets']['file']).read_text().splitlines())
    arms = tuple(cfg['arms'])
    report = {'created_at': now(), 'protocol': PROTOCOL,
              'forecast_seal_sha256': file_sha256(Path(sealed) / 'forecast_seal.json'),
              'target_count': len(targets), 'model_choices': receipt['choices'], 'views': {},
              'arm_aspect_scopes': {arm: list(aspects) for arm, aspects in cfg['arms'].items()},
              'automatic_graph_or_app_promotion': False,
              'reference_interpretation': 'Later curator annotation recovery; unmatched predictions are not biological negatives.'}
    try:
        for view in VIEWS:
            root = output / view
            root.mkdir()
            refs = cfg['references'][view]
            need(set(refs) == {'obo', 'toi', 'PK', 'PK_known', 'NK', 'LK'}, 'incomplete reference roles.')
            for spec in refs.values():
                need(file_sha256(spec['file']) == spec['sha256'], 'changed sealed-reference source: ' + spec['file'])
            ont = update_toi(native_ontologies(refs['obo']['file']), refs['toi']['file'])
            view_result = {'reference_pins': refs, 'cells': {}}
            report['views'][view] = view_result
            for setting in SETTINGS:
                frame = root / setting
                frame.mkdir()
                truth_audit = subset_reference([refs[setting]['file']], targets, frame / 'truth.tsv')
                gt = gt_parser(str(frame / 'truth.tsv'), ont)
                ex, known_audit = None, None
                if setting == 'PK' and gt:
                    known_audit = subset_reference([refs['PK_known']['file']], targets, frame / 'known.tsv')
                    ex = gt_exclude_parser(str(frame / 'known.tsv'), gt, ont)
                for ns, aspect in NS_ASPECT.items():
                    cell = {'setting': setting, 'namespace': ns, 'status': 'reference_absent',
                            'reference': truth_audit, 'known': known_audit, 'methods': {}}
                    view_result['cells'][setting + '/' + ns] = cell
                    if ns not in gt:
                        write_json(frame / (aspect + '_summary.json'), cell)
                        continue
                    arrays = {}
                    ids = np.asarray([p for p, i in sorted(gt[ns].ids.items(), key=lambda item: item[1])])
                    for arm in arms:
                        if ns not in cfg['arms'][arm]:
                            continue  # Explicit BPO-only extension, not a missing forecast.
                        print(now(), 'EVALUATE', view, setting, ns, arm, flush=True)
                        meta = pinned_json(cfg['arms'][arm][ns])
                        values = np.load(meta['prediction_file'], mmap_mode='r', allow_pickle=False)
                        pred, projection = project_native_forecasts(meta['proteins'], meta['terms'], values,
                            ont[ns], upper_roundoff_tolerance=meta.get('upper_roundoff_tolerance', 0.))
                        pred = align_predictions({ns: pred}, {ns: gt[ns]})
                        exclude = None if ex is None else {ns: ex[ns]}
                        curve, points = evaluate_native(pred, {ns: gt[ns]}, ont,
                            gt_exclude=exclude, tau=tau, n_cpu=cfg['n_cpu'])
                        curve.to_csv(frame / (aspect + '_' + arm + '_curves.tsv'), sep='\t', index=False)
                        counts, eligible = contributions(pred[ns], gt[ns], ont[ns], tau,
                                                         exclude=None if ex is None else ex[ns])
                        residual = int(np.count_nonzero(counts[:, 0, 1] + counts[:, 0, 3]))
                        parity = (verify_curve(counts, curve, namespace=ns) if residual else
                                  {'status': 'unscorable_no_residual_reference_proteins'})
                        arrays[arm] = {'ids': ids, 'tau': tau, 'ordinary': counts}
                        np.savez_compressed(frame / (aspect + '_' + arm + '_counts.npz'),
                                            **arrays[arm], eligible=eligible)
                        point = points.get(ns)
                        cell['methods'][arm] = {'native_micro_fmax': point,
                            'status': 'evaluated' if point is not None else 'no_native_coverage',
                            'pre_exclusion_GT_proteins': int(eligible.sum()),
                            'eligible_proteins': residual, 'raw_native_reference_proteins': len(ids),
                            'native_curve_agreement': parity, 'forecast_projection': projection}
                        print(now(), 'POINT', view, setting, ns, arm, point, flush=True)
                        del pred, values
                    cell['status'] = 'evaluated'
                    if receipt.get('source_slices'):
                        cell['source_slice_points'] = source_slice_points(arrays, receipt['source_slices'])
                    if len(ids) > 1 and all(m['status'] == 'evaluated' for m in cell['methods'].values()):
                        cell['bootstrap'] = bootstrap_contrast(arrays, CANDIDATE)
                        cell['GCN_MLP_bootstrap'] = bootstrap_contrast(
                            {k: arrays[k] for k in ('context_gcn', 'context_mlp')}, 'context_gcn')
                    else:
                        cell['bootstrap'] = {'status': 'unavailable',
                            'reason': 'fewer than two native reference proteins or an arm has no native coverage'}
                    write_json(frame / (aspect + '_summary.json'), cell)
                    del arrays
            write_json(root / 'view_summary.json', view_result)
        primary = {v: report['views'][v]['cells']['PK/biological_process'] for v in VIEWS}
        report['primary_success_over_literal_LocalPlus_both_views'] = all(
            positive_interval(c, 'localplus') for c in primary.values())
        report['primary_success_over_raw_and_soft_LocalPlus_both_views'] = all(
            positive_interval(c, arm) for c in primary.values() for arm in ('localplus', 'localplus_soft'))
        report['primary_success_over_nonexperimental_context_both_views'] = all(
            positive_interval(c, 'native_T0_nonexperimental') for c in primary.values())
        strong_controls = tuple(a for a in arms if a not in (CANDIDATE, *CONTEXT_ARMS))
        report['primary_success_over_all_noncontext_controls_both_views'] = all(
            positive_interval(c, arm) for c in primary.values()
            for arm in strong_controls)
        report['files'] = {str(p.relative_to(output)): file_sha256(p)
                           for p in output.rglob('*') if p.is_file()}
        write_json(output / 'report.json', report)
        return report
    except Exception as error:
        write_json(output / 'failure.json', {'created_at': now(), 'exception': repr(error),
                                            'traceback': traceback.format_exc(), 'partial_results_preserved': True})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('seal', 'evaluate'))
    parser.add_argument('--config')
    parser.add_argument('--sealed')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.phase == 'seal':
        seal(json.loads(Path(args.config).read_text()), args.output)
    else:
        evaluate(args.sealed, args.output)


if __name__ == '__main__':
    main()
