# SPDX-License-Identifier: GPL-3.0-only
"""Two fixed BP source controls for a consumed-reference development refit.

This module composes existing positive source sets and calls the unchanged
published LocalPlus helper. It neither changes the original producer guards
nor accepts validation/reference labels. Source admission is separate from
these small operators; real generation requires the frozen source contract.
"""
import argparse
import json
from pathlib import Path

from tools.learned_combination.core import need, validate_axes
from tools.learned_combination.reference import file_sha256
from tools.learned_combination.runner import write_json
from .current_annotation import ASPECT as CURRENT_ASPECT
from .freshness_controls import ASPECT as LEGACY_ASPECT, union_training, by_head
from .forecast import query_frame
from .annotation_prior import _array
from .prepare import _check_path


NAMESPACE = 'biological_process'
LOCALPLUS = 'retained_and_current_curated_LocalPlus'
DIRECT = 'T0_nonexperimental_plus_retained_curated_prior'
ARMS = (LOCALPLUS, DIRECT)
FINAL_COUNT = 3300
FIT_COUNT = 4040
ORIGINAL_SEAL_SHA256 = 'a41920a505c68dcc67891be66381b30eac4a028ddb459c52e7081a7e06250eb9'
STRICT_GRAPH_SHA256 = '41547ab466240f05b99e361f3f1b1f16afbbcd0e2c17d8f0c49d8a8668f0de9b'
ORIGINAL_NONEXPERIMENTAL_BP_SHA256 = '566c08e0a45cd3f938b3e9cb120c299ec98775651984556c1c480dad83f4c96f'
RETAINED_UNION_RECEIPT_SHA256 = '00d1f816a614ef6a04154691e792159aa5960c150211f0b52985ecbe01655834'
RETAINED_UNION_SEEDS_SHA256 = '092a482f23e4afeda3b1112f4af5a91f8f6491a5c7b55e3e7a855b4a99f65013'
CURRENT_PREPARED_SHA256 = '7191ef8dac0604b1da9519605fabeff7fdc91b23706da2f7098fa7d127a6ff4a'
CURRENT_SEEDS_SHA256 = 'cc0d13514e6a807387f8cae20a2e1fb8d4dba9d3e1d0806e4747513de418d454'
PLAN_SHA256 = '8128b0c3cbda794cb8cd75b711609cfed1f1a150ef81ba3e90339cd4815ecca9'


def validate_scope(config):
    """Fail before file access unless this is the fixed consumed/final/BP task."""
    need(config.get('format') == 'biograph-steward.current-refit-source-controls.v1'
         and config.get('development_after_reference_opening') is True
         and config.get('reference_previously_consumed') is True
         and config.get('fresh_final_reference_claimed') is False
         and config.get('independent_confirmation') is False,
         'explicit consumed-reference development source controls required.')
    need(config.get('namespace') == NAMESPACE and config.get('forecast_role') == 'final'
         and config.get('expected_final_count') == FINAL_COUNT
         and config.get('expected_fit_count') == FIT_COUNT
         and config.get('arms') == list(ARMS),
         'exactly the two fixed BP/final3300 source controls are permitted.')
    need(config.get('nonexperimental_LocalPlus_seeds') is False
         and config.get('old_validation_or_T1_labels_allowed') is False
         and config.get('model_or_threshold_selection') is False,
         'no nonexperimental LP seeds, validation/T1 labels or selection may enter.')


def validate_identity_frames(final, fit):
    final, fit = tuple(final), tuple(fit)
    need(len(final) == len(set(final)) == FINAL_COUNT
         and len(fit) == len(set(fit)) == FIT_COUNT,
         'complete unique final3300 and fit4040 identity frames required.')
    need(not set(final) & set(fit), 'fit additions cannot overlap final-query identities.')
    return final, fit


