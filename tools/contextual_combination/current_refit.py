# SPDX-License-Identifier: GPL-3.0-only
"""Native training I/O for one proposed current-T0 development refit.

This module freezes the original checkpoint schedule. It supplies no current
validation data or metric and changes no native optimizer, loss, model or SWA
body. Real data admission, model construction and GPU lifecycle remain outside
this small adapter and require their separately qualified source contract.
"""
import json
import math
from pathlib import Path
import re

from .training import now, sha, training_author, write_json
from .native_stacker import need


ORIGINAL_MODEL_SHA256 = '1839d2d09ad62b4ee6770fb623dc62dbca4b9ad2ab8c7ba91680c62b5acef2dc'
FROZEN_EPOCHS = (10, 12, 11)  # Zero-based, native descending-priority order.
EPOCHS = 20
PLAN_SHA256 = '8128b0c3cbda794cb8cd75b711609cfed1f1a150ef81ba3e90339cd4815ecca9'
ORIGINAL_OBO_SHA256 = '0c0062efbb1b199a6a54e62c0c48ff0038d39173aecc7edfab66a20090d5ec2d'
FINAL_CONTEXT_SHA256 = 'f8d10a3d57e40b670d961a8bbc16becb7d674aa8448484ccd4d247c7d09b9f4e'
ARM = 'current_T0_positive_union_context_refit'


def native_epoch_ranking(priorities, store=10):
    """Replay the source-pinned SWA insertion rule, including latest-on-tie."""
    ordered = []
    for epoch, value in enumerate(priorities):
        for position in range(store):
            if len(ordered) == position or value >= ordered[position][1]:
                break
        else:
            continue
        ordered.insert(position, (epoch, value))
        ordered = ordered[:store]
    return ordered


def frozen_priorities(spec):
    """Convert only the original pinned epoch scores to order/tie-equivalent ranks."""
    need(spec['sha256'] == ORIGINAL_MODEL_SHA256 and sha(spec['file']) == ORIGINAL_MODEL_SHA256,
         'only the original pre-opening chosen BPO model can supply checkpoint priorities.')
    source = json.loads(Path(spec['file']).read_text())
    need(source['namespace'] == 'biological_process' and source['n_layers'] == 8
         and source['in_goa'] == 40 and source['fresh_final_reference_opened'] is False,
         'checkpoint priorities must come from the original chosen forty-context BPO model.')
    scores = source['epoch_scores']
    need(len(scores) == EPOCHS and all(type(s) in (float, int) and math.isfinite(s)
                                     and 0 <= s <= 1 for s in scores), 'complete original epoch metadata required.')
    ranking = native_epoch_ranking(scores)
    need(tuple(epoch for epoch, _ in ranking[:3]) == FROZEN_EPOCHS,
         'original chosen epoch indices differ from the fixed pre-opening schedule.')
    saved = []
    for filename in source['selected_swa_sources']:
        match = re.fullmatch(r'checkpoint([0-9]+)_([^/]+)\.pth', Path(filename).name)
        need(match is not None, 'original native SWA source filename differs.')
        saved.append((int(match.group(1)), float(match.group(2))))
    need(sorted(saved) == list(enumerate(value for _, value in ranking[:3])),
         'original saved SWA sources do not match the original epoch-ranking metadata.')
    ranks = {value: rank + 1 for rank, value in enumerate(sorted(set(scores)))}
    priorities = tuple(float(ranks[value]) for value in scores)
    need(native_epoch_ranking(priorities) == [(epoch, float(ranks[value])) for epoch, value in ranking],
         'ordinal priority conversion changed score ordering or ties.')
    return priorities, {'original_model_metadata_sha256': ORIGINAL_MODEL_SHA256,
        'frozen_checkpoint_priorities': list(priorities),
        'frozen_epoch_indices_zero_based': list(FROZEN_EPOCHS),
        'frozen_epoch_numbers_one_based': [epoch + 1 for epoch in FROZEN_EPOCHS],
        'priority_semantics': 'ordinal ordering and ties from original pre-opening epoch metadata; not current validation scores',
        'current_validation_metric_computed': False}


class OpaqueNoValidation:
    """Poison placeholder: accidentally reading validation data must fail."""
    def __iter__(self):
        raise AssertionError('A final refit cannot iterate validation data.')

    def __len__(self):
        raise AssertionError('A final refit cannot inspect validation data.')

    def __getitem__(self, key):
        raise AssertionError('A final refit cannot index validation data.')


