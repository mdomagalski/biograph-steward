# SPDX-License-Identifier: GPL-3.0-only
"""One source-qualified forty-context BPO feature variant; native training.

The original one-context models remain intact. This wrapper adds no layer,
loss, optimizer, architecture sweep or label source: it supplies the existing
GCNStacker.in_goa input from a qualified ordered bool sidecar. The native train,
SWA, inference helper and published pure-GO postprocessing remain unchanged.
"""
import argparse
import json
from pathlib import Path
import random
import traceback

from .context_io import BooleanContextDataset, read_boolean_context
from .native_stacker import load_author, make_model, need, validate_model_axis, validate_model_context
from .training import (
    PARAMETERS, ConsumedValidationCallback, axis_sha, now, qualified_training_runtime,
    read_feature_manifest, require_pinned, root_positive_rows, save_soft_forecast,
    sha, training_author, validate_validation_sources, write_json,
)


CONTRACT_SHA256 = 'c71fb4e43664a64fbb32e1cb15a453bbee9ee4efd66931eb2d0d7c96c16a8c8e'
CONTRACT_NAME = 'source_derived_namespaced40_true_raw_prop_v1'
CONTEXT_PARAMETERS = {**PARAMETERS, 'architectures': [8], 'context_profile': CONTRACT_NAME}


def validate_context_contract(cfg):
    """Bind source-only qualification and literal channels before any fitting."""
    need(cfg['format'] == 'biograph-steward.coded-context-training.v1'
         and cfg['namespace'] == 'biological_process' and cfg['seed'] == 20261115,
         'only the one declared BPO feature variant and seed are permitted.')
    need(cfg['params'] == CONTEXT_PARAMETERS, 'coded context variant cannot change native fitting parameters.')
    spec = cfg['channel_contract']
    need(spec['sha256'] == CONTRACT_SHA256 and sha(spec['file']) == CONTRACT_SHA256,
         'source-only forty-channel qualification contract changed.')
    contract = json.loads(Path(spec['file']).read_text())
    need(contract['name'] == CONTRACT_NAME and len(contract['channels']) == 40
         and len(set(contract['channels'])) == 40 and contract['literal_published38_reproduction'] is False,
         'explicit source-derived forty-channel profile and I/O adaptations required.')
    return contract


class ContextValidationCallback(ConsumedValidationCallback):
    def evaluate(self, model, loader, label, *, save_checkpoint=False):
        validate_model_context(model, loader.dataset._biograph_context_channels)
        return super().evaluate(model, loader, label, save_checkpoint=save_checkpoint)


