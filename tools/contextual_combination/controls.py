# SPDX-License-Identifier: GPL-3.0-only
"""Matched fixed-soft parent controls and consumed-validation alpha selection.

Uses the existing eleven-weight selector and convex mixing, the pinned native
evaluator and the same published postprocessing as the contextual candidates.
Final forecasting never opens references. Original-precision parent scores on
the fixed model axis remain separate from explicitly float32 soft controls.
Complete original source-head baselines require separate artifacts: these
model-axis inputs have already undergone historical canonical-ID intake.
"""
import argparse
import json
from pathlib import Path

from tools.learned_combination.core import (
    ALPHA_GRID, LOCALPLUS_UPPER_ROUNDOFF, ScoreMatrix, convex_mix,
    select_development_alpha,
)
from .native_stacker import need
from .training import (
    PARAMETERS, VALIDATION_ROLE, axis_sha, now, read_feature_manifest,
    require_pinned, save_soft_forecast, score_saved_consumed_forecast,
    sha, validate_validation_sources, write_json,
)


NS_ASPECT = {'biological_process': 'bp', 'molecular_function': 'mf', 'cellular_component': 'cc'}


def load_parents(cfg):
    """Require dense literal, same-axis parent artifacts without silent repair."""
    import numpy as np

    need(cfg['format'] == 'biograph-steward.contextual-controls.v1', 'unexpected controls configuration.')
    need(cfg['namespace'] in NS_ASPECT, 'one explicit native GO namespace required.')
    pins = cfg['input_file_pins']
    for path in pins:
        require_pinned(path, pins)
    parents, metadata = {}, {}
    for name in ('localplus', 'deepgose'):
        spec = cfg['parents'][name]
        require_pinned(spec['file'], pins)
        need(sha(spec['file']) == spec['sha256'], 'changed parent metadata.')
        meta = json.loads(Path(spec['file']).read_text())
        need(meta['namespace'] == cfg['namespace']
             and meta.get('final_reference_labels_read_for_forecasting') is False,
             'explicit namespace and label-free parent provenance required.')
        require_pinned(meta['prediction_file'], pins)
        need(sha(meta['prediction_file']) == meta['prediction_sha256'], 'changed literal parent scores.')
        tolerance = LOCALPLUS_UPPER_ROUNDOFF if name == 'localplus' else 0.
        need(meta.get('upper_roundoff_tolerance', 0.) in (0., tolerance), 'unqualified parent score tolerance.')
        array = np.load(meta['prediction_file'], mmap_mode='r', allow_pickle=False)
        need(array.dtype in (np.dtype('float32'), np.dtype('float64')), 'qualified native parent precision required.')
        parents[name] = ScoreMatrix(tuple(meta['proteins']), tuple(meta['terms']), array, tolerance)
        metadata[name] = meta
    left, right = parents['localplus'], parents['deepgose']
    need(left.proteins == right.proteins and left.terms == right.terms,
         'parent literal identity axes differ; implicit alignment is prohibited.')
    return parents, metadata


def model_graph(cfg, terms):
    from tools.learned_combination.native_adapter import native_ontologies

    require_pinned(cfg['model_obo']['file'], cfg['input_file_pins'])
    need(sha(cfg['model_obo']['file']) == cfg['model_obo']['sha256'], 'fixed model ontology changed.')
    graph = native_ontologies(cfg['model_obo']['file'])[cfg['namespace']]
    need(tuple(n['id'] for n in graph.terms_list) == tuple(terms), 'parent/fixed model GO axes differ.')
    return graph


def soft_control(cfg, graph, parents, alpha, output):
    """Mix original scores first, cast once, then deploy the fixed source recipe."""
    import numpy as np

    mixture = convex_mix(parents['localplus'], parents['deepgose'], alpha)
    values = np.asarray(mixture.values, dtype=np.float32)
    need(np.isfinite(values).all() and (values >= 0).all() and (values <= 1).all(),
         'qualified float32 mixture conversion must remain a native probability.')
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=False)
    bundle = save_soft_forecast(cfg['author_root'], graph, mixture.proteins, mixture.terms, values, folder)
    result = {**bundle, 'namespace': cfg['namespace'], 'localplus_weight': alpha,
              'arithmetic': 'existing convex_mix in original score precision; explicit float32 cast; fixed published soft closure',
              'original_mixture_dtype': str(mixture.values.dtype),
              'float32_cast_max_abs': float(np.max(np.abs(values.astype(np.float64) - mixture.values), initial=0)),
              'probability_clipping': False,
              'final_reference_labels_read_for_forecasting': False}
    write_json(folder / 'predictions.json', result)
    return result