class FrozenCheckpointCallback:
    """Fill the native callback slot with a fixed checkpoint priority only."""
    def __init__(self, priorities):
        self.priorities = tuple(priorities)
        need(len(self.priorities) == EPOCHS and all(math.isfinite(v) for v in self.priorities),
             'exactly twenty finite frozen priorities required.')
        need(tuple(epoch for epoch, _ in native_epoch_ranking(self.priorities)[:3]) == FROZEN_EPOCHS,
             'frozen priority schedule changed.')
        self.placeholder = OpaqueNoValidation()
        self.calls = 0

    def __call__(self, model, loader):
        need(loader is self.placeholder, 'no validation loader or outcomes may enter the frozen-priority callback.')
        need(self.calls < EPOCHS, 'native trainer called the frozen callback more than twenty times.')
        value = self.priorities[self.calls]
        self.calls += 1
        return value

    def complete(self):
        need(self.calls == EPOCHS, 'native trainer did not consume exactly twenty frozen priorities.')


def fit_native_frozen_schedule(author, model, training_loader, original_model_metadata, output):
    """Low-level native call; real-data/source/model admission belongs to the caller.

    There is deliberately no evaluation config, validation loader, threshold
    choice or reference path in this API. Until a separately reviewed source
    producer is admitted, this function is exercised only on invented data.
    """
    import torch

    priorities, provenance = frozen_priorities(original_model_metadata)
    callback = FrozenCheckpointCallback(priorities)
    native_train, native_swa, _ = training_author(author)
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'frozen_checkpoint_priority_source.json', provenance)
    print('REFIT PROVENANCE: legacy native lines labeled "CAFA5 score" below contain '
          'FROZEN CHECKPOINT PRIORITIES ONLY. No current validation prediction or metric is computed.', flush=True)
    swa = native_swa(10, path=str(output / 'native_swa'), rewrite=False)
    model, swa, returned_priorities = native_train(model, swa, training_loader,
        callback.placeholder, callback, n_ep=20, lr=.001, clip_grad=.1, weight_decay=0.)
    callback.complete()
    need(tuple(returned_priorities) == priorities, 'native callback priority sequence changed.')
    need(tuple(swa.scores[:3]) == tuple(priorities[i] for i in FROZEN_EPOCHS),
         'native SWA selected a different fixed epoch schedule.')
    selected = [Path(swa.file.format(i, value)) for i, value in enumerate(swa.scores[:3])]
    states = [torch.load(path, map_location='cpu') for path in selected]
    model = swa.set_weights(model, 3, weighted=False)
    difference = max(float((value.detach().cpu() - sum(state[key] / 3 for state in states)).abs().max())
                     for key, value in model.state_dict().items())
    need(difference <= 1e-6, 'native uniform three-state parameter averaging differs.')
    checkpoint = output / 'frozen_epoch_average.pth'; torch.save(model.state_dict(), checkpoint)
    receipt = {'format': 'biograph-steward.native-frozen-schedule-refit.v1', 'created_at': now(),
        **provenance, 'native_callback_calls': callback.calls,
        'checkpoint_file': str(checkpoint), 'checkpoint_sha256': sha(checkpoint),
        'selected_swa_sources': {str(path): sha(path) for path in selected},
        'uniform_three_parameter_state_average_max_abs': difference,
        'reference_previously_consumed': True, 'independent_confirmation': False,
        'current_validation_predictions_or_metrics_computed': False,
        'best_on_refreshed_data_selection_claimed': False,
        'this_adapter_accepts_no_reference_or_validation_file_input': True,
        'native_train_and_SWA_bodies_changed': False}
    write_json(output / 'frozen_schedule_refit_receipt.json', receipt)
    return model, receipt


def pinned(spec):
    need(sha(spec['file']) == spec['sha256'], 'changed source/model preparation artifact.')
    return json.loads(Path(spec['file']).read_text())


def development_flags(value):
    need(value.get('development_after_reference_opening') is True
         and value.get('reference_previously_consumed') is True
         and value.get('independent_confirmation') is False,
         'post-opening development status must remain explicit.')


