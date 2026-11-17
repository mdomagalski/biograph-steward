# SPDX-License-Identifier: GPL-3.0-only
"""Cross-fitted historical LocalPlus and observed-annotation-frequency inputs.

This source-only adapter reuses the pinned author's LocalPlus kernel, native
conditional/marginal-prior producer and StackDataset cache writer. It neither
fits a model nor accepts validation/final scientific labels. Literal source
heads are scored BEFORE native alias MAX projection. The second parent emits
the complement's observed annotation frequency on every fixed model head; it
is not a biological-negative estimate or a positive-unlabeled correction.

``parents`` and ``features`` stages permit the existing LocalPlus and Torch
environments to retain their different qualified NumPy versions. No dependency
guard is weakened. A failed stage leaves its files and failure receipt intact;
use a new output directory for another attempt.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import traceback

from tools.learned_combination.core import need
from tools.learned_combination.reference import file_sha256
from . import prepare as prep
from .freshness_controls import by_head
from .native_stacker import load_author, make_dataset
from .rich_goa import CHANNELS, native_term_map


FORMAT = 'biograph-steward.crossfit-graph-prevalence-preparation.v1'
READY_FORMAT = 'biograph-steward.crossfit-graph-prevalence-features.v1'
NS = 'biological_process'
PARENTS = ['localplus', 'fit_label_frequency']
COUNTS = {'fit_universe': 4040, 'full_positive_cells': 208835,
          'root_positive_rows': 3557, 'validation_proteins': 797,
          'final_proteins': 3300, 'model_terms': 27942}
MODEL_OBO_SHA = '0c0062efbb1b199a6a54e62c0c48ff0038d39173aecc7edfab66a20090d5ec2d'
CONTRACT_SHA = 'c71fb4e43664a64fbb32e1cb15a453bbee9ee4efd66931eb2d0d7c96c16a8c8e'
FIT_MANIFEST_SHA = 'b6c84aae2d8e21c8f99a101b54ecbc92eb5d2eb9b100ad9f26c561b3271e3fb2'
CONTEXT_SHAS = {
    'fit': '4a26acf412c217922820ea15127e966c3af1b269f2ccdd397d093d8ee2ef02d9',
    'validation': '1f1ee66bfc398c28eec8a1b46a54efa1d2937a83a35b65344a09affea5c7849c',
    'final': 'f8d10a3d57e40b670d961a8bbc16becb7d674aa8448484ccd4d247c7d09b9f4e'}
FLAGS = {'development_after_reference_opening': True,
         'reference_previously_consumed': True, 'independent_confirmation': False,
         'fresh_final_reference_claimed': False,
         'final_reference_labels_read_for_feature_construction': False,
         'no_DeepGO_features_or_heads_read': True}
DIRECT_SPECS = ('plan', 'model_obo', 'channel_contract', 'original_fit_manifest',
                'sequence_records', 'graph', 'original_training', 'localplus_author_receipt')


def axis_sha(values):
    return hashlib.sha256(json.dumps(list(values), separators=(',', ':')).encode()).hexdigest()


def spec(path):
    return {'file': str(path), 'sha256': file_sha256(path)}


def pinned(source, pins=None):
    path = source['file']
    if pins is not None:
        need(pins.get(path) == source['sha256'], 'required input spec is not explicitly pinned: ' + path)
    need(file_sha256(path) == source['sha256'], 'source content changed: ' + path)
    return json.loads(Path(path).read_text())


def validate_schema(cfg):
    """Reject unauthorized or extra data roles before opening any source file."""
    required = set(DIRECT_SPECS) | {'format', 'parent_authorized_source_preparation',
        'parent_axis', 'contexts', 'raw_localplus', 'localplus_author_root',
        'stack_author_root', 'splitter_runtime', 'original_full_priors', 'input_file_pins', 'workers', *FLAGS}
    need(set(cfg) == required and cfg.get('format') == FORMAT
         and cfg.get('parent_authorized_source_preparation') is True,
         'explicit source-only authorization and exact configuration schema required.')
    need(all(cfg.get(k) is v for k, v in FLAGS.items()), 'truthful development/source-only flags required.')
    need(cfg['parent_axis'] == PARENTS and set(cfg['contexts']) == {'fit', 'validation', 'final'}
         and set(cfg['raw_localplus']) == {'validation', 'final'}, 'only the two declared parent/data roles are permitted.')
    need(type(cfg['workers']) is int and 1 <= cfg['workers'] <= 4, 'one-to-four CPU workers required.')
    sources = [cfg[key] for key in DIRECT_SPECS]
    need(set(cfg['original_full_priors']) == {'raw', 'conditional', 'nulls'}, 'all original native full-fit prior vectors required.')
    sources += list(cfg['contexts'].values()) + list(cfg['raw_localplus'].values()) + list(cfg['original_full_priors'].values())
    runtime = cfg['splitter_runtime']
    need(set(runtime) == {'sklearn_version', 'source'} and isinstance(runtime['sklearn_version'], str)
         and runtime['sklearn_version'], 'pin the actual installed GroupKFold version and source before generation.')
    sources.append(runtime['source'])
    need(all(set(s) == {'file', 'sha256'} and isinstance(s['file'], str)
             and re.fullmatch('[a-f0-9]{64}', s['sha256']) for s in sources), 'complete source file/SHA256 specs required.')
    for path, digest in cfg['input_file_pins'].items():
        prep._check_path(path)
        need(re.fullmatch('[a-f0-9]{64}', digest) is not None, 'invalid input SHA256.')
        need(not re.search(r'groundtruth|sealed_reference|(?:^|/)truth(?:[./_]|$)', path, re.I),
             'reference label files cannot enter this producer.')
        # The existing official sklearn installation happens to live inside
        # the historical DeepGO runtime directory. Only its explicitly bound
        # splitter source is allowed; sequence_folds also checks the running
        # class's actual source path/version/hash before any fold generation.
        declared_splitter = path == runtime['source']['file'] and Path(path).name == '_split.py'
        need('deepgo' not in path.lower() or declared_splitter,
             'DeepGO/reference label files cannot enter this producer.')
    need(all(cfg['input_file_pins'].get(s['file']) == s['sha256'] for s in sources),
         'every direct source spec must be pinned.')
    return cfg


def verify_config(cfg):
    validate_schema(cfg)
    for path, digest in cfg['input_file_pins'].items():
        need(file_sha256(path) == digest, 'pinned preparation input changed: ' + path)
    plan = pinned(cfg['plan'])
    need(plan['format'] == 'biograph-steward.crossfit-graph-frequency-development-plan.v1'
         and plan['arm'] == 'crossfit_graph_frequency_context'
         and plan['parent_axis'] == PARENTS and plan['namespace'] == NS
         and plan['reference_previously_consumed'] is True and plan['independent_confirmation'] is False,
         'wrong frozen development plan, reference role or ordered parent axis.')
    need(all(plan['folds'][k] == v for k, v in {
        'method': 'sklearn.model_selection.GroupKFold', 'n_splits': 5,
        'group_key': 'exact_full_sequence_SHA256', 'shuffle': False,
        'priors': 'native_complement_before_root_filter'}.items()), 'unqualified fold/prior method.')
    need(cfg['model_obo']['sha256'] == MODEL_OBO_SHA
         and cfg['channel_contract']['sha256'] == CONTRACT_SHA
         and cfg['original_fit_manifest']['sha256'] == FIT_MANIFEST_SHA
         and {r: s['sha256'] for r, s in cfg['contexts'].items()} == CONTEXT_SHAS,
         'only the original historical ontology, targets and dated forty-channel contexts are admitted.')
    contract = pinned(cfg['channel_contract'])
    need(contract['channels'] == list(CHANNELS), 'original forty-channel contract changed.')
    return plan


def stage_runtime():
    import platform
    import numpy as np
    import pandas as pd
    return {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__}


def sequence_folds(proteins, records, runtime):
    """Invoke the installed, pinned sklearn splitter, never a local imitation."""
    import inspect
    import numpy as np
    import sklearn
    from sklearn.model_selection import GroupKFold
    need(sklearn.__version__ == runtime['sklearn_version'], 'GroupKFold runtime version changed.')
    source = inspect.getsourcefile(GroupKFold)
    need(Path(source).resolve() == Path(runtime['source']['file']).resolve()
         and file_sha256(source) == runtime['source']['sha256'], 'GroupKFold implementation changed.')
    need(len(proteins) == len(set(proteins)), 'unique ordered fitting identities required.')
    groups = [records[p]['sequence_sha256'] for p in proteins]
    need(all(isinstance(g, str) and re.fullmatch('[a-f0-9]{64}', g) for g in groups)
         and len(set(groups)) >= 5, 'complete full-sequence SHA256 groups for at least five folds required.')
    splitter = GroupKFold(n_splits=5)  # Default no-shuffle, including sklearn >=1.6.
    need(not getattr(splitter, 'shuffle', False), 'fold shuffling is not admitted.')
    folds = []
    for number, (train, heldout) in enumerate(splitter.split(np.zeros((len(proteins), 1)), groups=groups)):
        folds.append({'fold_index': number, 'complement_rows': train.tolist(), 'heldout_rows': heldout.tolist()})
    return validate_folds(proteins, groups, folds)


def validate_folds(proteins, groups, folds):
    """Audit exact-once/global ordering and full-sequence exclusion independently."""
    need(len(folds) == 5 and len(groups) == len(proteins), 'exactly five full-sequence folds required.')
    seen = [0] * len(proteins); assignments = [-1] * len(proteins); all_rows = set(range(len(proteins)))
    result = []
    for number, fold in enumerate(folds):
        left, right = fold['complement_rows'], fold['heldout_rows']
        need(fold['fold_index'] == number and left == sorted(set(left)) and right == sorted(set(right))
             and left and right and set(left).isdisjoint(right) and set(left) | set(right) == all_rows,
             'fold rows must form an ordered, disjoint complete fitting partition.')
        a, b = {groups[i] for i in left}, {groups[i] for i in right}
        need(a.isdisjoint(b), 'identical full sequences crossed fitting/heldout fold boundaries.')
        for i in right: seen[i] += 1; assignments[i] = number
        result.append({**fold, 'complement_proteins': [proteins[i] for i in left],
            'heldout_proteins': [proteins[i] for i in right], 'group_overlap': 0,
            'complement_groups_sha256': axis_sha(sorted(a)), 'heldout_groups_sha256': axis_sha(sorted(b))})
    need(set(seen) == {1}, 'every fitting row must be held out exactly once.')
    return result, assignments


def localplus_projection(ontologies, literal_heads):
    """Return native canonical column destinations without merging seed sets."""
    mapping = native_term_map(ontologies); graph = ontologies[NS]
    terms = [n['id'] for n in graph.terms_list]; index = {t: i for i, t in enumerate(terms)}
    result = {}
    for aspect, term in sorted(literal_heads):
        mapped = mapping.get(term)
        if aspect == 'BPO' and mapped is not None and mapped[0] == NS:
            result[(aspect, term)] = tuple(index[t] for t in mapped[1])
    heads = sorted({column for columns in result.values() for column in columns})
    need(heads, 'historical LocalPlus has no heads in the fixed BP ontology.')
    return result, heads


def score_literal_heads(modules, P, literal_heads, projection, head_axis, query_indices,
                        excluded_indices, path):
    """Native per-literal-head score; native alias collisions use MAX afterwards."""
    import numpy as np
    need(not Path(path).exists(), 'preserve existing fold-parent forecasts.')
    output = np.lib.format.open_memmap(path, mode='w+', dtype=np.float64,
        shape=(len(query_indices), len(head_axis))); output[:] = 0
    columns = {head: i for i, head in enumerate(head_axis)}
    present = [(i, value) for i, value in enumerate(query_indices) if value is not None]
    rows = np.asarray([i for i, _ in present], dtype=np.int64)
    query = np.asarray([v for _, v in present], dtype=np.int64)
    empty = removed = 0; excluded = set(excluded_indices)
    for key, destinations in projection.items():
        # Crucial: never union the seed sets of different literal aliases.
        positives = literal_heads[key] - excluded; removed += len(literal_heads[key] & excluded)
        empty += not positives
        values, _, _ = modules['fss'].runLocal(P, np.asarray(sorted(positives), dtype=np.int64))
        need(values.shape == (P.shape[0],) and np.isfinite(values).all()
             and (values >= 0).all() and (values <= 1 + 1e-10).all(), 'native LocalPlus returned invalid source scores.')
        for destination in destinations:
            column = columns[destination]
            output[rows, column] = np.maximum(output[rows, column], values[query])
    output.flush()
    return {'file': str(path), 'sha256': file_sha256(path), 'shape': list(output.shape),
            'dtype': 'float64', 'literal_head_calls': len(projection), 'empty_complement_literal_heads': empty,
            'removed_literal_seed_assignments': removed, 'alias_projection': 'literal scores first; native canonical MAX',
            'full_source_head_axis_retained': True, 'empty_fold_head_means_missing': False}


def prior_receipt(targets, graph, proteins, fold, target_source, fold_spec, output):
    import numpy as np
    output.mkdir(parents=True, exist_ok=False)
    left = list(range(len(proteins))) if fold is None else fold['complement_rows']
    right = [] if fold is None else fold['heldout_rows']
    # All complementary proteins contribute BEFORE the native aspect-root filter.
    arrays = prep.priors_from_full_fit(targets[left], graph)
    files = {}
    for name, value in zip(('raw', 'conditional', 'nulls'), arrays):
        path = output / (name + '.npy'); np.save(path, value, allow_pickle=False); files[name] = spec(path)
    result = {'format': 'biograph-steward.crossfit-native-prior.v1',
        'fold_index': None if fold is None else fold['fold_index'],
        'complement_proteins': [proteins[i] for i in left], 'heldout_proteins': [proteins[i] for i in right],
        'complement_count': len(left), 'heldout_count': len(right),
        'complement_rows_sha256': axis_sha(left), 'heldout_rows_sha256': axis_sha(right),
        'computed_before_root_positive_filter': True, 'target_source': target_source,
        'crossfit_fold_manifest': fold_spec, 'files': files,
        'formula': 'native create_helpers NaN-parent block; Pandas means; raw=conditional*(1-null)',
        'frequency_meaning': 'observed annotation frequency; unlabeled zeros are not confirmed biological negatives', **FLAGS}
    prep.write_json(output / 'receipt.json', result)
    return spec(output / 'receipt.json')


def read_raw_localplus(source, proteins, terms, pins):
    """Read only the preserved LocalPlus raw cache; no combined/DeepGO arrays."""
    import numpy as np
    meta = pinned(source, pins)[NS]
    need(meta['terms'] == terms and len(meta['proteins']) == len(set(meta['proteins']))
         and set(proteins) <= set(meta['proteins']), 'raw LocalPlus identity axes differ.')
    need(pins.get(meta['file']) == meta['sha256'] == file_sha256(meta['file']), 'raw LocalPlus cache changed.')
    values = np.load(meta['file'], mmap_mode='r', allow_pickle=False)
    need(values.dtype == np.float64 and values.shape == (len(meta['proteins']), len(terms)),
         'original lossless LocalPlus float64 cache required.')
    index = {p: i for i, p in enumerate(meta['proteins'])}
    return values, np.asarray([index[p] for p in proteins], dtype=np.int64)


def inputs(cfg):
    """Open only original fitting labels and dated, pre-existing context axes."""
    import numpy as np
    from tools.learned_combination.native_adapter import native_ontologies
    from .context_io import read_boolean_context
    from .training import root_positive_rows
    ont = native_ontologies(cfg['model_obo']['file']); graph = ont[NS]
    meta = pinned(cfg['original_fit_manifest'], cfg['input_file_pins']); proteins = meta['proteins']; terms = meta['terms']
    need(terms == [n['id'] for n in graph.terms_list], 'original model/target term axes differ.')
    need(meta['target_semantics'] == 'known_T0_union_allowed_development_additions_upward_closed', 'original full target semantics required.')
    old_prior_path = meta['prior_receipt_file']
    old_prior = pinned({'file': old_prior_path, 'sha256': cfg['input_file_pins'][old_prior_path]}, cfg['input_file_pins'])
    for name in ('raw', 'conditional', 'nulls'):
        old_path = str(Path(old_prior_path).parent / (name + '.npy'))
        need(cfg['original_full_priors'][name] == {'file': old_path, 'sha256': old_prior['files'][name + '.npy']},
             'full-fit prior comparison must use the original target manifest prior source.')
    for key in ('targets_file', 'known_positive_mask_file'):
        path = meta[key]
        need(cfg['input_file_pins'].get(path) == meta['file_pins'][path] == file_sha256(path), 'original fitting label source changed.')
    targets = np.load(meta['targets_file'], mmap_mode='r', allow_pickle=False)
    known = np.load(meta['known_positive_mask_file'], mmap_mode='r', allow_pickle=False)
    need(targets.shape == known.shape == (len(proteins), len(terms)) and targets.dtype == np.float32
         and known.dtype == np.bool_, 'original target/mask shape or dtype differs.')
    positive_cells = 0
    for start in range(0, len(proteins), 32):
        block, guard = targets[start:start + 32], known[start:start + 32]
        need(np.isin(block, [0, 1]).all() and np.all(block[guard] == 1), 'original targets or known positives changed.')
        positive_cells += int(block.sum())
    contexts = {}; roles = {}
    for role, source in cfg['contexts'].items():
        context_meta = pinned(source, cfg['input_file_pins'])
        need(context_meta['terms'] == terms and context_meta['channels'] == list(CHANNELS), 'original context term/channel axes changed.')
        roles[role] = context_meta['proteins']
        _, context = read_boolean_context(source['file'], cfg['input_file_pins'], context_meta)
        contexts[role] = context
    need(roles['fit'] == proteins and all(len(v) == len(set(v)) for v in roles.values())
         and not (set(roles['fit']) & (set(roles['validation']) | set(roles['final'])))
         and not (set(roles['validation']) & set(roles['final'])), 'complete disjoint ordered role identities required.')
    counts = {'fit_universe': len(proteins), 'full_positive_cells': positive_cells,
        'root_positive_rows': len(root_positive_rows(graph, targets)[0]),
        'validation_proteins': len(roles['validation']), 'final_proteins': len(roles['final']), 'model_terms': len(terms)}
    need(counts == COUNTS, 'original source-admitted targets/root/cohort counts changed.')
    return ont, meta, targets, contexts, roles, counts


def prepare_parents(cfg, output):
    import numpy as np
    from tools.cafa_prediction import core
    from tools.cafa_prediction.run import read
    verify_config(cfg)
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    prep.write_json(output / 'configuration.json', cfg)
    try:
        ont, original, targets, contexts, roles, counts = inputs(cfg)
        proteins, terms = original['proteins'], original['terms']
        records = pinned(cfg['sequence_records'], cfg['input_file_pins'])
        folds, assignment = sequence_folds(proteins, records, cfg['splitter_runtime'])
        fold_meta = {'format': 'biograph-steward.crossfit-full-sequence-folds.v1', 'status': 'passed',
            'plan_sha256': cfg['plan']['sha256'], 'fit_proteins': proteins, 'fold_index_by_row': assignment,
            'sequence_source': cfg['sequence_records'], 'splitter_runtime': cfg['splitter_runtime'],
            'method': 'sklearn.model_selection.GroupKFold', 'n_splits': 5,
            'group_key': 'exact_full_sequence_SHA256', 'shuffle': False, 'folds': folds,
            'graph_seed_exclusion_scope': 'all fitting proteins in each heldout full-sequence group; other historical global source proteins retained',
            'global_nonfitting_sequence_disjointness_claimed': False, **FLAGS}
        prep.write_json(output / 'fold_manifest.json', fold_meta); fold_spec = spec(output / 'fold_manifest.json')
        modules = core.author_modules(cfg['localplus_author_root'], cfg['localplus_author_receipt']['file'])
        source_graph = read(cfg['graph']['file']); nodes = source_graph['nodes']
        need(nodes and len(nodes) == len(set(nodes))
             and all(re.fullmatch('UniProtKB:[A-Z0-9]+', p) for p in nodes), 'literal historical graph identity axis required.')
        index = {p.removeprefix('UniProtKB:'): i for i, p in enumerate(nodes)}
        W = core.adjacency(nodes, source_graph['pairs'])
        need((W.diagonal() == 0).all() and np.isfinite(W.data).all() and (W.data >= 0).all(), 'historical graph must have no self edges and finite nonnegative weights.')
        P = modules['alg_utils'].normalizeGraphEdgeWeights(W); del W, source_graph
        training = read(cfg['original_training']['file'])
        need(len(training) == 20412 and sum(len({tuple(x) for x in v}) for v in training.values()) == 988439,
             'original historical global source universe changed.')
        literal = by_head(training, index); projection, head_axis = localplus_projection(ont, literal)
        need(set(proteins) <= set(index), 'original fitting proteins must belong to the fixed source graph.')
        parents = {}
        for fold in folds:
            number = fold['fold_index']; folder = output / ('fold_%d' % number); folder.mkdir()
            ids = fold['heldout_proteins']
            parent = score_literal_heads(modules, P, literal, projection, head_axis,
                [index[p] for p in ids], {index[p] for p in ids}, folder / 'localplus.npy')
            parents[str(number)] = parent
            print(prep.now(), 'CROSSFIT_SOURCE_FOLD_READY', number, len(ids), flush=True)
        # Replay full-source native scores exactly against the preserved raw cache.
        # This guards graph, seed, literal-head and alias-projection integration.
        replay = {}
        for role in ('validation', 'final'):
            ids = roles[role]; raw, rows = read_raw_localplus(cfg['raw_localplus'][role], ids, terms, cfg['input_file_pins'])
            folder = output / role; folder.mkdir()
            made = score_literal_heads(modules, P, literal, projection, head_axis,
                [index.get(p) for p in ids], set(), folder / 'original_localplus_replay.npy')
            values = np.load(made['file'], mmap_mode='r', allow_pickle=False)
            for start in range(0, len(ids), 32):
                need(np.array_equal(values[start:start + 32], raw[np.ix_(rows[start:start + 32], head_axis)]),
                     'original literal-source LocalPlus replay differs from preserved raw scores.')
            replay[role] = {'exact': True, 'cells': int(values.size), 'source': cfg['raw_localplus'][role], 'replay': made}
        result = {'format': 'biograph-steward.crossfit-graph-frequency-parents.v1', 'status': 'complete',
            'plan': cfg['plan'], 'configuration': spec(output / 'configuration.json'), 'producer_source': spec(__file__),
            'parent_axis': PARENTS, 'namespace': NS, 'counts': counts, 'fold_manifest': fold_spec,
            'fold_parents': parents,
            'localplus_head_indices': head_axis, 'frequency_head_indices': list(range(len(terms))),
            'original_full_source_replay': replay, 'input_file_pins': cfg['input_file_pins'], **FLAGS}
        result['stage_runtime'] = stage_runtime()
        prep.write_json(output / 'parents_ready.json', result)
        return result
    except Exception as error:
        prep.write_json(output / 'parents_failure.json', {'status': 'failed', 'error': str(error), 'traceback': traceback.format_exc(), **FLAGS})
        raise


def write_role_features(author, graph, proteins, terms, localplus, head_axis, priors, context, context_rows, path, *, workers):
    """Use the unchanged two-parent dataset; only a broadcast view is needed."""
    import numpy as np
    raw, conditional = priors
    need(context.dtype == np.bool_ and context.shape[1:] == (40, len(terms))
         and len(context_rows) == len(proteins), 'original forty-channel context axes differ.')
    frequency = np.broadcast_to(raw, (len(proteins), len(terms)))
    dataset = make_dataset(author, proteins=proteins, terms=terms, graph=graph,
        predictions=[(localplus, np.asarray(head_axis, dtype=np.int64)),
                     (frequency, np.arange(len(terms), dtype=np.int64))],
        prior_raw=raw, prior_cond=conditional,
        goa_indices=[np.flatnonzero(context[i, 1]) for i in context_rows])
    prep.write_feature_memmap(dataset, path, workers=workers)
    features = np.load(path, mmap_mode='r', allow_pickle=False)
    expected_flag = np.ones(len(terms), dtype=np.float32); expected_flag[head_axis] = 0
    for start in range(0, len(proteins), 16):
        block = features[start:start + 16]
        need(np.isfinite(block).all() and (block >= 0).all() and (block <= 1).all(), 'native raw feature values are not finite [0,1].')
        need(np.all(block[:, 0] == expected_flag) and not block[:, 4].any(), 'source head availability changed with fold positivity.')
        need(np.array_equal(block[:, 8], context[np.asarray(context_rows[start:start + 16]), 1]),
             'native default context differs from original global propagated context.')
        need(np.all(block[:, 5:8] == raw.astype(np.float32)[None, None, :]), 'observed-frequency parent differs from the applicable native raw prior.')


def prepare_features(cfg, output):
    import numpy as np
    verify_config(cfg); output = Path(output)
    need(not (output / 'features_started.json').exists(), 'preserve existing/failed feature stage; use a new attempt directory.')
    try:
        prep.write_json(output / 'features_started.json', {'configuration': spec(output / 'configuration.json'), **FLAGS})
        ready = json.loads((output / 'parents_ready.json').read_text())
        need(ready['status'] == 'complete' and ready['parent_axis'] == PARENTS
             and ready['configuration']['sha256'] == file_sha256(output / 'configuration.json')
             and json.loads((output / 'configuration.json').read_text()) == cfg
             and ready['producer_source']['sha256'] == file_sha256(__file__), 'completed parent preparation/configuration/source changed.')
        ont, original, targets, contexts, roles, counts = inputs(cfg)
        fold_spec = ready['fold_manifest']; fold_meta = pinned(fold_spec)
        proteins, terms = original['proteins'], original['terms']; head_axis = ready['localplus_head_indices']
        records = pinned(cfg['sequence_records']); groups = [records[p]['sequence_sha256'] for p in proteins]
        folds, assignment = validate_folds(proteins, groups, fold_meta['folds'])
        need(assignment == fold_meta['fold_index_by_row'] and fold_meta['plan_sha256'] == cfg['plan']['sha256'], 'fold binding changed.')
        author = load_author(cfg['stack_author_root'], jit_backend='numba')
        target_source = {'file': original['targets_file'], 'sha256': original['file_pins'][original['targets_file']]}
        full_spec = prior_receipt(targets, ont[NS], proteins, None, target_source, fold_spec, output / 'all_fit_priors')
        full = pinned(full_spec)
        for name in ('raw', 'conditional', 'nulls'):
            need(np.array_equal(load_array(full['files'][name]), load_array(cfg['original_full_priors'][name])),
                 'recomputed native full-fit prior differs from its preserved original vector: ' + name)
        prior_specs = [prior_receipt(targets, ont[NS], proteins, fold, target_source, fold_spec,
                       output / ('fold_%d' % fold['fold_index']) / 'priors') for fold in folds]
        prior_receipts = {'folds': prior_specs, 'all_fit': full_spec}
        feature_dir = output / 'features'; feature_dir.mkdir()
        fit_path = feature_dir / 'fit.npy'
        fit = np.lib.format.open_memmap(fit_path, mode='w+', dtype=np.float32, shape=(len(proteins), 9, len(terms)))
        for fold, prior_spec in zip(folds, prior_specs):
            number = fold['fold_index']; parent = ready['fold_parents'][str(number)]; prior = pinned(prior_spec)
            need(prior['fold_index'] == number and prior['complement_proteins'] == fold['complement_proteins']
                 and prior['heldout_proteins'] == fold['heldout_proteins'] and prior['crossfit_fold_manifest'] == fold_spec,
                 'complement prior/fold binding changed.')
            arrays = [load_array(s) for s in (prior['files']['raw'], prior['files']['conditional'])]
            local = load_array(parent); rows = fold['heldout_rows']; path = feature_dir / ('fold_%d.npy' % number)
            write_role_features(author, ont[NS], fold['heldout_proteins'], terms, local, head_axis, arrays,
                contexts['fit'], rows, path, workers=cfg['workers'])
            made = np.load(path, mmap_mode='r', allow_pickle=False)
            for start in range(0, len(rows), 16): fit[rows[start:start + 16]] = made[start:start + 16]
        fit.flush(); del fit
        manifests = {}
        need(full['fold_index'] is None and full['complement_proteins'] == proteins and not full['heldout_proteins']
             and full['crossfit_fold_manifest'] == fold_spec, 'full-fitting prior binding changed.')
        full_priors = [load_array(full['files'][name]) for name in ('raw', 'conditional')]
        for role in ('fit', 'validation', 'final'):
            ids = roles[role]; path = fit_path if role == 'fit' else feature_dir / (role + '.npy')
            if role != 'fit':
                raw, rows = read_raw_localplus(cfg['raw_localplus'][role], ids, terms, cfg['input_file_pins'])
                # Read the source LP cache, not its replay or an old DeepGO feature cache.
                write_role_features(author, ont[NS], ids, terms, raw[np.ix_(rows, head_axis)], head_axis,
                    full_priors, contexts[role], list(range(len(ids))), path, workers=cfg['workers'])
            meta = {'namespace': NS, 'proteins': ids, 'terms': terms, 'parent_axis': PARENTS,
                'feature_file': str(path), 'features_shape': [len(ids), 9, len(terms)], 'features_dtype': 'float32',
                'features_semantics': 'native StackDataset before native logit transform; ordered LocalPlus and observed annotation frequency',
                'crossfit_fold_manifest': fold_spec,
                'feature_prior_receipts': prior_specs if role == 'fit' else [full_spec],
                'original_fit_manifest': cfg['original_fit_manifest'], 'original_context_manifest': cfg['contexts'][role],
                'file_pins': {str(path): file_sha256(path)}, **FLAGS}
            if role == 'fit':
                for key in ('targets_file', 'known_positive_mask_file'):
                    meta[key] = original[key]; meta['file_pins'][original[key]] = original['file_pins'][original[key]]
                meta['target_semantics'] = original['target_semantics']
            mp = feature_dir / (role + '.json'); prep.write_json(mp, meta); manifests[role] = spec(mp)
        admission = {'format': 'biograph-steward.crossfit-graph-frequency-source-admission.v1',
            'status': 'passed', 'qualified': True, 'plan_sha256': cfg['plan']['sha256'],
            'producer_source': spec(__file__), 'counts': counts, 'parent_axis': PARENTS,
            'localplus_head_count': len(head_axis), 'frequency_head_count': len(terms),
            'localplus_head_scope': 'full original literal-source vocabulary after native alias MAX; retained if fold has zero positives',
            'frequency_head_scope': 'all fixed model heads, including observed zero frequency',
            'fitting_frequency_and_missing_head_priors': 'complement only, all rows before root filter',
            'validation_final_frequency_and_missing_head_priors': 'all original 4040 fitting rows',
            'dates': {'fit_context': '2023-05-18', 'validation_context': '2025-09-04', 'final_context': '2026-04-10'},
            'new_annotation_source_or_target_cells': False, 'original_targets_and_known_mask_bytes_retained': True,
            'original_fit_manifest': cfg['original_fit_manifest'],
            'original_targets': {'file': original['targets_file'], 'sha256': original['file_pins'][original['targets_file']]},
            'original_known_positive_mask': {'file': original['known_positive_mask_file'],
                'sha256': original['file_pins'][original['known_positive_mask_file']]},
            'original_full_source_replay': ready['original_full_source_replay'],
            'full_ProtBoost_reproduction': False, 'isolated_OOF_effect_claimed': False,
            'scientific_accuracy_or_gain_established': False, **FLAGS}
        admission.update(parent_preparation_receipt=spec(output / 'parents_ready.json'),
            parent_stage_runtime=ready['stage_runtime'], feature_stage_runtime=stage_runtime(),
            native_dataset_source=author.source_receipt,
            native_full_fit_priors_match_original_vectors_exactly=True)
        prep.write_json(output / 'source_admission.json', admission)
        pins = dict(cfg['input_file_pins']); pins[str(Path(__file__))] = file_sha256(__file__)
        # The final consumer must bind generated arrays/receipts as well as the
        # historical inputs. ready.json itself is sealed by its caller.
        for generated in output.rglob('*'):
            if generated.is_file() and generated.name != 'ready.json':
                pins[str(generated)] = file_sha256(generated)
        result = {'format': READY_FORMAT, 'status': 'complete', 'plan': cfg['plan'],
            'configuration': spec(output / 'configuration.json'), 'producer_source': spec(__file__),
            'parent_axis': PARENTS, 'namespace': NS, 'manifests': manifests, 'contexts': cfg['contexts'],
            'model_obo': cfg['model_obo'], 'channel_contract': cfg['channel_contract'], 'fold_manifest': fold_spec,
            'prior_receipts': prior_receipts, 'source_admission': spec(output / 'source_admission.json'),
            'input_file_pins': pins, **FLAGS}
        prep.write_json(output / 'ready.json', result); return result
    except Exception as error:
        failure = output / 'features_failure.json'
        if not failure.exists(): prep.write_json(failure, {'status': 'failed', 'error': str(error), 'traceback': traceback.format_exc(), **FLAGS})
        raise


def load_array(source):
    import numpy as np
    need(file_sha256(source['file']) == source['sha256'], 'prepared array changed: ' + source['file'])
    return np.load(source['file'], mmap_mode='r', allow_pickle=False)


def prepare(cfg, output, *, stage='all'):
    need(stage in ('parents', 'features', 'all'), 'unknown source preparation stage.')
    if stage in ('parents', 'all'): result = prepare_parents(cfg, output)
    if stage in ('features', 'all'): result = prepare_features(cfg, output)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True); parser.add_argument('--output', required=True)
    parser.add_argument('--stage', choices=('parents', 'features', 'all'), default='all')
    args = parser.parse_args(); prepare(json.loads(Path(args.config).read_text()), args.output, stage=args.stage)


if __name__ == '__main__': main()
