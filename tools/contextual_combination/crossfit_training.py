# SPDX-License-Identifier: GPL-3.0-only
"""Admit named cross-fitted parents around the unchanged context trainer.

Only source/axis/provenance I/O is added. Native feature transforms, model,
training, loss, validation callback, SWA and forecast postprocessing are reused
unchanged. The old validation is consumed development data; the final reference
was previously consumed by earlier studies and is never a fitting input here.
"""
import argparse
import copy
import importlib
import json
from pathlib import Path

from .native_stacker import need
from .training import (PARAMETERS, VALIDATION_ROLE, axis_sha, now, sha,
                       validate_validation_sources, write_json)
from . import training_context as native


ARM = 'crossfit_graph_frequency_context'
NAMESPACE = 'biological_process'
PARENTS = ['localplus', 'fit_label_frequency']
COUNTS = {'fit_universe': 4040, 'full_positive_cells': 208835,
          'root_positive_rows': 3557, 'validation_proteins': 797,
          'final_proteins': 3300, 'model_terms': 27942}
MODEL_OBO_SHA256 = '0c0062efbb1b199a6a54e62c0c48ff0038d39173aecc7edfab66a20090d5ec2d'
ORIGINAL_FIT_MANIFEST_SHA256 = 'b6c84aae2d8e21c8f99a101b54ecbc92eb5d2eb9b100ad9f26c561b3271e3fb2'
READY_FORMAT = 'biograph-steward.crossfit-graph-prevalence-features.v1'
CONFIG_FORMAT = 'biograph-steward.crossfit-context-training.v1'
PLAN_FORMAT = 'biograph-steward.crossfit-graph-frequency-development-plan.v1'
SOURCE_MODULES = {'crossfit_training': __name__,
    'training_context': 'tools.contextual_combination.training_context',
    'training': 'tools.contextual_combination.training',
    'context_io': 'tools.contextual_combination.context_io',
    'native_stacker': 'tools.contextual_combination.native_stacker',
    'postprocessing': 'tools.contextual_combination.postprocessing'}
FLAGS = {'development_after_reference_opening': True,
         'reference_previously_consumed': True, 'independent_confirmation': False}


def pinned(spec):
    need(isinstance(spec, dict) and set(spec) == {'file', 'sha256'},
         'canonical file/sha256 source specification required.')
    need(sha(spec['file']) == spec['sha256'], 'pinned source artifact changed.')
    return json.loads(Path(spec['file']).read_text())


def truthful_flags(value):
    need(all(value.get(key) is expected for key, expected in FLAGS.items()),
         'consumed-reference development provenance must remain explicit.')


def validate_plan(plan):
    need(plan.get('format') == PLAN_FORMAT and plan.get('arm') == ARM
         and plan.get('namespace') == NAMESPACE and plan.get('parent_axis') == PARENTS
         and plan.get('reference_previously_consumed') is True
         and plan.get('independent_confirmation') is False,
         'only the fixed named cross-fitting development plan is accepted.')
    expected = {'seed': 20261115, 'params': native.CONTEXT_PARAMETERS,
        'fitting_universe': COUNTS['fit_universe'],
        'root_positive_fitting_rows': COUNTS['root_positive_rows'],
        'validation_proteins': COUNTS['validation_proteins'],
        'final_proteins': COUNTS['final_proteins'], 'model_terms': COUNTS['model_terms']}
    model = plan.get('model', {})
    need(all(model.get(key) == value for key, value in expected.items())
         and model.get('original_full_positive_cells') == COUNTS['full_positive_cells']
         and model.get('new_fits') == 1
         and model.get('native_training_loss_optimizer_and_SWA_unchanged') is True
         and model.get('normal_consumed_validation_checkpoint_selection') is True,
         'native model, fitting universe or fixed training budget changed.')
    expected_folds = {'n_splits': 5, 'group_key': 'exact_full_sequence_SHA256',
        'method': 'sklearn.model_selection.GroupKFold', 'shuffle': False,
        'priors': 'native_complement_before_root_filter'}
    need(all(plan.get('folds', {}).get(key) == value for key, value in expected_folds.items()),
         'fixed grouped-fold/prior contract changed.')
    need(plan.get('new_primary_success_gate') is False
         and plan.get('original_primary_comparison_unchanged') is True
         and plan.get('graph_pruning_or_app_promotion') is False
         and plan.get('test_outcome_based_model_selection') is False,
         'development comparison cannot add a test-selected model, primary gate or graph promotion.')