def bp_rows(source, *, current=False):
    """Use only the already-established literal aspect-tag correspondence."""
    valid = CURRENT_ASPECT if current else {a: ns for ns, a in LEGACY_ASPECT.items()}
    result = {}
    for protein, rows in source.items():
        projected = set()
        for item in rows:
            need(len(item) == 2 and item[0] in valid, 'unqualified source aspect tag.')
            aspect, term = item
            validate_axes((protein,), (term,))
            if valid[aspect] == NAMESPACE:
                projected.add((LEGACY_ASPECT[NAMESPACE], term))
        result[protein] = sorted(projected)
    return result


def union_bp_sources(retained, current, candidate_fit, fit_ids):
    """Retain every positive from all three admitted curated source objects.

    Current annotations already underwent the published native admission and
    propagation. Candidate targets already include original full positives and
    the allowed direct T0 additions on the original axis. No biology is inferred
    here: both unions use the existing audited set-UNION helper unchanged.
    """
    fit_ids = tuple(fit_ids)
    need(len(fit_ids) == len(set(fit_ids)) and set(candidate_fit) == set(fit_ids),
         'candidate additions must retain the entire explicit fitting universe.')
    old = bp_rows(retained); new = bp_rows(current, current=True)
    candidate = bp_rows(candidate_fit)
    need(set(old) == set(new), 'both curated seed sources must retain the exact graph frame.')
    with_fit, added_fit = union_training(old, candidate, fit_ids)
    combined, added_current = union_training(with_fit, new, set(old))
    for protein in old:
        actual = set(map(tuple, combined[protein]))
        need(set(map(tuple, old[protein])) <= actual and set(map(tuple, new[protein])) <= actual,
             'an admitted curated source positive was removed.')
        if protein in candidate:
            need(set(map(tuple, candidate[protein])) <= actual, 'candidate target positive was removed.')
    count = lambda rows: sum(len(set(map(tuple, value))) for value in rows.values())
    return combined, {'retained_BP_memberships': count(old), 'current_BP_memberships': count(new),
        'candidate_fit_BP_memberships': count(candidate), 'combined_BP_memberships': count(combined),
        'candidate_memberships_added_to_retained': sum(map(len, added_fit.values())),
        'current_memberships_added_after_candidate': sum(map(len, added_current.values())),
        'retained_memberships_removed': 0, 'fit_universe': len(fit_ids),
        'nonexperimental_annotations_seeded_into_LocalPlus': False,
        'new_alias_mapping_or_ontology_propagation': False}


def fit_repertoire(proteins, terms, targets, original_targets, known_positive_mask):
    """Decode a complete positive-preserving matrix; never select root rows here."""
    import numpy as np
    proteins, terms = validate_axes(proteins, terms)
    shape = (len(proteins), len(terms))
    values = _array(targets, shape, binary=True)
    original = _array(original_targets, shape, binary=True)
    known = np.asarray(known_positive_mask)
    need(known.shape == shape and known.dtype == np.bool_, 'original known-positive mask differs.')
    need(np.all(values[original == 1] == 1) and np.all(values[known] == 1),
         'current target union removed an original full or known positive.')
    result = {protein: [] for protein in proteins}
    for row in range(len(proteins)):
        result[proteins[row]] = [(LEGACY_ASPECT[NAMESPACE], terms[int(column)])
                                for column in np.flatnonzero(values[row])]
    return result


