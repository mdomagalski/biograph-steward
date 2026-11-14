"""Small call adapters for the immutable author predictor, not a new model.

Caller freezes file pins and executes in a fresh isolated author runtime. This
module never imports an evaluator, reads annotation labels, fetches a source,
selects an ensemble, trains a model or rewrites an ontology.
"""
import importlib
from pathlib import Path
import sys

from biograph_steward.client import digest
from .archive import fingerprints, need
from .scores import ENSEMBLES, average_author_models, validate_identity


def pinned(spec):
    path = Path(spec['file'])
    need(fingerprints(path)['sha256'] == spec['sha256'], 'input FILE pin differs: ' + path.name)
    return path


def check_author_import_paths(root):
    root = Path(root).resolve()
    for name, module in tuple(sys.modules.items()):
        if name == 'deepgo' or name.startswith('deepgo.'):
            need(module is not None and getattr(module, '__file__', None)
                 and Path(module.__file__).resolve().is_relative_to(root),
                 'another transitive author package is already imported.')


def author_modules(root, code_intake):
    """Bind all source members to the already checked immutable code ZIP."""
    import json
    root = Path(root).resolve()
    intake = json.loads(pinned(code_intake).read_text())
    need(intake['format'] == 'biograph-steward.deepgo-small-artifact-intake.v1'
         and intake['content_sha256'] == digest({k: v for k, v in intake.items() if k != 'content_sha256'}),
         'author code intake seal differs.')
    for row in intake['code_members']:
        relative = Path(*Path(row['name']).parts[1:])
        need(fingerprints(root / relative)['sha256'] == row['sha256'], 'immutable author source differs.')
    sys.path.insert(0, str(root))
    result = {}
    for key in ('deepgo.models', 'deepgo.data', 'deepgo.extract_esm'):
        module = importlib.import_module(key)
        need(Path(module.__file__).resolve().is_relative_to(root), 'another author package is already imported.')
        result[key] = module
    check_author_import_paths(root)
    return result


def extract_features(author, fasta, esm_model, esm_regression, output, *, device, expected_ids):
    """Exact native 1022-residue, last-layer, mean-pooling extraction."""
    import torch
    fasta_path, model, regression = map(pinned, (fasta, esm_model, esm_regression))
    need(model.name == 'esm2_t36_3B_UR50D.pt'
         and regression == model.with_name('esm2_t36_3B_UR50D-contact-regression.pt'),
         'local native ESM model/regression path contract differs.')
    output = Path(output)
    need(not output.exists(), 'fresh feature output required; native cache is not admitted implicitly.')
    output.parent.mkdir(parents=True, exist_ok=True)
    proteins, data = author['deepgo.extract_esm'].extract_esm(
        str(fasta_path), model_location=str(model), truncation_seq_length=1022,
        toks_per_batch=4096, device=device, out_file=str(output))
    need(data.dtype == torch.float32 and data.ndim == 2 and data.shape == (len(proteins), 2560),
         'native ESM feature shape/dtype differs.')
    need(len(set(proteins)) == len(proteins) == len(expected_ids) == len(set(expected_ids))
         and set(proteins) == set(expected_ids), 'native feature identities do not biject the fixed frame.')
    # The native batching order is retained. Caller must join literal IDs to its
    # frozen frames; no assumption that length batching preserves FASTA order.
    return proteins, data


def predict_aspect(author, feature_cache, terms_file, normal_forms, checkpoints,
                   aspect, *, device, expected_ids, batch_size=32):
    """The exact published six forwards/float32 average before CLI formatting."""
    import numpy as np
    import pandas as pd
    import torch as th
    need(aspect in ENSEMBLES and tuple(checkpoints) == ENSEMBLES[aspect]
         and batch_size == 32, 'native ensemble/order or batch size differs.')
    feature_path, terms_path, norm_path = map(pinned, (feature_cache, terms_file, normal_forms))
    model_paths = {index: pinned(spec) for index, spec in checkpoints.items()}
    need(norm_path.name == 'go-plus.norm' and terms_path.name == 'terms.pkl'
         and terms_path.parent.name == aspect,
         'native GO-Plus or namespace term-file contract differs.')
    need(all(path.name == f'deepgozero_esm_plus_{index}.th' and path.parent.name == aspect
             for index, path in model_paths.items()), 'native checkpoint index/namespace path differs.')
    cached = th.load(feature_path, map_location='cpu')
    need(set(cached) == {'data', 'proteins'}, 'native feature cache shape differs.')
    data, proteins = cached['data'], cached['proteins']
    need(data.dtype == th.float32 and data.ndim == 2 and data.shape == (len(proteins), 2560),
         'cached native feature dimensions/dtype differ.')
    need(len(set(proteins)) == len(proteins) == len(expected_ids) == len(set(expected_ids))
         and set(proteins) == set(expected_ids), 'cached identities do not biject the fixed frame.')
    terms = pd.read_pickle(terms_path)['gos'].values.flatten()
    validate_identity(proteins, terms)
    terms_dict = {value: index for index, value in enumerate(terms)}
    forms = author['deepgo.data'].load_normal_forms(str(norm_path), terms_dict)
    relations, zero_classes = forms[-2:]
    model = author['deepgo.models'].DeepGOModel(
        2560, len(terms), len(zero_classes), len(relations), device).to(device)
    predictions = {}
    for index, model_file in model_paths.items():
        model.load_state_dict(th.load(model_file, map_location=device))
        model.eval()
        batches = []
        with th.no_grad():
            for start in range(0, len(proteins), batch_size):
                values = model(data[start:start + batch_size].to(device))
                batches.append(values.detach().cpu().numpy())
        predictions[index] = np.concatenate(batches)
    # The helper uses precisely native sequential float32 additions, followed
    # by division by six. No clipping, calibration or test-based selection.
    return proteins, list(terms), average_author_models(aspect, predictions)
