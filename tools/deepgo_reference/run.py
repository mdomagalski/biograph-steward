"""Source-frozen DEVELOPMENT reuse of the published DeepGO-SE predictor.

Only existing PK target IDs, dated sequences, public checkpoints and ontology
metadata enter this producer. Labels and native evaluation are separate steps.
The actual author CLI must pass three-aspect presentation parity before a full
forecast is admitted. This does not reproduce author training or graph models.
"""
import argparse
import gzip
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output
from .archive import fingerprints, need, sealed
from .modelview import selected_paths, MAIN_MD5, CC_MD5
from .native import pinned, author_modules, extract_features, predict_aspect
from .scores import AUTHOR_ASPECT_ORDER, ENSEMBLES, NAMESPACES, raw_rows, native_rows
from .sequences import frame

FORMAT = 'biograph-steward.deepgo-development.v1'
PARAMETERS = {'execution_device': 'cuda:0', 'author_aspect_order': list(AUTHOR_ASPECT_ORDER),
    'ensembles': {key: list(value) for key, value in ENSEMBLES.items()},
    'feature_model': 'esm2_t36_3B_UR50D', 'feature_layer': 36,
    'feature_pooling': 'native mean of residue tokens', 'feature_dimensions': 2560,
    'native_first_residues': 1022, 'feature_tokens_per_batch': 4096,
    'prediction_batch_size': 32, 'ensemble_dtype': 'float32',
    'native_display_threshold': 0.1, 'native_display_decimals': 3,
    'score_export': 'all raw cells,17 significant digits,before native presentation',
    'score_propagation_in_producer': False, 'calibration_or_threshold_fitting': False}
CODE_FILES = ('__init__.py', 'archive.py', 'modelview.py', 'native.py', 'scores.py', 'sequences.py', 'run.py')
EXPECTED_VERSIONS = {'torch': '2.0.1', 'dgl': '1.1.2', 'fair-esm': '2.0.0',
    'numpy': '1.26.1', 'pandas': '1.5.0', 'scipy': '1.11.3', 'biopython': '1.81'}


def read_seal(path, format_value=None):
    value = json.loads(Path(path).read_text())
    need(value.get('content_sha256') == digest({k: v for k, v in value.items() if k != 'content_sha256'}),
         'content seal differs: ' + Path(path).name)
    if format_value:
        need(value['format'] == format_value, 'content format differs.')
    return value


