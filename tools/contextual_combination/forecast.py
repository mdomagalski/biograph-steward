"""Extend two qualified, unchanged predictors to a fixed accession/sequence frame.

This is an inference/data adapter. It reuses the published DeepGO-SE extractor,
six-model heads and native CLI, and the published LocalPlus scorer on the
already frozen historical graph/seeds. It never imports a reference evaluator
or reads future annotation columns. Missing graph queries retain arithmetic
zeros and explicit coverage; those zeros are not biological negative labels.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output
from tools.deepgo_reference.archive import fingerprints, need, sealed
from tools.deepgo_reference.native import pinned, extract_features, predict_aspect
from tools.deepgo_reference.nonpk import copy_rows
from tools.deepgo_reference.run import (
    PARAMETERS, AUTHOR_ASPECT_ORDER, CODE_FILES, aspect_specs, author_and_heads,
    load as load_parent, read_seal, verify_sources, write_lines,
)
from tools.deepgo_reference.scores import native_rows, raw_rows

FORMAT = 'biograph-steward.fixed-frame-base-forecast.v1'


def ids(spec):
    values = pinned(spec).read_text().splitlines()
    need(values and values == sorted(set(values))
         and all(x.isalnum() and x.isascii() for x in values),
         'literal sorted unique bare-accession frame required.')
    return values


def fasta_records(path):
    """Read literal bare IDs without interpreting source description fields."""
    values = {}; accession = None; parts = []
    with Path(path).open() as stream:
        for row in stream:
            if row.startswith('>'):
                if accession is not None:
                    need(accession not in values, 'repeated FASTA accession.')
                    values[accession] = ''.join(parts)
                accession = row[1:].rstrip('\n')
                need(accession and accession.isascii() and accession.isalnum(),
                     'FASTA header must contain only its literal bare accession.')
                parts = []
            else:
                need(accession is not None, 'sequence before FASTA accession.')
                sequence = row.strip()
                need(sequence and sequence.isascii() and sequence.isalpha()
                     and sequence == sequence.upper(), 'invalid sequence row.')
                parts.append(sequence)
    if accession is not None:
        need(accession not in values, 'repeated FASTA accession.')
        values[accession] = ''.join(parts)
    need(values and all(values.values()), 'empty FASTA sequence/frame.')
    return values


def qualify_partition(all_ids, cached, old, sequences):
    """Full-sequence equality, rather than identity/prefix alone, permits reuse."""
    need(len(all_ids) == len(set(all_ids)) and len(cached) == len(set(cached))
         and set(cached) <= set(all_ids) and set(sequences) == set(all_ids),
         'complete disjoint fixed frame required.')
    compatible = sorted(p for p in all_ids if p in old and
                        old[p]['sequence_sha256'] == sequences[p]['sequence_sha256'])
    need(compatible == sorted(cached), 'cached scores require exact full-sequence equality.')
    return compatible, sorted(set(all_ids) - set(compatible))


def source_files():
    root = Path(__file__).resolve().parents[2]
    names = ['tools/contextual_combination/forecast.py',
             'tools/deepgo_reference/nonpk.py',
             'tools/cafa_prediction/core.py', 'tools/cafa_prediction/strict_alias_context.py',
             'tools/cafa_prediction/full_context.py', 'tools/cafa_prediction/run.py']
    names += ['tools/deepgo_reference/' + name for name in CODE_FILES]
    return {name: fingerprints(root / name)['sha256'] for name in sorted(set(names))}


def prepare(config, output):
    config = Path(config); cfg = json.loads(config.read_text())
    need(cfg['format'] == FORMAT + '.inputs'
         and cfg['future_annotation_columns_read'] is False,
         'prediction-only fixed frame configuration required.')
    parent = load_parent(cfg['parent_frozen'], cfg['parent_protocol_sha256'])
    _, _, _, _, _ = verify_sources(parent['inputs'])
    all_ids = ids(cfg['targets']); cached = ids(cfg['cached_targets'])
    records = json.loads(pinned(cfg['sequence_records']).read_text())
    old = json.loads(pinned(cfg['old_sequence_records']).read_text())
    cached, fresh = qualify_partition(all_ids, cached, old, records)
    need((len(all_ids), len(cached), len(fresh)) ==
         tuple(cfg['expected_counts'][k] for k in ('all', 'cached', 'fresh')),
         'frozen accession/sequence partition differs.')
    full_fasta = fasta_records(pinned(cfg['all_fasta']))
    new_fasta = fasta_records(pinned(cfg['fresh_fasta']))
    need(set(full_fasta) == set(all_ids) and set(new_fasta) == set(fresh),
         'FASTA identities differ from frozen complete/novel frames.')
    for p, sequence in full_fasta.items():
        need(hashlib.sha256(sequence.encode()).hexdigest() == records[p]['sequence_sha256']
             and hashlib.sha256(sequence[:1022].encode()).hexdigest() ==
             records[p]['native_first1022_sha256'], 'T0 sequence/prefix hash differs.')
        need(p not in new_fasta or new_fasta[p] == sequence, 'fresh FASTA differs from T0 sequence.')
    pinned(cfg['reference_qualification'])  # Metadata receipt only; no term/TOI file is opened.
    parent_ids = set(Path(parent['inputs']['primary_targets']['file']).read_text().splitlines())
    parent_ids.update(Path(parent['inputs']['reserved_targets']['file']).read_text().splitlines())
    nonpk = read_seal(pinned(cfg['nonpk_protocol']))
    need(nonpk['parent_runtime'] == parent['runtime']
         and nonpk['inputs']['parent_protocol_sha256'] == cfg['parent_protocol_sha256'],
         'qualified nonPK forecast lineage differs.')
    groups = {'parent': sorted(set(cached) & parent_ids),
              'nonpk': sorted(set(cached) - parent_ids)}
    need(set(groups['nonpk']) <= set(nonpk['new_target_ids']),
         'cached identity absent from the exact previously inferred frame.')
    need(set(cfg['old_deepgo_manifests']) == set(groups), 'both qualified cache source manifests required.')
    for role, spec in cfg['old_deepgo_manifests'].items():
        manifest = read_seal(pinned(spec))
        need(role in groups and manifest['runtime'] == parent['runtime'],
             'qualified cached runtime differs.')
        for name, pin in manifest['files'].items():
            need(Path(name).name == name and fingerprints(Path(spec['file']).parent / name) == pin,
                 'immutable cached raw score file differs.')
    from tools.cafa_prediction import strict_alias_context
    strict = strict_alias_context.load_packet(cfg['strict_frozen'], cfg['strict_protocol_sha256'])
    pinned(cfg['localplus_author_receipt'])
    for spec in cfg['old_localplus_files']:
        pinned(spec)
    out = new_output(output, config, cfg['parent_frozen'], cfg['strict_frozen'])
    value = sealed({'format': FORMAT + '.freeze', 'created_at': utcnow(), 'inputs': cfg,
        'configuration_sha256': fingerprints(config)['sha256'],
        'source_files_sha256': source_files(), 'parameters': PARAMETERS,
        'parent_runtime': parent['runtime'], 'target_ids': all_ids,
        'cached_target_ids': cached, 'fresh_target_ids': fresh,
        'cached_source_groups': groups,
        'strict_graph_sha256': strict['files']['graph.json.gz'],
        'strict_training_sha256': strict['files']['training.json.gz'],
        'all_denominators_retained': True, 'future_annotation_columns_read': False,
        'model_graph_precision_or_threshold_changed': False,
        'localplus_missing_node_policy': 'retain the target with an all-zero arithmetic vector and explicit absent-node coverage',
        'status': 'ready'})
    write_json(out / 'protocol.json', value)
    return value


def load(frozen, expected):
    path = Path(frozen) / 'protocol.json'
    need(fingerprints(path)['sha256'] == expected, 'forecast protocol FILE differs.')
    value = read_seal(path, FORMAT + '.freeze')
    need(value['source_files_sha256'] == source_files() and value['parameters'] == PARAMETERS
         and value['future_annotation_columns_read'] is False
         and value['all_denominators_retained'] is True and value['status'] == 'ready',
         'frozen producer defaults/source/label boundary differs.')
    for key in ('targets', 'cached_targets', 'sequence_records', 'old_sequence_records',
                'all_fasta', 'fresh_fasta', 'reference_qualification', 'nonpk_protocol'):
        pinned(value['inputs'][key])
    return value


def predict_deepgo(frozen, expected, output):
    import torch
    policy = load(frozen, expected); cfg = policy['inputs']
    parent = load_parent(cfg['parent_frozen'], cfg['parent_protocol_sha256'])
    need(parent['runtime'] == policy['parent_runtime'], 'native runtime differs.')
    model, _, _, _, _ = verify_sources(parent['inputs'])
    author, heads = author_and_heads(parent['inputs'], model)
    out = new_output(output, frozen)
    need(shutil.disk_usage(out).free >= 16 * 1024**3, '16GiB task disk required.')
    fasta = out / 'fresh_targets.fasta'; shutil.copyfile(pinned(cfg['fresh_fasta']), fasta)
    feature = out / 'fresh_targets_esm.pkl'; fresh = policy['fresh_target_ids']
    _, data = extract_features(author, {'file': str(fasta), 'sha256': cfg['fresh_fasta']['sha256']},
        parent['inputs']['esm_model'], parent['inputs']['esm_regression'], feature,
        device='cuda:0', expected_ids=fresh)
    del data; torch.cuda.empty_cache()
    feature_pin = {'file': str(feature), 'sha256': fingerprints(feature)['sha256']}
    command = [sys.executable, str(Path(parent['inputs']['author_root']) / 'predict.py'),
               '--in-file', str(fasta), '--data-root', str(Path(parent['inputs']['modelview']['file']).parent),
               '--device', 'cuda:0']
    with (out / 'native_cli.log').open('xb') as log:
        subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=True)
    pinned(feature_pin)
    manifests = {role: read_seal(pinned(spec)) for role, spec in cfg['old_deepgo_manifests'].items()}
    files = {}; checks = {}; counts_by_aspect = {}
    for aspect in AUTHOR_ASPECT_ORDER:
        terms, forms, checkpoints = aspect_specs(parent['inputs'], model, aspect)
        proteins, terms, scores = predict_aspect(author, feature_pin, terms, forms, checkpoints,
            aspect, device='cuda:0', expected_ids=fresh)
        presented = native_rows(proteins, terms, scores); count = 0
        with gzip.open(out / ('fresh_targets_preds_' + aspect + '.tsv.gz'), 'rt') as stream:
            for line in stream:
                need(line == next(presented, None), 'unchanged native CLI presentation differs.')
                count += 1
        need(next(presented, None) is None, 'native CLI omits adapter-presented rows.')
        checks[aspect] = {'all_fresh_native_CLI_rows_exact': True, 'presented_rows': count}
        fresh_raw = out / ('fresh_deepgose_' + aspect + '.tsv.gz')
        write_lines(fresh_raw, raw_rows(proteins, terms, scores)); del scores
        totals = Counter(); target = out / ('deepgose_' + aspect + '.tsv.gz')
        with gzip.GzipFile(filename=str(target), mode='wb', mtime=0) as destination:
            copy_rows(fresh_raw, set(fresh), terms, destination, totals)
            for role, manifest in manifests.items():
                wanted = set(policy['cached_source_groups'][role])
                for name, spec in manifest['files'].items():
                    if not name.endswith('_' + aspect + '.tsv.gz'):
                        continue
                    source = Path(cfg['old_deepgo_manifests'][role]['file']).parent / name
                    need(fingerprints(source) == spec, 'cached raw forecasts differ before literal copy.')
                    copy_rows(source, wanted, terms, destination, totals)
                    need(fingerprints(source) == spec, 'cached raw forecasts changed during literal copy.')
        need(set(totals) == set(policy['target_ids']) and all(n == len(terms) for n in totals.values()),
             'complete accession/head forecast frame must be retained.')
        files[target.name] = fingerprints(target); counts_by_aspect[aspect] = sum(totals.values())
        write_json(out / 'progress.json', {'aspect_completed': aspect, 'rows': counts_by_aspect,
                   'native_CLI_checks': checks, 'future_annotation_columns_read': False})
    load(frozen, expected); pinned(feature_pin)
    result = sealed({'format': FORMAT + '.deepgo-predictions', 'created_at': utcnow(),
        'protocol_file_sha256': expected, 'protocol_content_sha256': policy['content_sha256'],
        'target_count': len(policy['target_ids']), 'fresh_inference_targets': len(fresh),
        'literal_cached_targets': len(policy['cached_target_ids']), 'heads': heads,
        'feature_cache': feature_pin, 'native_CLI_checks': checks, 'files': files,
        'raw_rows': counts_by_aspect, 'all_denominators_retained': True,
        'future_annotation_columns_read': False, 'model_graph_precision_or_threshold_changed': False,
        'runtime': parent['runtime']})
    write_json(out / 'predictions.json', result)
    return result


def saved_sparse_scores(sources, wanted):
    """Retain native arithmetic, tolerating only identical repeated old cells."""
    result = {}
    for spec in sources:
        source = pinned(spec)
        with gzip.open(source, 'rt') as stream:
            for line in stream:
                fields = line.rstrip('\n').split('\t')
                need(len(fields) == 3, 'malformed historical score row.')
                p, term, raw = fields
                if p not in wanted:
                    continue
                value = float(raw)
                need(math.isfinite(value) and 0 < value <= 1 + 1e-10, 'invalid historical sparse LocalPlus score.')
                key = p, term
                need(key not in result or result[key] == value, 'historical LocalPlus duplicate disagrees.')
                result[key] = value
    return result


def query_frame(targets, index):
    """No denominator filtering when an accession is absent from the old graph."""
    present = [p for p in targets if p in index]
    missing = [p for p in targets if p not in index]
    return present, missing


def predict_localplus(frozen, expected, output):
    import numpy as np
    from tools.cafa_prediction import core, strict_alias_context
    from tools.cafa_prediction.run import read
    policy = load(frozen, expected); cfg = policy['inputs']
    strict = strict_alias_context.load_packet(cfg['strict_frozen'], cfg['strict_protocol_sha256'])
    root = Path(cfg['strict_frozen'])
    need(strict['files']['graph.json.gz'] == policy['strict_graph_sha256']
         and strict['files']['training.json.gz'] == policy['strict_training_sha256'],
         'historical LocalPlus topology or seeds differ.')
    pinned(cfg['localplus_author_receipt'])
    modules = core.author_modules(cfg['localplus_author'], cfg['localplus_author_receipt']['file'])
    graph = read(root / 'graph.json.gz'); index = {n.removeprefix('UniProtKB:'): i for i, n in enumerate(graph['nodes'])}
    P = modules['alg_utils'].normalizeGraphEdgeWeights(core.adjacency(graph['nodes'], graph['pairs']))
    del graph
    targets = policy['target_ids']; present, missing = query_frame(targets, index)
    indices = np.asarray([index[p] for p in present], dtype=int)
    terms = defaultdict(list)
    for p, entries in read(root / 'training.json.gz').items():
        for aspect, term in entries:
            terms[aspect, term].append(index[p])
    old_target_ids = set()
    for key in ('primary_targets.txt', 'reserved_targets.txt'):
        old_target_ids.update((root / key).read_text().splitlines())
    old_target_ids.update(read_seal(pinned(cfg['nonpk_protocol']))['new_target_ids'])
    overlap = set(targets) & old_target_ids
    previous = saved_sparse_scores(cfg['old_localplus_files'], overlap)
    out = new_output(output, frozen); rows = 0; replayed = 0
    (out / 'targets.txt').write_text('\n'.join(targets) + '\n')
    with gzip.GzipFile(filename=str(out / 'localplus.tsv.gz'), mode='wb', mtime=0) as destination:
        for step, ((aspect, term), positive) in enumerate(sorted(terms.items()), 1):
            scores, _ = core.run_term(modules, P, None, positive, 'localplus')
            for p, value in zip(present, scores[indices]):
                value = float(value)
                if p in overlap:
                    need(value == previous.pop((p, term), 0.), 'new query changes an existing LocalPlus score.')
                    replayed += 1
                if value > 0:
                    destination.write(f'{p}\t{term}\t{value:.17g}\n'.encode('ascii')); rows += 1
            if step % 2000 == 0:
                print(json.dumps({'terms': step, 'total': len(terms), 'future_annotation_columns_read': False}), flush=True)
    need(not previous, 'old LocalPlus scores contain a head omitted by the unchanged predictor.')
    load(frozen, expected)
    result = sealed({'format': FORMAT + '.localplus-predictions', 'created_at': utcnow(),
        'protocol_file_sha256': expected, 'protocol_content_sha256': policy['content_sha256'],
        'target_count': len(targets), 'graph_present_targets': len(present),
        'graph_absent_targets': missing, 'arithmetic_zero_target_ids': missing,
        'head_count': len(terms), 'positive_rows': rows,
        'old_target_score_parity': {'targets': len(overlap), 'cells_replayed': replayed, 'exact': True},
        'files': {p.name: fingerprints(p) for p in out.iterdir() if p.is_file()},
        'all_denominators_retained': True, 'future_annotation_columns_read': False,
        'model_graph_precision_or_threshold_changed': False})
    write_json(out / 'predictions.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    for name in ('config', 'output'): p.add_argument('--' + name, required=True)
    for command in ('predict_deepgo', 'predict_localplus'):
        p = sub.add_parser(command)
        for name in ('frozen', 'expected', 'output'): p.add_argument('--' + name, required=True)
    args = vars(parser.parse_args()); result = globals()[args.pop('command')](**args)
    print(json.dumps({'format': result['format'], 'status': result.get('status', 'complete'),
                      'content_sha256': result['content_sha256']}))