def validate_positive_union(original, targets, retention_mask, expected):
    """Check all old full positives, not only the older known-mask subset."""
    import numpy as np

    need(original.shape == targets.shape == retention_mask.shape
         and retention_mask.dtype == np.bool_, 'original-full retention mask axes/dtype differ.')
    old_count = new_count = additions = addition_proteins = 0
    for start in range(0, len(targets), 32):
        old, new, mask = original[start:start + 32], targets[start:start + 32], retention_mask[start:start + 32]
        need(np.isin(old, [0, 1]).all() and np.isin(new, [0, 1]).all(), 'full positive targets must stay binary.')
        positive = old > 0
        need(np.array_equal(mask, positive) and (new[positive] == 1).all(),
             'new targets must retain every ORIGINAL FULL positive, with that exact retention mask.')
        delta = (new > 0) & ~positive
        old_count += int(positive.sum()); new_count += int((new > 0).sum())
        additions += int(delta.sum()); addition_proteins += int(delta.any(axis=1).sum())
    actual = {'original_full_positive_cells': old_count, 'augmented_positive_cells': new_count,
              'added_positive_cells': additions, 'fitting_proteins_with_additions': addition_proteins}
    need(actual == expected, 'source-positive union differs from the frozen source-only counts.')
    return actual


def read_development_context(spec, pins, manifest, *, fitting):
    """Same typed Boolean I/O; new provenance never claims an unopened study."""
    import numpy as np
    from .context_io import CONTEXT_FORMAT
    from .native_stacker import context_axis
    from .training import require_pinned

    require_pinned(spec['file'], pins); meta = pinned(spec)
    need(meta['format'] == CONTEXT_FORMAT and meta['proteins'] == manifest['proteins']
         and meta['terms'] == manifest['terms'], 'refit context axes/format differ.')
    channels = context_axis(meta['channels'])
    if fitting:
        development_flags(meta)
        need('fresh_final_reference_opened' not in meta
             and meta.get('final_reference_labels_read_for_feature_construction') is False,
             'new fitting context must truthfully record consumed-reference, source-only construction.')
    else:
        need(spec['sha256'] == FINAL_CONTEXT_SHA256,
             'only the exact original April-T0 final forty-channel cache may be reused.')
    require_pinned(meta['context_file'], pins)
    need(sha(meta['context_file']) == meta['context_sha256'], 'context array differs from its declaration.')
    values = np.load(meta['context_file'], mmap_mode='r', allow_pickle=False)
    need(values.dtype == np.bool_ and values.shape == (len(meta['proteins']), len(channels), len(meta['terms'])),
         'refit context requires complete Boolean rows/channels/term axes.')
    return meta, values


