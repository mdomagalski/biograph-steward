"""Source-pinned ProtBoost core and device-portable feature preparation.

The external Apache-2.0 GCNStacker, StackDataset, Propagator, propagation and
edge-building bodies execute unchanged. This adapter isolates CPU symbols from
the author's module-level CuPy kernels. It substitutes device placement for
the author's CUDA-only DataLoader, not graph mathematics or model layers.
No data, checkpoint, source download or scientific-reference access occurs.
"""
import ast
from dataclasses import dataclass
import hashlib
import importlib.util
from pathlib import Path
import sys
import types


AUTHOR_REPOSITORY = 'https://github.com/btbpanda/CAFA5-protein-function-prediction-2nd-place'
AUTHOR_COMMIT = '52dce6c471337f2820550f779a6a1bb201353b2a'
AUTHOR_PINS = {
    'LICENSE': '352a4208310cd9e8be157e00979dd06f375fbdbf384e4b691a2af1fcc9079600',
    'protnn/stacker.py': '001c086d74b3525f2419e138a4d3f575b4ab3b2d49c8b8057830775c23e91293',
    'protnn/dataset.py': '8d356992e2ef213d26672354559c8d44c5ea30caab9a40eb49e06e426ca58ae3',
    'protlib/metric.py': 'ab2deadf5041e0b3034ae0876c85941dff5343e3a7895798d522253789678f63',
}
NATIVE_PARAMETERS = {
    'hidden_size': 16, 'n_layers': 8, 'published_embed_size': 8,
    'epochs': 20, 'batch_size': 32, 'optimizer': 'Adam', 'lr': 1e-3,
    'clip_grad_value': 1e-1, 'weight_decay': 0.,
    'store_swa': 10, 'average_best_validation_checkpoints': 3,
}


def need(condition, message):
    if not condition:
        raise ValueError('Contextual stacker: ' + message)


# Literal identity axis, also required when a variant uses multiple native
# GOA channels. Feature order is part of the learned input meaning.
DEFAULT_CONTEXT_CHANNELS = ('qualified_historical_nonexperimental_goa',)