def train_context_model(cfg, output):
    """Fit one native eight-layer BPO model on unchanged allowed targets."""
    import numpy as np
    import torch
    from tools.learned_combination.native_adapter import native_ontologies
    from tools.learned_combination.runner import subset_reference

    contract = validate_context_contract(cfg)
    validate_validation_sources(cfg['evaluation'])
    pins = cfg['input_file_pins']
    for path in pins:
        require_pinned(path, pins)
    require_pinned(cfg['model_obo']['file'], pins)
    need(sha(cfg['model_obo']['file']) == cfg['model_obo']['sha256'], 'fixed model ontology changed.')
    fit, xf, yf = read_feature_manifest(cfg['fit_manifest'], pins, fitting=True)
    val, xv, _ = read_feature_manifest(cfg['validation_manifest'], pins, fitting=False)
    cf, bf = read_boolean_context(cfg['fit_context_manifest'], pins, fit)
    cv, bv = read_boolean_context(cfg['validation_context_manifest'], pins, val)
    need(cf['channels'] == cv['channels'] == contract['channels'], 'source-qualified context channel order differs.')
    need(fit['terms'] == val['terms'] and not set(fit['proteins']) & set(val['proteins']),
         'fit/consumed validation protein or model GO frames differ from their declared split.')
    need(len(fit['proteins']) == 4040 and len(val['proteins']) == 797,
         'source-qualified fitting/consumed-validation frames must stay complete.')
    graph = native_ontologies(cfg['model_obo']['file'])['biological_process']
    need(tuple(fit['terms']) == tuple(n['id'] for n in graph.terms_list), 'fixed model GO identity axis changed.')
    runtime = qualified_training_runtime()
    need(torch.cuda.is_available(), 'native embedded contextual model requires the already-authorized CUDA phase.')
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'configuration.json', cfg)
    frames = output / 'validation_frame'; frames.mkdir()
    refs = cfg['evaluation']['references']
    subset_reference([refs['truth']['file']], val['proteins'], frames / 'truth.tsv')
    subset_reference([refs['known']['file']], val['proteins'], frames / 'known.tsv')
    cfg = dict(cfg); cfg['_validation_frame'] = {'truth': str(frames / 'truth.tsv'), 'known': str(frames / 'known.tsv')}
    rows, scope = root_positive_rows(graph, yf)
    need(len(rows) == 3557, 'native root-positive BPO fitting scope changed.')
    scope['selected_proteins'] = [fit['proteins'][int(i)] for i in rows]
    write_json(output / 'fitting_scope.json', scope)
    author = load_author(cfg['author_root'], jit_backend='numba')
    native_train, native_swa, native_predict = training_author(author)
    fit_ds = BooleanContextDataset(fit, xf, graph, cf, bf, yf, row_indices=rows)
    val_ds = BooleanContextDataset(val, xv, graph, cv, bv)
    random.seed(cfg['seed']); np.random.seed(cfg['seed']); torch.manual_seed(cfg['seed']); torch.cuda.manual_seed_all(cfg['seed'])
    torch.save({'python': random.getstate(), 'numpy': np.random.get_state(),
                'torch_cpu': torch.get_rng_state(), 'torch_cuda': torch.cuda.get_rng_state_all()}, output / 'initial_rng.pth')
    try:
        train_dl = author.data_module.StackDataLoader(fit_ds, batch_size=32, shuffle=True,
            num_workers=0, generator=torch.Generator().manual_seed(cfg['seed']))
        val_dl = author.data_module.StackDataLoader(val_ds, batch_size=32, shuffle=False, num_workers=0)
        model = make_model(author, n_terms=len(fit['terms']), terms=fit['terms'],
            n_layers=8, embed_size=8, seed=cfg['seed'], context_channels=contract['channels']).cuda()
        validate_model_axis(model, fit['terms']); validate_model_context(model, contract['channels'])
        swa = native_swa(10, path=str(output / 'native_swa'), rewrite=False)
        (output / 'validation').mkdir()
        evaluator = ContextValidationCallback(cfg, output / 'validation', val, native_predict, graph)
        model, swa, scores = native_train(model, swa, train_dl, val_dl, evaluator,
            n_ep=20, lr=.001, clip_grad=.1, weight_decay=0.)
        need(len(scores) == evaluator.epoch == 20, 'coded context fit did not complete the fixed twenty epochs.')
        selected = [Path(swa.file.format(i, score)) for i, score in enumerate(swa.scores[:3])]
        states = [torch.load(p, map_location='cpu') for p in selected]
        model = swa.set_weights(model, 3, weighted=False)
        parity = max(float((value.detach().cpu() - sum(s[key] / 3 for s in states)).abs().max())
                     for key, value in model.state_dict().items())
        need(parity <= 1e-6, 'coded context native best-three parameter averaging differs.')
        checkpoint = output / 'swa_best3.pth'; torch.save(model.state_dict(), checkpoint)
        score = evaluator.evaluate(model, val_dl, 'swa_best3')
        metadata = {'created_at': now(), 'namespace': 'biological_process', 'n_layers': 8, 'embed_size': 8,
            'in_models': 2, 'in_goa': 40, 'context_channels_sha256': axis_sha(contract['channels']),
            'context_channels': contract['channels'], 'context_contract': cfg['channel_contract'],
            'model_terms_sha256': axis_sha(fit['terms']), 'checkpoint_file': str(checkpoint),
            'checkpoint_sha256': sha(checkpoint), 'validation_ordinary_micro_fmax': score,
            'epoch_scores': [float(s) for s in scores], 'selected_swa_sources': {str(p): sha(p) for p in selected},
            'swa_parameter_parity_max_abs': parity, 'postprocessing': PARAMETERS['postprocessing'],
            'fit_manifest_sha256': sha(cfg['fit_manifest']), 'validation_manifest_sha256': sha(cfg['validation_manifest']),
            'fit_context_manifest_sha256': sha(cfg['fit_context_manifest']),
            'validation_context_manifest_sha256': sha(cfg['validation_context_manifest']),
            'context_role_manifests': {'fit': {'file': cfg['fit_context_manifest'], 'sha256': sha(cfg['fit_context_manifest'])},
                                      'validation': {'file': cfg['validation_context_manifest'], 'sha256': sha(cfg['validation_context_manifest'])}},
            'configuration_sha256': sha(output / 'configuration.json'),
            'fitting_scope_sha256': sha(output / 'fitting_scope.json'),
            'prior_universe_count': 4040, 'supervised_fitting_rows': int(len(rows)),
            'runtime': runtime, 'fresh_final_reference_opened': False,
            'literal_CAFA6_reproduction': False, 'hyperparameter_or_seed_search': False}
        write_json(output / 'model.json', metadata)
        for path in pins:
            require_pinned(path, pins)
        result = {'created_at': now(), 'status': 'complete', 'params': CONTEXT_PARAMETERS,
            'configuration_sha256': sha(output / 'configuration.json'), 'model_file': str(output / 'model.json'),
            'model_metadata_sha256': sha(output / 'model.json'), 'validation_ordinary_micro_fmax': score,
            'channel_contract': cfg['channel_contract'], 'new_final_reference_labels_read': False}
        write_json(output / 'training_result.json', result)
        return result
    except Exception as error:
        write_json(output / 'failure.json', {'created_at': now(), 'error': repr(error),
            'traceback': traceback.format_exc(), 'all_partial_artifacts_retained': True})
        raise