def binary_prior_union(proteins, prior_terms, prior_values, retained_terms, retained_rows):
    """Literal binary membership UNION, with both complete vocabularies retained."""
    import numpy as np
    proteins, prior_terms = validate_axes(proteins, prior_terms)
    retained_proteins, retained_terms = validate_axes(proteins, retained_terms)
    need(retained_proteins == proteins and set(retained_rows) == set(proteins),
         'retained memberships must keep every literal final target, including empty rows.')
    prior = _array(prior_values, (len(proteins), len(prior_terms)), binary=True)
    prior_vocabulary = set(prior_terms)
    terms = prior_terms + tuple(term for term in retained_terms if term not in prior_vocabulary)
    columns = {term: i for i, term in enumerate(terms)}
    result = np.zeros((len(proteins), len(terms)), dtype=prior.dtype)
    result[:, :len(prior_terms)] = prior
    legacy = bp_rows(retained_rows); retained_vocabulary = set(retained_terms)
    memberships = 0
    for row, protein in enumerate(proteins):
        for _, term in legacy[protein]:
            need(term in retained_vocabulary, 'retained positive lies outside its complete source vocabulary.')
            result[row, columns[term]] = 1
            memberships += 1
    need(np.array_equal(result[:, :len(prior_terms)][prior == 1], prior[prior == 1]),
         'an original nonexperimental prior positive was removed.')
    return terms, result, {'operation': 'literal binary positive membership UNION at score 1',
        'source_nonexperimental_heads': len(prior_terms), 'source_retained_curated_heads': len(retained_terms),
        'union_heads': len(terms), 'retained_curated_query_memberships': memberships,
        'original_nonexperimental_positive_memberships': int(np.count_nonzero(prior)),
        'combined_positive_memberships': int(np.count_nonzero(result)),
        'source_positive_memberships_removed': 0, 'binary_annotation_score': 1,
        'target_rows': len(proteins), 'target_order_preserved': True,
        'model_axis_clipping': False, 'new_alias_mapping_or_ontology_propagation': False,
        'next_stage': 'unchanged native evaluator canonical/alternative-ID MAX and fill'}


def native_localplus_bp(modules, graph, seeds, targets, output_file):
    """Use existing graph normalization and run_term/runLocal without alteration."""
    import numpy as np
    from tools.cafa_prediction import core
    targets = tuple(targets)
    need(len(targets) == len(set(targets)), 'literal unique query identities required.')
    index = {protein.removeprefix('UniProtKB:'): i for i, protein in enumerate(graph['nodes'])}
    need(len(index) == len(graph['nodes']) and set(seeds) == set(index),
         'exact immutable graph and complete seed frame required.')
    matrix = modules['alg_utils'].normalizeGraphEdgeWeights(core.adjacency(graph['nodes'], graph['pairs']))
    need(np.isfinite(matrix.data).all() and (matrix.data >= 0).all(), 'unchanged native P is invalid.')
    heads = by_head(bp_rows(seeds), index)
    terms = tuple(sorted(term for aspect, term in heads if aspect == LEGACY_ASPECT[NAMESPACE]))
    validate_axes(targets, terms)
    present, missing = query_frame(targets, index)
    positions = {protein: row for row, protein in enumerate(targets)}
    query_rows = np.asarray([positions[protein] for protein in present], dtype=int)
    graph_rows = np.asarray([index[protein] for protein in present], dtype=int)
    need(not Path(output_file).exists(), 'preserve earlier source-control arrays.')
    values = np.lib.format.open_memmap(output_file, mode='w+', dtype=np.float64,
                                      shape=(len(targets), len(terms)))
    values[:] = 0
    for column, term in enumerate(terms):
        scores, _ = core.run_term(modules, matrix, None,
                                 heads[(LEGACY_ASPECT[NAMESPACE], term)], 'localplus')
        values[query_rows, column] = scores[graph_rows]
    values.flush()
    return terms, values, {'published_predictor': 'unchanged run_term/runLocal',
        'native_graph_normalization_unchanged': True, 'graph_topology_or_weights_changed': False,
        'native_LocalPlus_parameters': {}, 'target_rows': len(targets),
        'graph_absent_query_rows': len(missing), 'graph_absent_queries_are_arithmetic_zeros': True,
        'nonexperimental_annotations_seeded_into_LocalPlus': False,
        'new_alias_mapping_or_ontology_propagation': False}