def context_axis(channels):
    need(isinstance(channels, (tuple, list)) and channels
         and all(isinstance(name, str) and name and not any(c.isspace() for c in name)
                 for name in channels) and len(set(channels)) == len(channels),
         'complete unique literal ordered GOA context channel names required.')
    return tuple(channels)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _symbols(path, names, namespace):
    """Execute selected unchanged, source-pinned definitions without imports.

    The original metric module constructs CuPy kernels during import even
    though get_depths uses Pandas only. The dataset module imports that metric
    module solely for get_depths. Selected definitions retain their original
    decorators, argument defaults and bodies; dependency bindings are explicit.
    """
    tree = ast.parse(Path(path).read_bytes(), filename=str(path))
    selected = [node for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    need({node.name for node in selected} == set(names), 'qualified native symbol set is incomplete.')
    ast_receipt = {node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
                   for node in selected}
    module = ast.Module(body=selected, type_ignores=[])
    exec(compile(module, str(path), 'exec'), namespace)
    return ast_receipt


def _without_jit(*args, **kwargs):
    """Explicit no-JIT execution of the native CPU propagation function body."""
    need(not args and kwargs == {'nopython': True}, 'unexpected native JIT decorator contract.')
    return lambda function: function


@dataclass(frozen=True)
class AuthorCore:
    root: Path
    stacker_module: object
    data_module: object
    source_receipt: dict


def load_author(root, *, jit_backend='none'):
    """Load only the qualified author core; never run its training driver.

    ``none`` is a CPU reference path, not an optimized feature-cache runtime.
    ``numba`` retains the original @jit(nopython=True); version qualification is
    the caller's responsibility and a missing package fails rather than falling
    back silently. Neither mode imports CuPy or allocates a CUDA tensor.
    """
    import numpy as np
    import pandas as pd
    import torch
    from torch.utils.data import DataLoader, Dataset

    root = Path(root).resolve()
    need(jit_backend in ('none', 'numba'), 'JIT backend must be explicitly none or numba.')
    for name, pin in AUTHOR_PINS.items():
        need((root / name).is_file() and _sha(root / name) == pin,
             'author source/license differs from qualified revision: ' + name)
    name = '_biograph_protboost_stacker_' + AUTHOR_COMMIT
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, root / 'protnn/stacker.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[name] = module
    stacker = sys.modules[name]
    data = types.ModuleType('_biograph_protboost_data_' + jit_backend)
    data.__file__ = str(root / 'protnn/dataset.py')
    data.__dict__.update({'np': np, 'pd': pd, 'torch': torch,
                          'Dataset': Dataset, 'DataLoader': DataLoader})
    if jit_backend == 'numba':
        from numba import jit
        data.jit = jit
    else:
        data.jit = _without_jit
    depth = _symbols(root / 'protlib/metric.py', ('get_depths',), data.__dict__)
    symbols = _symbols(root / 'protnn/dataset.py',
                       ('propagate', 'Propagator', 'get_dag_dense', 'StackDataLoader', 'StackDataset'),
                       data.__dict__)
    receipt = {
        'repository': AUTHOR_REPOSITORY, 'commit': AUTHOR_COMMIT,
        'license': 'Apache-2.0; external source/license retained, not vendored',
        'source_sha256': dict(AUTHOR_PINS), 'selected_symbol_ast_sha256': {**depth, **symbols},
        'jit_backend': jit_backend, 'model_body_changed': False,
        'feature_and_graph_function_bodies_changed': False,
        'integration_changes': [
            'Select CPU definitions without importing unused module-level CuPy kernels.',
            'Explicit NumPy/Pandas/Torch/decorator dependency bindings.',
            'Replace CUDA-only batch placement with caller-selected device.',
            'Two marginal parents and a declared ordered qualified GOA context axis.',
            'Retain a fixed, literal model ontology axis when using the native per-node embedding.',
        ],
    }
    return AuthorCore(root, stacker, data, receipt)


def validate_graph(graph, terms):
    """Require an explicit native ordered GO axis and reciprocal native edges."""
    terms = tuple(terms)
    need(terms and len(set(terms)) == len(terms) == graph.idxs
         and terms == tuple(node['id'] for node in graph.terms_list),
         'literal term axis differs from native graph indexes.')
    for index, node in enumerate(graph.terms_list):
        for parent in node['adj']:
            need(type(parent) is int and 0 <= parent < graph.idxs
                 and index in graph.terms_list[parent]['children'],
                 'native parent/child indexes are incomplete or inconsistent.')
        for child in node['children']:
            need(type(child) is int and 0 <= child < graph.idxs
                 and index in graph.terms_list[child]['adj'],
                 'native child/parent indexes are incomplete or inconsistent.')
    return terms


def sequence_edge_graph(graph):
    """Container bridge: native evaluator sets to author integer sequences.

    This copies containers only. It retains all term IDs, indexes, traversal
    order and exact directed edges; preexisting sequence order is preserved.
    The author StackDataset constructs integer arrays from these containers.
    NumPy cannot directly cast the evaluator's sets to integer arrays.
    """
    import copy

    validate_graph(graph, tuple(node['id'] for node in graph.terms_list))
    view = copy.copy(graph)
    sequence = lambda edges: sorted(edges) if isinstance(edges, (set, frozenset)) else list(edges)
    view.terms_list = [{**node, 'adj': sequence(node['adj']), 'children': sequence(node['children'])}
                       for node in graph.terms_list]
    return view


def make_dataset(author, *, proteins, terms, graph, predictions,
                 prior_raw, prior_cond, goa_indices=None, goa_channels=None, targets=None):
    """Build the unchanged native dataset with two NONconditional parents.

    ``predictions`` is exactly two ``(Nprotein,Nhead score matrix, head indexes)``
    pairs. A head index means the model actually emits that function, not that
    this protein has a positive score. Explicit zero and omitted head differ.
    Missing heads use source-qualified priors. The native feature array is
    float32; original float64 forecast controls stay separately preserved.
    ``targets`` must represent the full training-positive repertoire, including
    known T0 positives, not a PK delta that relabels known positives as negatives.
    The caller owns source/cutoff/known-union provenance and split exclusion.
    """
    import numpy as np

    terms = validate_graph(graph, terms)
    graph = sequence_edge_graph(graph)
    proteins = tuple(proteins)
    need(proteins and len(proteins) == len(set(proteins)), 'unique literal protein axis required.')
    need(len(predictions) == 2, 'exactly two marginal parent models required.')
    native = []
    for values, head_indexes in predictions:
        values, indexes = np.asarray(values), np.asarray(head_indexes)
        need(indexes.ndim == 1 and indexes.dtype.kind in 'iu'
             and len(set(indexes.tolist())) == len(indexes)
             and (indexes >= 0).all() and (indexes < len(terms)).all(),
             'literal unique native model-head indexes required.')
        need(values.shape == (len(proteins), len(indexes)) and values.dtype.kind in 'fiu'
             and np.isfinite(values).all() and (values >= 0).all() and (values <= 1 + 1e-10).all(),
             'finite source-qualified scores matching protein/head axes required.')
        native.append((values, indexes, False))
    for prior in (prior_raw, prior_cond):
        prior = np.asarray(prior)
        need(prior.shape == (len(terms),) and np.isfinite(prior).all()
             and (prior >= 0).all() and (prior <= 1).all(),
             'complete qualified probability priors on the native term axis required.')
    need((goa_indices is None) != (goa_channels is None),
         'supply exactly one explicit default-GOA index frame or named multi-channel frame.')
    channels = [(DEFAULT_CONTEXT_CHANNELS[0], goa_indices)] if goa_channels is None else list(goa_channels)
    need(all(isinstance(item, (tuple, list)) and len(item) == 2 for item in channels),
         'named GOA channels require explicit (name, per-protein index rows) pairs.')
    channel_names = context_axis([item[0] for item in channels])
    goa_list = []
    for name, rows in channels:
        need(len(rows) == len(proteins), 'GOA row identities must match protein axis.')
        goa = []
        for indexes in rows:
            indexes = np.asarray(indexes)
            need(indexes.ndim == 1 and (not len(indexes) or indexes.dtype.kind in 'iu')
                 and len(set(indexes.tolist())) == len(indexes)
                 and (indexes >= 0).all() and (indexes < len(terms)).all(),
                 'unique GOA indexes inside the native term axis required.')
            goa.append(indexes.astype(np.int64))
        goa_list.append(np.asarray(goa, dtype=object))
    target_array = None
    if targets is not None:
        target_array = np.asarray(targets)
        need(target_array.shape == (len(proteins), len(terms))
             and ((target_array == 0) | (target_array == 1)).all(),
             'full binary training-positive targets matching both literal axes required.')
        target_array = target_array.astype(np.float32, copy=False)
    result = author.data_module.StackDataset(native, len(terms), np.asarray(prior_raw),
        np.asarray(prior_cond), graph, goa_list, p_goa=1, targets=target_array)
    result._biograph_proteins = proteins
    result._biograph_terms = terms
    result._biograph_context_channels = channel_names
    return result


def make_model(author, *, n_terms, terms=None, n_layers=8, embed_size=8, seed=20261115,
               context_channels=DEFAULT_CONTEXT_CHANNELS):
    """Return unchanged native class; n_layers=0 is the no-message control.

    The zero-layer class remains a shared per-term MLP: it still has its native
    input ReLU. It must not be described as a linear model. The native published
    embed_size=8 requires the same explicit model GO axis at training/inference;
    score export may then enter a separate current-ontology evaluator. Supported
    embed_size=0 is available for qualification, not an added experimental arm.
    """
    import torch

    channels = context_axis(context_channels)

    need(type(n_terms) is int and n_terms > 0 and n_layers in (0, 8)
         and type(n_layers) is int and type(seed) is int and embed_size in (0, 8)
         and type(embed_size) is int,
         'positive term count and declared 0/8-layer architecture required.')
    terms = None if terms is None else tuple(terms)
    need(embed_size == 0 or (terms is not None and len(terms) == len(set(terms)) == n_terms),
         'native per-node embedding requires a complete ordered literal model term axis.')
    # fork_rng avoids resetting a caller's unrelated model/service RNG.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        model = author.stacker_module.GCNStacker(2, len(channels), n_terms,
                                                hidden_size=16, n_layers=n_layers, embed_size=embed_size)
    model._biograph_model_terms = terms
    model._biograph_context_channels = channels
    return model