def prepare_inputs(cfg):
    """CPU-only complete real-source/axis/positive-retention admission."""
    from .training import axis_sha, read_feature_manifest, require_pinned, root_positive_rows
    from .training_context import CONTEXT_PARAMETERS, CONTRACT_SHA256
    from tools.learned_combination.native_adapter import native_ontologies

    allowed = {'format', 'namespace', 'seed', 'params', 'plan', 'source_readiness',
               'author_root', 'original_model_metadata', 'original_fit_manifest',
               'original_final_feature_manifest', 'channel_contract'}
    need(set(cfg) == allowed and cfg['format'] == 'biograph-steward.current-T0-BP-development-refit.v1'
         and cfg['namespace'] == 'biological_process' and cfg['seed'] == 20261115
         and cfg['params'] == CONTEXT_PARAMETERS, 'only the one frozen BP refit configuration is admitted.')
    import numpy as np
    need(cfg['plan']['sha256'] == PLAN_SHA256, 'refit plan differs from the frozen development plan.')
    plan = pinned(cfg['plan']); ready = pinned(cfg['source_readiness']); development_flags(ready)
    need(ready['format'] == 'biograph-steward.current-refit-source-preparation.v1'
         and ready['plan']['sha256'] == PLAN_SHA256
         and ready.get('final_reference_labels_read_for_feature_construction') is False,
         'source producer must bind the exact frozen plan and no held-out-label construction.')
    need(cfg['channel_contract']['sha256'] == CONTRACT_SHA256, 'qualified context profile differs.')
    contract = pinned(cfg['channel_contract'])
    source_admission = pinned(ready['source_admission'])
    pins = ready['input_file_pins']
    for path in pins: require_pinned(path, pins)
    model_source = pinned(cfg['original_model_metadata'])
    frozen_priorities(cfg['original_model_metadata'])
    need(cfg['original_fit_manifest']['sha256'] == model_source['fit_manifest_sha256'],
         'original full target source must be the actual original chosen model fitting manifest.')
    old = pinned(cfg['original_fit_manifest']); old_final = pinned(cfg['original_final_feature_manifest'])
    for field in ('targets_file', 'known_positive_mask_file'):
        need(sha(old[field]) == old['file_pins'][old[field]], 'original full/known target source changed.')
    original_y = np.load(old['targets_file'], mmap_mode='r', allow_pickle=False)
    original_known = np.load(old['known_positive_mask_file'], mmap_mode='r', allow_pickle=False)
    for start in range(0, len(original_y), 32):
        need((original_y[start:start + 32][original_known[start:start + 32]] == 1).all(),
             'original known positives differ from the qualified full target source.')
    manifests = ready['manifests']
    need(set(manifests) == {'targets', 'fit', 'final', 'fit_context', 'final_context'},
         'complete target/fit/final/context source manifests are required.')
    need(source_admission.get('status') == 'passed' and source_admission.get('qualified') is True
         and source_admission.get('plan_sha256') == PLAN_SHA256
         and source_admission.get('target_manifest_sha256') == manifests['targets']['sha256'],
         'source admission must be passed and bound to this plan and exact new target manifest.')
    for role in ('source_preparation_code', 'source_preparation_configuration'):
        spec = source_admission[role]
        need(sha(spec['file']) == spec['sha256'], 'qualified source-preparation code/configuration changed.')
    for spec in manifests.values(): pinned(spec)
    fit, xf, yf = read_feature_manifest(manifests['fit']['file'], pins, fitting=True)
    final, xx, _ = read_feature_manifest(manifests['final']['file'], pins, fitting=False)
    targets = pinned(manifests['targets'])
    need(fit['proteins'] == old['proteins'] and final['proteins'] == old_final['proteins']
         and len(fit['proteins']) == 4040 and len(final['proteins']) == 3300
         and not set(fit['proteins']) & set(final['proteins']), 'original full identity frames changed.')
    need(fit['terms'] == final['terms'] == old['terms'] == old_final['terms']
         and axis_sha(fit['terms']) == model_source['model_terms_sha256'], 'original fixed model GO axis changed.')
    need(not final.get('targets_file') and not final.get('known_positive_mask_file'),
         'final forecasting feature manifest must contain no outcome-label array.')
    need(all(targets[key] == fit[key] for key in ('proteins', 'terms', 'targets_file', 'known_positive_mask_file'))
         and fit.get('retention_mask_semantics') == 'original_full_fitting_positive_repertoire',
         'target-first delivery and fit delivery must bind the same original-FULL retention policy.')
    mask = np.load(fit['known_positive_mask_file'], mmap_mode='r', allow_pickle=False)
    count_fields = plan['source_adaptation']
    expected = {'original_full_positive_cells': count_fields['expected_original_full_BP_positive_cells'],
        'augmented_positive_cells': count_fields['expected_augmented_BP_positive_cells'],
        'added_positive_cells': count_fields['expected_added_BP_positive_cells'],
        'fitting_proteins_with_additions': count_fields['expected_fitting_proteins_with_additions']}
    counts = validate_positive_union(original_y, yf, mask, expected)
    prior = pinned(ready['prior_receipt'])
    need(fit['prior_receipt_file'] == final['prior_receipt_file'] == ready['prior_receipt']['file']
         and fit['prior_receipt_sha256'] == final['prior_receipt_sha256'] == ready['prior_receipt']['sha256']
         and prior['fit_universe'] == fit['proteins'] and prior['fit_universe_count'] == 4040
         and prior['computed_before_root_positive_filter'] is True,
         'fit and final features must share the same full4040 augmented-data priors.')
    need(set(prior['files']) == {'raw.npy', 'conditional.npy', 'nulls.npy'}, 'incomplete native prior outputs.')
    need(prior.get('target_source') == {'file': fit['targets_file'],
        'sha256': fit['file_pins'][fit['targets_file']]},
        'updated prior receipt must bind the actual augmented full target array.')
    for name, digest in prior['files'].items():
        need(sha(Path(ready['prior_receipt']['file']).parent / name) == digest, 'changed native prior array.')
    need(sha(ready['model_obo']['file']) == ready['model_obo']['sha256'] == ORIGINAL_OBO_SHA256,
         'fixed original ontology topology/source changed, even if its term IDs match.')
    graph = native_ontologies(ready['model_obo']['file'])['biological_process']
    need(tuple(fit['terms']) == tuple(n['id'] for n in graph.terms_list), 'cache/native model ontology axes differ.')
    rows, scope = root_positive_rows(graph, yf)
    need(len(rows) == count_fields['expected_augmented_root_positive_rows'] == 3567,
         'refreshed native root-positive fitting scope differs.')
    cf, bf = read_development_context(manifests['fit_context'], pins, fit, fitting=True)
    cx, bx = read_development_context(manifests['final_context'], pins, final, fitting=False)
    need(cf['channels'] == cx['channels'] == contract['channels'], 'ordered forty-channel identity changed.')
    global_channel = cf['channels'].index('global.propagated')
    for features, context in ((xf, bf), (xx, bx)):
        for start in range(0, len(features), 32):
            need(np.array_equal(features[start:start + 32, 8], context[start:start + 32, global_channel]),
                 'base GOA membership differs from the declared source context.')
    proof = {**counts, 'prior_universe_count': 4040, 'supervised_fitting_rows': len(rows),
             'forecast_rows': 3300, 'fixed_terms': len(fit['terms']), 'no_old_full_or_known_positive_lost': True,
             'same_updated_priors_used_fit_and_final': True,
             'original_final_boolean_context_sha256': manifests['final_context']['sha256'],
             'source_admission_sha256': ready['source_admission']['sha256']}
    return {'ready': ready, 'plan': plan, 'contract': contract, 'fit': fit, 'xf': xf, 'yf': yf,
            'final': final, 'xx': xx, 'cf': cf, 'bf': bf, 'cx': cx, 'bx': bx,
            'graph': graph, 'rows': rows, 'scope': scope, 'proof': proof}


