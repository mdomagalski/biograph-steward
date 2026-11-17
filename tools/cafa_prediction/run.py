"""Freeze historical inputs and execute published GO predictors without test truth."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import platform
import time

from .core import (ASPECTS, PARAMETERS, AUTHOR_COMMIT, RUNTIME, adjacency,
                   author_modules, graph_frame, need, ontology_terms,
                   run_term, sha, training_annotations)

FORMAT = 'biograph-steward.cafa5-prediction-freeze.v1'
RESULT = 'biograph-steward.cafa5-historical-predictions.v1'


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    import hashlib
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def write(path, value):
    path = Path(path)
    if path.suffix == '.gz':
        with gzip.GzipFile(filename=str(path), mode='wb', mtime=0) as stream:
            stream.write(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())
    else:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def read(path):
    path = Path(path)
    with (gzip.open(path, 'rt') if path.suffix == '.gz' else path.open()) as stream:
        return json.load(stream)


def pin(path):
    path = Path(path).resolve()
    need(path.is_file() and not path.is_symlink(), 'ordinary pinned file required.')
    return {'file': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def new_output(path):
    path = Path(path).resolve()
    need(not path.exists() and not path.is_symlink(), 'choose a new output path.')
    path.mkdir(parents=True)
    return path


def verify_pins(pins):
    for key, record in pins.items():
        path = Path(record['file'])
        need(path.is_file() and not path.is_symlink() and sha(path) == record['sha256'], 'bound input changed: ' + key)


def prepare(config_path, output):
    """Use t0 labels and opaque target identities; never read future GO columns."""
    config_path = Path(config_path).resolve()
    config = read(config_path)
    expected = {'network_nodes', 'weighted_pairs', 'network_qualification', 'known_t0',
                'ontology', 'targets', 'author_directory', 'author_receipt'}
    need(set(config) == expected, 'exact historical-input configuration required.')
    source_keys = expected - {'author_directory'}
    pins = {k: pin(config[k]) for k in sorted(source_keys)}
    pins['configuration'] = pin(config_path)
    pins['adapter_core'] = pin(Path(__file__).with_name('core.py'))
    pins['adapter_runner'] = pin(__file__)
    qualification = read(config['network_qualification'])
    need(qualification.get('format') == 'biograph-steward.qualified-historical-ranking-input.v1',
         'reviewed historical network qualification is required.')
    need(qualification['qualified_inputs_sha256']['weighted_pairs.tsv'] == pins['weighted_pairs']['sha256']
         and qualification['qualified_inputs_sha256']['network_nodes.tsv'] == pins['network_nodes']['sha256'],
         'weighted network differs from its exact historical qualification.')
    nodes, pairs = graph_frame(config['network_nodes'], config['weighted_pairs'])
    need(len(pairs) == qualification['qualified_weighted_pairs'], 'historical network count differs.')
    targets = Path(config['targets']).read_text().splitlines()
    need(targets and targets == sorted(set(targets)) and all('UniProtKB:' + t in set(nodes) for t in targets),
         'target file must be sorted unique exact graph accessions without a header.')
    ontology = ontology_terms(config['ontology'])
    labels, frequencies, counts = training_annotations(config['known_t0'], nodes, ontology)
    # Loading source and checking versions happens before any real prediction.
    author_modules(config['author_directory'], config['author_receipt'])
    receipt = read(config['author_receipt'])
    for name in receipt['files']:
        pins['author/' + name] = pin(Path(config['author_directory']) / name)
    verify_pins(pins)
    folder = new_output(output)
    write(folder / 'graph.json.gz', {'nodes': nodes, 'pairs': pairs})
    write(folder / 'training.json.gz', {p: sorted(v) for p, v in sorted(labels.items())})
    write(folder / 'frequencies.json.gz', frequencies)
    (folder / 'targets.txt').write_text('\n'.join(targets) + '\n')
    protocol = {'format': FORMAT, 'created_at': timestamp(), 'input_pins': pins,
        'files': {p.name: sha(p) for p in sorted(folder.iterdir())},
        'author_directory': str(Path(config['author_directory']).resolve()),
        'author_receipt': str(Path(config['author_receipt']).resolve()),
        'author_commit': AUTHOR_COMMIT, 'runtime': RUNTIME, 'python': platform.python_version(),
        'methods': {**PARAMETERS,
            'known_frequency': {'denominator': 'all known_t0 proteins annotated in the same aspect'},
            'cohort_frequency': {'denominator': 'historical graph proteins with known_t0 annotations in the same aspect'}},
        'primary': {'reference': 'CAFA5 author partial-knowledge 2025_03 labels', 'aspect': 'BPO',
            'target_scope': 'all exact historical graph proteins in author PK target identity union',
            'future_GO_labels_opened': False, 'hyperparameter_search': False,
            'candidate': 'fastsinksourceplus',
            'comparison': 'FSSplus must outperform native weighted LocalPlus, cohort frequency and the fixed official CAFA5 Naive and BLAST comparators; missing official baselines prevent a full positive claim.',
            'metric': 'Official CAFA5 partial-knowledge BPO micro Fmax; benchmark-optimal threshold is not deployment probability calibration.'},
        'secondary': ['MFO partial knowledge', 'CCO partial knowledge', 'fixed GeneMANIAPlus comparison; never substitute it for the primary candidate after outcomes'],
        'additional_official_baselines': {'source': 'author CAFA5 Zenodo 22381862 v2 baselines archive',
            'methods': ['CAFA5 Naive', 'CAFA5 BLAST'],
            'rule': 'Source/version/member pins are sealed separately before opening future GO labels. These fixed baseline scores cannot tune model parameters.'},
        'source_versions': {'network': 'exact qualified STRING v11 December 2018 weights',
            'labels': 'author known_t0 UniProt2023_03 at CAFA5 prediction deadline',
            'ontology': 'author CAFA5 GO 2023-01-01'},
        'counts': {**counts, 'graph_nodes': len(nodes), 'weighted_pairs': len(pairs), 'target_IDs': len(targets),
            'graph_training_terms_by_aspect': dict(Counter(a for a, t in {entry for entries in labels.values() for entry in entries}))},
        'score_format': 'gzip TSV accession, GO ID, full float64 score; all strictly positive scores, no header; no score threshold tuning',
        'known_label_handling': 'Known t0 target annotations are permitted PK inputs and remain in predictions; official evaluator removes them.',
        'scope_limits': ['Retrospective timed-annotation recovery on a fixed cancer-enriched graph, not a CAFA competition submission or whole-proteome estimate.',
            'Current2026 GOA and PharosGO annotations are not features. Earlier source investigations and studied genes remain disclosed.',
            'Unannotated pairs are not asserted biologically false. Published CAFA reference-based metrics do not certify every prediction.',
            'Published FastSinkSource/GeneMANIA transfer from their study to this task is being tested, not assumed.',
            'The separate GPL3 implementation is executed unchanged; no GPL source is bundled with the MIT application.']}
    protocol['content_sha256'] = digest(protocol)
    write(folder / 'protocol.json', protocol)
    return protocol


def load_frozen(folder, protocol_sha256):
    folder = Path(folder)
    protocol = read(folder / 'protocol.json')
    need(sha(folder / 'protocol.json') == protocol_sha256 and protocol.get('format') == FORMAT,
         'explicit frozen protocol file pin differs.')
    need(protocol['content_sha256'] == digest({k: v for k, v in protocol.items() if k != 'content_sha256'}),
         'frozen protocol content seal differs.')
    need({p.name for p in folder.iterdir()} == {'protocol.json', *protocol['files']}, 'frozen directory inventory differs.')
    for name, expected in protocol['files'].items():
        need(sha(folder / name) == expected, 'frozen preparation file changed: ' + name)
    verify_pins(protocol['input_pins'])
    return protocol


def predict(frozen, protocol_sha256, output):
    import numpy as np
    frozen = Path(frozen)
    protocol = load_frozen(frozen, protocol_sha256)
    modules = author_modules(protocol['author_directory'], protocol['author_receipt'])
    graph = read(frozen / 'graph.json.gz')
    labels = read(frozen / 'training.json.gz')
    frequency = read(frozen / 'frequencies.json.gz')
    targets = (frozen / 'targets.txt').read_text().splitlines()
    nodes, pairs = graph['nodes'], graph['pairs']
    index = {p.split(':', 1)[1]: i for i, p in enumerate(nodes)}
    target_index = np.asarray([index[p] for p in targets], dtype=int)
    W = adjacency(nodes, pairs)
    P = modules['alg_utils'].normalizeGraphEdgeWeights(W)
    L = modules['gm'].setup_laplacian(W)
    by_term = defaultdict(list)
    for protein, entries in labels.items():
        for aspect, term in entries:
            by_term[(aspect, term)].append(index[protein])
    cohort_denominators = Counter()
    for entries in labels.values():
        cohort_denominators.update({a for a, _ in entries})
    folder = new_output(output)
    write(folder / 'execution_started.json', {'protocol_file_sha256': protocol_sha256,
        'protocol_content_sha256': protocol['content_sha256'], 'created_at': timestamp(),
        'future_GO_labels_read': False, 'methods': protocol['methods']})
    diagnostics = []
    for method in PARAMETERS:
        start = time.time(); emitted, unknown_scores = 0, 0
        path = folder / (method + '.tsv.gz')
        with gzip.GzipFile(filename=str(path), mode='wb', mtime=0) as stream:
            for step, ((aspect, term), positive) in enumerate(sorted(by_term.items()), 1):
                scores, diagnostic = run_term(modules, P, L, positive, method)
                for protein, value in zip(targets, scores[target_index]):
                    if value > 0:
                        stream.write((protein + '\t' + term + '\t' + format(float(value), '.17g') + '\n').encode())
                        emitted += 1
                    else:
                        unknown_scores += 1
                diagnostics.append({'method': method, 'aspect': aspect, 'term': term,
                                    'historical_positives': len(positive), **diagnostic})
                if step % 1000 == 0:
                    print(json.dumps({'method': method, 'terms_finished': step, 'total_terms': len(by_term),
                                      'seconds': time.time() - start}), flush=True)
        print(json.dumps({'method': method, 'scores_emitted': emitted, 'zero_or_nonpositive_scores': unknown_scores,
                          'seconds': time.time() - start}), flush=True)
    with gzip.GzipFile(filename=str(folder / 'known_frequency.tsv.gz'), mode='wb', mtime=0) as stream:
        for aspect in sorted(frequency):
            for term, value in sorted(frequency[aspect].items()):
                for protein in targets:
                    stream.write((protein + '\t' + term + '\t' + format(value, '.17g') + '\n').encode())
    with gzip.GzipFile(filename=str(folder / 'cohort_frequency.tsv.gz'), mode='wb', mtime=0) as stream:
        for (aspect, term), positive in sorted(by_term.items()):
            value = len(positive) / cohort_denominators[aspect]
            for protein in targets:
                stream.write((protein + '\t' + term + '\t' + format(value, '.17g') + '\n').encode())
    write(folder / 'algorithm_diagnostics.json.gz', diagnostics)
    load_frozen(frozen, protocol_sha256)
    manifest = {'format': RESULT, 'created_at': timestamp(),
        'protocol_file_sha256': protocol_sha256, 'protocol_content_sha256': protocol['content_sha256'],
        'target_IDs': len(targets), 'graph_nodes': len(nodes), 'weighted_pairs': len(pairs),
        'fitted_on_future_annotations': False, 'future_GO_labels_read': False,
        'model_calls': 0, 'source_fetches': 0,
        'files': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(folder.iterdir())}}
    manifest['content_sha256'] = digest(manifest)
    write(folder / 'predictions.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--config', required=True); p.add_argument('--output', required=True)
    p = sub.add_parser('predict'); p.add_argument('--frozen', required=True); p.add_argument('--protocol-sha256', required=True); p.add_argument('--output', required=True)
    args = vars(parser.parse_args()); command = args.pop('command')
    result = prepare(args['config'], args['output']) if command == 'prepare' else predict(args['frozen'], args['protocol_sha256'], args['output'])
    print(json.dumps({k: result[k] for k in ('format', 'content_sha256')}, indent=2))


if __name__ == '__main__':
    main()