def validate_model_axis(model, terms):
    """Reject reordered/new node identities before embedded-model inference."""
    if model.embed_size:
        need(getattr(model, '_biograph_model_terms', None) == tuple(terms),
             'model GO identities/order changed; fixed per-node embeddings cannot be reindexed implicitly.')


def validate_model_context(model, channels):
    channels = context_axis(channels)
    need(getattr(model, '_biograph_context_channels', None) == channels
         and model.in_goa == len(channels),
         'model GOA context channel identities/order changed; implicit reordering is prohibited.')


def transform_batch(author, batch, graph, *, device='cpu', context_channels=DEFAULT_CONTEXT_CHANNELS):
    """The native StackDataLoader transformation with portable device placement.

    Every probability channel is clamped to [1e-6,1-1e-6] before logit conversion,
    exactly as native. Missing-head flags and binary GOA are not logit-converted.
    This numerical feature transform is not a calibration of scientific truth.
    """
    import torch

    channels = context_axis(context_channels)

    need(set(batch) <= {'x', 'y'} and 'x' in batch, 'only native x/optional y input batches supported.')
    graph = sequence_edge_graph(graph)
    need(batch['x'].ndim == 3 and batch['x'].shape[1:] == (8 + len(channels), graph.idxs),
         'native two-parent/four-channel plus declared-GOA batch shape required.')
    result = {name: value.to(device).clone() for name, value in batch.items()}
    indexes = torch.arange(8, device=device).reshape(2, 4)[:, 1:].ravel()
    probabilities = torch.clamp(result['x'][:, indexes], 1e-6, 1 - 1e-6)
    result['x'][:, indexes] = torch.log(probabilities / (1 - probabilities))
    result['x'] = result['x'].swapaxes(1, 2)
    result['x'], result['goa'] = result['x'][..., :8], result['x'][..., 8:]
    for direction in ('all', 'fwd', 'bwd'):
        dst, src = author.data_module.get_dag_dense(graph, direction=direction, self_loop=False)
        result[direction] = {'dst': dst.to(device), 'src': src.to(device)}
    return result


def collate_rows(author, dataset, rows, *, device='cpu'):
    from torch.utils.data import default_collate

    return transform_batch(author, default_collate([dataset[int(row)] for row in rows]),
                           dataset.G, device=device,
                           context_channels=getattr(dataset, '_biograph_context_channels', DEFAULT_CONTEXT_CHANNELS))
