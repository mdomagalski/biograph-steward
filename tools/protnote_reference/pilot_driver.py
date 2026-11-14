"""Research-only, label-blind native ProtNote parity/cache/547-target driver.

Execute only in the isolated qualified Brev runtime after source review. Every
phase has an explicit sealed inference-only config; it accepts no reference,
annotation, benchmark TOI, loss, optimizer, calibration or evaluation input.
The native architecture, dataset/collator and text helpers remain unmodified.
"""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata
import importlib.util
import json
import logging
import os
from pathlib import Path
import platform
import re
import sys
import time

FORMAT = 'biograph-steward.protnote-labelblind.v1'
COMMIT = 'b29e17fa308d8c0fc1d9692f705b37dff3a8cf5e'
CHECKPOINT = 'd855e6c40b986294f3f4c852020c58b362ec2d38d806f60ef78e2fef89ab0887'
ONTOLOGY = '0c0062efbb1b199a6a54e62c0c48ff0038d39173aecc7edfab66a20090d5ec2d'
AA20 = 'ACDEFGHIKLMNPQRSTVWY'
ACCESSION = re.compile(r'(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})\Z')
TOKEN_FILES = {'config.json', 'tokenizer.json', 'tokenizer_config.json',
               'special_tokens_map.json', 'sentencepiece.bpe.model'}
CONFIG_KEYS = {'format', 'status', 'created_at', 'seed', 'device',
    'runtime', 'official_source_root', 'official_source_commit', 'official_source_files',
    'adapter', 'implementation', 'checkpoint', 'tokenizer_directory', 'tokenizer_files',
    'ontology', 'targets', 'dated_fasta', 'sequence_batch', 'text_batch', 'label_pair_chunk',
    'reuse_sequence_embeddings', 'all547_denominators_retained', 'no_future_labels_or_TOI',
    'new_training_or_threshold_search', 'automatic_graph_changes', 'producer_input_qualification',
    'expected_target_ids_sha256', 'expected_go_ids_sha256', 'content_sha256'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def seal(value):
    return {**value, 'content_sha256': digest(value)}


def write(path, value):
    value = {'created_at': datetime.now(timezone.utc).isoformat(), **value}
    Path(path).write_text(json.dumps(seal(value), indent=2, sort_keys=True,
        ensure_ascii=False, allow_nan=False) + '\n')


def read(path, expected):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and sha(path) == expected,
         'Expected sealed ordinary FILE differs.')
    value = json.loads(path.read_text())
    need(value.get('content_sha256') == digest({k: v for k, v in value.items() if k != 'content_sha256'}),
         'JSON content seal differs.')
    return value


def check_pin(value):
    need(set(value) == {'file', 'sha256'} and re.fullmatch('[a-f0-9]{64}', value['sha256']),
         'Literal path and SHA256 pin required.')
    path = Path(value['file'])
    need(path.is_file() and not path.is_symlink() and sha(path) == value['sha256'], 'Input FILE differs.')
    return path