def check_source_pins(specs, ready):
    need(isinstance(specs, dict) and set(SOURCE_MODULES) | {'crossfit_prepare'} <= set(specs),
         'all wrapper, producer and unchanged native helper sources must be qualified.')
    for name, spec in specs.items():
        need(set(spec) == {'file', 'sha256'} and sha(spec['file']) == spec['sha256'],
             'qualified executable source changed: ' + name)
    for role, module_name in SOURCE_MODULES.items():
        module = importlib.import_module(module_name)
        need(sha(module.__file__) == specs[role]['sha256'],
             'running native helper differs from qualified source: ' + role)
    need(ready['producer_source'] == specs['crossfit_prepare'],
         'feature producer is not the qualified source.')


def bound_spec(spec, pins):
    need(isinstance(spec, dict) and set(spec) == {'file', 'sha256'}
         and pins.get(spec['file']) == spec['sha256'],
         'required artifact is absent from the complete input pins.')
    return pinned(spec)


def validate_folds_and_priors(ready, fit, pins, plan_sha):
    fold_spec = ready['fold_manifest']; folds = bound_spec(fold_spec, pins)
    proteins = fit['proteins']; n = len(proteins)
    need(folds.get('format') == 'biograph-steward.crossfit-full-sequence-folds.v1'
         and folds.get('status') == 'passed' and folds.get('plan_sha256') == plan_sha
         and folds.get('fit_proteins') == proteins, 'fold source/identity admission differs.')
    assignment = folds['fold_index_by_row']
    need(len(assignment) == n and all(type(value) is int and 0 <= value < 5 for value in assignment)
         and set(assignment) == set(range(5)) and len(folds['folds']) == 5,
         'exactly five complete fitting-row folds are required.')
    for spec in (folds['sequence_source'], folds['splitter_runtime']['source']):
        need(sha(spec['file']) == spec['sha256'], 'fold sequence or splitter source changed.')
    need(isinstance(folds['splitter_runtime']['sklearn_version'], str)
         and folds['splitter_runtime']['sklearn_version'], 'actual splitter runtime must be recorded.')
    prior_specs = ready['prior_receipts']
    need(set(prior_specs) == {'folds', 'all_fit'} and len(prior_specs['folds']) == 5,
         'five complement priors and one full-fit prior are required.')
    target_source = {'file': fit['targets_file'], 'sha256': pins[fit['targets_file']]}
    complement_counts = []
    for index, (fold, spec) in enumerate(zip(folds['folds'], prior_specs['folds'])):
        heldout = [i for i, value in enumerate(assignment) if value == index]
        complement = [i for i, value in enumerate(assignment) if value != index]
        need(fold['fold_index'] == index and fold['heldout_rows'] == heldout
             and fold['complement_rows'] == complement and fold['group_overlap'] == 0,
             'fold rows are incomplete, reordered or share exact-sequence groups.')
        hp, cp = [proteins[i] for i in heldout], [proteins[i] for i in complement]
        need(fold['heldout_proteins'] == hp and fold['complement_proteins'] == cp,
             'fold literal identities differ from their row assignment.')
        prior = bound_spec(spec, pins)
        need(prior['fold_index'] == index and prior['heldout_proteins'] == hp
             and prior['complement_proteins'] == cp and prior['target_source'] == target_source
             and prior['crossfit_fold_manifest'] == fold_spec
             and prior['computed_before_root_positive_filter'] is True,
             'per-feature prior must exclude its own complete fold before root filtering.')
        _prior_arrays(prior, pins)
        complement_counts.append(len(cp))
    full = bound_spec(prior_specs['all_fit'], pins)
    need(full['fold_index'] is None and full['complement_proteins'] == proteins
         and full['heldout_proteins'] == [] and full['target_source'] == target_source
         and full['crossfit_fold_manifest'] == fold_spec
         and full['computed_before_root_positive_filter'] is True,
         'validation/final features require the complete allowed fitting prior universe.')
    _prior_arrays(full, pins)
    return {'folds': 5, 'fitting_feature_complement_counts': complement_counts,
        'validation_and_final_feature_prior_count': n,
        'native_inner_prior_universe_count_semantics': 'Global allowed fitting frame; fitting feature rows use their own fold complement.',
        'prior_semantics': 'Native feature-completion/prevalence priors, not verified biological or PU class priors.'}


