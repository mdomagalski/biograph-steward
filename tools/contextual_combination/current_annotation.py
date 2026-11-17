# SPDX-License-Identifier: GPL-3.0-only
"""A current-T0 annotation control using two unchanged published pipelines.

The dated reviewed-human repertoire is constructed with the pinned democafa
filter/retrieve/propagate commands. It replaces, rather than unions, historical
seeds. The existing strict graph and published LocalPlus scorer are unchanged.
Only final-reference identities may be queried: this newer snapshot cannot be
used for earlier consumed-validation evaluation or model selection.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.learned_combination.core import need
from tools.learned_combination.reference import file_sha256, gaf_header, read_target_ids
from .prepare import _check_path, write_json

ARM = 'localplus_T0_curated'
ASPECT = {'P': 'biological_process', 'F': 'molecular_function', 'C': 'cellular_component'}


def load_config(path):
    cfg = json.loads(Path(path).read_text())
    need(cfg['format'] == 'biograph-steward.current-T0-curated-control.v1'
         and cfg['fresh_final_reference_opened'] is False
         and cfg['forecast_role'] == 'final' and cfg['expected_final_count'] == 3300,
         'current-T0 control is final3300-only, with the fresh reference closed.')
    need(cfg['gaf_generated_date'] == '2026-04-10'
         and cfg['native_evidence_selection'] == 'Experimental,IC,TAS'
         and cfg['historical_seed_union'] is False,
         'the one frozen current-T0 snapshot/admission policy is required.')
    required = {cfg[k] for k in ('graph', 'gaf', 'reviewed_human_fasta', 'ontology',
                'final_ids', 'localplus_author_receipt')}
    required.update(cfg['native_source_files'])
    need(required <= set(cfg['input_pins']), 'all direct T0 inputs/code require pins.')
    # Reject future paths before attempting to hash any file.
    for source in cfg['input_pins']:
        _check_path(source)
        need(not any(s in source for s in ('groundtruth', '/t1/', 'goa_human_t1_',
                 'go-basic_t1_', 'original_training', 'updated_training')),
             'future or historical seed tables cannot enter this current-only control.')
    for source, pin in cfg['input_pins'].items():
        need(file_sha256(source) == pin, 'current-T0 source differs: ' + source)
    header = gaf_header(cfg['gaf'])
    dates = [r.split(':', 1)[1].strip().split()[0] for r in header
             if r.startswith('!date-generated:')]
    need(dates == [cfg['gaf_generated_date']], 'dated GAF header differs.')
    return cfg


def native_pipeline(gaf, fasta, ontology, directory, *, python=sys.executable):
    """Execute the original CLIs; no replacement admission/propagation logic."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    filtered = directory / 'filtered.gaf.gz'
    terms = directory / 'train_terms.tsv'
    propagated = directory / 'train_terms_propagated.tsv'
    ia = directory / 'IA.tsv'
    calls = (
        ('filter_gaf', ['-a', gaf, '-q', fasta, '-o', filtered]),
        ('retrieve_terms', ['--annot', filtered, '-sgc', 'Experimental,IC,TAS',
                            '-g', ontology, '--tsv', terms]),
        ('propagate_and_ia', ['--terms', terms, '--graph', ontology,
                              '--tsv_propagated', propagated, '--output_tsv', ia]),
    )
    receipt = []
    for name, arguments in calls:
        command = [python, '-m', 'democafa.datacollection.' + name] + list(map(str, arguments))
        log = directory / (name + '.log')
        with log.open('x') as stream:
            result = subprocess.run(command, cwd=directory, env=os.environ.copy(),
                                    stdout=stream, stderr=subprocess.STDOUT)
        need(result.returncode == 0, 'unchanged native T0 helper failed: ' + name)
        receipt.append({'command': command, 'exit_code': result.returncode,
                        'log': str(log), 'log_sha256': file_sha256(log)})
    return propagated, receipt