def module_from(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def config(path, expected, *, qualification_only=False):
    cfg = read(path, expected)
    need(set(cfg) == CONFIG_KEYS and cfg['format'] == FORMAT + '.freeze'
         and cfg['status'] == ('PRE_FORWARD_QUALIFICATION_ONLY' if qualification_only else
                               'FROZEN_before_any_target_forecast')
         and cfg['official_source_commit'] == COMMIT and cfg['seed'] == 42
         and cfg['sequence_batch'] == 1 and cfg['text_batch'] == 8
         and cfg['label_pair_chunk'] == 1024 and type(cfg['reuse_sequence_embeddings']) is bool
         and cfg['device'] in ('cpu', 'cuda:0')
         and cfg['all547_denominators_retained'] is True and cfg['no_future_labels_or_TOI'] is True
         and cfg['new_training_or_threshold_search'] is False and cfg['automatic_graph_changes'] is False,
         'Only the fixed inference-only seed42 scope is accepted.')
    if qualification_only:
        need(cfg['producer_input_qualification'] is None and cfg['expected_target_ids_sha256'] is None
             and cfg['expected_go_ids_sha256'] is None, 'Qualification cannot reuse an outcome-dependent axis.')
    else:
        check_pin(cfg['producer_input_qualification'])
        for key in ('expected_target_ids_sha256', 'expected_go_ids_sha256'):
            need(re.fullmatch('[a-f0-9]{64}', cfg[key]), 'Explicit pre-forward axis/identity pin required.')
    source = Path(cfg['official_source_root']).resolve()
    need(cfg['official_source_files'] and all(not Path(p).is_absolute() and '..' not in Path(p).parts
         for p in cfg['official_source_files']), 'Pinned relative native source files required.')
    for name, expected_sha in cfg['official_source_files'].items():
        need(sha(source / name) == expected_sha, 'Native source differs: ' + name)
    for name in ('adapter', 'implementation', 'checkpoint', 'ontology'):
        check_pin(cfg[name])
    need(Path(cfg['implementation']['file']).resolve() == Path(__file__).resolve()
         and cfg['checkpoint']['sha256'] == CHECKPOINT
         and Path(cfg['checkpoint']['file']).name == 'seed_replicates_v9_42_sum_last_epoch.pt'
         and cfg['ontology']['sha256'] == ONTOLOGY, 'Driver, seed42 checkpoint or ontology differs.')
    need(set(cfg['tokenizer_files']) == TOKEN_FILES, 'All five pinned local tokenizer/config files required.')
    token_path = Path(cfg['tokenizer_directory'])
    for name, expected_sha in cfg['tokenizer_files'].items():
        need(sha(token_path / name) == expected_sha, 'Pinned tokenizer/config body differs.')
    need(set(cfg['runtime']) == {'python', 'torch', 'torchvision', 'transformers', 'tokenizers',
                                'numpy', 'pandas', 'obonet', 'biopython'},
         'Exact isolated core runtime must be supplied.')
    actual = {name: importlib.metadata.version(name) for name in cfg['runtime'] if name != 'python'}
    actual['python'] = platform.python_version()
    need(actual == cfg['runtime'] and platform.system() == 'Linux', 'Actual isolated core runtime differs.')
    need(all(os.environ.get(k) == '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')),
         'One-thread native numeric environment required.')
    # Local-only HF mode is set before importing transformers or native modules.
    os.environ['HF_HUB_OFFLINE'] = '1'; os.environ['TRANSFORMERS_OFFLINE'] = '1'
    sys.path.insert(0, str(source))
    import protnote
    need(Path(protnote.__file__).resolve().parent.parent == source, 'Actual native import comes from another source tree.')
    adapter = module_from(cfg['adapter']['file'], 'qualified_protnote_adapter')
    import torch
    import numpy as np
    torch.set_num_threads(1); torch.manual_seed(42); np.random.seed(42)
    if cfg['device'] == 'cuda:0':
        need(torch.cuda.is_available(), 'Frozen CUDA device is unavailable; no precision/device fallback.')
        torch.cuda.manual_seed_all(42)
    return cfg, adapter


def function_axis(cfg, adapter):
    import obonet
    # Reuse the author's annotation builder without executing its download/main.
    native_builder = module_from(Path(cfg['official_source_root']) / 'bin/download_GO_annotations.py',
                                 'qualified_native_GO_annotation_builder')
    from protnote.utils.data import remove_obsolete_from_string
    graph = obonet.read_obo(cfg['ontology']['file'], ignore_obsolete=False)
    terms, excluded = [], Counter()
    for go_id, row in graph.nodes(data=True):
        if not re.fullmatch(r'GO:\d{7}', go_id):
            excluded['not_GO_term'] += 1; continue
        if str(row.get('is_obsolete', 'false')).lower() == 'true':
            excluded['obsolete'] += 1; continue
        if not isinstance(row.get('name'), str) or not row['name'].strip():
            excluded['missing_name'] += 1; continue
        if not isinstance(row.get('def'), str) or not row['def'].strip():
            excluded['missing_definition'] += 1; continue
        label = native_builder.calculate_label(row)
        if not label:
            excluded['empty_native_cleaned_definition'] += 1; continue
        term = adapter.FunctionText(go_id, row['name'], row['def'])
        expected = [f'Instruct: {adapter.E5_TASK}\nQuery: {remove_obsolete_from_string(text)}'
                    for text in (row['name'], label)]
        need(adapter.axis_texts([term]) == expected, 'Adapter text preparation differs from native builder.')
        terms.append(term)
    axis = adapter.fixed_function_axis(terms)
    need(len(axis) > 4, 'Whole nonobsolete GO axis is unexpectedly empty/small.')
    return axis, {'eligible_nonobsolete_GO_terms': len(axis), 'description_rows': 2 * len(axis),
        'excluded_ontology_nodes': dict(excluded), 'ontology_file_sha256': cfg['ontology']['sha256'],
        'axis_sha256': adapter.axis_sha256(axis, cfg['ontology']['sha256']),
        'defined_from_ontology_only': True, 'benchmark_TOI_or_target_labels_used': False}