def _pin(spec):
    need(set(spec) == {'file', 'sha256'}, 'a literal file/hash source spec is required.')
    _check_path(spec['file'])
    need(not any(token in str(spec['file']) for token in
                 ('groundtruth', '/t1/', '_t1_', 'validation_labels')),
         'reference or validation labels cannot enter source-control preparation.')
    need(file_sha256(spec['file']) == spec['sha256'], 'source-control input changed.')
    return Path(spec['file'])


def _json(spec):
    return json.loads(_pin(spec).read_text())


def _original_prior(directory, expected):
    """Open only the sealed target metadata and the one binary source control."""
    import numpy as np
    from .assessment import validate_source_manifest
    need(expected == ORIGINAL_SEAL_SHA256, 'the unchanged original forecast seal is required.')
    directory = Path(directory)
    seal = _json({'file': str(directory / 'forecast_seal.json'), 'sha256': expected})
    need(seal['format'] == 'biograph-steward.contextual-forecast-seal.v1'
         and seal['future_GO_labels_opened'] is False, 'original historical forecast seal differs.')
    cfg = _json({'file': str(directory / 'configuration.json'), 'sha256': seal['configuration_sha256']})
    targets = tuple(_pin({key: cfg['targets'][key] for key in ('file', 'sha256')}).read_text().splitlines())
    spec = cfg['arms']['native_T0_nonexperimental'][NAMESPACE]
    need(spec['sha256'] == ORIGINAL_NONEXPERIMENTAL_BP_SHA256,
         'only the original complete T0 nonexperimental BP prior is permitted.')
    verified = validate_source_manifest(spec, targets, arm='native_T0_nonexperimental', namespace=NAMESPACE)
    need(verified == seal['forecasts']['native_T0_nonexperimental'][NAMESPACE], 'original prior seal binding differs.')
    meta = _json({key: spec[key] for key in ('file', 'sha256')})
    values = np.load(meta['prediction_file'], mmap_mode='r', allow_pickle=False)
    _array(values, (len(targets), len(meta['terms'])), binary=True)
    return targets, meta, values, {'original_seal_sha256': expected, 'targets': cfg['targets'],
        'original_nonexperimental_prior': spec,
        'original_configuration': {'file': str(directory / 'configuration.json'), 'sha256': seal['configuration_sha256']},
        'original_forecast_seal': {'file': str(directory / 'forecast_seal.json'), 'sha256': expected},
        'original_prior_values': {'file': meta['prediction_file'], 'sha256': meta['prediction_sha256']}}


