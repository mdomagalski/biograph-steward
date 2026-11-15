# SPDX-License-Identifier: GPL-3.0-only
"""BP-only source preparation for the fixed, consumed-reference final refit.

Existing target, prior, source-grouping and StackDataset helpers own all math.
This adapter binds exact inputs/axes and writes truthful development metadata.
It never accepts a validation loader, reference outcome or model-fit request.
"""
import argparse
import gzip
import json
from pathlib import Path
import traceback

from tools.learned_combination.core import need
from tools.learned_combination.reference import file_sha256, read_target_ids
from tools.learned_combination.runner import now, subset_reference
from . import prepare as prep
from . import rich_goa as rich
from .native_stacker import load_author, make_dataset


PLAN_SHA = '8128b0c3cbda794cb8cd75b711609cfed1f1a150ef81ba3e90339cd4815ecca9'
NS = 'biological_process'
FIT_COUNT = 4040
FLAGS = {'development_after_reference_opening': True, 'reference_previously_consumed': True,
         'independent_confirmation': False, 'fresh_final_reference_claimed': False,
         'final_reference_labels_read_for_feature_construction': False}


def pinned(spec):
    need(file_sha256(spec['file']) == spec['sha256'], 'source metadata changed: ' + spec['file'])
    return json.loads(Path(spec['file']).read_text())


def verify_config(cfg):
    need(cfg.get('format') == 'biograph-steward.current-refit-preparation.v1'
         and cfg.get('parent_authorized_source_preparation') is True,
         'explicit authorization of the fixed source preparation is required.')
    need(all(cfg.get(k) is v for k, v in FLAGS.items()), 'truthful consumed-reference preparation flags required.')
    need(cfg['plan']['sha256'] == PLAN_SHA, 'only the committed source-refit plan is accepted.')
    plan = pinned(cfg['plan'])
    need(plan['reference_already_consumed'] is True and plan['independent_confirmation'] is False,
         'this is development on a previously consumed reference.')
    for path, expected in cfg['input_file_pins'].items():
        prep._check_path(path)
        need('groundtruth' not in path or Path(path).suffix == '.py', 'reference data cannot enter source preparation.')
        need(file_sha256(path) == expected, 'pinned preparation input changed: ' + path)
    required = [cfg[key] for key in ('plan', 'original_configuration', 'original_fit_manifest',
        'original_final_feature_manifest', 'model_obo', 'channel_contract', 'direct_terms', 'gaf', 'final_context_manifest')]
    required.extend(spec for role in cfg['raw_parents'].values() for spec in role.values())
    for spec in required:
        need(cfg['input_file_pins'].get(spec['file']) == spec['sha256'], 'a required source spec is not pinned.')
    need(cfg['original_configuration']['sha256'] == '152a60cc7f18aa68b159cd60572b6cf5d2645d1de19488bd28fb3db6b7db0242'
         and cfg['original_fit_manifest']['sha256'] == 'b6c84aae2d8e21c8f99a101b54ecbc92eb5d2eb9b100ad9f26c561b3271e3fb2'
         and cfg['original_final_feature_manifest']['sha256'] == '72c053e58cf6ceb522918d5277db4a1b0c70ae58125f6e420a281d3a1ec20174'
         and cfg['model_obo']['sha256'] == '0c0062efbb1b199a6a54e62c0c48ff0038d39173aecc7edfab66a20090d5ec2d'
         and cfg['direct_terms']['sha256'] == 'a59448ee76404df1b61b753dbc1c609a426e395d6f81804d03235e99dc6c2e7d'
         and cfg['gaf']['sha256'] == '8db7f75ba9bb33f3778e1641bf4fde107f877e6a6af273b77eaf1ce60ad9e11f',
         'only the exact source-admitted historical and current T0 inputs are accepted.')
    return plan