def source_pins(cfg):
    source = Path(cfg['official_source_root'])
    token_path = Path(cfg['tokenizer_directory'])
    result = {str((source / name).resolve()): expected for name, expected in cfg['official_source_files'].items()}
    result.update({str((token_path / name).resolve()): expected for name, expected in cfg['tokenizer_files'].items()})
    for name in ('adapter', 'implementation', 'checkpoint', 'ontology', 'targets', 'dated_fasta'):
        result[str(Path(cfg[name]['file']).resolve())] = cfg[name]['sha256']
    return result


def fixed_targets(cfg):
    targets = check_pin(cfg['targets']).read_text().splitlines()
    need(len(targets) == len(set(targets)) == 547 and all(ACCESSION.fullmatch(x) for x in targets),
         'The full547 literal canonical target frame differs.')
    return targets


def qualify_inputs(cfg, adapter, axis, metadata, output):
    targets = fixed_targets(cfg); check_pin(cfg['dated_fasta'])
    go_ids = [term.go_id for term in axis]
    write(output / 'input_qualification.json', {
        'format': 'biograph-steward.protnote-development.v1.input-qualification',
        'created_at': datetime.now(timezone.utc).isoformat(), 'ordered_target_ids': targets,
        'axis_go_ids': go_ids, 'target_ids_sha256': digest(targets), 'go_ids_sha256': digest(go_ids),
        'ontology_sha256': cfg['ontology']['sha256'], 'axis_sha256': metadata['axis_sha256'],
        'source_files_sha256': source_pins(cfg), 'target_count': 547,
        'axis_defined_without_benchmark_TOI_or_target_labels': True,
        'reference_labels_read': False, 'model_forward_executed': False,
        'whole_dated_sequences_no_inferred_substitutions': True})


def verify_input_qualification(cfg, adapter, axis):
    value = read(cfg['producer_input_qualification']['file'], cfg['producer_input_qualification']['sha256'])
    targets = fixed_targets(cfg); go_ids = [term.go_id for term in axis]
    need(value['format'] == 'biograph-steward.protnote-development.v1.input-qualification'
         and value['ordered_target_ids'] == targets and value['axis_go_ids'] == go_ids
         and value['target_ids_sha256'] == cfg['expected_target_ids_sha256'] == digest(targets)
         and value['go_ids_sha256'] == cfg['expected_go_ids_sha256'] == digest(go_ids)
         and value['ontology_sha256'] == cfg['ontology']['sha256']
         and value['axis_sha256'] == adapter.axis_sha256(axis, cfg['ontology']['sha256'])
         and value['source_files_sha256'] == source_pins(cfg)
         and value['reference_labels_read'] is False and value['model_forward_executed'] is False
         and value['axis_defined_without_benchmark_TOI_or_target_labels'] is True,
         'Pre-forward source, original547 IDs or fixed complete GO axis changed.')
    return value


def engine(cfg, adapter):
    return adapter.NativeProtNote(checkpoint_path=Path(cfg['checkpoint']['file']),
        e5_config_path=Path(cfg['tokenizer_directory']) / 'config.json',
        checkpoint_sha256=cfg['checkpoint']['sha256'], device=cfg['device'])


