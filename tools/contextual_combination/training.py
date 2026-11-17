# SPDX-License-Identifier: GPL-3.0-only
"""Pinned native training/SWA, with consumed-only validation in its own runtime.

The original author training loop, loss, Adam calls and SWA parameter averaging
execute unchanged. A memmap dataset supplies already-qualified native features;
the native CUDA loader still performs its own feature transform and edges.
New final-reference paths or labels are never accepted by this module.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import traceback
from datetime import datetime, timezone

from .native_stacker import _symbols, load_author, make_model, need, validate_model_axis, sequence_edge_graph
from .postprocessing import POSTPROCESS_SOURCE_PINS, published_soft_closure
from tools.learned_combination.core import LOCALPLUS_UPPER_ROUNDOFF


TRAINING_AUTHOR_PINS = {
    'protnn/train.py': 'ce9320b242b7e3e6e513799199307f1949e7b25041e126f7d5e67f02585573f6',
    'protnn/swa.py': 'efa7dbc5cc5d9e21106f93e47fd447379c46261d0e0f526168d98788eceaa2c1',
    'protnn/utils.py': '463b184848af660af64963af43322dbf7b5106c58461951cc230d597ed498693',
    'protnn/scripts/train_gcn.py': '99ed46ba57624d8f31302d8db573f2435e259391e8cbe03526eb0ed61b12fa23',
}
VALIDATION_REFERENCE_PINS = {
    'obo': 'd9a5670865816dd63dcdd49f76864d3a621990d8bcbb6b758e4cdfbfdb9f2982',
    'truth': '9b224105d9a0276273e4138e1324423020b4032d700bbe70924241adceefc239',
    'known': '09819c8fa14693b63ddb52f7696749334bd7849d748b571a825e3864a6d7589d',
    'toi': '209a27a9a5bae0829718f6656a8e7eaf53dbed270c668bf6502ddb5f81857634',
}
PARAMETERS = {
    'epochs': 20, 'batch_size': 32, 'hidden_size': 16, 'embed_size': 8,
    'architectures': [0, 8], 'optimizer': 'Adam', 'lr': .001,
    'clip_grad_value': .1, 'weight_decay': 0.,
    'store_swa': 10, 'average_best': 3, 'num_workers': 0,
    'postprocessing': 'published_notebook_soft07_max_min_equal_fullprecision',
}
VALIDATION_ROLE = 'consumed_lafa_sep2025_mar2026_validation'
TARGET_SEMANTICS = 'known_T0_union_allowed_development_additions_upward_closed'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def axis_sha(values):
    return hashlib.sha256(json.dumps(list(values), separators=(',', ':')).encode()).hexdigest()


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def now():
    return datetime.now(timezone.utc).isoformat()


def qualified_training_runtime():
    import numpy as np
    import torch
    import numba
    import llvmlite

    versions = {'python': '.'.join(map(str, sys.version_info[:3])), 'torch': torch.__version__,
                'numpy': np.__version__, 'numba': numba.__version__, 'llvmlite': llvmlite.__version__}
    need(versions == {'python': '3.10.12', 'torch': '2.0.1+cu117', 'numpy': '1.26.1',
                      'numba': '0.59.1', 'llvmlite': '0.42.0'}, 'unqualified native training/runtime versions.')
    return versions


def require_pinned(path, pins):
    need(str(path) in pins and sha(path) == pins[str(path)], 'missing or changed input pin: ' + str(path))


def validate_validation_sources(evaluation):
    """Reject fresh-reference content before any annotation parsing is possible."""
    need(evaluation['role'] == VALIDATION_ROLE, 'only the already-consumed validation release is permitted.')
    refs = evaluation['references']
    need(set(refs) == set(VALIDATION_REFERENCE_PINS), 'complete fixed validation source roles required.')
    for role, expected in VALIDATION_REFERENCE_PINS.items():
        spec = refs[role]
        need(spec['sha256'] == expected and sha(spec['file']) == expected,
             'validation source differs from consumed immutable release: ' + role)


def read_feature_manifest(path, pins, *, fitting):
    """Validate both literal axes, typed feature cache and retained known labels."""
    import numpy as np

    require_pinned(path, pins)
    result = json.loads(Path(path).read_text())
    proteins, terms = tuple(result['proteins']), tuple(result['terms'])
    need(proteins and len(proteins) == len(set(proteins)) and terms and len(terms) == len(set(terms)),
         'complete unique feature-cache identity axes required.')
    require_pinned(result['feature_file'], pins)
    features = np.load(result['feature_file'], mmap_mode='r', allow_pickle=False)
    need(features.shape == (len(proteins), 9, len(terms)) and features.dtype == np.float32,
         'native raw feature cache must be float32 Nprotein×9×Nterms.')
    # Scan in bounded blocks; do not materialize another multi-GB cache.
    for start in range(0, len(proteins), 32):
        block = features[start:start + 32]
        need(np.isfinite(block).all() and (block >= 0).all() and (block <= 1).all(),
             'native pre-logit feature cache must contain finite [0,1] values.')
        need(np.isin(block[:, [0, 4, 8], :], [0., 1.]).all(),
             'native missing-head flags and GOA feature must stay binary.')
    targets = None
    if fitting:
        need(result.get('target_semantics') == TARGET_SEMANTICS,
             'fitting must declare full known-T0 union positives, not a PK delta.')
        for key in ('targets_file', 'known_positive_mask_file'):
            need(result.get(key), 'fitting requires targets and an auditable known-positive mask.')
            require_pinned(result[key], pins)
        targets = np.load(result['targets_file'], mmap_mode='r', allow_pickle=False)
        known = np.load(result['known_positive_mask_file'], mmap_mode='r', allow_pickle=False)
        need(targets.shape == known.shape == (len(proteins), len(terms)),
             'full training target/known-mask axes differ from feature axes.')
        need(known.dtype == np.bool_ and targets.dtype in (np.dtype('float32'), np.dtype('bool')),
             'binary known mask and bool/float32 full training targets required.')
        for start in range(0, len(proteins), 32):
            y, k = targets[start:start + 32], known[start:start + 32]
            need(np.isin(y, [0, 1]).all() and (y[k] == 1).all(),
                 'known positive function was relabeled negative, or targets are not binary.')
    result['_manifest_file'] = str(path)
    result['_manifest_sha256'] = sha(path)
    return result, features, targets


def root_positive_rows(graph, targets):
    """Native train_gcn.py row filter; priors retain the full allowed universe."""
    import numpy as np

    roots = [node['id'] for node in graph.terms_list if len(node['adj']) == 0]
    need(len(roots) == 1, 'native aspect fitting requires one literal parentless GO root.')
    root_id = roots[0]
    # Select by literal ID exactly as the author driver, never column zero.
    column = next(i for i, node in enumerate(graph.terms_list) if node['id'] == root_id)
    need(targets.ndim == 2 and targets.shape[1] == graph.idxs, 'fitting target/model GO axes differ.')
    rows = np.nonzero(targets[:, column] == 1)[0]
    need(len(rows), 'no root-positive supervised fitting rows in this GO aspect.')
    return rows, {'native_driver_sha256': TRAINING_AUTHOR_PINS['protnn/scripts/train_gcn.py'],
                  'root_id': root_id, 'root_column': column,
                  'allowed_prior_universe_rows': int(len(targets)), 'supervised_fitting_rows': int(len(rows)),
                  'prior_or_target_recomputation': False}


class CachedNativeDataset:
    """I/O only; native original StackDataLoader handles all feature math."""
    def __init__(self, manifest, features, graph, targets=None, *, row_indices=None):
        import numpy as np

        self.manifest, self.features, self.targets, self.G = manifest, features, targets, sequence_edge_graph(graph)
        self.rows = np.arange(len(manifest['proteins'])) if row_indices is None else np.asarray(row_indices)
        need(self.rows.ndim == 1 and self.rows.dtype.kind in 'iu' and len(self.rows)
             and len(set(self.rows.tolist())) == len(self.rows) and (self.rows >= 0).all()
             and (self.rows < len(manifest['proteins'])).all(), 'explicit valid unique dataset row indexes required.')
        self.nout = len(manifest['terms'])
        # The native loader reads len(preds); native raw predictor reads N rows.
        # These zero-column descriptors carry shape only, never fake scores.
        self.preds = [(np.empty((len(self.rows), 0)), (), False)] * 2

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, row):
        import numpy as np
        import torch

        row = self.rows[row]
        batch = {'x': torch.from_numpy(np.array(self.features[row], copy=True))}
        if self.targets is not None:
            batch['y'] = torch.from_numpy(np.array(self.targets[row], dtype=np.float32, copy=True))
        return batch


def training_author(author):
    """Return unchanged native loop, SWA class and full raw-prediction helper."""
    import numpy as np
    import torch
    import tqdm

    root = author.root
    for name, pin in TRAINING_AUTHOR_PINS.items():
        need((root / name).is_file() and sha(root / name) == pin, 'changed native training source: ' + name)
    modules = {}
    for name in ('train', 'swa'):
        key = '_biograph_protboost_training_' + name
        spec = importlib.util.spec_from_file_location(key, root / ('protnn/' + name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[name] = module
    helper = {'np': np, 'torch': torch, 'tqdm': tqdm}
    _symbols(root / 'protnn/utils.py', ('make_raw_prediction',), helper)
    return modules['train'].train, modules['swa'].SWA, helper['make_raw_prediction']


def project_native_forecasts(proteins, terms, values, ontology, *, upper_roundoff_tolerance=0.):
    """Native primary/alternative-ID MAX intake for dense saved model scores.

    This is the array form of the existing native TSV intake. It adds no GO
    relationships or replacement semantics. It must match that reader on an
    invented fixture before it is used for callback scoring.
    """
    import numpy as np
    from tools.learned_combination.native_adapter import _native

    native = _native()['graph']
    need(type(upper_roundoff_tolerance) in (int, float)
         and upper_roundoff_tolerance in (0., LOCALPLUS_UPPER_ROUNDOFF),
         'only the separately qualified LocalPlus upper roundoff tolerance is permitted.')
    proteins, terms = tuple(proteins), tuple(terms)
    need(len(set(proteins)) == len(proteins) and len(set(terms)) == len(terms), 'duplicate forecast axes.')
    values = np.asarray(values)
    need(values.shape == (len(proteins), len(terms)) and np.isfinite(values).all()
         and (values >= 0).all() and (values <= 1 + upper_roundoff_tolerance).all(),
         'invalid source model probabilities.')
    matrix = np.zeros((len(proteins), ontology.idxs), dtype=np.float64)
    mapped = dropped = 0
    for source, term in enumerate(terms):
        # The native TSV reader gives an explicit alternative-ID mapping
        # priority even in the unusual primary/alternative collision case.
        labels = (ontology.terms_dict_alt[term] if term in ontology.terms_dict_alt else
                  ([term] if term in ontology.terms_dict else ()))
        if not labels:
            dropped += 1
            continue
        mapped += 1
        for label in labels:
            destination = ontology.terms_dict[label]['index']
            np.maximum(matrix[:, destination], values[:, source], out=matrix[:, destination])
    if np.any(matrix):
        native.propagate(matrix, ontology, ontology.order, mode='fill')
    prediction = native.Prediction({p: i for i, p in enumerate(proteins)}, matrix, ontology.namespace)
    prediction._learned_combination_terms = tuple(node['id'] for node in ontology.terms_list)
    return prediction, {'source_heads': len(terms), 'mapped_heads': mapped, 'dropped_heads': dropped,
                         'duplicate_policy': 'native exact/alternative ID MAX', 'propagation': 'native fill once',
                         'upper_roundoff_tolerance': upper_roundoff_tolerance, 'probability_clipping': False}


def save_soft_forecast(author_root, graph, proteins, terms, raw_values, output):
    """Preserve literal native output and separately save the deployed recipe."""
    import numpy as np

    output = Path(output)
    need(raw_values.dtype == np.float32 and raw_values.shape == (len(proteins), len(terms)),
         'native prediction bundle requires float32 scores on explicit protein/GO axes.')
    soft, audit = published_soft_closure(author_root, graph, terms, raw_values)
    raw_file, soft_file = output / 'raw_predictions.npy', output / 'predictions.npy'
    np.save(raw_file, raw_values, allow_pickle=False)
    np.save(soft_file, soft, allow_pickle=False)
    result = {'proteins': list(proteins), 'terms': list(terms),
              'raw_prediction_file': str(raw_file), 'raw_prediction_sha256': sha(raw_file),
              'prediction_file': str(soft_file), 'prediction_sha256': sha(soft_file),
              'postprocessing': audit,
              'soft_minus_raw_max_abs': float(np.max(np.abs(soft - raw_values), initial=0))}
    write_json(output / 'forecast_axis.json', result)
    return result


def score_validation(job_file):
    """Run only in the separate source-pinned NumPy1.26.4 evaluator runtime."""
    import numpy as np
    import scipy
    import pandas as pd
    from cafaeval.parser import gt_parser, gt_exclude_parser, update_toi
    from tools.learned_combination.native_adapter import native_ontologies, align_predictions, evaluate_native

    need(sys.version_info[:3] == (3, 10, 12) and np.__version__ == '1.26.4'
         and scipy.__version__ == '1.13.1' and pd.__version__ == '2.2.3',
         'callback must retain the qualified CAFA numeric runtime.')
    job = json.loads(Path(job_file).read_text())
    validate_validation_sources(job['evaluation'])
    for path, pin in job['input_pins'].items():
        need(sha(path) == pin, 'changed callback forecast/frame input: ' + path)
    metadata = json.loads(Path(job['forecast_metadata']).read_text())
    values = np.load(job['forecast_file'], mmap_mode='r', allow_pickle=False)
    ont = update_toi(native_ontologies(job['evaluation']['references']['obo']['file']),
                     job['evaluation']['references']['toi']['file'])
    ns = job['namespace']
    gt = gt_parser(job['truth_frame'], ont)
    need(ns in gt, 'native validation namespace is absent.')
    ex = gt_exclude_parser(job['known_frame'], {ns: gt[ns]}, ont)
    pred, audit = project_native_forecasts(metadata['proteins'], metadata['terms'], values, ont[ns])
    pred = align_predictions({ns: pred}, {ns: gt[ns]})
    curve, points = evaluate_native(pred, {ns: gt[ns]}, ont, gt_exclude={ns: ex[ns]},
                                    tau=np.arange(.01, 1, .01), n_cpu=job['evaluation']['n_cpu'])
    need(points.get(ns) is not None, 'no native scored validation coverage.')
    output = Path(job['output'])
    output.mkdir(exist_ok=False)
    curve.to_csv(output / 'curves.tsv', sep='\t', index=False)
    result = {'status': 'evaluated', 'role': VALIDATION_ROLE, 'namespace': ns,
              'ordinary_micro_fmax': points[ns], 'forecast_projection': audit,
              'metric_grid': '.01,.02,...,.99', 'IA_used': False,
              'raw_native_reference_proteins': len(gt[ns].ids), 'job_sha256': sha(job_file),
              'fresh_final_reference_opened': False}
    write_json(output / 'score.json', result)
    return result


def score_saved_consumed_forecast(cfg, frame, forecast_bundle, output):
    """One pinned scorer boundary shared by contextual and alpha selection."""
    target = Path(output)
    forecast, meta = forecast_bundle['prediction_file'], target / 'forecast_axis.json'
    need(sha(forecast) == forecast_bundle['prediction_sha256'], 'changed deployed validation forecast.')
    job = {'namespace': cfg['namespace'], 'evaluation': cfg['evaluation'],
           'forecast_file': str(forecast), 'forecast_metadata': str(meta),
           'truth_frame': frame['truth'], 'known_frame': frame['known'],
           'input_pins': {str(forecast): sha(forecast), str(meta): sha(meta),
                          frame['truth']: sha(frame['truth']), frame['known']: sha(frame['known'])},
           'output': str(target / 'native_score')}
    job_file = target / 'score_job.json'
    write_json(job_file, job)
    evaluation = cfg['evaluation']
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(evaluation['pythonpath'])
    for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
        env[name] = '1'
    with (target / 'native_score.log').open('x') as log:
        subprocess.run([evaluation['python'], '-m', 'tools.contextual_combination.training',
                        'score-validation', '--job', str(job_file)], env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=3600)
    result = json.loads((target / 'native_score/score.json').read_text())
    return float(result['ordinary_micro_fmax'])


class ConsumedValidationCallback:
    def __init__(self, cfg, output, validation_manifest, native_predict, graph):
        self.cfg, self.output, self.manifest, self.native_predict = cfg, Path(output), validation_manifest, native_predict
        self.graph = graph
        self.epoch = 0

    def __call__(self, model, loader):
        self.epoch += 1
        return self.evaluate(model, loader, 'epoch_' + str(self.epoch).zfill(2), save_checkpoint=True)

    def evaluate(self, model, loader, label, *, save_checkpoint=False):
        import numpy as np
        import torch

        target = self.output / label
        target.mkdir(exist_ok=False)
        validate_model_axis(model, self.manifest['terms'])
        if save_checkpoint:
            torch.save(model.state_dict(), target / 'parameters.pth')
        values = self.native_predict(model, loader)
        need(values.dtype == np.float32 and np.isfinite(values).all()
             and (values >= 0).all() and (values <= 1).all(), 'nonfinite native validation predictions.')
        bundle = save_soft_forecast(self.cfg['author_root'], self.graph, self.manifest['proteins'],
                                    self.manifest['terms'], values, target)
        frame = self.cfg['_validation_frame']
        return score_saved_consumed_forecast(self.cfg, frame, bundle, target)


def train_models(cfg, output):
    """Fit exactly the declared native 0/8-layer models; never access final labels."""
    import numpy as np
    import torch
    from tools.learned_combination.native_adapter import native_ontologies
    from tools.learned_combination.runner import subset_reference

    need(cfg['format'] == 'biograph-steward.contextual-stacker-training.v1', 'unexpected training configuration.')
    need(cfg['params'] == PARAMETERS, 'training parameters differ from the fixed published recipe/adaptations.')
    need(type(cfg['seed']) is int and cfg['namespace'] in ('molecular_function', 'biological_process', 'cellular_component'),
         'explicit seed and one native namespace required.')
    validate_validation_sources(cfg['evaluation'])
    pins = cfg['input_file_pins']
    for path in pins:
        require_pinned(path, pins)
    require_pinned(cfg['model_obo']['file'], pins)
    need(sha(cfg['model_obo']['file']) == cfg['model_obo']['sha256'], 'fixed model ontology changed.')
    fit, x_fit, y_fit = read_feature_manifest(cfg['fit_manifest'], pins, fitting=True)
    val, x_val, _ = read_feature_manifest(cfg['validation_manifest'], pins, fitting=False)
    need(fit['terms'] == val['terms'], 'training/validation model GO axes differ.')
    need(not set(fit['proteins']) & set(val['proteins']), 'fitting and validation protein identities overlap.')
    graph = native_ontologies(cfg['model_obo']['file'])[cfg['namespace']]
    need(tuple(fit['terms']) == tuple(n['id'] for n in graph.terms_list), 'cache/model ontology term axes differ.')
    runtime = qualified_training_runtime()
    need(torch.cuda.is_available(), 'qualified native embedded stacker requires available CUDA; do not start compute automatically.')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'configuration.json', cfg)
    validation_frame = output / 'validation_frame'
    validation_frame.mkdir()
    refs = cfg['evaluation']['references']
    subset_reference([refs['truth']['file']], val['proteins'], validation_frame / 'truth.tsv')
    subset_reference([refs['known']['file']], val['proteins'], validation_frame / 'known.tsv')
    cfg = dict(cfg)
    cfg['_validation_frame'] = {'truth': str(validation_frame / 'truth.tsv'), 'known': str(validation_frame / 'known.tsv')}
    author = load_author(cfg['author_root'], jit_backend='numba')
    native_train, native_swa, native_predict = training_author(author)
    fit_rows, fit_scope = root_positive_rows(graph, y_fit)
    fit_scope['selected_proteins'] = [fit['proteins'][int(i)] for i in fit_rows]
    selected_set = set(fit_scope['selected_proteins'])
    fit_scope['excluded_proteins'] = [p for p in fit['proteins'] if p not in selected_set]
    write_json(output / 'fitting_scope.json', fit_scope)
    training_dataset = CachedNativeDataset(fit, x_fit, graph, y_fit, row_indices=fit_rows)
    validation_dataset = CachedNativeDataset(val, x_val, graph)
    candidates = {}
    try:
        for layers in (0, 8):
            print(now(), 'TRAIN', cfg['namespace'], 'layers', layers, flush=True)
            folder = output / ('layers_' + str(layers))
            folder.mkdir()
            random.seed(cfg['seed']); np.random.seed(cfg['seed']); torch.manual_seed(cfg['seed']); torch.cuda.manual_seed_all(cfg['seed'])
            torch.save({'python': random.getstate(), 'numpy': np.random.get_state(),
                        'torch_cpu': torch.get_rng_state(), 'torch_cuda': torch.cuda.get_rng_state_all()}, folder / 'initial_rng.pth')
            train_dl = author.data_module.StackDataLoader(training_dataset, batch_size=32, shuffle=True,
                num_workers=0, generator=torch.Generator().manual_seed(cfg['seed']))
            val_dl = author.data_module.StackDataLoader(validation_dataset, batch_size=32,
                                                       shuffle=False, num_workers=0)
            model = make_model(author, n_terms=len(fit['terms']), terms=fit['terms'],
                               n_layers=layers, embed_size=8, seed=cfg['seed']).cuda()
            validate_model_axis(model, fit['terms'])
            swa = native_swa(10, path=str(folder / 'native_swa'), rewrite=False)
            (folder / 'validation').mkdir()
            evaluator = ConsumedValidationCallback(cfg, folder / 'validation', val, native_predict, graph)
            model, swa, scores = native_train(model, swa, train_dl, val_dl, evaluator,
                n_ep=20, lr=.001, clip_grad=.1, weight_decay=0.)
            need(len(scores) == 20 and evaluator.epoch == 20, 'native training did not complete every declared epoch.')
            # Preserve all epoch parameters before the native SWA object rotates
            # its managed top-ten directory. The callback already saved them.
            selected_sources = [Path(swa.file.format(i, score)) for i, score in enumerate(swa.scores[:3])]
            source_states = [torch.load(p, map_location='cpu') for p in selected_sources]
            model = swa.set_weights(model, 3, weighted=False)
            maximum = 0.
            for key, observed in model.state_dict().items():
                expected = sum(state[key] / 3 for state in source_states)
                maximum = max(maximum, float((observed.detach().cpu() - expected).abs().max()))
            need(maximum <= 1e-6, 'native SWA parameters differ from uniform top-three parameter average.')
            checkpoint = folder / 'swa_best3.pth'
            torch.save(model.state_dict(), checkpoint)
            final_score = evaluator.evaluate(model, val_dl, 'swa_best3')
            metadata = {'created_at': now(), 'namespace': cfg['namespace'], 'n_layers': layers,
                        'embed_size': 8, 'model_terms_sha256': axis_sha(fit['terms']),
                        'checkpoint_file': str(checkpoint), 'checkpoint_sha256': sha(checkpoint),
                        'validation_ordinary_micro_fmax': final_score, 'epoch_scores': [float(v) for v in scores],
                        'selected_swa_sources': {str(p): sha(p) for p in selected_sources},
                        'swa_parameter_parity_max_abs': maximum,
                        'aggregation': 'uniform average of three checkpoint parameter states, not predictions',
                        'postprocessing': PARAMETERS['postprocessing'],
                        'fit_manifest_sha256': fit['_manifest_sha256'], 'validation_manifest_sha256': val['_manifest_sha256'],
                        'fresh_final_reference_opened': False}
            write_json(folder / 'model.json', metadata)
            candidates[str(layers)] = metadata
            del model, source_states
            torch.cuda.empty_cache()  # This process only; no other service state.
        winner = max((0, 8), key=lambda layers: (candidates[str(layers)]['validation_ordinary_micro_fmax'], -layers))
        for path in pins:
            require_pinned(path, pins)
        result = {'created_at': now(), 'namespace': cfg['namespace'], 'source_receipt': author.source_receipt,
                  'native_training_source_pins': TRAINING_AUTHOR_PINS,
                  'postprocessing_source_pins': POSTPROCESS_SOURCE_PINS,
                  'params': PARAMETERS, 'runtime': runtime,
                  'configuration_sha256': sha(output / 'configuration.json'),
                  'fitting_scope_sha256': sha(output / 'fitting_scope.json'), 'fitting_scope': fit_scope,
                  'candidates': candidates, 'selected_layers': winner, 'selection_tie_rule': 'simpler zero-layer model',
                  'selection_metric': 'deployed soft-output consumed validation ordinary native micro-Fmax, .01 grid',
                  'fresh_final_reference_opened': False}
        write_json(output / 'training_result.json', result)
        return result
    except Exception as error:
        write_json(output / 'failure.json', {'created_at': now(), 'exception': repr(error),
                                            'traceback': traceback.format_exc(), 'partial_results_preserved': True})
        raise


def export_predictions(cfg, *, model_metadata, feature_manifest, output):
    """Use a frozen model on an exact fixed-axis, label-free feature manifest."""
    import numpy as np
    import torch
    from tools.learned_combination.native_adapter import native_ontologies

    metadata = json.loads(Path(model_metadata).read_text())
    runtime = qualified_training_runtime()
    need(metadata['fresh_final_reference_opened'] is False, 'model selection must precede final labels.')
    need(metadata['postprocessing'] == PARAMETERS['postprocessing'], 'selected model used a different deployed recipe.')
    need(sha(metadata['checkpoint_file']) == metadata['checkpoint_sha256'], 'selected checkpoint changed.')
    manifest, features, _ = read_feature_manifest(feature_manifest, cfg['input_file_pins'], fitting=False)
    need(not manifest.get('targets_file'), 'final forecasting requires a label-free feature manifest.')
    need(axis_sha(manifest['terms']) == metadata['model_terms_sha256'], 'frozen embedded model GO axis changed.')
    graph = native_ontologies(cfg['model_obo']['file'])[cfg['namespace']]
    author = load_author(cfg['author_root'], jit_backend='numba')
    _, _, native_predict = training_author(author)
    dataset = CachedNativeDataset(manifest, features, graph)
    loader = author.data_module.StackDataLoader(dataset, batch_size=32, shuffle=False, num_workers=0)
    model = make_model(author, n_terms=len(manifest['terms']), terms=manifest['terms'],
                       n_layers=metadata['n_layers'], embed_size=8, seed=cfg['seed']).cuda()
    model.load_state_dict(torch.load(metadata['checkpoint_file'], map_location='cpu'))
    validate_model_axis(model, manifest['terms'])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    scores = native_predict(model, loader)
    need(scores.dtype == np.float32 and np.isfinite(scores).all() and (scores >= 0).all()
         and (scores <= 1).all(), 'nonfinite native forecast.')
    bundle = save_soft_forecast(cfg['author_root'], graph, manifest['proteins'], manifest['terms'], scores, output)
    result = {'created_at': now(), 'namespace': cfg['namespace'],
              **bundle,
              'model_metadata_sha256': sha(model_metadata), 'feature_manifest_sha256': sha(feature_manifest),
              'runtime': runtime,
              'fresh_final_reference_opened': False, 'final_reference_labels_read_for_forecasting': False}
    write_json(output / 'predictions.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('train', 'score-validation'))
    parser.add_argument('--config')
    parser.add_argument('--job')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.phase == 'train':
        result = train_models(json.loads(Path(args.config).read_text()), args.output)
    else:
        result = score_validation(args.job)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