def _prior_arrays(prior, pins):
    need(set(prior['files']) == {'raw', 'conditional', 'nulls'}, 'complete native prior array roles required.')
    for spec in prior['files'].values():
        need(pins.get(spec['file']) == spec['sha256'] and sha(spec['file']) == spec['sha256'],
             'native complement prior array changed or is unpinned.')


def native_input_admission(inner, manifests, contexts, contract):
    """Reuse existing CPU readers before the native trainer can claim the GPU."""
    import numpy as np
    from .context_io import read_boolean_context
    from .training import read_feature_manifest, root_positive_rows
    from tools.learned_combination.native_adapter import native_ontologies

    pins = inner['input_file_pins']; read = {}; arrays = {}; labels = None
    for role in ('fit', 'validation', 'final'):
        meta, values, y = read_feature_manifest(manifests[role]['file'], pins, fitting=role == 'fit')
        context, boolean = read_boolean_context(contexts[role]['file'], pins, meta)
        need(context['channels'] == contract['channels'], 'native context order changed.')
        global_index = context['channels'].index('global.propagated')
        for start in range(0, len(values), 32):
            need(np.array_equal(values[start:start + 32, 8], boolean[start:start + 32, global_index]),
                 'base cache GOA channel differs from the unchanged forty-channel context.')
        read[role] = meta; arrays[role] = values
        if role == 'fit': labels = y
    graph = native_ontologies(inner['model_obo']['file'])[NAMESPACE]
    need(read['fit']['terms'] == [node['id'] for node in graph.terms_list], 'native fixed ontology term order changed.')
    rows, _ = root_positive_rows(graph, labels)
    positive = sum(int(np.count_nonzero(labels[start:start + 32])) for start in range(0, len(labels), 32))
    need(positive == COUNTS['full_positive_cells'] and len(rows) == COUNTS['root_positive_rows'],
         'native full fitting-positive or root-positive scope changed.')
    return {'native_input_checks_performed': True, 'full_positive_cells': positive,
            'root_positive_rows': len(rows), 'role_counts': {role: len(meta['proteins']) for role, meta in read.items()}}