def save_cache(cache, axis, cfg, config_sha, adapter, output):
    import torch
    body = output / 'label_cache.pt'
    torch.save(asdict(cache), body)
    value = {'format': FORMAT + '.cache', 'config_file_sha256': config_sha,
        'cache_body': {'file': str(body.resolve()), 'sha256': sha(body)},
        'axis_sha256': adapter.axis_sha256(axis, cfg['ontology']['sha256']),
        'ontology_file_sha256': cfg['ontology']['sha256'], 'checkpoint_sha256': cfg['checkpoint']['sha256'],
        'source_fingerprint': cache.source_fingerprint, 'tokenizer_fingerprint': cache.tokenizer_fingerprint,
        'shape': list(cache.embeddings.shape), 'dtype': str(cache.embeddings.dtype),
        'reference_labels_read': False, 'benchmark_TOI_used': False}
    write(output / 'cache_manifest.json', value)
    return output / 'cache_manifest.json'


def load_cache(path, expected, cfg, config_sha, axis, adapter):
    import torch
    value = read(path, expected)
    need(value['format'] == FORMAT + '.cache' and value['config_file_sha256'] == config_sha
         and value['axis_sha256'] == adapter.axis_sha256(axis, cfg['ontology']['sha256'])
         and value['ontology_file_sha256'] == cfg['ontology']['sha256']
         and value['checkpoint_sha256'] == cfg['checkpoint']['sha256']
         and value['reference_labels_read'] is False and value['benchmark_TOI_used'] is False,
         'Cache receipt was generated for another fixed source/axis.')
    body = check_pin(value['cache_body'])  # Verify bytes before interpreting torch serialization.
    payload = torch.load(body, map_location='cpu', weights_only=True)
    cache = adapter.LabelCache(**payload)
    need(cache.axis_sha256 == value['axis_sha256'] and cache.source_fingerprint == value['source_fingerprint']
         and cache.tokenizer_fingerprint == value['tokenizer_fingerprint']
         and tuple(cache.embeddings.shape) == tuple(value['shape']) == (2 * len(axis), 1024)
         and tuple(cache.go_ids) == tuple(t.go_id for t in axis)
         and str(cache.embeddings.dtype) == value['dtype'] and torch.isfinite(cache.embeddings).all(),
         'Serialized cache metadata, full axis or finite vectors differ.')
    return cache


def parity_receipt(path, expected, cfg, config_sha):
    value = read(path, expected)
    need(value['format'] == FORMAT + '.synthetic-parity' and value['config_file_sha256'] == config_sha
         and value['passed'] is True and value['synthetic_only'] is True
         and value['reference_labels_read'] is False
         and (not cfg['reuse_sequence_embeddings'] or value['cached_sequence_embeddings_bitwise_equal'] is True),
         'Required synthetic native/adaptor parity is absent or incompatible.')
    return value


def invoke_and_capture(model, function):
    pieces = []
    hook = model.register_forward_hook(lambda _module, _args, output: pieces.append(output[0].detach().cpu().clone()))
    try:
        probabilities = function()
    finally:
        hook.remove()
    need(pieces, 'Native full-model forward was not exercised.')
    import torch
    return probabilities, torch.cat(pieces, dim=1)[0]


def synthetic_header(value):
    from Bio import SeqIO
    from io import StringIO
    record = next(SeqIO.parse(StringIO(value), 'fasta'))
    # Biological labels elsewhere in description are deliberately not returned.
    return record.id, str(record.seq)