def admit_sources(config):
    """Admit the fixed sources without opening any validation/reference labels.

    The caller's independently reviewed configuration and pinned source plan
    provide execution authority. This does not run either original pre-opening
    producer with a false freshness declaration: their immutable outputs are
    re-used as historical source artifacts under explicit consumed status.
    """
    validate_scope(config)
    import numpy as np
    from tools.cafa_prediction.run import read
    required = {'format', 'development_after_reference_opening', 'reference_previously_consumed',
        'fresh_final_reference_claimed', 'independent_confirmation', 'namespace', 'forecast_role',
        'expected_final_count', 'expected_fit_count', 'arms', 'nonexperimental_LocalPlus_seeds',
        'old_validation_or_T1_labels_allowed', 'model_or_threshold_selection', 'source_plan',
        'source_generation_authorized', 'graph', 'fit_ids', 'retained_seed_union',
        'current_curated_prepared', 'candidate_fit_manifest', 'original_seal_directory',
        'original_seal_sha256', 'localplus_author', 'localplus_author_receipt'}
    need(set(config) == required and config['source_generation_authorized'] is True,
         'only the independently admitted frozen source contract may generate these controls.')
    need(config['source_plan']['sha256'] == PLAN_SHA256, 'only the frozen three-arm development plan is admitted.')
    plan = _json(config['source_plan'])
    need(plan['format'] == 'biograph-steward.current-T0-union-refit-development-plan.v1'
         and plan['reference_already_consumed'] is True and plan['independent_confirmation'] is False
         and set(plan['arms']) == set(ARMS) | {'current_T0_positive_union_context_refit'}
         and all(names == [NAMESPACE] for names in plan['arms'].values()),
         'source authority must be the complete frozen consumed-reference three-arm plan.')
    need(config['graph']['sha256'] == STRICT_GRAPH_SHA256, 'the strict graph topology/weights cannot change.')
    graph = read(_pin(config['graph']))
    retained_spec = config['retained_seed_union']
    need(retained_spec['sha256'] == RETAINED_UNION_RECEIPT_SHA256, 'original matched4040 seed receipt changed.')
    retained = _json(retained_spec)
    need(retained['format'] == 'biograph-steward.fitting-only-seed-union.v1'
         and retained['role_counts'] == {'fit': FIT_COUNT, 'validation': 797, 'final': FINAL_COUNT}
         and retained['original_pairs_removed'] == 0
         and retained['only_allowed4040_proteins_gained_labels'] is True
         and retained['all_original_nonfitting_rows_retained'] is True,
         'the exact positive-preserving old matched4040 source is required.')
    need(retained['source_input_pins'].get(config['graph']['file']) == config['graph']['sha256']
         and retained['source_input_pins'].get(config['fit_ids']['file']) == config['fit_ids']['sha256'],
         'graph/fitting identities do not match the original retained seed source.')
    need(retained['updated_training_sha256'] == RETAINED_UNION_SEEDS_SHA256, 'old matched seeds changed.')
    old_seeds = read(_pin({'file': retained['updated_training_file'], 'sha256': RETAINED_UNION_SEEDS_SHA256}))
    historical = read(_pin({'file': retained['original_training_file'], 'sha256': retained['original_training_sha256']}))
    need(config['current_curated_prepared']['sha256'] == CURRENT_PREPARED_SHA256, 'dated current curated preparation changed.')
    current = _json(config['current_curated_prepared'])
    need(current['format'] == 'biograph-steward.current-T0-curated-seeds.v1'
         and current['forecast_role'] == 'final' and current['forecast_count'] == FINAL_COUNT
         and current['future_reference_read'] is False and current['historical_labels_merged'] is False
         and current['native_admission_and_propagation_unchanged'] is True
         and current['source_input_pins'].get(config['graph']['file']) == config['graph']['sha256']
         and current['seed_sha256'] == CURRENT_SEEDS_SHA256,
         'only the existing native current-T0 curated source on the same graph is admitted.')
    current_seeds = read(_pin({'file': current['seed_file'], 'sha256': CURRENT_SEEDS_SHA256}))
    final, prior_meta, prior, original_pins = _original_prior(
        config['original_seal_directory'], config['original_seal_sha256'])
    fit_ids = tuple(_pin(config['fit_ids']).read_text().splitlines())
    final, fit_ids = validate_identity_frames(final, fit_ids)
    candidate = _json(config['candidate_fit_manifest'])
    need(candidate['proteins'] == list(fit_ids) and candidate['namespace'] == NAMESPACE
         and candidate['target_semantics'] == 'known_T0_union_allowed_development_additions_upward_closed'
         and candidate['development_after_reference_opening'] is True
         and candidate['reference_previously_consumed'] is True
         and candidate['fresh_final_reference_claimed'] is False
         and candidate['original_full_positive_retention'] is True
         and candidate['retention_mask_semantics'] == 'original_full_fitting_positive_repertoire',
         'complete positive-preserving candidate fit targets with consumed provenance are required.')
    old_manifest = _json({key: retained['fit_manifest_sources'][NAMESPACE][key] for key in ('file', 'sha256')})
    need(old_manifest['proteins'] == candidate['proteins'] and old_manifest['terms'] == candidate['terms'],
         'candidate target identities/order/original full BP axis changed.')
    def array(manifest, key):
        source = manifest[key]
        _pin({'file': source, 'sha256': manifest['file_pins'][source]})
        return np.load(source, mmap_mode='r', allow_pickle=False)
    values = array(candidate, 'targets_file')
    original_values = array(old_manifest, 'targets_file')
    known = array(old_manifest, 'known_positive_mask_file')
    candidate_rows = fit_repertoire(fit_ids, candidate['terms'], values, original_values, known)
    retained_full = array(candidate, 'known_positive_mask_file')
    need(retained_full.dtype == np.bool_ and retained_full.shape == original_values.shape
         and np.array_equal(retained_full, original_values == 1),
         'candidate retention mask must identify exactly every original full positive.')
    source_expectations = plan['source_adaptation']
    root_column = candidate['terms'].index('GO:0008150')
    old_count, new_count = int(np.count_nonzero(original_values)), int(np.count_nonzero(values))
    added_proteins = int(np.count_nonzero(np.any(values > original_values, axis=1)))
    need(old_count == source_expectations['expected_original_full_BP_positive_cells']
         and new_count == source_expectations['expected_augmented_BP_positive_cells']
         and new_count - old_count == source_expectations['expected_added_BP_positive_cells']
         and added_proteins == source_expectations['expected_fitting_proteins_with_additions']
         and int(np.count_nonzero(original_values[:, root_column])) == source_expectations['expected_original_root_positive_rows']
         and int(np.count_nonzero(values[:, root_column])) == source_expectations['expected_augmented_root_positive_rows'],
         'candidate full positive union/root counts differ from the frozen source audit.')
    seeds, union_audit = union_bp_sources(old_seeds, current_seeds, candidate_rows, fit_ids)
    need(set(seeds) == {protein.removeprefix('UniProtKB:') for protein in graph['nodes']}
         and set(historical) == set(seeds), 'all curated source tables must retain the exact graph frame.')
    retained_bp = bp_rows(historical)
    historical_terms = tuple(sorted({term for rows in retained_bp.values() for _, term in rows}))
    query_memberships = {protein: retained_bp.get(protein, []) for protein in final}
    # Exact disjointness makes the matched4040 additions irrelevant to this
    # direct final-query prior; verify rather than infer that source property.
    old_bp = bp_rows(old_seeds)
    need(all(set(old_bp.get(protein, [])) == set(query_memberships[protein]) for protein in final),
         'historical final-query memberships unexpectedly include fitting additions.')
    _pin(config['localplus_author_receipt'])
    source_specs = [config[key] for key in ('source_plan', 'graph', 'fit_ids', 'retained_seed_union',
        'current_curated_prepared', 'candidate_fit_manifest', 'localplus_author_receipt')]
    source_specs += [spec for spec in original_pins.values() if isinstance(spec, dict)]
    source_specs += [retained['fit_manifest_sources'][NAMESPACE],
        {'file': retained['updated_training_file'], 'sha256': RETAINED_UNION_SEEDS_SHA256},
        {'file': retained['original_training_file'], 'sha256': retained['original_training_sha256']},
        {'file': current['seed_file'], 'sha256': CURRENT_SEEDS_SHA256}]
    for manifest in (candidate, old_manifest):
        for key in ('targets_file', 'known_positive_mask_file'):
            path = manifest[key]
            source_specs.append({'file': path, 'sha256': manifest['file_pins'][path]})
    return {'targets': final, 'graph': graph, 'seeds': seeds, 'union_audit': union_audit,
        'prior_metadata': prior_meta, 'prior_values': prior, 'historical_terms': historical_terms,
        'query_memberships': query_memberships, 'original_source_pins': original_pins,
        'source_input_pins': {spec['file']: spec['sha256'] for spec in source_specs}}