def prepare_inputs(cfg):
    allowed = {'format', 'plan', 'source_readiness', 'native_training_configuration', 'qualified_source_pins'}
    need(isinstance(cfg, dict) and set(cfg) == allowed and cfg.get('format') == CONFIG_FORMAT,
         'only the allowlisted cross-fit wrapper configuration is accepted.')
    plan = pinned(cfg['plan']); validate_plan(plan)
    ready = pinned(cfg['source_readiness']); truthful_flags(ready)
    need(ready.get('format') == READY_FORMAT and ready.get('status') == 'complete'
         and ready.get('plan') == cfg['plan'] and ready.get('parent_axis') == PARENTS
         and ready.get('namespace') == NAMESPACE
         and ready.get('final_reference_labels_read_for_feature_construction') is False
         and ready.get('no_DeepGO_features_or_heads_read') is True,
         'complete qualified named-parent source readiness is required.')
    check_source_pins(cfg['qualified_source_pins'], ready)
    source_cfg = pinned(ready['configuration'])
    need(source_cfg.get('plan') == cfg['plan'] and source_cfg.get('parent_axis') == PARENTS
         and source_cfg.get('contexts') == ready['contexts']
         and source_cfg.get('model_obo') == ready['model_obo']
         and source_cfg.get('channel_contract') == ready['channel_contract']
         and source_cfg.get('original_fit_manifest', {}).get('sha256') == ORIGINAL_FIT_MANIFEST_SHA256,
         'producer configuration does not bind the exact plan/context/original fitting sources.')
    original_fit = pinned(source_cfg['original_fit_manifest'])
    inner = cfg['native_training_configuration']
    fields = {'format', 'namespace', 'seed', 'params', 'channel_contract', 'author_root', 'model_obo',
        'fit_manifest', 'validation_manifest', 'fit_context_manifest', 'validation_context_manifest',
        'input_file_pins', 'evaluation'}
    need(isinstance(inner, dict) and set(inner) == fields, 'native configuration must contain only original supported inputs.')
    need(inner['format'] == 'biograph-steward.coded-context-training.v1'
         and inner['namespace'] == NAMESPACE and inner['seed'] == plan['model']['seed']
         and inner['params'] == plan['model']['params'], 'native training parameters differ from the frozen plan.')
    contract = native.validate_context_contract(inner); validate_validation_sources(inner['evaluation'])
    pins = ready['input_file_pins']
    need(inner['input_file_pins'] == pins and isinstance(pins, dict), 'native and source-admitted input pin sets differ.')
    for filename, digest in pins.items():
        need(sha(filename) == digest, 'source-admitted input changed.')
    need(ready['model_obo'] == inner['model_obo'] and ready['model_obo']['sha256'] == MODEL_OBO_SHA256
         and sha(ready['model_obo']['file']) == MODEL_OBO_SHA256
         and ready['channel_contract'] == inner['channel_contract'], 'fixed ontology or unchanged context contract changed.')
    manifests, contexts = ready['manifests'], ready['contexts']
    need(set(manifests) == set(contexts) == {'fit', 'validation', 'final'}, 'all three exact source roles are required.')
    metas = {role: bound_spec(spec, pins) for role, spec in manifests.items()}
    context_meta = {role: bound_spec(spec, pins) for role, spec in contexts.items()}
    expected = {'fit': COUNTS['fit_universe'], 'validation': COUNTS['validation_proteins'], 'final': COUNTS['final_proteins']}
    term_axis = metas['fit']['terms']
    need(len(term_axis) == len(set(term_axis)) == COUNTS['model_terms'], 'complete unique fixed model term axis required.')
    seen = set()
    for role, meta in metas.items():
        proteins = meta['proteins']
        need(len(proteins) == len(set(proteins)) == expected[role] and not seen.intersection(proteins),
             'complete disjoint fitting/validation/final protein identities required.')
        seen.update(proteins)
        need(meta['terms'] == term_axis and meta.get('parent_axis') == PARENTS
             and meta.get('crossfit_fold_manifest') == ready['fold_manifest'], 'role parent/term/fold identity differs.')
        need(meta['features_shape'] == [len(proteins), 9, len(term_axis)] and meta['features_dtype'] == 'float32',
             'raw native feature cache must retain exactly two parents plus one GOA channel.')
        need(pins.get(meta['feature_file']) == meta['file_pins'][meta['feature_file']], 'feature cache is not source pinned.')
        expected_priors = (ready['prior_receipts']['folds'] if role == 'fit' else [ready['prior_receipts']['all_fit']])
        need(meta['feature_prior_receipts'] == expected_priors, 'role features use a different prior universe.')
        if role != 'fit':
            need(not meta.get('targets_file') and not meta.get('known_positive_mask_file'), 'validation/final features must contain no outcome target array.')
        ctx = context_meta[role]
        need(ctx['proteins'] == proteins and ctx['terms'] == term_axis and ctx['channels'] == contract['channels'],
             'unchanged source-context role order differs.')
    for role, feature_key, context_key in (('fit', 'fit_manifest', 'fit_context_manifest'),
                                           ('validation', 'validation_manifest', 'validation_context_manifest')):
        need(inner[feature_key] == manifests[role]['file'] and inner[context_key] == contexts[role]['file'],
             'native helper paths are not the admitted source-role paths.')
    need(metas['fit']['proteins'] == original_fit['proteins']
         and metas['fit']['terms'] == original_fit['terms'], 'original complete fitting identities changed.')
    for field in ('targets_file', 'known_positive_mask_file'):
        filename = original_fit[field]
        need(metas['fit'][field] == filename
             and pins.get(filename) == original_fit['file_pins'][filename]
             and sha(filename) == original_fit['file_pins'][filename],
             'original full targets or known-positive mask bytes changed.')
    prior_scope = validate_folds_and_priors(ready, metas['fit'], pins, cfg['plan']['sha256'])
    admission = bound_spec(ready['source_admission'], pins)
    need(admission.get('status') == 'passed' and admission.get('qualified') is True
         and admission.get('plan_sha256') == cfg['plan']['sha256']
         and admission.get('producer_source') == ready['producer_source']
         and admission.get('counts') == COUNTS and admission.get('parent_axis') == PARENTS,
         'actual source producer did not admit this complete fitting/fold scope.')
    need(admission.get('original_targets_and_known_mask_bytes_retained') is True
         and admission.get('new_annotation_source_or_target_cells') is False
         and admission.get('original_fit_manifest') == source_cfg['original_fit_manifest']
         and admission.get('original_targets') == {'file': original_fit['targets_file'],
             'sha256': original_fit['file_pins'][original_fit['targets_file']]}
         and admission.get('original_known_positive_mask') == {'file': original_fit['known_positive_mask_file'],
             'sha256': original_fit['file_pins'][original_fit['known_positive_mask_file']]}
         and admission.get('native_full_fit_priors_match_original_vectors_exactly') is True,
         'cross-fitting cannot introduce refreshed labels or alter original full positives.')
    actual = native_input_admission(inner, manifests, contexts, contract)
    proof = {**actual, **prior_scope, 'parent_axis': PARENTS,
        'source_admission': ready['source_admission'], 'fold_manifest': ready['fold_manifest'],
        'no_DeepGO_features_or_heads_read': True, 'final_reference_labels_read_for_fitting': False,
        'final_reference_labels_read_for_forecasting': False,
        'exact_sequence_grouping_is_not_distant_family_separation': True, **FLAGS}
    return {'plan': plan, 'ready': ready, 'inner': copy.deepcopy(inner), 'proof': proof,
            'metas': metas, 'contract': contract}