def export_context_predictions(cfg, *, model_metadata, feature_manifest, context_manifest, output):
    """Forecast with exact GO/context axes and no final-reference labels."""
    import torch
    from tools.learned_combination.native_adapter import native_ontologies

    contract = validate_context_contract(cfg)
    metadata = json.loads(Path(model_metadata).read_text())
    need(metadata['context_channels'] == contract['channels'] and metadata['fresh_final_reference_opened'] is False,
         'selected context model identity/boundary differs.')
    need(metadata['n_layers'] == 8 and metadata['in_goa'] == 40 and metadata['in_models'] == 2
         and metadata['context_channels_sha256'] == axis_sha(contract['channels']),
         'model layer/input/ordered context identity differs.')
    need(sha(metadata['checkpoint_file']) == metadata['checkpoint_sha256'], 'context model checkpoint changed.')
    require_pinned(cfg['model_obo']['file'], cfg['input_file_pins'])
    need(sha(cfg['model_obo']['file']) == cfg['model_obo']['sha256'], 'fixed model ontology changed.')
    need(metadata['postprocessing'] == PARAMETERS['postprocessing'], 'context model deployed recipe differs.')
    manifest, features, _ = read_feature_manifest(feature_manifest, cfg['input_file_pins'], fitting=False)
    need(not manifest.get('targets_file') and len(manifest['proteins']) == 3300,
         'context forecasting requires the complete label-free target frame.')
    context, values = read_boolean_context(context_manifest, cfg['input_file_pins'], manifest)
    need(context['channels'] == metadata['context_channels']
         and axis_sha(manifest['terms']) == metadata['model_terms_sha256'], 'forecast model/context identity order changed.')
    graph = native_ontologies(cfg['model_obo']['file'])['biological_process']
    runtime = qualified_training_runtime(); author = load_author(cfg['author_root'], jit_backend='numba')
    _, _, native_predict = training_author(author)
    ds = BooleanContextDataset(manifest, features, graph, context, values)
    loader = author.data_module.StackDataLoader(ds, batch_size=32, shuffle=False, num_workers=0)
    model = make_model(author, n_terms=len(manifest['terms']), terms=manifest['terms'],
        n_layers=8, embed_size=8, seed=cfg['seed'], context_channels=metadata['context_channels']).cuda()
    model.load_state_dict(torch.load(metadata['checkpoint_file'], map_location='cpu'))
    validate_model_axis(model, manifest['terms']); validate_model_context(model, context['channels'])
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    bundle = save_soft_forecast(cfg['author_root'], graph, manifest['proteins'], manifest['terms'],
                                native_predict(model, loader), output)
    result = {**bundle, 'namespace': 'biological_process', 'context_channels': context['channels'],
        'in_goa': 40, 'n_layers': 8, 'context_channels_sha256': axis_sha(context['channels']),
        'context_contract': cfg['channel_contract'], 'model_metadata_sha256': sha(model_metadata),
        'feature_manifest_sha256': sha(feature_manifest), 'context_manifest_sha256': sha(context_manifest),
        'runtime': runtime, 'fresh_final_reference_opened': False,
        'final_reference_labels_read_for_forecasting': False}
    write_json(output / 'predictions.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('train', 'forecast'))
    parser.add_argument('--config', required=True); parser.add_argument('--output', required=True)
    parser.add_argument('--model'); parser.add_argument('--features'); parser.add_argument('--context')
    args = parser.parse_args(); cfg = json.loads(Path(args.config).read_text())
    result = (train_context_model(cfg, args.output) if args.phase == 'train' else
        export_context_predictions(cfg, model_metadata=args.model, feature_manifest=args.features,
                                   context_manifest=args.context, output=args.output))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