def run_parity(cfg, adapter, axis, config_sha, output):
    import torch
    import pandas as pd
    from transformers import AutoTokenizer
    from protnote.data.datasets import ProteinDataset
    from protnote.data.collators import collate_variable_sequence_length
    model = engine(cfg, adapter)
    # One full and one partial fixed1024-term chunk exercise sequence-feature
    # reuse across chunks, not just a single-call no-op scheduling change.
    small = tuple(axis[:cfg['label_pair_chunk'] + 1]); sequence = AA20 * 60
    cache = model.generate_label_cache(axis=small, ontology_sha256=cfg['ontology']['sha256'],
        tokenizer_path=Path(cfg['tokenizer_directory']), batch_size=cfg['text_batch'])
    need(not model.model.training, 'Native cache helper left the model in training mode.')
    manifest = save_cache(cache, small, cfg, config_sha, adapter, output)
    loaded = load_cache(manifest, sha(manifest), cfg, config_sha, small, adapter)
    need(torch.equal(cache.embeddings, loaded.embeddings), 'Serialized cache roundtrip changed vectors.')
    # The synthetic native Dataset uses exactly the same fixed small class axis.
    # Its multihot labels never enter either forward call or any loss function.
    texts = adapter.axis_texts(small)
    tokenizer = AutoTokenizer.from_pretrained(cfg['tokenizer_directory'], local_files_only=True)
    mapping = pd.DataFrame([{'id': row.go_id, 'description_type': kind,
        'description': text, 'token_count': len(tokenizer.tokenize(text))}
        for row, pair in zip(small, [texts[i:i+2] for i in range(0, len(texts), 2)])
        for kind, text in zip(('name', 'label'), pair)])
    native_embeddings = output / 'native_embeddings.pt'
    torch.save(cache.embeddings, native_embeddings)
    torch.save(mapping, output / 'native_embeddings_index.pt')
    fasta = output / 'synthetic.fasta'
    fasta.write_text('>SYNTHETIC_ONLY ' + ' '.join(t.go_id for t in small) + '\n' + sequence + '\n')
    native_config = {'params': {'AUGMENT_RESIDUE_PROBABILITY': 0,
        'LABEL_AUGMENTATION_DESCRIPTIONS': 'name+label', 'TEST_SUBSET_FRACTION': 1.,
        'INFERENCE_GO_DESCRIPTIONS': 'name+label', 'EXTRACT_VOCABULARIES_FROM': None,
        'DEDUPLICATE': False, 'MAX_SEQUENCE_LENGTH': None}, 'paths': {},
        'LABEL_EMBEDDING_PATH': str(native_embeddings)}
    dataset = ProteinDataset({'data_path': str(fasta), 'dataset_type': 'test'},
        native_config, logger=logging.getLogger('synthetic_native_parity'))
    need(dataset.amino_acid_vocabulary == list(AA20)
         and dataset.label_vocabulary == [t.go_id for t in small], 'Native dataset feature axis differs.')
    batch = collate_variable_sequence_length([dataset[0]], return_label_multihots=False)
    need('label_multihots' not in batch, 'Synthetic truth must not be supplied to forward.')
    onehots, lengths = model.sequence_features(sequence)
    need(torch.equal(onehots.cpu(), batch['sequence_onehots'])
         and torch.equal(lengths.cpu(), batch['sequence_lengths'])
         and torch.equal(cache.embeddings, batch['label_embeddings']), 'Native dataset/collator features differ.')
    native_logits, native_probabilities = [], []
    with torch.inference_mode():
        for start in range(0, len(small), cfg['label_pair_chunk']):
            with torch.cuda.amp.autocast(enabled=model.device.type == 'cuda'):
                logits, _ = model.model(sequence_onehots=batch['sequence_onehots'].to(model.device),
                    sequence_lengths=batch['sequence_lengths'].to(model.device),
                    label_embeddings=batch['label_embeddings'][2*start:2*(start+cfg['label_pair_chunk'])].to(model.device),
                    save_embeddings=False)
            native_logits.append(logits.detach().cpu())
            native_probabilities.append(torch.sigmoid(logits).detach().cpu())
    native_logits = torch.cat(native_logits, dim=1)[0]
    native_probabilities = torch.cat(native_probabilities, dim=1)[0]
    def predict(seq, *, active_cache=cache, reuse=False, active_axis=small):
        return model.predict_sequence(sequence=seq, axis=active_axis, cache=active_cache,
            ontology_sha256=cfg['ontology']['sha256'], label_chunk_size=cfg['label_pair_chunk'],
            reuse_sequence_embeddings=reuse)
    probabilities, logits = invoke_and_capture(model.model, lambda: predict(sequence))
    need(torch.equal(logits, native_logits) and torch.equal(probabilities, native_probabilities),
         'Native Dataset/adaptor same-cache/precision/chunk logits or probabilities differ.')
    headers = ['', ' '.join(t.go_id for t in reversed(small)), 'GO:9999998 GO:9999999']
    for header in headers:
        identity, unchanged = synthetic_header('>SYNTHETIC_ONLY ' + header + '\n' + sequence + '\n')
        need(identity == 'SYNTHETIC_ONLY' and unchanged == sequence, 'Header-only variation changed sequence or ID.')
        replay, replay_logits = invoke_and_capture(model.model, lambda: predict(unchanged))
        need(torch.equal(replay, probabilities) and torch.equal(replay_logits, logits),
             'Removed/permuted/unrelated header labels changed adapter predictions.')
    for wrong_axis, wrong_cache in ((tuple(reversed(small)), cache),
            (small, replace(cache, go_ids=tuple(reversed(cache.go_ids))))):
        entered = []
        hook = model.model.register_forward_hook(lambda *_args: entered.append(True))
        rejected = False
        try:
            predict(sequence, active_axis=wrong_axis, active_cache=wrong_cache)
        except ValueError:
            rejected = True
        finally:
            hook.remove()
        need(rejected and not entered, 'Reordered axis/cache was not rejected before forward.')
    # Serialized vector bytes are independently pinned, not trusted solely from
    # an internally consistent metadata/fingerprint object.
    body = output / 'label_cache.pt'; original_bytes = body.read_bytes()
    try:
        body.write_bytes(original_bytes[:-1] + bytes([original_bytes[-1] ^ 1]))
        rejected = False
        try:
            load_cache(manifest, sha(manifest), cfg, config_sha, small, adapter)
        except ValueError:
            rejected = True
        need(rejected, 'A changed serialized cache body was accepted.')
    finally:
        body.write_bytes(original_bytes)
    reuse_equal = False
    if cfg['reuse_sequence_embeddings']:
        reused, reused_logits = invoke_and_capture(model.model, lambda: predict(sequence, reuse=True))
        reuse_equal = torch.equal(reused, probabilities) and torch.equal(reused_logits, logits)
        need(reuse_equal, 'Optional native cached-sequence scheduling differs bitwise; stop without fallback.')
    write(output / 'parity.json', {'format': FORMAT + '.synthetic-parity',
        'config_file_sha256': config_sha, 'passed': True, 'synthetic_only': True,
        'synthetic_sequence_residues': len(sequence), 'synthetic_axis_rule': 'first1025_canonical_eligible_GO_ids',
        'native_same_chunk_plan': [1024, 1],
        'synthetic_axis_sha256': cache.axis_sha256, 'native_dataset_logits_and_probabilities_bitwise_equal': True,
        'native_dataset_collator_onehot_length_and_cache_bitwise_equal': True,
        'adapter_header_removal_permutation_unrelated_labels_invariant': True,
        'reordered_axis_cache_rejected_before_forward': True, 'changed_serialized_cache_body_rejected': True,
        'cached_sequence_embeddings_bitwise_equal': bool(reuse_equal),
        'reference_labels_read': False, 'benchmark_TOI_used': False,
        'cache_manifest_sha256': sha(manifest), 'device': cfg['device'], 'runtime': cfg['runtime']})