def produce(config, output):
    """Generate only these two source controls; there is no evaluation entry point."""
    import numpy as np
    from tools.cafa_prediction import core
    admitted = admit_sources(config)
    modules = core.author_modules(config['localplus_author'], config['localplus_author_receipt']['file'])
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'configuration.json', config)
    shared = {'development_after_reference_opening': True, 'reference_previously_consumed': True,
        'fresh_final_reference_claimed': False, 'independent_confirmation': False,
        'scientific_metrics_computed': False, 'models_fitted': False,
        'current_validation_metric_computed': False,
        'final_reference_labels_read_for_forecasting': False,
        'old_validation_labels_read': False, 'automatic_graph_or_app_promotion': False}
    from . import freshness_controls, current_annotation
    helper_sources = {str(Path(module.__file__)): file_sha256(module.__file__)
        for module in (core, freshness_controls, current_annotation)}
    author_receipt = _json(config['localplus_author_receipt'])
    native_sources = {str(Path(config['localplus_author']) / relative): item['sha256']
        for relative, item in author_receipt['files'].items()}
    generation = {'format': 'biograph-steward.current-refit-source-control-generation.v1', **shared,
        'plan_sha256': PLAN_SHA256, 'source_code_sha256': file_sha256(__file__),
        'configuration_sha256': file_sha256(output / 'configuration.json'),
        'source_input_pins': admitted['source_input_pins'], 'unchanged_helper_code_pins': helper_sources,
        'unchanged_native_author_code_pins': native_sources,
        'stage': 'admission complete; before first generated forecast array',
        'new_forecast_arrays_generated_at_receipt': False}
    gate = output / 'generation_gate.json'; write_json(gate, generation)
    lp_path = output / (LOCALPLUS + '.npy')
    lp_terms, lp_values, lp_audit = native_localplus_bp(modules, admitted['graph'], admitted['seeds'], admitted['targets'], lp_path)
    prior = admitted['prior_metadata']
    terms, values, direct_audit = binary_prior_union(admitted['targets'], prior['terms'],
        admitted['prior_values'], admitted['historical_terms'], admitted['query_memberships'])
    direct_path = output / (DIRECT + '.npy'); np.save(direct_path, values, allow_pickle=False)
    forecasts = {}
    for arm, path, axis, audit, tolerance in ((LOCALPLUS, lp_path, lp_terms,
            {**lp_audit, 'seed_union': admitted['union_audit']}, 1e-10),
            (DIRECT, direct_path, terms, direct_audit, 0.)):
        meta = {'format': 'biograph-steward.current-refit-source-control-forecast.v1', **shared, 'status': 'complete',
            'arm': arm, 'namespace': NAMESPACE, 'forecast_role': 'final',
            'proteins': list(admitted['targets']), 'terms': list(axis),
            'prediction_file': str(path), 'prediction_sha256': file_sha256(path),
            'upper_roundoff_tolerance': tolerance, 'source_provenance': audit,
            'plan_sha256': PLAN_SHA256,
            'producer_code_sha256': file_sha256(__file__),
            'source_plan': config['source_plan'], 'configuration_sha256': file_sha256(output / 'configuration.json'),
            'generation_receipt': {'file': str(gate), 'sha256': file_sha256(gate)},
            'source_input_pins': admitted['source_input_pins'],
            'original_source_pins': admitted['original_source_pins']}
        metadata = path.with_suffix('.json'); write_json(metadata, meta)
        forecasts[arm] = {NAMESPACE: {'file': str(metadata), 'sha256': file_sha256(metadata)}}
    result = {'format': 'biograph-steward.current-refit-source-controls-delivery.v1', **shared, 'status': 'complete',
        'source_code_sha256': file_sha256(__file__), 'configuration_sha256': file_sha256(output / 'configuration.json'),
        'plan_sha256': PLAN_SHA256, 'generation_receipt_sha256': file_sha256(gate),
        'source_plan': config['source_plan'], 'forecast_role': 'final', 'target_count': FINAL_COUNT,
        'arms': forecasts, 'no_reference_or_validation_labels_read': True,
        'nonexperimental_LocalPlus_seeds': False, 'new_source_admission_rule': False}
    write_json(output / 'delivery.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text()); validate_scope(config)
    need(args.execute, 'real source arrays require the explicit frozen-plan execution step.')
    produce(config, args.output)