def retained_union_counts(old, new, retention, graph):
    import numpy as np
    need(old.shape == new.shape == retention.shape and old.ndim == 2,
         'positive-retention target axes differ.')
    need(np.isin(old, [0., 1.]).all() and np.isin(new, [0., 1.]).all()
         and retention.dtype == np.bool_ and np.array_equal(retention, old > 0),
         'retention mask must equal the complete original full positive repertoire.')
    need(np.all(new[retention] == 1), 'an original full positive was lost.')
    roots = [i for i, node in enumerate(graph.terms_list) if not node['adj']]
    need(len(roots) == 1, 'one literal old-ontology root required.')
    add = (new > 0) & ~retention
    return {'fit_universe': len(old), 'original_full_positive_cells': int(retention.sum()),
            'augmented_positive_cells': int((new > 0).sum()), 'added_positive_cells': int(add.sum()),
            'fitting_proteins_with_additions': int(add.any(axis=1).sum()),
            'original_root_positive_rows': int(retention[:, roots[0]].sum()),
            'augmented_root_positive_rows': int((new[:, roots[0]] > 0).sum()),
            'original_full_positive_cells_lost': 0, 'retention_mask_equals_original_FULL': True}


def prepare_targets(cfg, ont, original, output, plan):
    import numpy as np
    old_meta = pinned(cfg['original_fit_manifest'])
    proteins, terms = old_meta['proteins'], old_meta['terms']
    need(len(proteins) == len(set(proteins)) == FIT_COUNT
         and terms == [node['id'] for node in ont[NS].terms_list], 'original fitting axes differ.')
    for path in (old_meta['targets_file'], old_meta['known_positive_mask_file']):
        need(file_sha256(path) == old_meta['file_pins'][path] == cfg['input_file_pins'][path], 'original fitting label source changed.')
    old = np.load(old_meta['targets_file'], mmap_mode='r', allow_pickle=False)
    old_known = np.load(old_meta['known_positive_mask_file'], mmap_mode='r', allow_pickle=False)
    need(np.all(old[old_known] == 1), 'original known-positive guard differs.')
    output.mkdir(parents=True, exist_ok=False)
    direct = output / 'direct_T0_fitting_only.tsv'
    need(file_sha256(cfg['direct_terms']['file']) == cfg['direct_terms']['sha256'], 'direct T0 source changed.')
    direct_audit = subset_reference([cfg['direct_terms']['file']], proteins, direct)
    with gzip.open(original['strict_training'], 'rt') as stream:
        strict = json.load(stream)
    native_dir = output / 'native_union'; native_dir.mkdir()
    arrays, _, sources = prep.full_targets(proteins, ont, strict,
        [*original['allowed_development_annotations'], str(direct)], native_dir)
    values = arrays[NS]
    retention = np.asarray(old > 0, dtype=bool)
    counts = retained_union_counts(old, values, retention, ont[NS])
    expected = plan['source_adaptation']
    need(counts['original_full_positive_cells'] == expected['expected_original_full_BP_positive_cells']
         and counts['augmented_positive_cells'] == expected['expected_augmented_BP_positive_cells']
         and counts['added_positive_cells'] == expected['expected_added_BP_positive_cells']
         and counts['fitting_proteins_with_additions'] == expected['expected_fitting_proteins_with_additions']
         and counts['original_root_positive_rows'] == expected['expected_original_root_positive_rows']
         and counts['augmented_root_positive_rows'] == expected['expected_augmented_root_positive_rows'],
         'actual source union differs from the fixed source-admitted counts.')
    target, mask = output / 'targets.npy', output / 'known_positive_mask.npy'
    np.save(target, values, allow_pickle=False); np.save(mask, retention, allow_pickle=False)
    meta = {'namespace': NS, 'proteins': proteins, 'terms': terms, 'targets_file': str(target),
        'known_positive_mask_file': str(mask), 'file_pins': {str(target): file_sha256(target), str(mask): file_sha256(mask)},
        'target_semantics': 'known_T0_union_allowed_development_additions_upward_closed',
        'retention_mask_semantics': 'original_full_fitting_positive_repertoire',
        'original_full_positive_retention': True, 'original_fit_manifest': cfg['original_fit_manifest'],
        'direct_curated_source': cfg['direct_terms'], 'model_obo': cfg['model_obo'], **FLAGS}
    prep.write_json(output / 'manifest.json', meta)
    admission = {'format': 'biograph-steward.current-refit-target-admission.v1', 'created_at': now(),
        'status': 'passed', 'qualified': True, 'plan_sha256': cfg['plan']['sha256'],
        'target_manifest_sha256': file_sha256(output / 'manifest.json'),
        'source_preparation_code': {'file': __file__, 'sha256': file_sha256(__file__)},
        'source_preparation_configuration': {'file': str(output.parent / 'configuration.json'),
            'sha256': file_sha256(output.parent / 'configuration.json')},
        'counts': counts, 'all4040_before_aspect_filter': True, 'original_FULL_retention': True,
        'original_known_positives_retained': True, 'retention_mask_equals_original_FULL': True,
        'native_old_alias_MAX_closure_unchanged': True, 'current_propagated_seed_table_used_as_targets': False,
        'direct_fitting_subset': direct_audit, 'native_union_source_files': sources,
        'original_fit_manifest': cfg['original_fit_manifest'], 'direct_source': cfg['direct_terms'],
        'target_manifest': {'file': str(output / 'manifest.json'), 'sha256': file_sha256(output / 'manifest.json')},
        'absence_in_current_source_means_historical_negative': False, **FLAGS}
    prep.write_json(output / 'admission.json', admission)
    return meta, values, {'file': str(output / 'admission.json'), 'sha256': file_sha256(output / 'admission.json')}


