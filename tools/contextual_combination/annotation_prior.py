# SPDX-License-Identifier: GPL-3.0-only
"""One source-qualified, consumed-reference annotation-prior development arm.

Adapts only the author's final Float32(.99)/literal-key MAX operation. Inputs
are the unchanged already-soft selected forecasts and strict T0 nonexperimental
control from the original seal. No fitting, new ontology operation or scoring.
"""
import argparse
import json
from pathlib import Path

from tools.learned_combination.core import need, validate_axes
from tools.learned_combination.reference import file_sha256
from tools.learned_combination.runner import NS_ASPECT, write_json
from .postprocessing import POSTPROCESS_SOURCE_PINS, SOFT_RATE, MAX_MIN_RATE


ORIGINAL_SEAL_SHA256 = 'a41920a505c68dcc67891be66381b30eac4a028ddb459c52e7081a7e06250eb9'
TARGET_COUNT = 3300
AUTHOR_COMMIT = '0ee85d2f07f724be1721ea39211f1b364535f976'
AUTHOR_SCRIPT_SHA256 = 'fd85e98fa815ae7459f99caffb92221f76d5e4a781a4b6e4f0eda51c3ba6d5b2'
AUTHOR_SCRIPT_URL = ('https://github.com/btbpanda/CAFA6-updates/blob/' + AUTHOR_COMMIT
                     + '/model_scripts/postproc_and_sub.py')


def _array(values, shape, *, binary):
    import numpy as np

    values = np.asarray(values)
    allowed = (np.dtype('bool'), np.dtype('float32'), np.dtype('float64')) if binary else (
        np.dtype('float32'), np.dtype('float64'))
    need(values.dtype in allowed and values.shape == shape, 'prior-union shape/dtype differs from literal axes.')
    for start in range(0, len(values), 32):
        block = values[start:start + 32]
        need(np.isfinite(block).all() and (block >= 0).all() and (block <= 1).all(),
             'prior union requires finite [0,1] inputs; no clipping is allowed.')
        if binary:
            need(((block == 0) | (block == 1)).all(), 'annotation control must be binary positive membership.')
    return values


def merge_full_union(proteins, model_terms, model_values, prior_proteins, prior_terms, prior_values):
    """Literal-key MAX after the existing soft stage; aliases remain distinct.

    Parent values retain their numerical precision. The fixed annotation score
    is first represented as author Float32(.99), even for float64 parents.
    """
    import numpy as np

    proteins, model_terms = validate_axes(proteins, model_terms)
    prior_proteins, prior_terms = validate_axes(prior_proteins, prior_terms)
    need(proteins == prior_proteins, 'literal complete target order differs; no implicit reindexing.')
    model = _array(model_values, (len(proteins), len(model_terms)), binary=False)
    prior = _array(prior_values, (len(proteins), len(prior_terms)), binary=True)
    model_set = set(model_terms)
    terms = model_terms + tuple(term for term in prior_terms if term not in model_set)
    lookup = {term: column for column, term in enumerate(terms)}
    columns = np.asarray([lookup[term] for term in prior_terms], dtype=np.int64)
    result = np.zeros((len(proteins), len(terms)), dtype=model.dtype)
    result[:, :len(model_terms)] = model
    annotation_score = np.float32(.99)
    positive_cells = 0; positive_proteins = 0
    for start in range(0, len(proteins), 32):
        block = prior[start:start + 32]
        rows, local_columns = np.nonzero(block)
        destination = columns[local_columns]
        positive_cells += len(rows); positive_proteins += int(np.any(block, axis=1).sum())
        # Do not touch a model cell where no source annotation is present.
        # This also retains signed zero and every parent mantissa bit.
        result[start + rows, destination] = np.maximum(
            result[start + rows, destination], annotation_score)
    return terms, result, {
        'operation': 'literal (EntryID,term) union followed by MAX',
        'author_annotation_score_dtype': 'float32',
        'author_annotation_score_exact': float(annotation_score),
        'model_dtype': str(model.dtype), 'output_dtype': str(result.dtype),
        'model_source_heads': len(model_terms), 'prior_source_heads': len(prior_terms),
        'union_heads': len(terms), 'appended_prior_heads': len(terms) - len(model_terms),
        'prior_positive_cells': positive_cells, 'prior_positive_proteins': positive_proteins,
        'target_rows': len(proteins), 'target_order_preserved': True,
        'aliases_resolved_by_operator': False, 'new_soft_MIN_or_ontology_operation': False,
        'parent_downcast_clipping_or_rounding': False,
        'next_stage': 'existing native evaluator exact/alternative-ID MAX, then fill once',
        'score_is_calibrated_biological_confidence': False,
        'guarantees_Fmax_at_least_annotation_baseline': False}