def graph_seeds(propagated, graph_ids):
    """Join native current-only canonical rows to exact existing graph IDs."""
    graph_ids = set(graph_ids)
    result = {p: set() for p in graph_ids}
    counts = Counter()
    with Path(propagated).open(newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        need(reader.fieldnames == ['EntryID', 'term', 'aspect'], 'native propagated header differs.')
        for row in reader:
            p, term, aspect = row['EntryID'], row['term'], row['aspect']
            need(aspect in ASPECT, 'unknown native aspect.')
            counts['native_rows'] += 1
            if p not in graph_ids:
                counts['outside_exact_graph_rows'] += 1
                continue
            result[p].add((aspect, term))
    counts['graph_proteins'] = len(result)
    counts['graph_proteins_with_current_labels'] = sum(bool(rows) for rows in result.values())
    counts['unique_graph_label_pairs'] = sum(map(len, result.values()))
    return {p: sorted(rows) for p, rows in sorted(result.items())}, dict(counts)


def prepare(cfg, output):
    from tools.cafa_prediction.run import read
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    targets = read_target_ids(cfg['final_ids'])
    need(len(targets) == 3300, 'final target identity frame changed.')
    propagated, commands = native_pipeline(cfg['gaf'], cfg['reviewed_human_fasta'],
                                           cfg['ontology'], output / 'native_current_T0')
    graph = read(cfg['graph'])
    proteins = [p.removeprefix('UniProtKB:') for p in graph['nodes']]
    need(len(proteins) == len(set(proteins)), 'exact graph identity collision.')
    training, counts = graph_seeds(propagated, proteins)
    source = output / 'current_T0_graph_seeds.json.gz'
    with source.open('xb') as raw:
        with gzip.GzipFile(fileobj=raw, filename='', mtime=0, mode='wb') as stream:
            stream.write((json.dumps(training, sort_keys=True, separators=(',', ':')) + '\n').encode())
    heads = {ns: sorted({t for rows in training.values() for a, t in rows if ASPECT[a] == ns})
             for ns in ASPECT.values()}
    receipt = {'format': 'biograph-steward.current-T0-curated-seeds.v1',
        'source_input_pins': cfg['input_pins'], 'native_commands': commands,
        'propagated_current_file': str(propagated), 'propagated_current_sha256': file_sha256(propagated),
        'seed_file': str(source), 'seed_sha256': file_sha256(source), 'counts': counts,
        'heads': heads, 'forecast_role': 'final', 'forecast_count': len(targets),
        'historical_labels_merged': False, 'native_admission_and_propagation_unchanged': True,
        'future_reference_read': False, 'old_validation_predictions_or_choices_allowed': False,
        'limits': ['Native source qualifier/form/extension/WithFrom behavior is retained; no new contextual inference.',
                   'Native canonical/alternative-GO handling is retained; graph identity uses exact accessions only.',
                   'Current T0 annotations can include known labels of final-query proteins; the later native evaluator masks known labels.']}
    write_json(output / 'prepared.json', receipt)
    return receipt


def predict(cfg, prepared, output):
    import numpy as np
    from tools.cafa_prediction import core
    from tools.cafa_prediction.run import read
    from .forecast import query_frame
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    receipt = json.loads((Path(prepared) / 'prepared.json').read_text())
    need(receipt['source_input_pins'] == cfg['input_pins']
         and receipt['forecast_role'] == 'final' and receipt['future_reference_read'] is False
         and receipt['historical_labels_merged'] is False,
         'prepared current-only/final-only source boundary differs.')
    need(file_sha256(receipt['seed_file']) == receipt['seed_sha256'], 'current seeds changed.')
    modules = core.author_modules(cfg['localplus_author'], cfg['localplus_author_receipt'])
    graph = read(cfg['graph'])
    index = {p.removeprefix('UniProtKB:'): i for i, p in enumerate(graph['nodes'])}
    P = modules['alg_utils'].normalizeGraphEdgeWeights(core.adjacency(graph['nodes'], graph['pairs']))
    need((P.data >= 0).all() and np.isfinite(P.data).all(), 'unchanged native P invalid.')
    del graph
    targets = read_target_ids(cfg['final_ids'])
    need(len(targets) == 3300, 'only the final3300 query frame is allowed.')
    present, missing = query_frame(targets, index)
    positions = {p: i for i, p in enumerate(targets)}
    query_rows = np.asarray([positions[p] for p in present], dtype=int)
    graph_rows = np.asarray([index[p] for p in present], dtype=int)
    training = read(receipt['seed_file'])
    need(set(training) == set(index), 'seed table must retain complete strict graph frame.')
    heads = defaultdict(set)
    for p, rows in training.items():
        for aspect, term in rows:
            heads[(ASPECT[aspect], term)].add(index[p])
    result = {'arm': ARM, 'roles': {'final': {}}, 'source_input_pins': cfg['input_pins'],
              'prepared_receipt_sha256': file_sha256(Path(prepared) / 'prepared.json'),
              'native_localplus_unchanged': True, 'new_reference_opened': False,
              'graph_absent_final_queries': missing, 'validation_forecast_count': 0,
              'historical_labels_merged': False}
    for ns in ASPECT.values():
        terms = sorted(t for namespace, t in heads if namespace == ns)
        need(terms == receipt['heads'][ns], 'complete current T0 source head axis differs.')
        path = output / (ns + '.npy')
        values = np.lib.format.open_memmap(path, mode='w+', dtype=np.float64,
                                          shape=(len(targets), len(terms)))
        values[:] = 0
        for column, term in enumerate(terms):
            scores, _ = core.run_term(modules, P, None, heads[(ns, term)], 'localplus')
            values[query_rows, column] = scores[graph_rows]
        values.flush()
        meta = {'arm': ARM, 'namespace': ns, 'proteins': list(targets), 'terms': terms,
            'prediction_file': str(path), 'prediction_sha256': file_sha256(path),
            'final_reference_labels_read_for_forecasting': False, 'upper_roundoff_tolerance': 1e-10,
            'source_provenance': {'prepared_receipt': str(Path(prepared) / 'prepared.json'),
                'dated_T0_GAF': cfg['gaf'], 'native_evidence': 'Experimental,IC,TAS',
                'historical_labels_merged': False, 'seed_population': 'all exact-graph reviewed-human T0 curated annotations',
                'model_axis_clipping': False, 'graph_absent_queries_are_arithmetic_zeros': missing,
                'old_validation_forecasts_or_selection': False}}
        metadata = path.with_suffix('.json')
        write_json(metadata, meta)
        result['roles']['final'][ns] = {'file': str(metadata), 'sha256': file_sha256(metadata)}
        print('CURRENT_T0_NATIVE_LOCALPLUS_COMPLETE', ns, len(terms), flush=True)
    write_json(output / 'forecasts.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'predict'))
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--prepared')
    args = parser.parse_args()
    cfg = load_config(args.config)
    if args.phase == 'prepare':
        prepare(cfg, args.output)
    else:
        predict(cfg, args.prepared, args.output)


if __name__ == '__main__':
    main()