def fit_context(cfg, ont, target_meta, targets, output):
    import numpy as np
    output.mkdir(parents=True, exist_ok=False)
    groups, native_count, source = rich.load_author(cfg['rich_author_root'], output / 'native_source')
    frame, source_audit = rich.read_t0_gaf(cfg['gaf']['file'], target_meta['proteins'], expected_date='2026-04-10')
    normalized, normalization = rich.normalize(frame, ont)
    channel_groups, admission = rich.native_groups(groups, normalized, target_meta['proteins'], target_meta['terms'])
    # Native is_pos already records NOT before coarsening. This flags exact
    # canonical pair overlap only; it changes no target or negative semantics.
    classified = groups['process_uniprot'](normalized.copy())
    not_rows = classified.loc[(~classified.is_pos) & classified.valid_terms, ['EntryID', 'term']].drop_duplicates()
    pidx = {p: i for i, p in enumerate(target_meta['proteins'])}; tidx = {t: i for i, t in enumerate(target_meta['terms'])}
    overlaps = sum(bool(targets[pidx[p], tidx[t]]) for p, t in not_rows.itertuples(index=False, name=None))
    context_file = output / 'context.npy'
    terms = rich.build_context(target_meta['proteins'], ont[NS], channel_groups, native_count, context_file)
    need(list(terms) == target_meta['terms'], 'context/model term axes differ.')
    meta = {'format': 'biograph-steward.contextual-boolean-features.v1', 'namespace': NS,
        'proteins': target_meta['proteins'], 'terms': list(terms), 'channels': list(rich.CHANNELS),
        'context_file': str(context_file), 'context_sha256': file_sha256(context_file),
        'context_shape': [len(target_meta['proteins']), 40, len(terms)], 'context_dtype': 'bool',
        'source_input': cfg['gaf'], 'source_audit': source_audit, 'normalization_audit': normalization,
        'admission_audit': admission, 'native_author_source': source,
        'exact_canonical_NOT_overlap': {'unique_NOT_pairs': len(not_rows), 'accepted_positive_pairs_also_explicit_NOT': overlaps,
            'biological_contradiction_established': False, 'labels_removed_or_flipped': 0,
            'context_or_assay_qualifications_inferred': False}, **FLAGS}
    prep.write_json(output / 'context.json', meta)
    return meta


def read_parent(spec, proteins, terms, pins):
    import numpy as np
    entry = pinned(spec)[NS]
    need(entry['terms'] == terms and set(proteins) <= set(entry['proteins']), 'raw parent source axes differ.')
    path = entry['file']
    need(pins[path] == entry['sha256'] == file_sha256(path), 'raw parent values changed.')
    values = np.load(path, mmap_mode='r', allow_pickle=False)
    need(values.shape == (len(entry['proteins']), len(terms)) and values.dtype == np.float64,
         'qualified lossless parent cache shape/dtype differs.')
    lookup = {p: i for i, p in enumerate(entry['proteins'])}
    return values, np.asarray([lookup[p] for p in proteins], dtype=np.int64)