def fit_alpha_controls(cfg, output):
    """Choose one global alpha per aspect on the same consumed validation IDs."""
    from tools.learned_combination.runner import subset_reference

    validate_validation_sources(cfg['evaluation'])
    parents, metadata = load_parents(cfg)
    left = parents['localplus']
    val, _, _ = read_feature_manifest(cfg['validation_manifest'], cfg['input_file_pins'], fitting=False)
    need(tuple(val['proteins']) == left.proteins and tuple(val['terms']) == left.terms,
         'alpha fitting must use the identical consumed contextual-validation protein/term frame.')
    graph = model_graph(cfg, left.terms)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'configuration.json', cfg)
    frame = output / 'validation_frame'; frame.mkdir()
    refs = cfg['evaluation']['references']
    subset_reference([refs['truth']['file']], left.proteins, frame / 'truth.tsv')
    subset_reference([refs['known']['file']], left.proteins, frame / 'known.tsv')
    frame_files = {'truth': str(frame / 'truth.tsv'), 'known': str(frame / 'known.tsv')}
    objectives, artifacts = {}, {}
    for alpha in ALPHA_GRID:
        folder = output / ('alpha_' + f'{alpha:.1f}'.replace('.', '_'))
        bundle = soft_control(cfg, graph, parents, alpha, folder)
        objectives[alpha] = score_saved_consumed_forecast(cfg, frame_files, bundle, folder)
        artifacts[str(alpha)] = {'file': str(folder / 'predictions.json'), 'sha256': sha(folder / 'predictions.json')}
    selection = select_development_alpha(NS_ASPECT[cfg['namespace']], objectives,
        development_id=VALIDATION_ROLE + ':' + axis_sha(left.proteins))
    for path in cfg['input_file_pins']:
        require_pinned(path, cfg['input_file_pins'])
    result = {'created_at': now(), 'namespace': cfg['namespace'], **selection.to_dict(),
              'format': 'biograph-steward.contextual-alpha-selection.v1',
              'configuration_sha256': sha(output / 'configuration.json'),
              'validation_manifest_sha256': sha(cfg['validation_manifest']),
              'postprocessing': PARAMETERS['postprocessing'], 'metric_grid': '.01,.02,...,.99',
              'validation_artifacts': artifacts, 'parent_metadata_pins': cfg['parents'],
              'fresh_final_reference_opened': False}
    write_json(output / 'alpha_selection.json', result)
    return result


def export_controls(cfg, selection, output):
    """Forecast using a preselected alpha; accepts no reference/evaluator paths."""
    need('evaluation' not in cfg and 'references' not in cfg and 'validation_manifest' not in cfg,
         'final control forecasting cannot receive any reference/evaluation configuration.')
    need(sha(selection['file']) == selection['sha256'], 'changed frozen development alpha selection.')
    chosen = json.loads(Path(selection['file']).read_text())
    need(chosen['format'] == 'biograph-steward.contextual-alpha-selection.v1'
         and chosen['namespace'] == cfg['namespace'] and chosen['fresh_final_reference_opened'] is False
         and chosen['postprocessing'] == PARAMETERS['postprocessing'], 'unqualified development alpha choice.')
    need(chosen['alpha'] in ALPHA_GRID and chosen['alpha_grid'] == list(ALPHA_GRID)
         and chosen['tie_rule'] == 'smallest alpha on the fixed grid', 'frozen alpha/grid/tie rule differs.')
    parents, metadata = load_parents(cfg)
    graph = model_graph(cfg, parents['localplus'].terms)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'configuration.json', cfg)
    artifacts = {}
    for name, alpha in (('localplus_soft', 1.), ('deepgose_soft', 0.), ('equal_mix', .5),
                        ('development_alpha_mix', chosen['alpha'])):
        folder = output / name
        soft_control(cfg, graph, parents, alpha, folder)
        artifacts[name] = {'file': str(folder / 'predictions.json'), 'sha256': sha(folder / 'predictions.json')}
    # These arms retain the captured model-axis arrays' original precision.
    # They must not replace complete original source-head baseline controls.
    for name, meta in metadata.items():
        arm = name + '_model_axis_raw'
        path = output / (arm + '.json')
        write_json(path, {**meta, 'upper_roundoff_tolerance':
                          LOCALPLUS_UPPER_ROUNDOFF if name == 'localplus' else 0.,
                          'parent_metadata_source': cfg['parents'][name],
                          'source_scope': 'historical fixed model axis after native canonical-ID intake; not complete original source heads',
                          'postprocessing': 'none; model-axis parent precision retained'})
        artifacts[arm] = {'file': str(path), 'sha256': sha(path)}
    for path in cfg['input_file_pins']:
        require_pinned(path, cfg['input_file_pins'])
    result = {'created_at': now(), 'namespace': cfg['namespace'], 'arms': artifacts,
              'alpha_selection': selection, 'selected_alpha': chosen['alpha'],
              'reference_files_read_for_forecasting': False,
              'final_reference_labels_read_for_forecasting': False}
    write_json(output / 'controls.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('fit', 'forecast'))
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--selection')
    parser.add_argument('--selection-sha256')
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    if args.phase == 'fit':
        result = fit_alpha_controls(cfg, args.output)
    else:
        result = export_controls(cfg, {'file': args.selection, 'sha256': args.selection_sha256}, args.output)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