def target_records(cfg):
    from Bio import SeqIO
    targets = fixed_targets(cfg)
    path = check_pin(cfg['dated_fasta']); found = {}; ambiguous = set(); wanted = set(targets)
    with gzip.open(path, 'rt') as stream:
        for record in SeqIO.parse(stream, 'fasta'):
            pieces = record.id.split('|')
            if len(pieces) != 3 or pieces[1] not in wanted:
                continue
            accession = pieces[1]
            need(pieces[0] == 'sp' and re.search(r'(?:^| )OX=9606(?: |$)', record.description),
                 'Selected dated record is not canonical human Swiss-Prot.')
            if accession in found:
                ambiguous.add(accession)
            else:
                found[accession] = str(record.seq)
    return targets, found, ambiguous


def run_pilot(cfg, adapter, axis, config_sha, output, cache_path, cache_expected,
              protocol_expected, protocol_content_expected):
    import torch
    cache = load_cache(cache_path, cache_expected, cfg, config_sha, axis, adapter)
    targets, found, ambiguous = target_records(cfg)
    model = engine(cfg, adapter)
    rows = []; shared = {}; started = time.monotonic(); terms = [t.go_id for t in axis]
    forecast = output / 'all_go_native_probabilities.tsv.gz'
    with gzip.open(forecast, 'wt') as stream:
        for accession in targets:
            row = {'protein': accession, 'status': 'pending'}
            sequence = found.get(accession)
            if accession in ambiguous:
                row['status'] = 'abstain_ambiguous_dated_sequence'
            elif sequence is None or not sequence:
                row['status'] = 'abstain_missing_or_empty_dated_sequence'
            elif set(sequence) - set(AA20):
                row['status'] = 'abstain_noncanonical_sequence'
                row['residues'] = len(sequence)
            else:
                sequence_sha = hashlib.sha256(sequence.encode('ascii')).hexdigest()
                row.update(sequence_sha256=sequence_sha, residues=len(sequence), residues_passed_to_model=len(sequence))
                try:
                    if sequence_sha not in shared:
                        scores = model.predict_sequence(sequence=sequence, axis=axis, cache=cache,
                            ontology_sha256=cfg['ontology']['sha256'], label_chunk_size=cfg['label_pair_chunk'],
                            reuse_sequence_embeddings=cfg['reuse_sequence_embeddings'])
                        need(scores.numel() == len(axis) and torch.isfinite(scores).all()
                             and bool(((scores >= 0) & (scores <= 1)).all()), 'Missing/nonfinite/invalid native probabilities.')
                        shared[sequence_sha] = scores
                    scores = shared[sequence_sha]
                    # Python float exactly represents every native float16/32.
                    # .17g roundtrips without display cutoff or score rounding.
                    stream.writelines(f'{accession}\t{term}\t{float(value):.17g}\n'
                                      for term, value in zip(terms, scores.tolist()))
                    row.update(status='predicted', emitted_GO_terms=len(axis), native_score_dtype=str(scores.dtype))
                except (RuntimeError, ValueError) as error:
                    message = str(error).lower()
                    if 'out of memory' in message or 'cannot allocate memory' in message:
                        row['status'] = 'abstain_native_OOM'
                        if model.device.type == 'cuda': torch.cuda.empty_cache()
                    elif 'nonfinite' in message:
                        row['status'] = 'abstain_nonfinite_native_probabilities'
                    else:
                        raise
            rows.append(row)
            with (output / 'private_scope_ledger.jsonl').open('a') as ledger:
                ledger.write(json.dumps(row, sort_keys=True) + '\n')
    need([row['protein'] for row in rows] == targets and all(row['status'] != 'pending' for row in rows),
         'An original target identity was dropped or left unresolved.')
    counts = dict(Counter(row['status'] for row in rows))
    ledger = output / 'private_scope_ledger.jsonl'
    scorable = [row['protein'] for row in rows if row['status'] == 'predicted']
    unscorable = [{'id': row['protein'], 'reason': row['status']} for row in rows if row['status'] != 'predicted']
    inventory = output / 'private_inventory.json'
    write(inventory, {'format': 'biograph-steward.protnote-development.v1.private-inventory',
        'ordered_target_ids': targets, 'axis_go_ids': terms, 'scorable_ids': scorable,
        'unscorable': unscorable, 'forecast_rows': len(scorable) * len(terms),
        'ontology_sha256': cfg['ontology']['sha256'], 'axis_sha256': adapter.axis_sha256(axis, cfg['ontology']['sha256']),
        'target_ids_sha256': digest(targets), 'go_ids_sha256': digest(terms),
        'input_qualification_file_sha256': cfg['producer_input_qualification']['sha256'],
        'protocol_file_sha256': protocol_expected, 'reference_labels_read': False})
    write(output / 'predictions.json', {'format': 'biograph-steward.protnote-development.v1.predictions',
        'protocol_file_sha256': protocol_expected, 'protocol_content_sha256': protocol_content_expected,
        'config_file_sha256': config_sha,
        'all547_original_identities_accounted_for': True, 'reference_labels_read': False,
        'benchmark_TOI_used_for_prediction_axis': False, 'forecast': {
            'file': str(forecast.resolve()), 'sha256': sha(forecast), 'bytes': forecast.stat().st_size},
        'private_inventory': {'file': str(inventory.resolve()), 'sha256': sha(inventory)},
        'input_qualification': cfg['producer_input_qualification'],
        'source_files_sha256': {**source_pins(cfg), str(Path(cache_path).resolve()): cache_expected},
        'private_scope_ledger': {'file': str(ledger.resolve()), 'sha256': sha(ledger)},
        'axis_sha256': adapter.axis_sha256(axis, cfg['ontology']['sha256']), 'GO_terms': len(axis),
        'target_count': 547, 'status_counts': counts, 'unique_sequences_inferred': len(shared),
        'sequence_residues_truncated_or_substituted': False, 'missing_cases_removed_from_evaluation': False,
        'downstream_original_denominators_retained': True, 'probability_serialization': 'native values; .17g; no cutoff',
        'probability_calibration_or_ontology_propagation_in_producer': False,
        'cached_sequence_embeddings': cfg['reuse_sequence_embeddings'], 'cache_manifest_sha256': cache_expected,
        'runtime': cfg['runtime'], 'device': cfg['device'], 'seconds': time.monotonic() - started,
        'source_graph_or_app_modified': False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'expected', 'phase', 'output'):
        parser.add_argument('--' + name, required=True)
    for name in ('parity', 'parity-expected', 'cache-manifest', 'cache-expected',
                 'protocol-expected', 'protocol-content-expected'):
        parser.add_argument('--' + name)
    args = parser.parse_args()
    need(args.phase in ('qualify', 'parity', 'cache', 'pilot'), 'Unknown explicit phase.')
    cfg, adapter = config(args.config, args.expected, qualification_only=args.phase == 'qualify')
    output = Path(args.output)
    need(not output.exists(), 'Use a new private output directory.')
    output.mkdir(parents=True)
    write(output / 'STARTED.json', {'format': FORMAT + '.started', 'phase': args.phase,
        'config_file_sha256': args.expected, 'reference_labels_read': False,
        'created_at': datetime.now(timezone.utc).isoformat()})
    try:
        axis, metadata = function_axis(cfg, adapter)
        write(output / 'axis_metadata.json', metadata)
        if args.phase == 'qualify':
            need(not any((args.parity, args.parity_expected, args.cache_manifest, args.cache_expected,
                          args.protocol_expected, args.protocol_content_expected)),
                 'Pre-forward qualification never takes scoring, cache or scientific-evaluation input.')
            qualify_inputs(cfg, adapter, axis, metadata, output)
        else:
            verify_input_qualification(cfg, adapter, axis)
        if args.phase == 'parity':
            need(not any((args.parity, args.parity_expected, args.cache_manifest, args.cache_expected)),
                 'Synthetic parity does not take real target cache/receipt inputs.')
            run_parity(cfg, adapter, axis, args.expected, output)
        elif args.phase in ('cache', 'pilot'):
            need(args.parity and args.parity_expected, 'Successful same-config synthetic parity receipt required.')
            parity_receipt(args.parity, args.parity_expected, cfg, args.expected)
            if args.phase == 'cache':
                need(not args.cache_manifest and not args.cache_expected, 'Cache generation never loads an old cache.')
                model = engine(cfg, adapter)
                cache = model.generate_label_cache(axis=axis, ontology_sha256=cfg['ontology']['sha256'],
                    tokenizer_path=Path(cfg['tokenizer_directory']), batch_size=cfg['text_batch'])
                need(not model.model.training, 'Native text helper changed evaluation mode.')
                save_cache(cache, axis, cfg, args.expected, adapter, output)
            else:
                need(args.cache_manifest and args.cache_expected, 'Body-pinned full GO label cache required.')
                need(args.protocol_expected and args.protocol_content_expected
                     and re.fullmatch('[a-f0-9]{64}', args.protocol_expected)
                     and re.fullmatch('[a-f0-9]{64}', args.protocol_content_expected),
                     'Final scientific protocol FILE/content hash required as metadata-only scalars.')
                run_pilot(cfg, adapter, axis, args.expected, output, args.cache_manifest, args.cache_expected,
                          args.protocol_expected, args.protocol_content_expected)
        completion = {'format': FORMAT + '.complete', 'phase': args.phase,
            'config_file_sha256': args.expected, 'reference_labels_read': False}
        if args.phase == 'pilot':
            manifest = output / 'predictions.json'
            completion['prediction_manifest_file_sha256'] = sha(manifest)
            completion['prediction_manifest_content_sha256'] = json.loads(manifest.read_text())['content_sha256']
        write(output / 'DONE.json', completion)
    except BaseException as error:
        write(output / 'FAILURE.json', {'format': FORMAT + '.failure', 'phase': args.phase,
            'error_type': type(error).__name__, 'reference_labels_read': False,
            'partial_scores_not_admitted_for_comparison': True, 'automatic_fallback_or_denominator_change': False})
        raise


if __name__ == '__main__': main()