def _json(path, expected):
    need(file_sha256(path) == expected, 'changed original sealed metadata: ' + str(path))
    return json.loads(Path(path).read_text())


def read_original_pair(directory, seal_sha256, namespace):
    """No annotation-source parameter: only the original presealed T0 control."""
    from .assessment import validate_source_manifest
    import numpy as np

    need(namespace in NS_ASPECT and seal_sha256 == ORIGINAL_SEAL_SHA256,
         'only the original presealed strict T0 nonexperimental control is admitted.')
    folder = Path(directory)
    seal = _json(folder / 'forecast_seal.json', ORIGINAL_SEAL_SHA256)
    need(seal['format'] == 'biograph-steward.contextual-forecast-seal.v1'
         and seal['future_GO_labels_opened'] is False,
         'the original pre-reference forecast seal is required.')
    cfg = _json(folder / 'configuration.json', seal['configuration_sha256'])
    target_spec = cfg['targets']
    need(file_sha256(target_spec['file']) == target_spec['sha256'], 'original target list changed.')
    targets = tuple(Path(target_spec['file']).read_text().splitlines())
    need(len(targets) == len(set(targets)) == seal['target_count'] == TARGET_COUNT,
         'the entire original ordered target universe is required.')
    models = {}
    for arm in ('validation_selected_context', 'native_T0_nonexperimental'):
        spec = cfg['arms'][arm][namespace]
        verified = validate_source_manifest(spec, targets, arm=arm, namespace=namespace)
        need(verified == seal['forecasts'][arm][namespace], 'original source/seal declaration differs.')
        metadata = _json(spec['file'], spec['sha256'])
        values = np.load(metadata['prediction_file'], mmap_mode='r', allow_pickle=False)
        models[arm] = metadata, values, spec
    parent, values, parent_spec = models['validation_selected_context']
    post = parent['postprocessing']
    need(post['source_sha256'] == POSTPROCESS_SOURCE_PINS and post['soft_rate'] == SOFT_RATE
         and post['max_min_rate'] == MAX_MIN_RATE and post['annotation_or_reference_files_read'] is False,
         'input must be the original already-soft, annotation-unmerged selected forecast.')
    prior, membership, prior_spec = models['native_T0_nonexperimental']
    _array(membership, (len(targets), len(prior['terms'])), binary=True)
    return parent, values, prior, membership, {
        'original_forecast_seal_sha256': seal_sha256, 'targets': target_spec,
        'selected_model_forecast': parent_spec, 'strict_T0_nonexperimental_control': prior_spec,
        'source_inputs_reused_from_original_seal': True,
        'competition_labels_curated_annotations_or_T1_source_accepted': False}