def write_role_features(author, graph, proteins, terms, parents, head_indices, priors, context, path, *, workers):
    import numpy as np
    raw, conditional = priors
    need(context.dtype == np.bool_ and context.shape == (len(proteins), 40, len(terms)), 'Boolean context shape differs.')
    need(rich.CHANNELS[1] == 'global.propagated', 'qualified global-propagated channel order changed.')
    predictions = []
    for method in ('localplus', 'deepgose'):
        values, rows = parents[method]; columns = np.asarray(head_indices[method], dtype=np.int64)
        predictions.append((values[np.ix_(rows, columns)], columns))
    goa = [np.flatnonzero(context[i, 1]) for i in range(len(proteins))]
    dataset = make_dataset(author, proteins=proteins, terms=terms, graph=graph,
        predictions=predictions, prior_raw=raw, prior_cond=conditional, goa_indices=goa)
    prep.write_feature_memmap(dataset, path, workers=workers)
    values = np.load(path, mmap_mode='r', allow_pickle=False)
    for start in range(0, len(proteins), 32):
        need(np.array_equal(values[start:start + 32, 8], context[start:start + 32, 1]),
             'default nonexperimental feature differs from the native forty-channel global propagation.')


def run(cfg, output):
    import numpy as np
    from tools.learned_combination.native_adapter import native_ontologies
    plan = verify_config(cfg)
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    prep.write_json(output / 'configuration.json', cfg)
    try:
        original = pinned(cfg['original_configuration'])
        need(original['ontology'] == cfg['model_obo']['file'], 'model ontology differs from original preparation.')
        for path in (original['strict_training'], *original['allowed_development_annotations'], *original['deepgo_heads'].values()):
            need(cfg['input_file_pins'].get(path) == original['input_pins'][path],
                 'an original label/head source is not bound to its original configuration.')
        ont = native_ontologies(cfg['model_obo']['file']); graph = ont[NS]
        target_meta, targets, admission = prepare_targets(cfg, ont, original, output / 'targets', plan)
        target_spec = {'file': str(output / 'targets/manifest.json'), 'sha256': file_sha256(output / 'targets/manifest.json')}
        prep.write_json(output / 'target_ready.json', {'target_manifest': target_spec, 'source_admission': admission, **FLAGS})
        print(now(), 'CURRENT_REFIT_TARGETS_READY', json.dumps(target_spec), flush=True)
        prior_dir = output / 'priors'; prior_dir.mkdir()
        raw, conditional, nulls = prep.priors_from_full_fit(targets, graph)
        for name, values in (('raw', raw), ('conditional', conditional), ('nulls', nulls)):
            np.save(prior_dir / (name + '.npy'), values, allow_pickle=False)
        prior = {'fit_universe': target_meta['proteins'], 'fit_universe_count': 4040,
            'computed_before_root_positive_filter': True, 'target_manifest': target_spec,
            'target_source': {'file': target_meta['targets_file'], 'sha256': target_meta['file_pins'][target_meta['targets_file']]},
            'formula': 'native create_helpers NaN-parent block; Pandas mean/isnull mean; raw=conditional*(1-null)',
            'files': {p.name: file_sha256(p) for p in prior_dir.iterdir()}, **FLAGS}
        prep.write_json(prior_dir / 'receipt.json', prior)
        prior_spec = {'file': str(prior_dir / 'receipt.json'), 'sha256': file_sha256(prior_dir / 'receipt.json')}
        contract = pinned(cfg['channel_contract']); need(contract['channels'] == list(rich.CHANNELS), 'forty-channel contract differs.')
        new_context = fit_context(cfg, ont, target_meta, targets, output / 'fit_context')
        old_final = pinned(cfg['original_final_feature_manifest']); final_context = pinned(cfg['final_context_manifest'])
        need(cfg['final_context_manifest']['sha256'] == 'f8d10a3d57e40b670d961a8bbc16becb7d674aa8448484ccd4d247c7d09b9f4e', 'reuse the exact presealed final context.')
        need(len(old_final['proteins']) == 3300 and old_final['proteins'] == final_context['proteins']
             and old_final['terms'] == final_context['terms'] == target_meta['terms']
             and final_context['channels'] == list(rich.CHANNELS), 'final source/context axes differ.')
        need(file_sha256(final_context['context_file']) == final_context['context_sha256'], 'original final context changed.')
        need(cfg['input_file_pins'].get(final_context['context_file']) == final_context['context_sha256'],
             'the reused final context array requires its original explicit pin.')
        contexts = {'fit': np.load(new_context['context_file'], mmap_mode='r', allow_pickle=False),
                    'final': np.load(final_context['context_file'], mmap_mode='r', allow_pickle=False)}
        with gzip.open(original['strict_training'], 'rt') as stream: original_training = json.load(stream)
        heads, head_audit = prep.projected_heads(original, ont, original_training)
        head_indices = {method: heads[method][NS] for method in ('localplus', 'deepgose')}
        prep.write_json(output / 'parent_head_indices.json', {'indices': head_indices, 'original_source_audit': head_audit,
            'actual_producer_vocabulary_unchanged': True, 'inferred_from_nonzero_predictions': False})
        author = load_author(cfg['stack_author_root'], jit_backend='numba')
        manifests = {'targets': target_spec, 'fit_context': {'file': str(output / 'fit_context/context.json'),
                     'sha256': file_sha256(output / 'fit_context/context.json')}, 'final_context': cfg['final_context_manifest']}
        for role, source in (('fit', target_meta), ('final', old_final)):
            proteins, terms = source['proteins'], source['terms']
            parents = {method: read_parent(cfg['raw_parents'][role][method], proteins, terms, cfg['input_file_pins'])
                       for method in ('localplus', 'deepgose')}
            folder = output / role; folder.mkdir(); path = folder / 'features.npy'
            print(now(), 'CURRENT_REFIT_NATIVE_PARENT_FEATURES', role, len(proteins), flush=True)
            write_role_features(author, graph, proteins, terms, parents, head_indices, (raw, conditional), contexts[role],
                                path, workers=cfg.get('workers', 4))
            meta = {'namespace': NS, 'proteins': proteins, 'terms': terms, 'feature_file': str(path),
                'features_shape': [len(proteins), 9, len(terms)], 'features_dtype': 'float32',
                'features_semantics': 'unchanged native StackDataset eight parent channels with updated common fit priors; global-propagated nonexperimental default channel',
                'prior_receipt_file': prior_spec['file'], 'prior_receipt_sha256': prior_spec['sha256'],
                'file_pins': {str(path): file_sha256(path)}, **FLAGS}
            if role == 'fit':
                meta.update({k: target_meta[k] for k in ('targets_file', 'known_positive_mask_file', 'target_semantics',
                    'retention_mask_semantics', 'original_full_positive_retention')})
                meta['file_pins'].update(target_meta['file_pins'])
            prep.write_json(folder / 'manifest.json', meta)
            manifests[role] = {'file': str(folder / 'manifest.json'), 'sha256': file_sha256(folder / 'manifest.json')}
        pins = dict(cfg['input_file_pins'])
        for path in output.rglob('*'):
            if path.is_file(): pins[str(path)] = file_sha256(path)
        head_spec = {'file': str(output / 'parent_head_indices.json'), 'sha256': file_sha256(output / 'parent_head_indices.json')}
        result = {'format': 'biograph-steward.current-refit-source-preparation.v1', 'created_at': now(),
            'plan': cfg['plan'], 'manifests': manifests, 'source_admission': admission, 'prior_receipt': prior_spec,
            'model_obo': cfg['model_obo'], 'parent_head_indices': head_spec, 'input_file_pins': pins,
            'only_BP_caches_written': True, 'all4040_prior_universe_before_root_filter': True,
            'final_context_reused_without_changes': True, 'no_new_parent_predictions_or_sequence_inference': True, **FLAGS}
        prep.write_json(output / 'ready.json', result)
        return result
    except Exception as error:
        prep.write_json(output / 'failure.json', {'created_at': now(), 'exception': repr(error),
            'traceback': traceback.format_exc(), 'partial_artifacts_preserved': True, 'no_model_fit_or_evaluation': True})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); run(json.loads(Path(args.config).read_text()), args.output)