def train_prepared(cfg, output):
    import random
    import numpy as np
    import torch
    from .context_io import BooleanContextDataset
    from .native_stacker import load_author, make_model, validate_model_axis, validate_model_context
    from .training import axis_sha, qualified_training_runtime, PARAMETERS

    data = prepare_inputs(cfg); runtime = qualified_training_runtime()
    need(torch.cuda.is_available(), 'real refit requires a separately authorized owned CUDA lifecycle.')
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'configuration.json', cfg); write_json(output / 'source_admission.json', data['proof'])
    author = load_author(cfg['author_root'], jit_backend='numba')
    dataset = BooleanContextDataset(data['fit'], data['xf'], data['graph'], data['cf'], data['bf'],
                                   data['yf'], row_indices=data['rows'])
    random.seed(cfg['seed']); np.random.seed(cfg['seed']); torch.manual_seed(cfg['seed']); torch.cuda.manual_seed_all(cfg['seed'])
    torch.save({'python': random.getstate(), 'numpy': np.random.get_state(), 'torch_cpu': torch.get_rng_state(),
                'torch_cuda': torch.cuda.get_rng_state_all()}, output / 'initial_rng.pth')
    loader = author.data_module.StackDataLoader(dataset, batch_size=32, shuffle=True, num_workers=0,
                                               generator=torch.Generator().manual_seed(cfg['seed']))
    model = make_model(author, n_terms=len(data['fit']['terms']), terms=data['fit']['terms'], n_layers=8,
        embed_size=8, seed=cfg['seed'], context_channels=data['contract']['channels']).cuda()
    validate_model_axis(model, data['fit']['terms']); validate_model_context(model, data['contract']['channels'])
    model, receipt = fit_native_frozen_schedule(author, model, loader, cfg['original_model_metadata'], output / 'native_training')
    metadata = {**receipt, 'format': 'biograph-steward.current-T0-BP-development-model.v1', 'status': 'complete',
        'namespace': 'biological_process', 'n_layers': 8, 'in_goa': 40, 'in_models': 2, 'embed_size': 8,
        'context_channels': data['contract']['channels'], 'context_channels_sha256': axis_sha(data['contract']['channels']),
        'model_terms_sha256': axis_sha(data['fit']['terms']), 'postprocessing': PARAMETERS['postprocessing'],
        'configuration_sha256': sha(output / 'configuration.json'), 'plan_sha256': PLAN_SHA256,
        'source_readiness': cfg['source_readiness'], 'source_admission': data['proof'], 'runtime': runtime,
        'source_input_pins': data['ready']['input_file_pins'],
        'producer_code_sha256': sha(__file__), 'development_after_reference_opening': True,
        'models_fitted': True, 'scientific_metrics_computed': False, 'current_validation_metric_computed': False,
        'automatic_graph_or_app_promotion': False}
    write_json(output / 'model.json', metadata)
    return metadata