def runtime():
    import torch
    versions = {name: importlib.metadata.version(name) for name in EXPECTED_VERSIONS}
    need(all(versions[name].split('+')[0] == version for name, version in EXPECTED_VERSIONS.items()),
         'isolated author package versions differ.')
    need(platform.python_version_tuple()[:2] == ('3', '10') and platform.system() == 'Linux'
         and platform.machine() == 'x86_64' and torch.version.cuda == '11.7'
         and os.environ.get('DGLBACKEND') == 'pytorch' and versions['dgl'] == '1.1.2'
         and torch.get_default_dtype() == torch.float32,
         'isolated author platform/CUDA/backend differs.')
    return {'python': platform.python_version(), 'system': platform.system(), 'machine': platform.machine(),
        'packages': versions, 'torch_build_cuda': torch.version.cuda,
        'dgl_backend': os.environ.get('DGLBACKEND'), 'dgl_build_adaptation': 'official PyPI CPU1.1.2; no DGL graph instantiated',
        'torch_default_dtype': str(torch.get_default_dtype()),
        'torch_matmul_allow_tf32': torch.backends.cuda.matmul.allow_tf32,
        'torch_cudnn_allow_tf32': torch.backends.cudnn.allow_tf32,
        'thread_environment': {x: os.environ.get(x) for x in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')}}


def verify_sources(config):
    """All public source files are rehashed; no pickle/model is interpreted."""
    for name in ('code_intake', 'modelview', 'sequences', 'primary_targets', 'reserved_targets',
                 'esm_model', 'esm_regression', 'runtime_receipt', 'source_qualification', 'evaluation_plan'):
        pinned(config[name])
    model_file = Path(config['modelview']['file'])
    model = read_seal(model_file, 'biograph-steward.deepgo-derived-modelview.v1')
    need(set(model['files']) == selected_paths(('mf', 'bp'), True) | selected_paths(('cc',))
         and model['model_selection'] == PARAMETERS['ensembles']
         and model['cross_namespace_model_hash_overlap'] is False,
         'modelview membership differs.')
    for relative, spec in model['files'].items():
        need(fingerprints(model_file.parent / relative) == {key: spec[key] for key in ('bytes', 'sha256', 'md5')},
             'modelview file changed.')
        expected = CC_MD5 if relative.startswith('cc/') else MAIN_MD5
        need(spec['archive_md5'] == expected, 'checkpoint/term correction lineage differs.')
    sequence_file = Path(config['sequences']['file'])
    sequences = read_seal(sequence_file, 'biograph-steward.deepgo-dated-target-sequences.v1')
    primary = frame(config['primary_targets']['file'], config['primary_targets']['sha256'])
    reserved = frame(config['reserved_targets']['file'], config['reserved_targets']['sha256'])
    need(len(primary) == 1294 and len(reserved) == 4806 and not set(primary) & set(reserved),
         'fixed PK target frames differ.')
    need(sequences['primary_target_file_sha256'] == config['primary_targets']['sha256']
         and sequences['reserved_target_file_sha256'] == config['reserved_targets']['sha256']
         and sequences['fixed_targets'] == 6100 and sequences['current_sequence_fallback_used'] is False
         and sequences['missing_targets_removed_from_evaluation'] is False,
         'dated sequence/frame boundary differs.')
    covered = sorted(sequences['source_records'])
    need(set(covered) | set(sequences['missing_target_ids']) == set(primary) | set(reserved)
         and not set(covered) & set(sequences['missing_target_ids']) and len(covered) >= 3,
         'dated sequence coverage ledger differs.')
    fasta = sequence_file.parent / 'targets_2023_03.fasta'
    need(fingerprints(fasta) == sequences['staged_fasta'], 'staged literal FASTA differs.')
    return model, sequences, {'primary': primary, 'reserved': reserved}, covered, fasta


def prepare(config, output):
    config = Path(config); value = json.loads(config.read_text())
    need(value['format'] == FORMAT + '.inputs' and value['previous_CAFA_outcomes_exposed'] is True,
         'explicit consumed-reference development scope required.')
    model, sequences, frames, covered, fasta = verify_sources(value)
    actual_runtime = runtime()
    out = new_output(output, config)
    code = {name: fingerprints(Path(__file__).parent / name)['sha256'] for name in CODE_FILES}
    result = sealed({'format': FORMAT + '.freeze', 'created_at': utcnow(), 'inputs': value,
        'input_config': {'file': str(config.resolve()), **fingerprints(config)}, 'producer_files_sha256': code,
        'parameters': PARAMETERS, 'runtime': actual_runtime, 'target_counts': {k: len(v) for k, v in frames.items()},
        'sequence_covered': len(covered), 'sequence_missing': len(sequences['missing_target_ids']),
        'missing_sequence_policy': 'Retain all6100 evaluation denominators; no prediction emitted without exact dated sequence, no current replacement.',
        'fixture_policy': 'First three lexically ordered source-covered accessions; metadata-only selection, no label inspection.',
        'fixture_target_ids': covered[:3], 'prior_CAFA_reference_exposure': 'DEVELOPMENT reuse of the already released exact1294+4806 PK frames; not a fresh independent test.',
        'retention_gate': 'Paired95% lower difference bound>0 for both ordinary and IA BPO microFmax versus frozen full strict LocalPlus, separately in BOTH PK cohorts; retain every aspect, macro and fixed0.5 trade-off.',
        'all_six_cohort_aspect_outcomes_required': True, 'native_MLP_control': model['native_MLP_control'],
        'new_reference_release': False, 'graph_or_axiom_only_causal_effect_identified': False})
    write_json(out / 'protocol.json', result)
    return result


def load(frozen, expected):
    path = Path(frozen) / 'protocol.json'
    need(fingerprints(path)['sha256'] == expected, 'protocol FILE pin differs.')
    value = read_seal(path, FORMAT + '.freeze')
    need(value['parameters'] == PARAMETERS and value['all_six_cohort_aspect_outcomes_required'] is True,
         'frozen native defaults/scope differ.')
    for name, expected_sha in value['producer_files_sha256'].items():
        need(fingerprints(Path(__file__).parent / name)['sha256'] == expected_sha,
             'frozen producer source differs: ' + name)
    need(runtime() == value['runtime'], 'actual inference runtime differs from freeze.')
    return value


def author_and_heads(config, model):
    import pandas as pd
    import importlib
    author = author_modules(config['author_root'], config['code_intake'])
    utils = importlib.import_module('deepgo.utils')
    from .native import check_author_import_paths
    check_author_import_paths(config['author_root'])
    root = Path(config['modelview']['file']).parent
    ontology = utils.Ontology(str(root / 'go.obo'), with_rels=True)
    heads = {}
    for aspect in AUTHOR_ASPECT_ORDER:
        terms = pd.read_pickle(root / aspect / 'terms.pkl')['gos'].values.flatten()
        need(len(terms) == len(set(terms)) and len(terms) > 0, 'ordered native head identities repeat/empty.')
        need(all(ontology.has_term(x) and ontology.get_namespace(x) == NAMESPACES[aspect] for x in terms),
             'model heads absent from original ontology or wrong namespace.')
        heads[aspect] = {'count': len(terms), 'ordered_head_sha256': digest(list(terms)),
            'native_namespace': NAMESPACES[aspect]}
    return author, heads


def write_lines(path, lines):
    # Fixed gzip header: decompressed bytes, rather than compressed timestamps,
    # are the parity object. Predictions retain full-precision model values.
    with gzip.GzipFile(filename=str(path), mode='wb', mtime=0) as stream:
        for line in lines:
            stream.write(line.encode('ascii'))


def aspect_specs(config, model, aspect):
    root = Path(config['modelview']['file']).parent
    spec = lambda relative: {'file': str(root / relative), 'sha256': model['files'][relative]['sha256']}
    return spec(aspect + '/terms.pkl'), spec('go-plus.norm'), {
        i: spec(f'{aspect}/deepgozero_esm_plus_{i}.th') for i in ENSEMBLES[aspect]}


def parity(frozen, expected, output, device='cuda:0'):
    import torch
    from Bio import SeqIO
    protocol = load(frozen, expected); config = protocol['inputs']
    need(device == protocol['parameters']['execution_device'], 'selected device differs from frozen CUDA execution.')
    model, sequences, frames, covered, fasta = verify_sources(config)
    author, heads = author_and_heads(config, model)
    out = new_output(output, frozen)
    chosen = protocol['fixture_target_ids']; records = {}
    with fasta.open() as stream:
        for record in SeqIO.parse(stream, 'fasta'):
            if record.id in chosen: records[record.id] = record
    need(set(records) == set(chosen), 'native fixture source identities differ.')
    fixture = out / 'fixture.fasta'
    with fixture.open('w') as stream:
        SeqIO.write([records[x] for x in chosen], stream, 'fasta')
    feature = out / 'fixture_esm.pkl'
    proteins, data = extract_features(author, {'file': str(fixture), 'sha256': fingerprints(fixture)['sha256']},
        config['esm_model'], config['esm_regression'], feature, device=device, expected_ids=chosen)
    feature_pin = {'file': str(feature), 'sha256': fingerprints(feature)['sha256']}
    # Release only this process's unused allocator cache before the separate
    # unchanged CLI invocation. No model weights or computation mode changes.
    del data
    if torch.cuda.is_available(): torch.cuda.empty_cache()
    command = [sys.executable, str(Path(config['author_root']) / 'predict.py'), '--in-file', str(fixture),
        '--data-root', str(Path(config['modelview']['file']).parent), '--device', device]
    with (out / 'native_cli.log').open('wb') as log:
        status = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
    need(status.returncode == 0, 'unchanged author CLI failed; preserve native_cli.log.')
    need(fingerprints(feature)['sha256'] == feature_pin['sha256'], 'native CLI mutated the pinned shared fixture features.')
    checks = {}
    for aspect in AUTHOR_ASPECT_ORDER:
        terms, forms, checkpoints = aspect_specs(config, model, aspect)
        p, terms, scores = predict_aspect(author, feature_pin, terms, forms, checkpoints,
            aspect, device=device, expected_ids=chosen)
        native = out / f'fixture_preds_{aspect}.tsv.gz'
        need(native.is_file(), 'unchanged native CLI output missing.')
        expected_rows = native_rows(p, terms, scores); count = 0
        with gzip.open(native, 'rt') as stream:
            for actual in stream:
                target = next(expected_rows, None)
                need(actual == target, 'native CLI presentation differs from lossless adapter projection.')
                count += 1
        need(next(expected_rows, None) is None, 'adapter has extra native-presented rows.')
        checks[aspect] = {'decompressed_rows_exact': True, 'rows': count, 'native_file': fingerprints(native)}
    load(frozen, expected)
    result = sealed({'format': FORMAT + '.native-parity', 'created_at': utcnow(),
        'protocol_file_sha256': expected, 'protocol_content_sha256': protocol['content_sha256'],
        'fixed_target_ids': chosen, 'native_default_cutoff_and_format': '>=0.1;3decimals;unchanged author predict.py',
        'fixture_fasta': fingerprints(fixture), 'shared_native_features': feature_pin,
        'heads': heads, 'checks': checks, 'all_three_aspects_exact': True,
        'actual_author_CLI_executed': True, 'model_or_source_modified': False, 'execution_device': device,
        'reference_labels_read': False, 'runtime': protocol['runtime']})
    write_json(out / 'parity.json', result)
    return result


def predict(frozen, expected, parity_file, parity_sha256, output, device='cuda:0'):
    protocol = load(frozen, expected); config = protocol['inputs']
    need(device == protocol['parameters']['execution_device'], 'selected device differs from frozen CUDA execution.')
    parity_path = pinned({'file': parity_file, 'sha256': parity_sha256})
    proof = read_seal(parity_path, FORMAT + '.native-parity')
    need(proof['protocol_file_sha256'] == expected and proof['all_three_aspects_exact'] is True
         and proof['fixed_target_ids'] == protocol['fixture_target_ids']
         and proof['runtime'] == protocol['runtime'] and proof['execution_device'] == device,
         'native CLI fixture admission differs.')
    model, sequences, frames, covered, fasta = verify_sources(config)
    author, heads = author_and_heads(config, model)
    out = new_output(output, frozen, parity_path)
    need(shutil.disk_usage(out).free >= 8 * 1024**3, 'Require8GiB free; preserve existing artifacts.')
    start = time.time(); feature = out / 'targets_2023_03_esm.pkl'
    proteins, data = extract_features(author, {'file': str(fasta), 'sha256': sequences['staged_fasta']['sha256']},
        config['esm_model'], config['esm_regression'], feature, device=device, expected_ids=covered)
    feature_pin = {'file': str(feature), 'sha256': fingerprints(feature)['sha256']}
    del data
    files, rows = {}, {}
    for aspect in AUTHOR_ASPECT_ORDER:
        terms, forms, checkpoints = aspect_specs(config, model, aspect)
        ids, terms, scores = predict_aspect(author, feature_pin, terms, forms, checkpoints,
            aspect, device=device, expected_ids=covered)
        for frame_name, targets in frames.items():
            target_set = set(targets)
            indices = [i for i, protein in enumerate(ids) if protein in target_set]
            selected_ids = [ids[i] for i in indices]
            need(set(selected_ids) == set(targets) & set(covered), 'forecast frame projection differs.')
            name = f'{frame_name}_deepgose_{aspect}.tsv.gz'
            write_lines(out / name, raw_rows(selected_ids, terms, scores[indices]))
            files[name] = fingerprints(out / name)
            rows[name] = len(indices) * len(terms)
        write_json(out / 'progress.json', {'aspect_completed': aspect, 'raw_rows': rows,
            'wall_seconds': time.time() - start, 'reference_labels_read': False})
    load(frozen, expected); verify_sources(config)
    result = sealed({'format': FORMAT + '.predictions', 'created_at': utcnow(),
        'protocol_file_sha256': expected, 'protocol_content_sha256': protocol['content_sha256'],
        'native_parity_file': {'file': str(parity_path.resolve()), 'sha256': parity_sha256},
        'feature_cache': feature_pin, 'heads': heads, 'files': files, 'raw_rows': rows,
        'target_counts': {k: len(v) for k, v in frames.items()},
        'sequence_missing_target_ids': sequences['missing_target_ids'],
        'all_evaluation_denominators_retained': True, 'source_and_score_postprocessing': PARAMETERS,
        'wall_seconds': time.time() - start, 'runtime': protocol['runtime'],
        'development_exposed_reference_reuse': True, 'new_reference_labels_read': False,
        'MLP_control_unavailable': True, 'PPI_increment_or_axiom_only_effect_demonstrated': False})
    write_json(out / 'predictions.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    for key in ('config', 'output'): p.add_argument('--' + key, required=True)
    p = sub.add_parser('parity')
    for key in ('frozen', 'expected', 'output'): p.add_argument('--' + key, required=True)
    p.add_argument('--device', default='cuda:0')
    p = sub.add_parser('predict')
    for key in ('frozen', 'expected', 'parity-file', 'parity-sha256', 'output'): p.add_argument('--' + key, required=True)
    p.add_argument('--device', default='cuda:0')
    args = vars(parser.parse_args()); command = args.pop('command')
    result = globals()[command](**args)
    print(json.dumps({'format': result['format'], 'content_sha256': result['content_sha256']}))