def train_prepared(cfg, output):
    data = prepare_inputs(cfg); output = Path(output); output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'configuration.json', cfg); write_json(output / 'source_admission.json', data['proof'])
    result = native.train_context_model(data['inner'], output / 'native_training')
    spec = {'file': result['model_file'], 'sha256': result['model_metadata_sha256']}
    model = pinned(spec)
    need(result['status'] == 'complete', 'native training did not complete.')
    validate_native_model(model, data)
    need(pinned({'file': str(output / 'native_training/configuration.json'),
                 'sha256': model['configuration_sha256']}) == data['inner'], 'native helper configuration changed.')
    metadata = {'format': 'biograph-steward.crossfit-context-model.v1', 'status': 'complete',
        'arm': ARM, 'namespace': NAMESPACE, 'parent_axis': PARENTS, 'created_at': now(),
        'native_model_metadata': spec, 'checkpoint_file': model['checkpoint_file'],
        'checkpoint_sha256': model['checkpoint_sha256'], 'n_layers': 8, 'in_goa': 40, 'in_models': 2,
        'model_terms_sha256': model['model_terms_sha256'], 'context_channels': model['context_channels'],
        'postprocessing': model['postprocessing'], 'source_readiness': cfg['source_readiness'],
        'plan_sha256': cfg['plan']['sha256'], 'qualified_source_pins': cfg['qualified_source_pins'],
        'producer_source': cfg['qualified_source_pins']['crossfit_training'], 'producer_code_sha256': sha(__file__),
        'configuration_sha256': sha(output / 'configuration.json'), 'source_admission': data['proof'],
        'consumed_validation_used_for_SWA': True, 'validation_metric_role': VALIDATION_ROLE,
        'validation_ordinary_micro_fmax': model['validation_ordinary_micro_fmax'],
        'native_inner_fresh_flag_scope': 'This phase does not open the final reference; earlier project comparisons already consumed it.',
        'final_reference_labels_read_for_fitting': False, 'final_reference_metrics_computed': False,
        'automatic_graph_or_app_promotion': False, **FLAGS}
    write_json(output / 'model.json', metadata)
    return metadata


def validate_native_model(model, data):
    ready = data['ready']
    need(model['n_layers'] == 8 and model['in_goa'] == 40
         and model['in_models'] == 2 and len(model['epoch_scores']) == 20
         and model['supervised_fitting_rows'] == COUNTS['root_positive_rows']
         and model['prior_universe_count'] == COUNTS['fit_universe']
         and 0 <= model['swa_parameter_parity_max_abs'] <= 1e-6
         and model['fresh_final_reference_opened'] is False,
         'unchanged native trainer did not complete the fixed architecture/scope/SWA.')
    for field, spec in (('fit_manifest_sha256', ready['manifests']['fit']),
                        ('validation_manifest_sha256', ready['manifests']['validation']),
                        ('fit_context_manifest_sha256', ready['contexts']['fit']),
                        ('validation_context_manifest_sha256', ready['contexts']['validation'])):
        need(model[field] == spec['sha256'], 'native model role/source binding differs.')
    need(model['model_terms_sha256'] == axis_sha(data['metas']['fit']['terms'])
         and model['context_channels'] == data['contract']['channels']
         and model['context_channels_sha256'] == axis_sha(data['contract']['channels'])
         and model['postprocessing'] == PARAMETERS['postprocessing']
         and len(model['selected_swa_sources']) == 3
         and all(sha(filename) == digest for filename, digest in model['selected_swa_sources'].items())
         and sha(model['checkpoint_file']) == model['checkpoint_sha256'],
         'native selected states, fixed term axis, postprocessing or weights changed.')