def forecast_prepared(cfg, model_spec, output):
    import torch
    from .context_io import BooleanContextDataset
    from .native_stacker import load_author, make_model, validate_model_axis, validate_model_context
    from .training import axis_sha, qualified_training_runtime, save_soft_forecast, PARAMETERS

    data = prepare_inputs(cfg); model_meta = pinned(model_spec); development_flags(model_meta)
    need(model_meta['format'] == 'biograph-steward.current-T0-BP-development-model.v1'
         and model_meta['plan_sha256'] == PLAN_SHA256 and model_meta['source_readiness'] == cfg['source_readiness']
         and model_meta['producer_code_sha256'] == sha(__file__)
         and model_meta['model_terms_sha256'] == axis_sha(data['final']['terms'])
         and model_meta['context_channels'] == data['contract']['channels']
         and model_meta['n_layers'] == 8 and model_meta['in_goa'] == 40
         and model_meta['postprocessing'] == PARAMETERS['postprocessing']
         and model_meta['current_validation_metric_computed'] is False,
         'frozen refit model/source identity differs.')
    need(sha(model_meta['checkpoint_file']) == model_meta['checkpoint_sha256'], 'refit checkpoint changed.')
    source_config = {'file': str(Path(model_spec['file']).parent / 'configuration.json'),
                     'sha256': model_meta['configuration_sha256']}
    need(pinned(source_config) == cfg, 'forecast configuration differs from the completed refit source configuration.')
    author = load_author(cfg['author_root'], jit_backend='numba')
    _, _, predict = training_author(author)
    dataset = BooleanContextDataset(data['final'], data['xx'], data['graph'], data['cx'], data['bx'])
    loader = author.data_module.StackDataLoader(dataset, batch_size=32, shuffle=False, num_workers=0)
    model = make_model(author, n_terms=len(data['final']['terms']), terms=data['final']['terms'], n_layers=8,
        embed_size=8, seed=cfg['seed'], context_channels=data['contract']['channels']).cuda()
    model.load_state_dict(torch.load(model_meta['checkpoint_file'], map_location='cpu'))
    validate_model_axis(model, data['final']['terms']); validate_model_context(model, data['contract']['channels'])
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    bundle = save_soft_forecast(cfg['author_root'], data['graph'], data['final']['proteins'],
                               data['final']['terms'], predict(model, loader), output)
    result = {**bundle, 'status': 'complete', 'arm': ARM, 'namespace': 'biological_process', 'upper_roundoff_tolerance': 0.,
        'plan_sha256': PLAN_SHA256, 'model_metadata_sha256': model_spec['sha256'], 'model_metadata': model_spec,
        'source_readiness': cfg['source_readiness'], 'producer_code_sha256': sha(__file__),
        'producer_source': {'file': str(Path(__file__).resolve()), 'sha256': sha(__file__)},
        'source_configuration': source_config, 'source_input_pins': data['ready']['input_file_pins'],
        'context_channels': data['contract']['channels'], 'context_channels_sha256': axis_sha(data['contract']['channels']),
        'in_goa': 40, 'n_layers': 8, 'postprocessing_recipe': PARAMETERS['postprocessing'],
        'runtime': qualified_training_runtime(), 'development_after_reference_opening': True,
        'reference_previously_consumed': True, 'independent_confirmation': False,
        'final_reference_labels_read_for_forecasting': False, 'scientific_metrics_computed': False,
        'models_fitted': True, 'current_validation_metric_computed': False,
        'automatic_graph_or_app_promotion': False}
    write_json(output / 'predictions.json', result)
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('check', 'train', 'forecast'))
    parser.add_argument('--config', required=True); parser.add_argument('--output'); parser.add_argument('--model')
    args = parser.parse_args(); config = json.loads(Path(args.config).read_text())
    if args.phase == 'check': result = prepare_inputs(config)['proof']
    elif args.phase == 'train': result = train_prepared(config, args.output)
    else: result = forecast_prepared(config, {'file': args.model, 'sha256': sha(args.model)}, args.output)
    print(json.dumps(result, indent=2))