def run(config, output):
    """Generate one three-aspect DEVELOPMENT arm; never evaluate or promote it."""
    import numpy as np

    need(set(config) == {'format', 'original_seal_directory', 'original_seal_sha256', 'author_script'}
         and config['format'] == 'biograph-steward.annotation-prior-development.v1',
         'only the fixed development input contract is accepted; no extra source or rate.')
    need(config['author_script']['sha256'] == AUTHOR_SCRIPT_SHA256
         and file_sha256(config['author_script']['file']) == AUTHOR_SCRIPT_SHA256,
         'the qualified author MAX/Float32 score operation source changed.')
    output = Path(output); need(not output.exists(), 'choose a new development output directory.')
    # Validate the source gate before creating any generated forecast artifact.
    need(config['original_seal_sha256'] == ORIGINAL_SEAL_SHA256,
         'only the original presealed strict T0 nonexperimental control is admitted.')
    output.mkdir(parents=True)
    write_json(output / 'configuration.json', config)
    results, matched = {}, {}
    for namespace in NS_ASPECT:
        parent, values, prior, membership, pins = read_original_pair(
            config['original_seal_directory'], config['original_seal_sha256'], namespace)
        terms, merged, audit = merge_full_union(parent['proteins'], parent['terms'], values,
                                               prior['proteins'], prior['terms'], membership)
        # Algebraic control for the authored .99 floor: the exact same union
        # operation with a zero model, keeping even model-only heads and rows.
        zero_model = np.zeros(values.shape, dtype=np.float32)
        control_terms, control, control_audit = merge_full_union(
            parent['proteins'], parent['terms'], zero_model,
            prior['proteins'], prior['terms'], membership)
        need(control_terms == terms, 'matched annotation control has a different literal union axis.')
        del zero_model
        folder = output / namespace; folder.mkdir()
        prediction = folder / 'predictions.npy'; np.save(prediction, merged, allow_pickle=False)
        meta = {'format': 'biograph-steward.annotation-prior-forecast.v1', 'namespace': namespace,
            'proteins': parent['proteins'], 'terms': list(terms),
            'prediction_file': str(prediction), 'prediction_sha256': file_sha256(prediction),
            'model_metadata_sha256': parent['model_metadata_sha256'],
            'original_source_pins': pins, 'operation': audit,
            'development_after_reference_opening': True, 'reference_previously_consumed': True,
            'fresh_final_reference_claimed': False, 'automatic_graph_or_app_promotion': False,
            'models_fitted': False, 'scientific_metrics_computed': False,
            'forecast_scores_transformed': True,
            'final_reference_labels_read_for_forecasting': False}
        path = folder / 'predictions.json'; write_json(path, meta)
        results[namespace] = {'file': str(path), 'sha256': file_sha256(path),
                              'namespace': namespace, 'operation': audit}
        control_path = folder / 'annotation_only_099.npy'; np.save(control_path, control, allow_pickle=False)
        control_meta = {key: value for key, value in meta.items()
                        if key not in ('model_metadata_sha256', 'prediction_file', 'prediction_sha256', 'operation')}
        control_meta.update(prediction_file=str(control_path), prediction_sha256=file_sha256(control_path),
            operation=control_audit, matched_prior_only=True, model_forecast_is_exactly_zero=True)
        control_json = folder / 'annotation_only_099.json'; write_json(control_json, control_meta)
        matched[namespace] = {'file': str(control_json), 'sha256': file_sha256(control_json),
                              'namespace': namespace, 'operation': control_audit}
        del merged, control, values, membership
    receipt = {'format': 'biograph-steward.annotation-prior-development-delivery.v1',
        'source_code_sha256': file_sha256(__file__), 'config_sha256': file_sha256(output / 'configuration.json'),
        'original_forecast_seal_sha256': ORIGINAL_SEAL_SHA256,
        'author_operation': {'commit': AUTHOR_COMMIT, 'file_sha256': AUTHOR_SCRIPT_SHA256,
            'URL': AUTHOR_SCRIPT_URL, 'full_author_pipeline_reproduced': False,
            'input_adaptation': 'only presealed strict T0 nonexperimental positives; no competition labels'},
        'stage_order': ['original published soft processing already complete',
                        'literal full-head union/MAX with author Float32(.99)',
                        'existing evaluator canonicalization/fill only, owned by caller'],
        'forecasts': results, 'matched_prior_forecasts': matched,
        'matched_control': 'same union/Float32(.99) operation with exact-zero model; compare to original score1 prior',
        'development_only': True, 'development_after_reference_opening': True,
        'reference_previously_consumed': True, 'fresh_final_reference_claimed': False,
        'models_fitted': False, 'scientific_metrics_computed': False,
        'forecast_scores_transformed': True, 'reference_labels_read': False}
    write_json(output / 'delivery.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(run(json.loads(Path(args.config).read_text()), args.output), indent=2))