def forecast_prepared(cfg, model_spec, output):
    data = prepare_inputs(cfg); model = pinned(model_spec); truthful_flags(model)
    need(model.get('format') == 'biograph-steward.crossfit-context-model.v1' and model.get('status') == 'complete'
         and model.get('arm') == ARM and model.get('parent_axis') == PARENTS
         and model.get('plan_sha256') == cfg['plan']['sha256']
         and model.get('source_readiness') == cfg['source_readiness']
         and model.get('qualified_source_pins') == cfg['qualified_source_pins']
         and model.get('consumed_validation_used_for_SWA') is True
         and model.get('validation_metric_role') == VALIDATION_ROLE
         and model.get('final_reference_metrics_computed') is False, 'completed cross-fit model source/phase provenance differs.')
    source_cfg = {'file': str(Path(model_spec['file']).parent / 'configuration.json'),
                  'sha256': model['configuration_sha256']}
    need(pinned(source_cfg) == cfg, 'forecast configuration differs from the completed training source.')
    native_model = pinned(model['native_model_metadata'])
    validate_native_model(native_model, data)
    need(native_model['checkpoint_file'] == model['checkpoint_file']
         and native_model['checkpoint_sha256'] == model['checkpoint_sha256']
         and sha(model['checkpoint_file']) == model['checkpoint_sha256'], 'native selected weights changed.')
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    result = native.export_context_predictions(data['inner'], model_metadata=model['native_model_metadata']['file'],
        feature_manifest=data['ready']['manifests']['final']['file'],
        context_manifest=data['ready']['contexts']['final']['file'], output=output / 'native_forecast')
    native_receipt = {'file': str(output / 'native_forecast/predictions.json'),
                      'sha256': sha(output / 'native_forecast/predictions.json')}
    need(result['model_metadata_sha256'] == model['native_model_metadata']['sha256']
         and result['feature_manifest_sha256'] == data['ready']['manifests']['final']['sha256']
         and result['context_manifest_sha256'] == data['ready']['contexts']['final']['sha256']
         and sha(result['prediction_file']) == result['prediction_sha256']
         and sha(result['raw_prediction_file']) == result['raw_prediction_sha256'],
         'native forecast/source/checkpoint output binding differs.')
    # Keep all hash-bound native files unchanged. Honest study-level provenance
    # belongs to this separate outer metadata file.
    result = {key: value for key, value in result.items() if key != 'fresh_final_reference_opened'}
    result.update(format='biograph-steward.crossfit-context-forecast.v1', status='complete', arm=ARM,
        parent_axis=PARENTS, namespace=NAMESPACE, plan_sha256=cfg['plan']['sha256'],
        in_models=2, in_goa=40, n_layers=8, embed_size=8,
        model_terms_sha256=axis_sha(result['terms']),
        model_metadata=model_spec, model_metadata_sha256=model_spec['sha256'],
        native_forecast_metadata=native_receipt,
        native_model_metadata=model['native_model_metadata'],
        source_configuration=source_cfg, source_readiness=cfg['source_readiness'],
        producer_source=cfg['qualified_source_pins']['crossfit_training'], producer_code_sha256=sha(__file__),
        no_DeepGO_features_or_heads_read=True, models_fitted=True, upper_roundoff_tolerance=0.,
        final_reference_labels_read_for_forecasting=False, final_reference_metrics_computed=False,
        forecast_phase_scientific_metrics_computed=False,
        consumed_validation_used_for_SWA=True, validation_metric_role=VALIDATION_ROLE,
        native_inner_fresh_flag_scope=model['native_inner_fresh_flag_scope'],
        source_admission=data['proof'], automatic_graph_or_app_promotion=False, **FLAGS)
    need(len(result['proteins']) == COUNTS['final_proteins'] and len(result['terms']) == COUNTS['model_terms'],
         'complete unchanged final forecasting frame required.')
    write_json(output / 'predictions.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('check', 'train', 'forecast'))
    parser.add_argument('--config', required=True); parser.add_argument('--output'); parser.add_argument('--model')
    args = parser.parse_args(); cfg = json.loads(Path(args.config).read_text())
    if args.phase == 'check': result = prepare_inputs(cfg)['proof']
    else:
        need(args.output is not None, 'new separate output directory required.')
        if args.phase == 'train': result = train_prepared(cfg, args.output)
        else:
            need(args.model is not None, 'completed outer model metadata required.')
            result = forecast_prepared(cfg, {'file': args.model, 'sha256': sha(args.model)}, args.output)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__': main()
